"""Config flow for the Remote Devices integration.

Two-step flow: first pick the device type, then the integration shows only
emitters that match that device's protocol (IR or RF).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import infrared, radio_frequency
from homeassistant.components.radio_frequency import ModulationType
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    AIRWIT_FAN_FREQUENCY_HZ,
    CONF_ATTACH_TO_DEVICE,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_EMITTER_ENTITY_ID,
    DEVICE_PROTOCOLS,
    DEVICE_TYPES,
    DOMAIN,
)

SETUP_MODE_NEW = "new_device"
SETUP_MODE_ATTACH = "attach_to_device"


def _get_emitters_for_protocol(hass: Any, protocol: str) -> list[str]:
    """Return the list of emitter entity ids matching the given protocol."""
    if protocol == "rf":
        emitters = radio_frequency.async_get_transmitters(
            hass,
            frequency=AIRWIT_FAN_FREQUENCY_HZ,
            modulation=ModulationType.OOK,
        )
    else:
        emitters = infrared.async_get_emitters(hass)
    return list(emitters or [])


def _emitter_selector(emitters: list[str], protocol: str) -> EntitySelector:
    """Build an EntitySelector for the given protocol."""
    selector_domain = "radio_frequency" if protocol == "rf" else "infrared"
    return EntitySelector(
        EntitySelectorConfig(
            domain=selector_domain,
            include_entities=emitters,
        )
    )


class RemoteDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Remote Devices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise per-flow cache."""
        self._cache: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: choose setup mode."""
        if user_input is not None:
            if user_input["setup_mode"] == SETUP_MODE_ATTACH:
                return await self.async_step_attach()
            return await self.async_step_new_device()

        # Need at least one emitter (IR or RF) to do anything useful.
        any_emitters = _get_emitters_for_protocol(self.hass, "ir") or _get_emitters_for_protocol(
            self.hass, "rf"
        )
        if not any_emitters:
            return self.async_abort(reason="no_emitters")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("setup_mode", default=SETUP_MODE_NEW): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=SETUP_MODE_NEW,
                                    label="Create new device",
                                ),
                                SelectOptionDict(
                                    value=SETUP_MODE_ATTACH,
                                    label="Attach to existing device",
                                ),
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_new_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2 (new): pick device type and optional name."""
        if user_input is not None:
            self._cache[CONF_DEVICE_TYPE] = user_input[CONF_DEVICE_TYPE]
            self._cache[CONF_DEVICE_NAME] = user_input.get(CONF_DEVICE_NAME, "").strip()
            return await self.async_step_select_emitter()

        device_options = [
            SelectOptionDict(value=key, label=label) for key, label in DEVICE_TYPES.items()
        ]

        return self.async_show_form(
            step_id="new_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE, default="nec_tv"): SelectSelector(
                        SelectSelectorConfig(
                            options=device_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_DEVICE_NAME, default=""): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                }
            ),
        )

    async def async_step_select_emitter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3 (new): pick the emitter for the chosen device type's protocol."""
        device_type = self._cache[CONF_DEVICE_TYPE]
        protocol = DEVICE_PROTOCOLS.get(device_type, "ir")

        if user_input is not None:
            entity_id = user_input[CONF_EMITTER_ENTITY_ID]
            device_name = self._cache.get(CONF_DEVICE_NAME) or DEVICE_TYPES.get(
                device_type, "Remote Device"
            )

            await self.async_set_unique_id(f"{entity_id}_{device_type}_{device_name}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_EMITTER_ENTITY_ID: entity_id,
                    CONF_DEVICE_TYPE: device_type,
                    CONF_DEVICE_NAME: device_name,
                },
            )

        emitters = _get_emitters_for_protocol(self.hass, protocol)
        if not emitters:
            return self.async_abort(
                reason="no_rf_emitters" if protocol == "rf" else "no_ir_emitters"
            )

        return self.async_show_form(
            step_id="select_emitter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMITTER_ENTITY_ID): _emitter_selector(emitters, protocol),
                }
            ),
            description_placeholders={
                "device_type": DEVICE_TYPES.get(device_type, device_type),
                "protocol": protocol.upper(),
            },
        )

    async def async_step_attach(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Attach: pick device and device type, then emitter."""
        if user_input is not None:
            self._cache[CONF_ATTACH_TO_DEVICE] = user_input[CONF_ATTACH_TO_DEVICE]
            self._cache[CONF_DEVICE_TYPE] = user_input[CONF_DEVICE_TYPE]
            return await self.async_step_attach_select_emitter()

        device_options = [
            SelectOptionDict(value=key, label=label)
            for key, label in DEVICE_TYPES.items()
            if key != "raw_test"
        ]

        return self.async_show_form(
            step_id="attach",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ATTACH_TO_DEVICE): DeviceSelector(
                        DeviceSelectorConfig(
                            entity=[{"domain": "media_player"}],
                        )
                    ),
                    vol.Required(CONF_DEVICE_TYPE, default="nec_tv"): SelectSelector(
                        SelectSelectorConfig(
                            options=device_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_attach_select_emitter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attach step 2: pick the protocol-matching emitter."""
        device_type = self._cache[CONF_DEVICE_TYPE]
        device_id = self._cache[CONF_ATTACH_TO_DEVICE]
        protocol = DEVICE_PROTOCOLS.get(device_type, "ir")

        if user_input is not None:
            entity_id = user_input[CONF_EMITTER_ENTITY_ID]

            dev_reg = dr.async_get(self.hass)
            dev_entry = dev_reg.async_get(device_id)
            device_name = dev_entry.name if dev_entry else device_id

            await self.async_set_unique_id(f"{entity_id}_{device_type}_attach_{device_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{device_name} Buttons",
                data={
                    CONF_EMITTER_ENTITY_ID: entity_id,
                    CONF_DEVICE_TYPE: device_type,
                    CONF_DEVICE_NAME: device_name,
                    CONF_ATTACH_TO_DEVICE: device_id,
                },
            )

        emitters = _get_emitters_for_protocol(self.hass, protocol)
        if not emitters:
            return self.async_abort(
                reason="no_rf_emitters" if protocol == "rf" else "no_ir_emitters"
            )

        return self.async_show_form(
            step_id="attach_select_emitter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMITTER_ENTITY_ID): _emitter_selector(emitters, protocol),
                }
            ),
            description_placeholders={
                "device_type": DEVICE_TYPES.get(device_type, device_type),
                "protocol": protocol.upper(),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure: change emitter, device type, and name.

        Both standalone and attach entries render the same field order:
        Emitter > Target Device (attach only) > Device Type > Device Name.
        Device Name is editable in both modes; if left blank it falls back to
        the target device's name (attach) or the device type label (standalone).
        """
        entry = self._get_reconfigure_entry()
        is_attach = bool(entry.data.get(CONF_ATTACH_TO_DEVICE))

        if user_input is not None:
            entity_id = user_input[CONF_EMITTER_ENTITY_ID]
            device_type = user_input[CONF_DEVICE_TYPE]
            device_name = user_input.get(CONF_DEVICE_NAME, "").strip()

            if is_attach:
                device_id = user_input[CONF_ATTACH_TO_DEVICE]
                if not device_name:
                    dev_reg = dr.async_get(self.hass)
                    dev_entry = dev_reg.async_get(device_id)
                    device_name = dev_entry.name if dev_entry else device_id

                return self.async_update_reload_and_abort(
                    entry,
                    title=f"{device_name} Buttons",
                    data={
                        CONF_EMITTER_ENTITY_ID: entity_id,
                        CONF_DEVICE_TYPE: device_type,
                        CONF_DEVICE_NAME: device_name,
                        CONF_ATTACH_TO_DEVICE: device_id,
                    },
                    reason="reconfigure_successful",
                )

            if not device_name:
                device_name = DEVICE_TYPES.get(device_type, "Remote Device")

            return self.async_update_reload_and_abort(
                entry,
                title=device_name,
                data={
                    CONF_EMITTER_ENTITY_ID: entity_id,
                    CONF_DEVICE_TYPE: device_type,
                    CONF_DEVICE_NAME: device_name,
                },
                reason="reconfigure_successful",
            )

        # Reconfigure shows both IR and RF emitters > user picks the one matching
        # the device type they (re-)select.
        ir_emitters = _get_emitters_for_protocol(self.hass, "ir")
        rf_emitters = _get_emitters_for_protocol(self.hass, "rf")
        all_emitters = ir_emitters + rf_emitters

        device_options = [
            SelectOptionDict(value=key, label=label)
            for key, label in DEVICE_TYPES.items()
            if not is_attach or key != "raw_test"
        ]

        emitter_selector = EntitySelector(
            EntitySelectorConfig(
                domain=["infrared", "radio_frequency"],
                include_entities=all_emitters,
            )
        )

        device_type_selector = SelectSelector(
            SelectSelectorConfig(
                options=device_options,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        device_name_selector = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))

        # Same field order for both modes; attach entries additionally show the
        # Target Device field (inherent to attach mode) after the emitter.
        fields: dict[Any, Any] = {
            vol.Required(CONF_EMITTER_ENTITY_ID): emitter_selector,
        }
        if is_attach:
            fields[vol.Required(CONF_ATTACH_TO_DEVICE)] = DeviceSelector(
                DeviceSelectorConfig(
                    entity=[{"domain": "media_player"}],
                )
            )
        fields[vol.Required(CONF_DEVICE_TYPE)] = device_type_selector
        fields[vol.Optional(CONF_DEVICE_NAME, default="")] = device_name_selector

        schema = vol.Schema(fields)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, entry.data),
            description_placeholders={
                "emitter": entry.data.get(CONF_EMITTER_ENTITY_ID, "unknown"),
            },
        )
