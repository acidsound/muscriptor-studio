from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_store import ProjectStore


class ProjectActionsTests(unittest.TestCase):
    def test_track_and_clip_mutations_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory))
            track = store.add_track("audio", "Texture")
            self.assertEqual(track["name"], "Texture")
            updated = store.update_track(track["id"], {"mute": True, "volume": 0.5})
            self.assertTrue(updated["mute"])
            self.assertEqual(updated["volume"], 0.5)

            job_id = "job-123456789abc"
            result = {
                "audio_url": f"/api/artifacts/{job_id}/audio.wav",
                "midi_url": f"/api/artifacts/{job_id}/notes.mid",
                "duration_seconds": 4.0,
                "sample_rate": 44100,
            }
            project = store.insert_generation(job_id, "loop", result, notes=[])
            clip_id = project["tracks"][0]["clips"][0]["id"]
            changed = store.update_clip(clip_id, {"start_beat": 12, "length_beats": 24, "name": "Moved loop"})
            self.assertEqual(changed["start_beat"], 12.0)
            self.assertEqual(changed["length_beats"], 24.0)
            self.assertEqual(changed["name"], "Moved loop")
            midi_clip = store.get_clip(f"{job_id}-midi")
            self.assertEqual(midi_clip["start_beat"], 12.0)
            self.assertEqual(midi_clip["length_beats"], 24.0)
            self.assertEqual(ProjectStore(Path(directory)).snapshot(), store.snapshot())

    def test_remove_clip_removes_its_linked_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory))
            job_id = "job-abcdef012345"
            result = {
                "audio_url": f"/api/artifacts/{job_id}/audio.wav",
                "midi_url": f"/api/artifacts/{job_id}/notes.mid",
                "duration_seconds": 4.0,
                "sample_rate": 44100,
            }
            project = store.insert_generation(job_id, "loop", result, notes=[])
            audio_id = project["tracks"][0]["clips"][0]["id"]
            after = store.remove_clip(audio_id)
            self.assertEqual(sum(len(track["clips"]) for track in after["tracks"]), 0)


if __name__ == "__main__":
    unittest.main()
