from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from server import JobManager


class FakeRuntime:
    def snapshot(self):
        return {"model_state": "loaded"}

    def generate_and_transcribe(self, job_id, prompt, duration_seconds, steps, seed, update):
        update("generating", 65, "fake generation")
        return {
            "audio_url": f"/api/artifacts/{job_id}/audio.wav",
            "midi_url": f"/api/artifacts/{job_id}/notes.mid",
            "audio_bytes": 100,
            "midi_bytes": 50,
            "sample_rate": 44100,
            "duration_seconds": duration_seconds,
            "generation_seconds": 0.01,
            "transcription_seconds": 0.01,
            "seed": seed,
            "device": "fake",
        }


class JobManagerProjectTests(unittest.TestCase):
    def test_ready_job_is_added_to_project(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = JobManager(Path(directory), runtime=FakeRuntime())
            job = manager.submit({"prompt": "test loop", "duration_seconds": 4, "target_bars": 8})
            self.assertEqual(job["target_bars"], 8)

            for _ in range(50):
                current = manager.get(job["job_id"])
                if current and current["status"] == "ready":
                    break
                time.sleep(0.01)

            self.assertEqual(current["status"], "ready")
            project = manager.project.snapshot()
            self.assertEqual(len(project["tracks"][0]["clips"]), 1)
            self.assertEqual(project["tracks"][0]["clips"][0]["job_id"], job["job_id"])


if __name__ == "__main__":
    unittest.main()
