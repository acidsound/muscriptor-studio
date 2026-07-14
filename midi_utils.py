from __future__ import annotations

from typing import Any


def _vlq(value: int) -> bytes:
    value = max(0, int(value))
    buffer = value & 0x7F
    output = bytearray()
    while value > 0x7F:
        value >>= 7
        buffer <<= 8
        buffer |= (value & 0x7F) | 0x80
    while True:
        output.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(output)


def _read_vlq(data: bytes, offset: int, end: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if offset >= end:
            raise ValueError("truncated MIDI variable-length value")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset
    raise ValueError("invalid MIDI variable-length value")


def parse_midi(data: bytes) -> dict[str, Any]:
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("not a Standard MIDI File")
    header_length = int.from_bytes(data[4:8], "big")
    if header_length < 6 or len(data) < 8 + header_length:
        raise ValueError("invalid MIDI header")
    format_type = int.from_bytes(data[8:10], "big")
    track_count = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    ticks_per_beat = division if not division & 0x8000 else 480
    notes: list[dict[str, Any]] = []
    tempo_bpm = 120.0
    offset = 8 + header_length

    for _ in range(track_count):
        if offset + 8 > len(data) or data[offset:offset + 4] != b"MTrk":
            raise ValueError("invalid MIDI track chunk")
        track_length = int.from_bytes(data[offset + 4:offset + 8], "big")
        track_start = offset + 8
        track_end = min(len(data), track_start + track_length)
        offset = track_end
        tick = 0
        running_status: int | None = None
        active: dict[tuple[int, int], list[tuple[int, int]]] = {}
        cursor = track_start
        while cursor < track_end:
            delta, cursor = _read_vlq(data, cursor, track_end)
            tick += delta
            if cursor >= track_end:
                break
            status = data[cursor]
            if status & 0x80:
                cursor += 1
                if status < 0xF0:
                    running_status = status
            elif running_status is not None:
                status = running_status
            else:
                raise ValueError("MIDI event has no running status")

            if status == 0xFF:
                if cursor >= track_end:
                    break
                meta_type = data[cursor]
                cursor += 1
                length, cursor = _read_vlq(data, cursor, track_end)
                payload = data[cursor:min(track_end, cursor + length)]
                cursor += length
                if meta_type == 0x51 and len(payload) == 3:
                    micros = int.from_bytes(payload, "big")
                    if micros:
                        tempo_bpm = round(60_000_000 / micros, 3)
                if meta_type == 0x2F:
                    break
                continue
            if status in (0xF0, 0xF7):
                length, cursor = _read_vlq(data, cursor, track_end)
                cursor += length
                continue

            event_type = status & 0xF0
            channel = status & 0x0F
            data_length = 1 if event_type in (0xC0, 0xD0) else 2
            if cursor + data_length > track_end:
                break
            first = data[cursor]
            second = data[cursor + 1] if data_length == 2 else 0
            cursor += data_length
            if event_type == 0x90 and second > 0:
                active.setdefault((channel, first), []).append((tick, second))
            elif event_type in (0x80, 0x90):
                starts = active.get((channel, first), [])
                if starts:
                    start_tick, velocity = starts.pop(0)
                    notes.append({
                        "pitch": int(first),
                        "velocity": int(velocity),
                        "start_beat": round(start_tick / ticks_per_beat, 6),
                        "duration_beats": round(max(1, tick - start_tick) / ticks_per_beat, 6),
                        "channel": int(channel),
                    })

        for (channel, pitch), starts in active.items():
            for start_tick, velocity in starts:
                notes.append({
                    "pitch": int(pitch),
                    "velocity": int(velocity),
                    "start_beat": round(start_tick / ticks_per_beat, 6),
                    "duration_beats": round(max(1, tick - start_tick) / ticks_per_beat, 6),
                    "channel": int(channel),
                })

    notes.sort(key=lambda note: (note["start_beat"], note["pitch"], note["channel"]))
    return {
        "format": format_type,
        "ticks_per_beat": ticks_per_beat,
        "tempo_bpm": tempo_bpm,
        "notes": notes,
    }


def encode_midi(notes: list[dict[str, Any]], tempo_bpm: float = 120.0, ticks_per_beat: int = 480) -> bytes:
    events: list[tuple[int, int, bytes]] = []
    for note in notes:
        pitch = max(0, min(127, int(note.get("pitch", 60))))
        velocity = max(1, min(127, int(note.get("velocity", 90))))
        channel = max(0, min(15, int(note.get("channel", 0))))
        start = max(0, round(float(note.get("start_beat", 0)) * ticks_per_beat))
        duration = max(1, round(float(note.get("duration_beats", 0.25)) * ticks_per_beat))
        end = start + duration
        events.append((start, 1, bytes([0x90 | channel, pitch, velocity])))
        events.append((end, 0, bytes([0x80 | channel, pitch, 0])))
    events.sort(key=lambda item: (item[0], item[1]))

    micros = max(1, round(60_000_000 / max(1.0, float(tempo_bpm))))
    track = bytearray(b"\x00\xFF\x51\x03" + micros.to_bytes(3, "big"))
    previous_tick = 0
    for tick, _, message in events:
        track.extend(_vlq(tick - previous_tick))
        track.extend(message)
        previous_tick = tick
    track.extend(b"\x00\xFF\x2F\x00")

    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + int(ticks_per_beat).to_bytes(2, "big")
    return header + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)
