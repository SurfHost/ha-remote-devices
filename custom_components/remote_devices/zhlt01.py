"""ZH/LT-01 air-conditioner IR protocol encoder.

Stateful protocol used by many generic portable ACs (the Tristar PD-8779 and
its relatives). Unlike a TV remote, every transmission carries the *full*
desired state — power, mode, target temperature, fan speed and swing — in a
single 12-byte frame. The unit has no return channel; the remote owns the
state and re-sends everything on each press.

Frame layout (12 bytes, sent LSB first). The odd-indexed bytes carry data;
each even-indexed byte is the bitwise complement of the following odd byte,
which the receiver uses as an integrity check:

  byte 1  timer        (0x00 = off)
  byte 3  turbo        (0x00 = off)
  byte 5  last button  (0x00 = power)
  byte 7  power | fan | vertical swing | horizontal swing
  byte 9  mode | (temperature - 16)
  byte 11 remote id    (0xD5)

Timing: 38 kHz carrier, 6100µs/7400µs header, 500µs bit mark, 1800µs/600µs
one/zero spaces, 500µs footer mark.

Ported from the ESPHome `zhlt01` component and ToniA's HeatpumpIR ZHLT01.
This encoder has not been verified against real Tristar hardware.
"""

from __future__ import annotations

from homeassistant.components.infrared import InfraredCommand

from .const import (
    ZHLT01_BIT_MARK_US,
    ZHLT01_FREQUENCY_KHZ,
    ZHLT01_HDR_MARK_US,
    ZHLT01_HDR_SPACE_US,
    ZHLT01_ONE_SPACE_US,
    ZHLT01_REMOTE_ID,
    ZHLT01_TEMP_MAX,
    ZHLT01_TEMP_MIN,
    ZHLT01_ZERO_SPACE_US,
)


class ZHLT01Command(InfraredCommand):
    """ZH/LT-01 protocol IR command — emits a full 12-byte AC state frame."""

    def __init__(
        self,
        *,
        power: int,
        mode: int,
        fan: int,
        vertical_swing: int,
        horizontal_swing: int,
        temperature: int,
        repeat_count: int = 0,
    ) -> None:
        """Initialize a ZH/LT-01 command from a full AC state.

        Args:
            power: ZHLT01_POWER_ON / ZHLT01_POWER_OFF
            mode: one of the ZHLT01_MODE_* values (byte 9 high bits)
            fan: one of the ZHLT01_FAN_* values (byte 7)
            vertical_swing: ZHLT01_VDIR_SWING / ZHLT01_VDIR_FIXED
            horizontal_swing: ZHLT01_HDIR_FIXED (only fixed is exposed)
            temperature: target temperature in °C, clamped to 16-32
            repeat_count: number of additional times to transmit
        """
        super().__init__(modulation=ZHLT01_FREQUENCY_KHZ, repeat_count=repeat_count)
        self.power = power & 0xFF
        self.mode = mode & 0xFF
        self.fan = fan & 0xFF
        self.vertical_swing = vertical_swing & 0xFF
        self.horizontal_swing = horizontal_swing & 0xFF
        self.temperature = max(ZHLT01_TEMP_MIN, min(ZHLT01_TEMP_MAX, int(temperature)))

    def _build_message(self) -> list[int]:
        """Build the 12-byte frame, filling even bytes with the complements."""
        msg = [0] * 12
        msg[1] = 0x00  # timer off
        msg[3] = 0x00  # turbo off
        msg[5] = 0x00  # last button = power
        msg[7] = self.power | self.fan | self.vertical_swing | self.horizontal_swing
        msg[9] = self.mode | ((self.temperature - ZHLT01_TEMP_MIN) & 0x1F)
        msg[11] = ZHLT01_REMOTE_ID
        for i in range(0, 12, 2):
            msg[i] = (~msg[i + 1]) & 0xFF
        return msg

    def _encode_byte_lsb(self, byte: int) -> list[int]:
        """Encode a single byte as ZH/LT-01 mark/space pairs, LSB first."""
        timings: list[int] = []
        for bit_idx in range(8):
            timings.append(ZHLT01_BIT_MARK_US)
            if (byte >> bit_idx) & 1:
                timings.append(-ZHLT01_ONE_SPACE_US)
            else:
                timings.append(-ZHLT01_ZERO_SPACE_US)
        return timings

    def get_raw_timings(self) -> list[int]:
        """Return the full ZH/LT-01 frame as signed-µs mark/space pairs."""
        timings: list[int] = [ZHLT01_HDR_MARK_US, -ZHLT01_HDR_SPACE_US]
        for byte in self._build_message():
            timings.extend(self._encode_byte_lsb(byte))
        # Footer mark + trailing space (keeps even-length mark/space pairs).
        timings.append(ZHLT01_BIT_MARK_US)
        timings.append(-ZHLT01_ZERO_SPACE_US)
        return timings
