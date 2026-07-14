from __future__ import annotations

import unittest

from midi_utils import encode_midi, parse_midi


def sample_midi() -> bytes:
    events = bytes([
        0x00, 0x90, 60, 100,
        0x83, 0x60, 0x80, 60, 0,
        0x00, 0xFF, 0x2F, 0x00,
    ])
    track = b"MTrk" + len(events).to_bytes(4, "big") + events
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + (480).to_bytes(2, "big")
    return header + track


class MidiUtilsTests(unittest.TestCase):
    def test_parse_midi_returns_note_beats(self):
        parsed = parse_midi(sample_midi())
        self.assertEqual(parsed["ticks_per_beat"], 480)
        self.assertEqual(len(parsed["notes"]), 1)
        self.assertEqual(parsed["notes"][0]["pitch"], 60)
        self.assertEqual(parsed["notes"][0]["start_beat"], 0.0)
        self.assertEqual(parsed["notes"][0]["duration_beats"], 1.0)

    def test_encode_midi_round_trips_notes(self):
        notes = [{"pitch": 64, "velocity": 90, "start_beat": 0.5, "duration_beats": 2.0, "channel": 0}]
        parsed = parse_midi(encode_midi(notes))
        self.assertEqual(parsed["notes"], notes)


if __name__ == "__main__":
    unittest.main()
