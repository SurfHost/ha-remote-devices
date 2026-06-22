"""Button platform for Remote Devices.

Creates one button entity per command for the configured device. IR devices
dispatch via the `infrared` platform; RF devices via `radio_frequency`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components import infrared, radio_frequency
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AMINO_STB_BROADLINK_CODES,
    AUDIOENGINE_A5_COMMANDS,
    CONF_ATTACH_TO_DEVICE,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_EMITTER_ENTITY_ID,
    DENON_AVR_COMMANDS,
    DEVICE_PROTOCOLS,
    DEVICE_TYPE_AIRWIT_FAN,
    DEVICE_TYPE_AMINO_STB,
    DEVICE_TYPE_AUDIOENGINE_A5,
    DEVICE_TYPE_DENON_AVR,
    DEVICE_TYPE_NEC_TV,
    DEVICE_TYPE_PHILIPS_LAMP,
    DEVICE_TYPE_RAW_TEST,
    DEVICE_TYPE_SAMSUNG_TV,
    DEVICE_TYPE_SHARP_TV,
    DEVICE_TYPE_TRISTAR_AC,
    DEVICE_TYPES,
    DOMAIN,
    LG_TV_COMMANDS,
    PHILIPS_LAMP_COMMANDS,
    SAMSUNG_TV_COMMANDS,
    SHARP_TV_COMMANDS,
    TRISTAR_AC_BUTTONS,
)
from .ir_commands import (
    make_amino_stb_command,
    make_audioengine_a5_command,
    make_denon_avr_command,
    make_lg_command,
    make_philips_lamp_command,
    make_raw_test_command,
    make_samsung_command,
    make_sharp_tv_command,
    make_tristar_ac_command,
)
from .rf_commands import make_airwit_fan_command

_LOGGER = logging.getLogger(__name__)

BUTTON_ICONS = {
    "power": "mdi:power",
    "volume_up": "mdi:volume-plus",
    "volume_down": "mdi:volume-minus",
    "channel_up": "mdi:arrow-up-bold",
    "channel_down": "mdi:arrow-down-bold",
    "mute": "mdi:volume-mute",
    "input": "mdi:import",
    "ok": "mdi:check-circle",
    "up": "mdi:chevron-up",
    "down": "mdi:chevron-down",
    "left": "mdi:chevron-left",
    "right": "mdi:chevron-right",
    "back": "mdi:arrow-left",
    "home": "mdi:home",
    "menu": "mdi:menu",
    "play": "mdi:play",
    "pause": "mdi:pause",
    "stop": "mdi:stop",
    "test_signal": "mdi:access-point",
    "display": "mdi:monitor",
    "flashback": "mdi:history",
    "power_on": "mdi:power-on",
    "power_off": "mdi:power-off",
    "input_cd": "mdi:disc",
    "input_dvd": "mdi:disc-player",
    "input_tv_dbs": "mdi:television",
    "input_tuner": "mdi:radio",
    "input_vcr": "mdi:video-vintage",
    "input_v_aux": "mdi:audio-input-stereo-minijack",
    "input_cdr_tape": "mdi:cassette",
    "pure_direct": "mdi:surround-sound",
    "stereo": "mdi:speaker-stereo",
    "standard": "mdi:surround-sound-2-0",
    "multi_channel": "mdi:surround-sound-5-1",
    "0": "mdi:numeric-0",
    "1": "mdi:numeric-1",
    "2": "mdi:numeric-2",
    "3": "mdi:numeric-3",
    "4": "mdi:numeric-4",
    "5": "mdi:numeric-5",
    "6": "mdi:numeric-6",
    "7": "mdi:numeric-7",
    "8": "mdi:numeric-8",
    "9": "mdi:numeric-9",
    "on": "mdi:lightbulb-on",
    "off": "mdi:lightbulb-off",
    "brightness_up": "mdi:brightness-7",
    "brightness_down": "mdi:brightness-5",
    "red": "mdi:palette",
    "green": "mdi:palette",
    "blue": "mdi:palette",
    "white": "mdi:white-balance-sunny",
    "orange": "mdi:palette",
    "yellow": "mdi:palette",
    "night_mode": "mdi:weather-night",
    "forward": "mdi:fast-forward",
    "rewind": "mdi:rewind",
    "all_off": "mdi:power-off",
    "temp_up": "mdi:thermometer-plus",
    "temp_down": "mdi:thermometer-minus",
    "speed": "mdi:fan",
    "mode": "mdi:thermostat",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for the configured device."""
    emitter_entity_id = config_entry.data[CONF_EMITTER_ENTITY_ID]
    device_type = config_entry.data[CONF_DEVICE_TYPE]
    device_name = config_entry.data.get(
        CONF_DEVICE_NAME, DEVICE_TYPES.get(device_type, "Remote Device")
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

    protocol = DEVICE_PROTOCOLS.get(device_type, "ir")
    button_cls = RFButton if protocol == "rf" else IRButton

    entities: list[ButtonEntity] = []

    if device_type == DEVICE_TYPE_NEC_TV:
        for cmd_name in LG_TV_COMMANDS:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_lg_command(name),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_SAMSUNG_TV:
        for cmd_name in SAMSUNG_TV_COMMANDS:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_samsung_command(name),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_SHARP_TV:
        for cmd_name in SHARP_TV_COMMANDS:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_sharp_tv_command(name),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_DENON_AVR:
        for cmd_name in DENON_AVR_COMMANDS:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_denon_avr_command(name),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_TRISTAR_AC:
        # Temperature is a separate number entity (+/- stepper); only the
        # discrete buttons are exposed here.
        for cmd_name in TRISTAR_AC_BUTTONS:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_tristar_ac_command(
                        name
                    ),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_AUDIOENGINE_A5:
        for cmd_name in AUDIOENGINE_A5_COMMANDS:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_audioengine_a5_command(
                        name
                    ),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_PHILIPS_LAMP:
        for cmd_name in PHILIPS_LAMP_COMMANDS:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_philips_lamp_command(name),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_AMINO_STB:
        for cmd_name in AMINO_STB_BROADLINK_CODES:
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_amino_stb_command(name),
                    device_info=device_info,
                )
            )
    elif device_type == DEVICE_TYPE_RAW_TEST:
        entities.append(
            button_cls(
                config_entry=config_entry,
                emitter_entity_id=emitter_entity_id,
                command_name="test_signal",
                command_factory=make_raw_test_command,
                device_info=device_info,
            )
        )
    elif device_type == DEVICE_TYPE_AIRWIT_FAN:
        # Fan entity covers Fan1-6 + natural_wind + fan_off + direction.
        # Light entity covers lamp toggle. Buttons just for the rest.
        for cmd_name in ("brightness_up", "brightness_down", "all_off"):
            entities.append(
                button_cls(
                    config_entry=config_entry,
                    emitter_entity_id=emitter_entity_id,
                    command_name=cmd_name,
                    command_factory=lambda name=cmd_name: make_airwit_fan_command(name),
                    device_info=device_info,
                )
            )

    async_add_entities(entities)


