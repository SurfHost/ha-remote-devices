# Remote Devices

[![Validate](https://github.com/SurfHost/ha-remote-devices/actions/workflows/validate.yml/badge.svg)](https://github.com/SurfHost/ha-remote-devices/actions/workflows/validate.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration that creates **button**, **media_player**, **fan**, and **light** entities to control IR and RF devices through the Home Assistant 2026.5 `infrared` and `radio_frequency` platforms.

## What does this do?

This is a **consumer integration** for the HA `infrared` and `radio_frequency` platforms. It sends commands through any compatible emitter (like [Broadlink IR/RF Emitter](https://github.com/SurfHost/ha-broadlink-emitter) or ESPHome).

Set it up, pick your device type, pick the matching emitter (the integration filters automatically based on whether the device uses IR or RF), and you get appropriate HA-native entities:

- A **media_player** entity for TVs and AV receivers (power, volume, mute)
- A **fan** entity for ceiling fans (speed, preset modes, direction)
- A **light** entity for lamps (on/off)
- **Button** entities for everything else
- Option to **attach to an existing device** (like Battery Notes does) instead of creating a separate one
- **Reconfigure** support — change emitter, type, or name after setup

## Supported devices

| Device Type | Protocol | Entities |
|-------------|----------|----------|
| LG TV | IR — NEC (addr 0x04) | media_player + 18 buttons |
| Samsung TV | IR — NEC (addr 0x07) | media_player + 15 buttons |
| Sharp TV (Aquos) | IR — Sharp (addr 0x01) | media_player + 20 buttons |
| Denon AVR Receiver | IR — Denon (addr 0x02) | media_player + 16 buttons |
| Audioengine A5+ Speakers | IR — extended NEC (addr 0x00FD) | media_player (volume + mute) + 3 buttons |
| Tristar PD-8779 Air Conditioner | IR — NEC (addr 0x04) | 5 buttons (power, temp ±, mode, speed) |
| Philips RGBIC Lamp | IR — NEC (addr 0x00) | 11 buttons |
| Amino Kamai 7X STB | IR — RC6 (raw learned) | 8 buttons |
| Raw Test | IR — raw burst | 1 button |
| Airwit Plafondventilator | RF 433 MHz — raw learned | fan + light + 3 buttons |

## Requirements

- Home Assistant **2026.5** or later
- An IR or RF emitter integration (e.g., [Broadlink IR/RF Emitter](https://github.com/SurfHost/ha-broadlink-emitter), ESPHome IR/RF proxy)

## Installation

### HACS (Recommended)

[![Add Repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=SurfHost&repository=ha-remote-devices&category=integration)

Or manually:

1. Open HACS in Home Assistant
2. Click the three dots in the top right and select **Custom repositories**
3. Add this repository URL and select **Integration** as category
4. Click **Download**
5. Restart Home Assistant

### Manual

1. Download the `custom_components/remote_devices` folder
2. Place it in your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Setup

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=remote_devices)

Or manually:

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Remote Devices**
3. Choose setup mode (new device or attach to existing)
4. Pick the device type (e.g., "Airwit Plafondventilator (RF 433 MHz)")
5. Pick the matching emitter (only emitters compatible with your device type's protocol are shown)
6. Optionally give it a name (e.g., "Slaapkamer ventilator")
7. Done — your fan/TV/lamp now shows up as proper HA entities

## Airwit Plafondventilator

The Airwit ceiling fan is exposed as **three entities under one device**, so you get HA-native control:

- `fan.airwit_plafondventilator` — speeds 1-6 (mapped to 17%/33%/50%/67%/83%/100%), `natural_wind` preset, forward/reverse direction
- `light.airwit_plafondventilator_lamp` — on/off (lamp is a single toggle code; state is optimistic)
- 3 buttons: `brightness_up`, `brightness_down`, `all_off`

This means voice assistants ("Alexa, set ceiling fan to medium"), Lovelace fan/light cards, scenes, and standard automations all work without scripts.

## Tristar PD-8779 Air Conditioner

Despite being an air conditioner, the PD-8779 remote is a plain **NEC** remote (address `0x04`) that sends discrete button codes — the AC keeps its own temperature/mode state on its front display. It is therefore exposed as **button** entities that mirror the physical remote, not a climate entity:

- `power`, `temp_up`, `temp_down`, `mode` (cycles cool/dry/fan), `speed` (cycles fan speed)

The codes were decoded from real Broadlink-learned packets (all with valid NEC checksums). If your remote has extra buttons (timer, swing, sleep, …), learn them and open an issue — they're almost certainly more NEC codes on address `0x04` and easy to add.

> Tip: if you'd prefer a single `−`/`+` temperature stepper instead of two buttons, add a **Tile card** for a [helper](https://www.home-assistant.io/integrations/input_number/) or use the `temp_up`/`temp_down` buttons in a custom card — the AC sends only relative steps, so there's no absolute "set 23 °C" code.

## Testing

1. **Raw test first** (IR): Set up with "Raw Test Signal". Press the button. If your IR blaster blinks, the chain works.
2. **TV / receiver / fan**: Set up with the matching device type and emitter.
3. **Dashboard**: Add the appropriate fan/light/media_player card.

## Adding more device types

Built-in protocol encoders: **NEC** (incl. extended NEC), **Sharp**, and **Denon** for IR. RF (Airwit) uses raw Broadlink-learned packets. For unsupported protocols, learned codes can be stored as raw timings — see [`rf_commands.py`](custom_components/remote_devices/rf_commands.py) and [`nec.py`](custom_components/remote_devices/nec.py) for the pattern. PRs welcome!

## Upgrading from 0.7.x (`infrared_remote`)

Version 0.8.0 renames the integration from `infrared_remote` to `remote_devices` to reflect that it now handles both IR and RF. To upgrade:

1. Remove the old "Infrared Remote" config entries from **Settings > Devices & Services**
2. Update via HACS (or replace the `custom_components/infrared_remote` folder with `custom_components/remote_devices`)
3. Restart Home Assistant
4. Add the new "Remote Devices" integration and re-create your devices
