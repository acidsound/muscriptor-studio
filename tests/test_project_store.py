from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_store import ProjectStore


def ready_result(job_id: str) -> dict[str, object]:
    return {
        "audio_url": f"/api/artifacts/{job_id}/audio.wav",
        "midi_url": f"/api/artifacts/{job_id}/notes.mid",
        "audio_bytes": 1234,
        "midi_bytes": 456,
        "sample_rate": 44100,
        "duration_seconds": 4.0,
        "generation_seconds": 8.2,
        "transcription_seconds": 3.1,
        "seed": 99,
        "device": "Tesla T4",
    }


class ProjectStoreTests(unittest.TestCase):
    def test_generated_job_is_inserted_as_linked_audio_and_midi_clips(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory))
            before = store.snapshot()

            self.assertEqual(before["bpm"], 120)
            self.assertEqual([track["clips"] for track in before["tracks"]], [[], []])

            job_id = "job-123456789abc"
            after = store.insert_generation(
                job_id=job_id,
                prompt="warm analog bass loop",
                result=ready_result(job_id),
            )

            audio_track = next(track for track in after["tracks"] if track["type"] == "audio")
            midi_track = next(track for track in after["tracks"] if track["type"] == "midi")
            audio_clip = audio_track["clips"][0]
            midi_clip = midi_track["clips"][0]

            self.assertEqual(audio_clip["job_id"], job_id)
            self.assertEqual(audio_clip["kind"], "audio")
            self.assertTrue(audio_clip["url"].endswith("audio.wav"))
            self.assertEqual(audio_clip["length_beats"], 8.0)
            self.assertEqual(midi_clip["job_id"], job_id)
            self.assertEqual(midi_clip["kind"], "midi")
            self.assertTrue(midi_clip["url"].endswith("notes.mid"))
            self.assertEqual(midi_clip["linked_clip_id"], audio_clip["id"])

    def test_insert_generation_is_idempotent_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ProjectStore(root)
            job_id = "job-abcdef012345"
            result = ready_result(job_id)

            first = store.insert_generation(job_id, "first loop", result)
            second = store.insert_generation(job_id, "first loop", result)
            reloaded = ProjectStore(root).snapshot()

            self.assertEqual(first, second)
            self.assertEqual(reloaded, first)
            self.assertEqual(sum(len(track["clips"]) for track in reloaded["tracks"]), 2)


if __name__ == "__main__":
    unittest.main()
