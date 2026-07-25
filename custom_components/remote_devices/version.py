"""Single source of truth for the version shown on the device page.

The `sw_version` handed to DeviceInfo used to be a hardcoded literal in
button.py, fan.py, light.py and media_player.py. Four copies meant four
manual edits per release, and they had already drifted: all four still said
"0.13.0" while manifest.json was at 0.14.0. HA already parses manifest.json
when it loads us, so ask it instead of restating the number.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN


def integration_version(hass: HomeAssistant) -> str | None:
    """Return the version string from our manifest.json.

    Safe to call from any platform's async_setup_entry: HA has necessarily
    loaded the integration by the time it forwards a platform setup, so the
    lookup is a cache hit and needs no await.

    Returns None when HA reports no version. DeviceInfo treats that as "no
    firmware row", which is better than showing a number we know is stale.
    """
    version = async_get_loaded_integration(hass, DOMAIN).version
    return str(version) if version is not None else None
