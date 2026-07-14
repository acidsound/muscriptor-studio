from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fixture_runtime import FixtureRuntime
from midi_utils import parse_midi


class FixtureRuntimeTests(unittest.TestCase):
    def test_fixture_writes_playable_audio_and_midi_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = FixtureRuntime(Path(directory))
            result = runtime.generate_and_transcribe(
                "job-123456789abc", "fixture loop", 4.0, 20, 7, lambda *_: None
            )
            root = Path(directory) / "job-123456789abc"
            self.assertTrue((root / "audio.wav").is_file())
            self.assertTrue((root / "notes.mid").is_file())
            self.assertEqual(result["duration_seconds"], 4.0)
            self.assertGreater(result["audio_bytes"], 1000)
            self.assertGreater(len(parse_midi((root / "notes.mid").read_bytes())["notes"]), 0)


if __name__ == "__main__":
    unittest.main()
