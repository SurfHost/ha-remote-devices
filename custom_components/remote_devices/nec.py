"""NEC IR protocol encoder and friends.

Each command class inherits from the official `InfraredCommand` ABC re-exported
from `homeassistant.components.infrared`. `get_raw_timings()` returns the
official flat `list[int]` of signed microseconds (positive = pulse/high,
negative = space/low) so any compliant emitter (HA core Broadlink, ESPHome,
or our `broadlink_emitter`) can dispatch them.

NEC protocol:
  - Carrier: 38 kHz
  - Unit: 560 us
  - Header: 9000us mark, 4500us space
  - Bit 1: 560us mark, 1690us space
  - Bit 0: 560us mark, 560us space
  - Data: 32 bits LSB first (8-bit address + 8-bit ~address + 8-bit command + 8-bit ~command)
  - Extended NEC: the second byte carries a 16-bit address high byte instead
    of ~address (see NECCommand.address_high)
  - Stop bit: 560us mark
"""

from __future__ import annotations

from homeassistant.components.infrared import InfraredCommand

from .broadlink_decode import decode_broadlink_b64_to_timings
from .const import (
    NEC_FREQUENCY_KHZ,
    NEC_HEADER_MARK_US,
    NEC_HEADER_SPACE_US,
    NEC_ONE_MARK_US,
    NEC_ONE_SPACE_US,
    NEC_STOP_MARK_US,
    NEC_STOP_SPACE_US,
    NEC_ZERO_MARK_US,
    NEC_ZERO_SPACE_US,
)


class NECCommand(InfraredCommand):
    """NEC protocol IR command > emits the standard 32-bit NEC frame."""

    def __init__(
        self,
        address: int,
        command: int,
        repeat_count: int = 0,
        address_high: int | None = None,
    ) -> None:
        """Initialize NEC command.

        Args:
            address: 8-bit device address (0x00-0xFF)
            command: 8-bit command code (0x00-0xFF)
            repeat_count: number of additional times to transmit
            address_high: optional explicit high address byte for *extended*
                NEC. When None (default), standard NEC is used and the second
                address byte is the complement of ``address``. When set, the
                given byte is sent verbatim (e.g. Audioengine's 0x00FD address,
                where 0xFD is not ~0x00).
        """
        super().__init__(modulation=NEC_FREQUENCY_KHZ, repeat_count=repeat_count)
        self.address = address & 0xFF
        self.address_high = None if address_high is None else address_high & 0xFF
        self.command = command & 0xFF

    def _encode_byte_lsb(self, byte: int) -> list[int]:
        """Encode a single byte as NEC mark/space pairs, LSB first."""
        timings: list[int] = []
        for bit_idx in range(8):
            if (byte >> bit_idx) & 1:
                timings.append(NEC_ONE_MARK_US)
                timings.append(-NEC_ONE_SPACE_US)
            else:
                timings.append(NEC_ZERO_MARK_US)
                timings.append(-NEC_ZERO_SPACE_US)
        return timings

    def get_raw_timings(self) -> list[int]:
        """Return the complete NEC frame as signed-µs mark/space pairs."""
        timings: list[int] = [NEC_HEADER_MARK_US, -NEC_HEADER_SPACE_US]
        timings.extend(self._encode_byte_lsb(self.address))
        if self.address_high is None:
            timings.extend(self._encode_byte_lsb(~self.address & 0xFF))
        else:
            timings.extend(self._encode_byte_lsb(self.address_high))
        timings.extend(self._encode_byte_lsb(self.command))
        timings.extend(self._encode_byte_lsb(~self.command & 0xFF))
        timings.append(NEC_STOP_MARK_US)
        timings.append(-NEC_STOP_SPACE_US)
        return timings


class RawBroadlinkCommand(InfraredCommand):
    """IR command decoded from a Broadlink-learned base64 packet.

    Used for protocols too complex to encode from scratch (e.g., RC6).
    """

    def __init__(self, b64_code: str, repeat_count: int = 0) -> None:
        """Initialize from a Broadlink base64-encoded IR packet."""
        super().__init__(modulation=NEC_FREQUENCY_KHZ, repeat_count=repeat_count)
        self._timings = decode_broadlink_b64_to_timings(b64_code)

    def get_raw_timings(self) -> list[int]:
        """Return the decoded raw timings."""
        return self._timings


class RawTestCommand(InfraredCommand):
    """A simple raw test signal for verifying the IR chain works."""

    def __init__(self, repeat_count: int = 0) -> None:
        """Initialize raw test command."""
        super().__init__(modulation=NEC_FREQUENCY_KHZ, repeat_count=repeat_count)

    def get_raw_timings(self) -> list[int]:
        """Return a simple test pattern as signed-µs mark/space pairs."""
        timings: list[int] = [9000, -4500]
        for _ in range(8):
            timings.append(560)
            timings.append(-1690)
        for _ in range(8):
            timings.append(560)
            timings.append(-560)
        timings.append(560)
        timings.append(-560)
        return timings
