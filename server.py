from __future__ import annotations

import argparse
import io
import json
import os
import re
import secrets
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from fixture_runtime import FixtureRuntime
from midi_utils import encode_midi, parse_midi
from model_runtime import ModelRuntime
from project_store import ProjectStore

ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "web"
OUTPUT_ROOT = Path(os.environ.get("STUDIO_OUTPUT_ROOT", str(ROOT / "outputs"))).resolve()
APP_VERSION = "0.2.0-inference"


class JobManager:
    def __init__(
        self,
        output_root: Path,
        runtime: Any | None = None,
        project: ProjectStore | None = None,
    ):
        self.output_root = output_root
        self.runtime = runtime or ModelRuntime(output_root)
        self.project = project or ProjectStore(output_root)
        self._jobs: dict[str, dict[str, object]] = {}
        self._lock = threading.Lock()
        # T4 memory policy: one model job at a time.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="studio-job")

    def submit(self, request: dict[str, object]) -> dict[str, object]:
        prompt = str(request.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required")
        if len(prompt) > 1000:
            raise ValueError("prompt is limited to 1000 characters")
        try:
            duration = float(request.get("duration_seconds", 8))
        except (TypeError, ValueError):
            raise ValueError("duration_seconds must be a number") from None
        if duration not in (4.0, 8.0, 16.0):
            raise ValueError("duration_seconds must be 4, 8, or 16")
        target_value = request.get("target_bars")
        target_text = "" if target_value is None else str(target_value).strip().lower()
        if target_text in {"", "free", "none"}:
            target_bars = None
        elif target_text in {"4", "4.0"}:
            target_bars = 4
        elif target_text in {"8", "8.0"}:
            target_bars = 8
        else:
            raise ValueError("target_bars must be 4, 8, or free")
        try:
            steps = int(request.get("steps", 20))
        except (TypeError, ValueError):
            raise ValueError("steps must be an integer") from None
        steps = max(10, min(steps, 40))
        try:
            seed_value = request.get("seed")
            seed = int(seed_value) if seed_value not in (None, "") else secrets.randbelow(2**31 - 1)
        except (TypeError, ValueError):
            raise ValueError("seed must be an integer") from None

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Queued for the single T4 inference worker",
            "prompt": prompt,
            "duration_seconds": duration,
            "target_bars": target_bars,
            "steps": steps,
            "seed": seed,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run, job_id)
        return self.get(job_id)

    def _update(self, job_id: str, status: str, progress: int, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update({"status": status, "progress": progress, "message": message})

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = dict(self._jobs[job_id])
        try:
            result = self.runtime.generate_and_transcribe(
                job_id=job_id,
                prompt=str(job["prompt"]),
                duration_seconds=float(job["duration_seconds"]),
                steps=int(job["steps"]),
                seed=int(job["seed"]),
                update=lambda status, progress, message: self._update(
                    job_id, status, progress, message
                ),
            )
            midi_path = self.output_root / job_id / "notes.mid"
            try:
                parsed_midi = parse_midi(midi_path.read_bytes())
                midi_notes = parsed_midi["notes"]
            except (OSError, ValueError):
                midi_notes = []
            self.project.insert_generation(
                job_id=job_id,
                prompt=str(job["prompt"]),
                result=result,
                notes=midi_notes,
            )
        except Exception as exc:
            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None:
                    current.update(
                        {
                            "status": "failed",
                            "progress": 0,
                            "message": "Inference failed",
                            "error": self._safe_error(f"{type(exc).__name__}: {exc}"),
                        }
                    )
            return
        with self._lock:
            current = self._jobs.get(job_id)
            if current is not None:
                current.update(
                    {
                        "status": "ready",
                        "progress": 100,
                        "message": "WAV and MIDI are ready",
                        "result": result,
                    }
                )

    def get(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            value = self._jobs.get(job_id)
            return dict(value) if value is not None else None

    def runtime_snapshot(self) -> dict[str, object]:
        with self._lock:
            active = next(
                (
                    job["job_id"]
                    for job in self._jobs.values()
                    if job["status"] in {"queued", "loading_models", "generating", "transcribing"}
                ),
                None,
            )
        snapshot = self.runtime.snapshot()
        snapshot["active_job_id"] = active
        return snapshot

    @staticmethod
    def _safe_error(value: str) -> str:
        value = re.sub(r"/(?:content|home|tmp)/[^\s:]+", "[path]", value)
        return value[:500]


JOBS = JobManager(
    OUTPUT_ROOT,
    runtime=FixtureRuntime(OUTPUT_ROOT) if os.environ.get("STUDIO_RUNTIME") == "fixture" else None,
)


def project_snapshot() -> dict[str, object]:
    return JOBS.project.snapshot()


class StudioHandler(SimpleHTTPRequestHandler):
    server_version = "MuScriptorStudio/0.2"

    @property
    def deployment(self) -> str:
        return self.server.studio_deployment  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        if self.path.startswith("/api/"):
            super().log_message(format, *args)

    def _json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _artifact(self, job_id: str, filename: str) -> None:
        if not re.fullmatch(r"job-[a-f0-9]{12}", job_id) or filename not in {"audio.wav", "notes.mid"}:
            self._json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        root = OUTPUT_ROOT.resolve()
        path = (root / job_id / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            self._json({"ok": False, "error": "Artifact not ready"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type = "audio/wav" if filename.endswith(".wav") else "audio/midi"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'{"inline" if filename.endswith(".wav") else "attachment"}; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _midi_json(self, clip_id: str) -> None:
        try:
            clip = JOBS.project.get_clip(clip_id)
        except KeyError:
            self._json({"ok": False, "error": "Clip not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if clip.get("kind") != "midi":
            self._json({"ok": False, "error": "Clip is not MIDI"}, status=HTTPStatus.BAD_REQUEST)
            return
        notes = clip.get("notes", [])
        if not notes:
            job_id = str(clip.get("job_id", ""))
            path = OUTPUT_ROOT / job_id / "notes.mid"
            try:
                notes = parse_midi(path.read_bytes())["notes"]
            except (OSError, ValueError):
                notes = []
        self._json({"clip_id": clip_id, "notes": notes})

    def _project_export(self) -> None:
        project = JOBS.project.snapshot()
        archive = io.BytesIO()
        included: set[tuple[str, str]] = set()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("project.json", json.dumps(project, ensure_ascii=False, indent=2) + "\n")
            for track in project.get("tracks", []):
                for clip in track.get("clips", []):
                    job_id = str(clip.get("job_id", ""))
                    if not re.fullmatch(r"job-[a-f0-9]{12}", job_id):
                        continue
                    for filename, folder in (("audio.wav", "audio"), ("notes.mid", "midi")):
                        key = (job_id, filename)
                        path = OUTPUT_ROOT / job_id / filename
                        if key in included or not path.is_file():
                            continue
                        bundle.writestr(f"{folder}/{job_id}.{filename.split('.')[-1]}", path.read_bytes())
                        included.add(key)
        self._send_bytes(archive.getvalue(), "application/zip", "muscriptor-studio-project.zip")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(
                {
                    "ok": True,
                    "app": "muscriptor-studio",
                    "version": APP_VERSION,
                    "deployment": self.deployment,
                    "service": "studio-server",
                    "model_state": JOBS.runtime_snapshot()["model_state"],
                }
            )
            return
        if path == "/api/runtime":
            self._json({**JOBS.runtime_snapshot(), "app": "muscriptor-studio", "version": APP_VERSION, "deployment": self.deployment})
            return
        if path == "/api/project/export":
            self._project_export()
            return
        if path.startswith("/api/project/midi/"):
            self._midi_json(unquote(path.removeprefix("/api/project/midi/")).strip("/"))
            return
        if path == "/api/project":
            self._json(project_snapshot())
            return
        if path.startswith("/api/jobs/"):
            job_id = unquote(path.removeprefix("/api/jobs/")).strip("/")
            job = JOBS.get(job_id)
            if job is None:
                self._json({"ok": False, "error": "Job not found"}, status=HTTPStatus.NOT_FOUND)
            else:
                self._json(job)
            return
        if path.startswith("/api/artifacts/"):
            parts = path.split("/")
            if len(parts) == 5:
                self._artifact(unquote(parts[3]), unquote(parts[4]))
                return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/project/track":
            payload = self._read_json()
            try:
                track = JOBS.project.add_track(str(payload.get("type", "audio")), str(payload.get("name", "New Track")))
            except (TypeError, ValueError) as exc:
                self._json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json({"track": track, "project": JOBS.project.snapshot()}, status=HTTPStatus.CREATED)
            return
        if path in {"/api/jobs", "/api/demo/generate"}:
            try:
                job = JOBS.submit(self._read_json())
            except ValueError as exc:
                self._json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json(job, status=HTTPStatus.ACCEPTED)
            return
        self._json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        payload = self._read_json()
        try:
            if path.startswith("/api/project/track/"):
                track_id = unquote(path.removeprefix("/api/project/track/")).strip("/")
                updated = JOBS.project.update_track(track_id, payload)
            elif path.startswith("/api/project/clip/"):
                clip_id = unquote(path.removeprefix("/api/project/clip/")).strip("/")
                updated = JOBS.project.update_clip(clip_id, payload)
            elif path.startswith("/api/project/midi/"):
                clip_id = unquote(path.removeprefix("/api/project/midi/")).strip("/")
                notes = payload.get("notes")
                if not isinstance(notes, list) or not all(isinstance(note, dict) for note in notes):
                    raise ValueError("notes must be a list of objects")
                clip = JOBS.project.get_clip(clip_id)
                encoded = encode_midi(notes, tempo_bpm=float(JOBS.project.snapshot().get("bpm", 120)))
                job_id = str(clip.get("job_id", ""))
                if not re.fullmatch(r"job-[a-f0-9]{12}", job_id):
                    raise ValueError("MIDI clip has no writable artifact")
                (OUTPUT_ROOT / job_id).mkdir(parents=True, exist_ok=True)
                (OUTPUT_ROOT / job_id / "notes.mid").write_bytes(encoded)
                updated = JOBS.project.update_midi_notes(clip_id, notes)
            else:
                self._json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self._json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._json({"updated": updated, "project": JOBS.project.snapshot()})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/project/clip/"):
            clip_id = unquote(path.removeprefix("/api/project/clip/")).strip("/")
            try:
                project = JOBS.project.remove_clip(clip_id)
            except KeyError as exc:
                self._json({"ok": False, "error": str(exc)}, status=HTTPStatus.NOT_FOUND)
                return
            self._json({"project": project})
            return
        self._json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve MuScriptor Studio")
    parser.add_argument("--host", default=os.environ.get("STUDIO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", "7860")))
    parser.add_argument(
        "--deployment",
        default=os.environ.get("STUDIO_DEPLOYMENT", "desktop"),
        choices=("desktop", "colab-t4"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not STATIC_ROOT.is_dir():
        raise SystemExit(f"Static web root does not exist: {STATIC_ROOT}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    handler = lambda *handler_args, **handler_kwargs: StudioHandler(  # noqa: E731
        *handler_args,
        directory=str(STATIC_ROOT),
        **handler_kwargs,
    )
    server = StudioServer((args.host, args.port), handler)
    server.studio_deployment = args.deployment  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "ready": True,
                "app": "muscriptor-studio",
                "version": APP_VERSION,
                "deployment": args.deployment,
                "host": args.host,
                "port": args.port,
                "static_root": str(STATIC_ROOT),
                "output_root": str(OUTPUT_ROOT),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