class _RemoteButtonBase(ButtonEntity):
    """Common base for IR and RF button entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        emitter_entity_id: str,
        command_name: str,
        command_factory: Callable[[], Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the remote button."""
        self._emitter_entity_id = emitter_entity_id
        self._command_name = command_name
        self._command_factory = command_factory
        self._attr_name = command_name.replace("_", " ").title()
        self._attr_unique_id = f"{config_entry.entry_id}_{command_name}"
        self._attr_icon = BUTTON_ICONS.get(command_name, "mdi:remote")
        self._attr_device_info = device_info

    async def _send(self, command: Any) -> None:
        """Send the command via the appropriate platform."""
        raise NotImplementedError

    async def async_press(self) -> None:
        """Send the command when the button is pressed."""
        command = self._command_factory()
        if command is None:
            _LOGGER.error("Failed to create command for '%s'", self._command_name)
            return

        _LOGGER.info(
            "Sending command '%s' via emitter %s",
            self._command_name,
            self._emitter_entity_id,
        )

        try:
            await self._send(command)
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to send command '%s' via %s: %s",
                self._command_name,
                self._emitter_entity_id,
                err,
            )
            raise


class IRButton(_RemoteButtonBase):
    """Button that sends an IR command via the infrared platform."""

    async def _send(self, command: Any) -> None:
        await infrared.async_send_command(
            self.hass,
            self._emitter_entity_id,
            command,
            context=self._context,
        )


class RFButton(_RemoteButtonBase):
    """Button that sends an RF command via the radio_frequency platform."""

    async def _send(self, command: Any) -> None:
        await radio_frequency.async_send_command(
            self.hass,
            self._emitter_entity_id,
            command,
            context=self._context,
        )
