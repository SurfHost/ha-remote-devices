"""RF command factory for the Remote Devices integration.

Provides `RawBroadlinkRFCommand` for devices we control via captured Broadlink
RF packets (e.g. the Airwit Plafondventilator). Inherits from the official
`RadioFrequencyCommand` ABC re-exported by `homeassistant.components.radio_frequency`,
so any compliant emitter can dispatch the resulting commands.

Pre-decoded once at import: looking up an Airwit command at button-press time
returns the cached instance.
"""

from __future__ import annotations

from itertools import cycle

from homeassistant.components.radio_frequency import (
    ModulationType,
    RadioFrequencyCommand,
)

from .broadlink_decode import decode_broadlink_b64_to_timings
from .const import (
    AIRWIT_FAN_BROADLINK_RF_CODES,
    AIRWIT_FAN_COUNTER_CYCLES,
    AIRWIT_FAN_FREQUENCY_HZ,
)


class RawBroadlinkRFCommand(RadioFrequencyCommand):
    """RF command decoded from a Broadlink-learned base64 packet."""

    def __init__(
        self,
        b64_code: str,
        frequency: int = AIRWIT_FAN_FREQUENCY_HZ,
        repeat_count: int = 0,
    ) -> None:
        """Initialize from a Broadlink base64-encoded RF packet."""
        super().__init__(
            frequency=frequency,
            modulation=ModulationType.OOK,
            repeat_count=repeat_count,
        )
        # RF signals contain long internal gaps (sync to data) that are NOT
        # repeat-frame boundaries. Decode the full packet without stripping.
        self._timings = decode_broadlink_b64_to_timings(b64_code, strip_repeats=False)

    def get_raw_timings(self) -> list[int]:
        """Return the decoded signed-microsecond timings."""
        return self._timings


# Pre-decode every Airwit code once at import.
AIRWIT_FAN_COMMANDS: dict[str, RawBroadlinkRFCommand] = {
    name: RawBroadlinkRFCommand(b64) for name, b64 in AIRWIT_FAN_BROADLINK_RF_CODES.items()
}


# Buttons that must never be replayed identically twice: see
# AIRWIT_FAN_COUNTER_CYCLES. Pre-decoded once, then handed out in turn.
_AIRWIT_CYCLES = {
    name: cycle(tuple(RawBroadlinkRFCommand(b64) for b64 in codes))
    for name, codes in AIRWIT_FAN_COUNTER_CYCLES.items()
}


def make_airwit_fan_command(name: str) -> RawBroadlinkRFCommand | None:
    """Return the RF command for the named Airwit button, or None.

    Most buttons replay one fixed packet. The lamp and the two dimmer buttons
    walk the remote's counter sequence instead, so that two presses in a row
    are never identical and the receiver reads each one as a fresh press.
    """
    if (cycled := _AIRWIT_CYCLES.get(name)) is not None:
        return next(cycled)
    return AIRWIT_FAN_COMMANDS.get(name)
