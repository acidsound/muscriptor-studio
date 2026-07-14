from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Callable

from midi_utils import encode_midi


class FixtureRuntime:
    """Deterministic local runtime for UI/E2E tests; never loads model weights."""

    def __init__(self, output_root: Path):
        self.output_root = Path(output_root)

    def snapshot(self) -> dict[str, object]:
        return {
            "model_state": "fixture",
            "models": {"stable_audio": "fixture", "muscriptor": "fixture"},
            "device": "fixture",
            "device_name": "Browser Fixture",
            "cuda_available": False,
            "torch_version": None,
            "model_ids": {"stable_audio": "fixture/stable-audio", "muscriptor": "fixture/muscriptor"},
            "error": None,
        }

    def generate_and_transcribe(
        self,
        job_id: str,
        prompt: str,
        duration_seconds: float,
        steps: int,
        seed: int,
        update: Callable[[str, int, str], None],
    ) -> dict[str, object]:
        update("loading_models", 20, "Fixture runtime ready")
        update("generating", 65, "Rendering deterministic fixture audio…")
        job_dir = self.output_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        sample_rate = 22050
        frame_count = round(float(duration_seconds) * sample_rate)
        audio_path = job_dir / "audio.wav"
        with wave.open(str(audio_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            frames = bytearray()
            for index in range(frame_count):
                time_position = index / sample_rate
                envelope = min(1.0, time_position * 10) * min(1.0, (duration_seconds - time_position) * 10)
                value = int(0.24 * envelope * 32767 * math.sin(2 * math.pi * 110 * time_position))
                frames.extend(struct.pack("<h", value))
            handle.writeframes(bytes(frames))

        update("transcribing", 82, "Writing deterministic fixture MIDI…")
        notes = [
            {"pitch": pitch, "velocity": 88, "start_beat": beat, "duration_beats": 0.5, "channel": 0}
            for beat, pitch in zip((0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5), (48, 48, 55, 55, 50, 50, 57, 57))
        ]
        midi_path = job_dir / "notes.mid"
        midi_path.write_bytes(encode_midi(notes))
        return {
            "audio_url": f"/api/artifacts/{job_id}/audio.wav",
            "midi_url": f"/api/artifacts/{job_id}/notes.mid",
            "audio_bytes": audio_path.stat().st_size,
            "midi_bytes": midi_path.stat().st_size,
            "sample_rate": sample_rate,
            "duration_seconds": float(duration_seconds),
            "generation_seconds": 0.001,
            "transcription_seconds": 0.001,
            "seed": seed,
            "device": "Browser Fixture",
        }
