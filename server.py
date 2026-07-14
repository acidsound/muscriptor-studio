from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "web"
APP_VERSION = "0.1.0-shell"


def runtime_snapshot(deployment: str) -> dict[str, object]:
    device = "cpu"
    device_name = "CPU"
    cuda_available = False
    torch_version = None
    try:
        import torch  # type: ignore

        torch_version = torch.__version__
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            device = "cuda"
            device_name = torch.cuda.get_device_name(0)
    except Exception:
        # The shell must remain runnable without PyTorch installed.
        pass

    return {
        "app": "muscriptor-studio",
        "version": APP_VERSION,
        "deployment": deployment,
        "device": device,
        "device_name": device_name,
        "cuda_available": cuda_available,
        "torch_version": torch_version,
        "model_state": "ui-shell-not-loaded",
    }


class StudioHandler(SimpleHTTPRequestHandler):
    server_version = "MuScriptorStudio/0.1"

    @property
    def deployment(self) -> str:
        return self.server.studio_deployment  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        # Keep Colab logs useful without emitting browser asset noise.
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
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

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
                }
            )
            return
        if path == "/api/runtime":
            self._json(runtime_snapshot(self.deployment))
            return
        if path == "/api/project":
            self._json(
                {
                    "name": "Untitled Signal Study",
                    "bpm": 120,
                    "time_signature": "4/4",
                    "tracks": [
                        {"id": "audio-1", "type": "audio", "name": "AI Bass Loop"},
                        {"id": "midi-1", "type": "midi", "name": "Bass MIDI"},
                    ],
                }
            )
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/demo/generate":
            request = self._read_json()
            prompt = str(request.get("prompt", "")).strip()
            self._json(
                {
                    "ok": True,
                    "status": "prototype",
                    "job_id": "demo-shell-job",
                    "message": "Studio shell interaction only; model job wiring is the next slice.",
                    "prompt_received": bool(prompt),
                },
                status=HTTPStatus.ACCEPTED,
            )
            return
        self._json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the MuScriptor Studio web shell")
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

    handler = lambda *handler_args, **handler_kwargs: StudioHandler(  # noqa: E731
        *handler_args,
        directory=str(STATIC_ROOT),
        **handler_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.studio_deployment = args.deployment  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "ready": True,
                "app": "muscriptor-studio",
                "deployment": args.deployment,
                "host": args.host,
                "port": args.port,
                "static_root": str(STATIC_ROOT),
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
