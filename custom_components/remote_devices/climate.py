"""Climate platform for Remote Devices.

Currently only used by the Tristar PD-8779 portable air conditioner (ZH/LT-01
protocol). Exposes a single `climate` entity with assumed state: each change
re-sends the full AC state (power, mode, target temperature, fan, swing) as one
IR frame via the `infrared` platform.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import infrared
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
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
    ZHLT01_FAN_AUTO,
    ZHLT01_FAN_HIGH,
    ZHLT01_FAN_LOW,
    ZHLT01_FAN_MEDIUM,
    ZHLT01_HDIR_FIXED,
    ZHLT01_MODE_AUTO,
    ZHLT01_MODE_COOL,
    ZHLT01_MODE_DRY,
    ZHLT01_MODE_FAN,
    ZHLT01_POWER_OFF,
    ZHLT01_POWER_ON,
    ZHLT01_TEMP_MAX,
    ZHLT01_TEMP_MIN,
    ZHLT01_VDIR_FIXED,
    ZHLT01_VDIR_SWING,
)
from .zhlt01 import ZHLT01Command

_LOGGER = logging.getLogger(__name__)

# HA HVAC mode -> ZH/LT-01 mode byte. HEAT is omitted: the PD-8779 is a
# cooling-only portable AC (cool / dry / fan / auto).
MODE_TO_BYTE = {
    HVACMode.AUTO: ZHLT01_MODE_AUTO,
    HVACMode.COOL: ZHLT01_MODE_COOL,
    HVACMode.DRY: ZHLT01_MODE_DRY,
    HVACMode.FAN_ONLY: ZHLT01_MODE_FAN,
}

# HA fan mode -> ZH/LT-01 fan byte.
FAN_TO_BYTE = {
    FAN_AUTO: ZHLT01_FAN_AUTO,
    FAN_LOW: ZHLT01_FAN_LOW,
    FAN_MEDIUM: ZHLT01_FAN_MEDIUM,
    FAN_HIGH: ZHLT01_FAN_HIGH,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tristar AC climate entity."""
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
            manufacturer="Tristar",
            model="PD-8779",
            sw_version="0.10.0",
        )

    async_add_entities(
        [TristarACClimate(config_entry, emitter_entity_id, device_info)]
    )


class TristarACClimate(ClimateEntity):
    """Tristar PD-8779 portable AC controlled via ZH/LT-01 IR frames."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_assumed_state = True
    _attr_icon = "mdi:air-conditioner"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = ZHLT01_TEMP_MIN
    _attr_max_temp = ZHLT01_TEMP_MAX
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
    ]
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_swing_modes = [SWING_OFF, SWING_VERTICAL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    # We declare TURN_ON/TURN_OFF explicitly; opt out of the legacy shim.
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        emitter_entity_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Tristar AC climate entity."""
        self._emitter_entity_id = emitter_entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_climate"
        self._attr_device_info = device_info
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 24.0
        self._attr_fan_mode = FAN_AUTO
        self._attr_swing_mode = SWING_OFF
        # Mode restored on turn-on and used for the (mode-carrying) off frame.
        self._last_active_mode = HVACMode.COOL

    def _apply_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Update the stored HVAC mode, remembering the last active one."""
        self._attr_hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_active_mode = hvac_mode

    async def _send_state(self) -> None:
        """Encode the current state as a ZH/LT-01 frame and transmit it."""
        if self._attr_hvac_mode == HVACMode.OFF:
            power = ZHLT01_POWER_OFF
            mode_byte = MODE_TO_BYTE[self._last_active_mode]
        else:
            power = ZHLT01_POWER_ON
            mode_byte = MODE_TO_BYTE.get(self._attr_hvac_mode, ZHLT01_MODE_COOL)

        fan_byte = FAN_TO_BYTE.get(self._attr_fan_mode, ZHLT01_FAN_AUTO)
        vdir = (
            ZHLT01_VDIR_SWING
            if self._attr_swing_mode == SWING_VERTICAL
            else ZHLT01_VDIR_FIXED
        )
        command = ZHLT01Command(
            power=power,
            mode=mode_byte,
            fan=fan_byte,
            vertical_swing=vdir,
            horizontal_swing=ZHLT01_HDIR_FIXED,
            temperature=int(self._attr_target_temperature or 24),
        )

        try:
            await infrared.async_send_command(
                self.hass,
                self._emitter_entity_id,
                command,
                context=self._context,
            )
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to send AC state via %s: %s", self._emitter_entity_id, err
            )
            raise

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode (or turn off)."""
        self._apply_hvac_mode(hvac_mode)
        await self._send_state()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature (and optionally the HVAC mode)."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            self._attr_target_temperature = float(temperature)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._apply_hvac_mode(hvac_mode)
        await self._send_state()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        self._attr_fan_mode = fan_mode
        await self._send_state()
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the (vertical) swing mode."""
        self._attr_swing_mode = swing_mode
        await self._send_state()
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the AC on, restoring the last active mode."""
        self._apply_hvac_mode(self._last_active_mode)
        await self._send_state()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        self._apply_hvac_mode(HVACMode.OFF)
        await self._send_state()
        self.async_write_ha_state()
