"""Light platform for Remote Devices.

Currently only used by the Airwit Plafondventilator. Provides an on/off
light entity that drives the single-toggle "lamp" RF code with optimistic
state tracking.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import radio_frequency
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ATTACH_TO_DEVICE,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_EMITTER_ENTITY_ID,
    DEVICE_TYPE_AIRWIT_FAN,
    DEVICE_TYPES,
    DOMAIN,
)
from .rf_commands import make_airwit_fan_command

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airwit lamp entity."""
    device_type = config_entry.data[CONF_DEVICE_TYPE]
    if device_type != DEVICE_TYPE_AIRWIT_FAN:
        return

    emitter_entity_id = config_entry.data[CONF_EMITTER_ENTITY_ID]
    device_name = config_entry.data.get(
        CONF_DEVICE_NAME, DEVICE_TYPES.get(device_type, "Plafondventilator")
    )

    attach_device_id = config_entry.data.get(CONF_ATTACH_TO_DEVICE)
    if attach_device_id:
        dev_reg = dr.async_get(hass)
        dev_entry = dev_reg.async_get(attach_device_id)
        if dev_entry:
            device_info = DeviceInfo(identifiers=dev_entry.identifiers)
        else:
            _LOGGER.error("Target device %s not found", attach_device_id)
            return
    else:
        device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=device_name,
            manufacturer="Airwit",
            model="Plafondventilator",
            sw_version="0.11.0",
        )

    async_add_entities(
        [AirwitLamp(config_entry, emitter_entity_id, device_info)]
    )


class AirwitLamp(LightEntity):
    """Airwit ceiling fan lamp — single toggle code, optimistic on/off."""

    _attr_has_entity_name = True
    _attr_translation_key = "lamp"
    _attr_name = "Lamp"
    _attr_icon = "mdi:ceiling-light"
    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        config_entry: ConfigEntry,
        emitter_entity_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Airwit lamp."""
        self._emitter_entity_id = emitter_entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_lamp"
        self._attr_device_info = device_info
        self._attr_is_on = False

    async def _send_toggle(self) -> None:
        """Send the lamp toggle code."""
        command = make_airwit_fan_command("lamp")
        if command is None:
            _LOGGER.error("Airwit lamp command unavailable")
            return
        try:
            await radio_frequency.async_send_command(
                self.hass,
                self._emitter_entity_id,
                command,
                context=self._context,
            )
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to send Airwit lamp toggle via %s: %s",
                self._emitter_entity_id,
                err,
            )
            raise

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lamp on."""
        if not self._attr_is_on:
            await self._send_toggle()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off."""
        if self._attr_is_on:
            await self._send_toggle()
        self._attr_is_on = False
        self.async_write_ha_state()
