"""Media player platform for Remote Devices."""

from __future__ import annotations

import logging

from homeassistant.components import infrared
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ATTACH_TO_DEVICE,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_EMITTER_ENTITY_ID,
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
)
from .ir_commands import (
    make_audioengine_a5_command,
    make_denon_avr_command,
    make_lg_command,
    make_samsung_command,
    make_sharp_tv_command,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Remote Devices media player entities."""
    emitter_entity_id = config_entry.data[CONF_EMITTER_ENTITY_ID]
    device_type = config_entry.data[CONF_DEVICE_TYPE]
    device_name = config_entry.data.get(
        CONF_DEVICE_NAME, DEVICE_TYPES.get(device_type, "Remote Device")
    )

    if config_entry.data.get(CONF_ATTACH_TO_DEVICE):
        return  # Existing device already has a media player

    if device_type in (
        DEVICE_TYPE_RAW_TEST,
        DEVICE_TYPE_PHILIPS_LAMP,
        DEVICE_TYPE_AMINO_STB,
        DEVICE_TYPE_AIRWIT_FAN,
        DEVICE_TYPE_TRISTAR_AC,
    ):
        return

    if device_type == DEVICE_TYPE_NEC_TV:
        command_factory = make_lg_command
    elif device_type == DEVICE_TYPE_SAMSUNG_TV:
        command_factory = make_samsung_command
    elif device_type == DEVICE_TYPE_SHARP_TV:
        command_factory = make_sharp_tv_command
    elif device_type == DEVICE_TYPE_DENON_AVR:
        command_factory = make_denon_avr_command
    elif device_type == DEVICE_TYPE_AUDIOENGINE_A5:
        command_factory = make_audioengine_a5_command
    else:
        return

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=device_name,
        manufacturer="Remote Devices",
        model=DEVICE_TYPES.get(device_type, device_type),
        sw_version="0.10.0",
    )

    # Power command names and entity presentation vary by device type. Denon has
    # discrete power on/off codes; TVs use a single power toggle. The A5+ has no
    # IR power code (it powers on/off via the front knob), so it exposes only
    # volume + mute and has no power on/off feature.
    supports_power = True
    if device_type == DEVICE_TYPE_DENON_AVR:
        power_on_cmd, power_off_cmd = "power_on", "power_off"
        name, icon = "Receiver", "mdi:audio-video"
    elif device_type == DEVICE_TYPE_AUDIOENGINE_A5:
        power_on_cmd = power_off_cmd = "power"
        name, icon = "Speakers", "mdi:speaker"
        supports_power = False
    else:
        power_on_cmd = power_off_cmd = "power"
        name, icon = "TV", "mdi:television"

    async_add_entities(
        [
            IRMediaPlayer(
                config_entry=config_entry,
                emitter_entity_id=emitter_entity_id,
                command_factory=command_factory,
                device_info=device_info,
                power_on_command=power_on_cmd,
                power_off_command=power_off_cmd,
                name=name,
                icon=icon,
                supports_power=supports_power,
            )
        ]
    )


class IRMediaPlayer(MediaPlayerEntity):
    """A media player entity that controls a TV or receiver via IR."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        emitter_entity_id: str,
        command_factory: object,
        device_info: DeviceInfo,
        power_on_command: str = "power",
        power_off_command: str = "power",
        name: str = "TV",
        icon: str = "mdi:television",
        supports_power: bool = True,
    ) -> None:
        """Initialize the IR media player.

        When ``supports_power`` is False the entity exposes only volume + mute
        (no turn on/off) and assumes an "on" state so the volume controls stay
        active — used for devices with no IR power code (e.g. Audioengine A5+).
        """
        self._emitter_entity_id = emitter_entity_id
        self._command_factory = command_factory
        self._power_on_command = power_on_command
        self._power_off_command = power_off_command
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{config_entry.entry_id}_media_player"
        self._attr_device_info = device_info
        self._attr_is_volume_muted = False

        features = (
            MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        if supports_power:
            features |= (
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )
        self._attr_supported_features = features
        self._attr_state = (
            MediaPlayerState.OFF if supports_power else MediaPlayerState.ON
        )

    async def _send_command(self, command_name: str) -> None:
        """Send an IR command by name."""
        command = self._command_factory(command_name)
        if command is None:
            _LOGGER.warning("Command '%s' not available", command_name)
            return

        _LOGGER.debug("Media player sending '%s'", command_name)

        try:
            await infrared.async_send_command(
                self.hass,
                self._emitter_entity_id,
                command,
                context=self._context,
            )
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to send IR command '%s' via %s: %s",
                command_name,
                self._emitter_entity_id,
                err,
            )
            raise

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self._send_command(self._power_on_command)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await self._send_command(self._power_off_command)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Turn volume up."""
        await self._send_command("volume_up")

    async def async_volume_down(self) -> None:
        """Turn volume down."""
        await self._send_command("volume_down")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute the TV."""
        await self._send_command("mute")
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()
