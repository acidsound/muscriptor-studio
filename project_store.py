from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any


class ProjectStore:
    """Small durable project store shared by the Studio HTTP server and UI."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "project.json"
        self._lock = threading.RLock()
        self._project = self._load()

    @staticmethod
    def _default_project() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "name": "Untitled Signal Study",
            "bpm": 120,
            "time_signature": "4/4",
            "length_bars": 16,
            "tracks": [
                {"id": "audio-1", "type": "audio", "name": "AI Audio", "color": "audio", "mute": False, "solo": False, "volume": 1.0, "clips": []},
                {"id": "midi-1", "type": "midi", "name": "Derived MIDI", "color": "midi", "mute": False, "solo": False, "instrument": "Acoustic Grand Piano", "clips": []},
            ],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._default_project()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return self._default_project()
        if not isinstance(value, dict) or not isinstance(value.get("tracks"), list):
            return self._default_project()
        return value

    def _persist(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="project.", suffix=".json", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._project, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._project)

    def _find_track(self, track_id: str) -> dict[str, Any]:
        for track in self._project["tracks"]:
            if track.get("id") == track_id:
                return track
        raise KeyError("track not found")

    def _find_clip(self, clip_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for track in self._project["tracks"]:
            for clip in track.get("clips", []):
                if clip.get("id") == clip_id:
                    return track, clip
        raise KeyError("clip not found")

    def insert_generation(
        self,
        job_id: str,
        prompt: str,
        result: dict[str, Any],
        notes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            for track in self._project["tracks"]:
                for clip in track.get("clips", []):
                    if clip.get("job_id") == job_id:
                        return self.snapshot()

            bpm = float(self._project.get("bpm", 120))
            duration = float(result["duration_seconds"])
            length_beats = round(duration * bpm / 60.0, 3)
            start_beat = 0.0
            for track in self._project["tracks"]:
                for clip in track.get("clips", []):
                    end = float(clip.get("start_beat", 0)) + float(clip.get("length_beats", 0))
                    start_beat = max(start_beat, end)

            safe_name = " ".join(prompt.strip().split())[:48] or "Generated clip"
            audio_clip_id = f"{job_id}-audio"
            midi_clip_id = f"{job_id}-midi"
            common = {
                "job_id": job_id,
                "start_beat": start_beat,
                "length_beats": length_beats,
                "duration_seconds": duration,
                "prompt": safe_name,
                "status": "ready",
            }
            audio_clip = {
                **common,
                "id": audio_clip_id,
                "kind": "audio",
                "name": safe_name,
                "url": result["audio_url"],
                "sample_rate": result.get("sample_rate"),
                "linked_clip_id": midi_clip_id,
            }
            midi_clip = {
                **common,
                "id": midi_clip_id,
                "kind": "midi",
                "name": f"{safe_name} · MIDI",
                "url": result["midi_url"],
                "linked_clip_id": audio_clip_id,
                "notes": copy.deepcopy(notes or []),
            }
            audio_track = next(track for track in self._project["tracks"] if track["type"] == "audio")
            midi_track = next(track for track in self._project["tracks"] if track["type"] == "midi")
            audio_track.setdefault("clips", []).append(audio_clip)
            midi_track.setdefault("clips", []).append(midi_clip)
            self._persist()
            return self.snapshot()

    def add_track(self, track_type: str, name: str) -> dict[str, Any]:
        if track_type not in {"audio", "midi"}:
            raise ValueError("track type must be audio or midi")
        clean_name = " ".join(str(name).strip().split())[:80] or f"New {track_type.title()}"
        track: dict[str, Any] = {
            "id": f"{track_type}-{uuid.uuid4().hex[:8]}",
            "type": track_type,
            "name": clean_name,
            "color": track_type,
            "mute": False,
            "solo": False,
            "clips": [],
        }
        if track_type == "audio":
            track["volume"] = 1.0
        else:
            track["instrument"] = "Acoustic Grand Piano"
        with self._lock:
            self._project["tracks"].append(track)
            self._persist()
            return copy.deepcopy(track)

    def update_track(self, track_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            track = self._find_track(track_id)
            if "name" in changes:
                track["name"] = " ".join(str(changes["name"]).strip().split())[:80] or track["name"]
            if "mute" in changes:
                track["mute"] = bool(changes["mute"])
            if "solo" in changes:
                track["solo"] = bool(changes["solo"])
            if "volume" in changes and track["type"] == "audio":
                track["volume"] = max(0.0, min(1.0, float(changes["volume"])))
            if "instrument" in changes and track["type"] == "midi":
                track["instrument"] = " ".join(str(changes["instrument"]).strip().split())[:80] or track.get("instrument", "Acoustic Grand Piano")
            self._persist()
            return copy.deepcopy(track)

    def update_clip(self, clip_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            _, clip = self._find_clip(clip_id)
            if "name" in changes:
                clip["name"] = " ".join(str(changes["name"]).strip().split())[:80] or clip["name"]
            if "start_beat" in changes:
                clip["start_beat"] = round(max(0.0, float(changes["start_beat"])), 3)
            if "length_beats" in changes:
                clip["length_beats"] = round(max(0.25, float(changes["length_beats"])), 3)
            linked_id = clip.get("linked_clip_id")
            if linked_id:
                try:
                    _, linked = self._find_clip(str(linked_id))
                except KeyError:
                    linked = None
                if linked is not None:
                    for key in ("start_beat", "length_beats"):
                        if key in clip:
                            linked[key] = clip[key]
                    if "name" in changes and linked.get("kind") == "midi":
                        linked["name"] = f"{clip['name']} · MIDI"
            self._persist()
            return copy.deepcopy(clip)

    def update_midi_notes(self, clip_id: str, notes: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            _, clip = self._find_clip(clip_id)
            if clip.get("kind") != "midi":
                raise ValueError("clip is not MIDI")
            clip["notes"] = copy.deepcopy(notes)
            self._persist()
            return copy.deepcopy(clip)

    def get_clip(self, clip_id: str) -> dict[str, Any]:
        with self._lock:
            _, clip = self._find_clip(clip_id)
            return copy.deepcopy(clip)

    def remove_clip(self, clip_id: str) -> dict[str, Any]:
        with self._lock:
            _, target = self._find_clip(clip_id)
            remove_ids = {clip_id}
            if target.get("linked_clip_id"):
                remove_ids.add(str(target["linked_clip_id"]))
            for track in self._project["tracks"]:
                track["clips"] = [
                    clip for clip in track.get("clips", [])
                    if clip.get("id") not in remove_ids and clip.get("linked_clip_id") not in remove_ids
                ]
            self._persist()
            return self.snapshot()
