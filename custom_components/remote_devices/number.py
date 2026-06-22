"""Number platform for Remote Devices.

Currently only used by the Tristar PD-8779 air conditioner: a single
assumed-state temperature number that renders as a -/+ stepper. The AC has no
discrete "set 23 °C" code — only relative temp_up / temp_down button codes —
so changing the value sends that many up/down presses and tracks the target
optimistically (it can drift if the physical remote is also used).
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components import infrared
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    DEVICE_TYPE_TRISTAR_AC,
    DEVICE_TYPES,
    DOMAIN,
    TRISTAR_AC_TEMP_DEFAULT,
    TRISTAR_AC_TEMP_MAX,
    TRISTAR_AC_TEMP_MIN,
)
from .ir_commands import make_tristar_ac_command

_LOGGER = logging.getLogger(__name__)

# Gap between successive presses so the AC registers each as a distinct step.
_STEP_DELAY_S = 0.3


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tristar AC temperature number entity."""
    device_type = config_entry.data[CONF_DEVICE_TYPE]
    if device_type != DEVICE_TYPE_TRISTAR_AC:
        return

    emitter_entity_id = config_entry.data[CONF_EMITTER_ENTITY_ID]
    device_name = config_entry.data.get(
        CONF_DEVICE_NAME, DEVICE_TYPES.get(device_type, "Air Conditioner")
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
            manufacturer="Remote Devices",
            model=DEVICE_TYPES.get(device_type, device_type),
            sw_version="0.12.0",
        )

    async_add_entities(
        [TristarTemperatureNumber(config_entry, emitter_entity_id, device_info)]
    )


class TristarTemperatureNumber(NumberEntity):
    """Assumed-state temperature stepper that drives temp_up / temp_down."""

    _attr_has_entity_name = True
    _attr_name = "Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = TRISTAR_AC_TEMP_MIN
    _attr_native_max_value = TRISTAR_AC_TEMP_MAX
    _attr_native_step = 1

    def __init__(
        self,
        config_entry: ConfigEntry,
        emitter_entity_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the temperature number."""
        self._emitter_entity_id = emitter_entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_temperature"
        self._attr_device_info = device_info
        self._attr_native_value = float(TRISTAR_AC_TEMP_DEFAULT)

    async def _send(self, command_name: str) -> None:
        """Send a single temp_up/temp_down IR command."""
        command = make_tristar_ac_command(command_name)
        if command is None:
            _LOGGER.error("Command '%s' unavailable", command_name)
            return
        try:
            await infrared.async_send_command(
                self.hass,
                self._emitter_entity_id,
                command,
                context=self._context,
            )
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to send '%s' via %s: %s",
                command_name,
                self._emitter_entity_id,
                err,
            )
            raise

    async def async_set_native_value(self, value: float) -> None:
        """Step the AC up or down to the requested temperature."""
        target = int(round(value))
        target = max(
            int(self._attr_native_min_value), min(int(self._attr_native_max_value), target)
        )
        delta = target - int(self._attr_native_value)
        if delta == 0:
            return

        command_name = "temp_up" if delta > 0 else "temp_down"
        steps = abs(delta)
        for i in range(steps):
            await self._send(command_name)
            if i < steps - 1:
                await asyncio.sleep(_STEP_DELAY_S)

        self._attr_native_value = float(target)
        self.async_write_ha_state()
