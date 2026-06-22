"""The Remote Devices integration.

A consumer integration for the Home Assistant 2026.4 `infrared` and 2026.5
`radio_frequency` entity platforms. Creates button, media_player, fan, and
light entities that send IR or RF commands via any available emitter
(e.g., Broadlink, ESPHome).

Built-in support: NEC, Sharp, and Denon protocol encoders for IR; raw
Broadlink-learned packet playback for both IR and RF.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ATTACH_TO_DEVICE, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BUTTON,
    Platform.FAN,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Remote Devices from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    # Register config entry with the target device so HA knows we own entities there
    attach_device_id = entry.data.get(CONF_ATTACH_TO_DEVICE)
    if attach_device_id:
        dev_reg = dr.async_get(hass)
        dev_reg.async_update_device(
            attach_device_id, add_config_entry_id=entry.entry_id
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Remote Devices config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
