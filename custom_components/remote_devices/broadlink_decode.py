"""Shared helper for decoding Broadlink-learned base64 packets to raw timings.

Output format matches the official HA contract from
`infrared_protocols.Command.get_raw_timings()`:
a flat list of signed microseconds alternating positive (pulse / signal-on)
and negative (space / signal-off).

Two packet layouts occur in the wild. Both start with a type byte, a repeat
count and a little-endian payload length, but they differ in what follows:

    0xb2, 0xb4  IR and the documented RF form. Pulses start at byte 4.
    0xb1        what an RM4 Pro actually returns after an RF learn. Bytes 4
                to 7 hold the carrier frequency in kHz, little-endian, and the
                pulses only start at byte 8.

Reading a 0xb1 packet as if it were 0xb2 turns those four frequency bytes into
phantom pulses: a long carrier burst, a gap, a short blip, and then a 0x00 that
the escape rule swallows together with the first real pulse pair. The result is
a signal that begins with roughly a tenth of a second of noise and whose first
frame has lost its top bit.
"""

from __future__ import annotations

import base64
import struct

# Broadlink time quantum: 269/8192 seconds ~= 32.84 µs per tick.
BROADLINK_TICK_US = 269000 / 8192

# Type byte of an RF packet as learned by an RM4 Pro: carries a 4-byte carrier
# frequency in kHz before the pulses.
RF_LEARNED_TYPE_BYTE = 0xB1


def decode_broadlink_b64_to_timings(
    b64_code: str,
    *,
    strip_repeats: bool = True,
) -> list[int]:
    """Decode a Broadlink base64 packet into signed-microsecond timings.

    Returns a flat list `[+pulse_us, -space_us, +pulse_us, -space_us, ...]`.

    By default (strip_repeats=True), stops at the first inter-frame gap
    longer than 50 ms, appropriate for IR codes where the captured packet
    contains repeat frames separated by long gaps.

    For RF codes, pass strip_repeats=False: RF signals routinely contain long
    (100+ ms) gaps between sync pulse and data burst that are part of the
    intended signal, not repeat-frame boundaries.
    """
    data = base64.b64decode(b64_code)
    length = struct.unpack("<H", data[2:4])[0]
    offset = 4
    if data[0] == RF_LEARNED_TYPE_BYTE:
        # Skip the carrier frequency; the payload length counts it in.
        offset = 8
        length -= 4
    timing_data = data[offset : offset + length]

    raw_us: list[int] = []
    i = 0
    while i < len(timing_data):
        if timing_data[i] == 0x00 and i + 2 < len(timing_data):
            val = (timing_data[i + 1] << 8) | timing_data[i + 2]
            i += 3
        else:
            val = timing_data[i]
            i += 1
        raw_us.append(round(val * BROADLINK_TICK_US))

    timings: list[int] = []
    idx = 0
    while idx + 1 < len(raw_us):
        mark = raw_us[idx]
        space = raw_us[idx + 1]
        if strip_repeats and space > 50000:
            # End of first frame: emit a final mark/space using mark length
            # for both sides (matches the previous sentinel behaviour) and
            # stop, dropping subsequent repeat frames.
            timings.append(mark)
            timings.append(-mark)
            break
        timings.append(mark)
        timings.append(-space)
        idx += 2

    return timings
