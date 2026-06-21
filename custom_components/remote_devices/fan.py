"""Fan platform for Remote Devices.

Currently only used by the Airwit Plafondventilator (RF 433 MHz). Provides a
Fan entity with 6 speeds, a "natural_wind" preset, and forward/reverse
direction (toggle on hardware, optimistically tracked locally).
"""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components import radio_frequency
from homeassistant.components.fan import FanEntity, FanEntityFeature
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

AIRWIT_SPEED_COUNT = 6
PRESET_NATURAL_WIND = "natural_wind"
SPEED_TO_CODE = {1: "fan_1", 2: "fan_2", 3: "fan_3", 4: "fan_4", 5: "fan_5", 6: "fan_6"}


def _percentage_to_speed(percentage: int) -> int:
    """Map a 1-100% percentage to 1-6 fan speed (rounded up)."""
    if percentage <= 0:
        return 0
    speed = math.ceil(percentage * AIRWIT_SPEED_COUNT / 100)
    return max(1, min(AIRWIT_SPEED_COUNT, speed))


def _speed_to_percentage(speed: int) -> int:
    """Map a 1-6 fan speed to a percentage (so it rounds back via _percentage_to_speed)."""
    if speed <= 0:
        return 0
    return round(speed * 100 / AIRWIT_SPEED_COUNT)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fan entity (Airwit only)."""
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
            sw_version="0.10.0",
        )

    async_add_entities(
        [AirwitFan(config_entry, emitter_entity_id, device_info)]
    )


class AirwitFan(FanEntity):
    """Airwit Plafondventilator fan entity (optimistic state, RF 433 MHz)."""

    _attr_has_entity_name = True
    _attr_translation_key = "fan"
    _attr_name = "Fan"
    _attr_icon = "mdi:ceiling-fan"
    _attr_assumed_state = True
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.DIRECTION
    )
    _attr_speed_count = AIRWIT_SPEED_COUNT
    _attr_preset_modes = [PRESET_NATURAL_WIND]

    def __init__(
        self,
        config_entry: ConfigEntry,
        emitter_entity_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Airwit fan."""
        self._emitter_entity_id = emitter_entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_fan"
        self._attr_device_info = device_info
        self._attr_is_on = False
        self._attr_percentage = 0
        self._attr_preset_mode: str | None = None
        self._attr_current_direction = "forward"
        self._last_speed = 1

    async def _send(self, name: str) -> None:
        """Send a named Airwit RF command."""
        command = make_airwit_fan_command(name)
        if command is None:
            _LOGGER.error("Unknown Airwit command: %s", name)
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
                "Failed to send Airwit '%s' via %s: %s",
                name,
                self._emitter_entity_id,
                err,
            )
            raise

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if preset_mode == PRESET_NATURAL_WIND:
            await self._send("natural_wind")
            self._attr_preset_mode = PRESET_NATURAL_WIND
            self._attr_percentage = None
        else:
            speed = (
                _percentage_to_speed(percentage)
                if percentage is not None
                else self._last_speed
            )
            speed = max(1, speed)
            await self._send(SPEED_TO_CODE[speed])
            self._attr_percentage = _speed_to_percentage(speed)
            self._attr_preset_mode = None
            self._last_speed = speed
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off (lamp stays as-is)."""
        await self._send("fan_off")
        self._attr_is_on = False
        self._attr_percentage = 0
        self._attr_preset_mode = None
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = _percentage_to_speed(percentage)
        await self._send(SPEED_TO_CODE[speed])
        self._attr_percentage = _speed_to_percentage(speed)
        self._attr_preset_mode = None
        self._attr_is_on = True
        self._last_speed = speed
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Activate a preset mode."""
        if preset_mode != PRESET_NATURAL_WIND:
            raise HomeAssistantError(f"Unsupported preset mode: {preset_mode}")
        await self._send("natural_wind")
        self._attr_preset_mode = PRESET_NATURAL_WIND
        self._attr_percentage = None
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_set_direction(self, direction: str) -> None:
        """Toggle fan direction (the hardware exposes a single toggle code)."""
        await self._send("fan_direction")
        self._attr_current_direction = (
            "reverse" if self._attr_current_direction == "forward" else "forward"
        )
        self.async_write_ha_state()
