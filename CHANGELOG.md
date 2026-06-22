# Changelog

All notable changes to the Remote Devices integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.12.0] - 2026-06-22

### Added
- **Tristar PD-8779 temperature as a `number` entity** — a `−`/`+` stepper (16–31 °C) instead of separate Temp Up / Temp Down buttons. Changing it sends the matching number of `temp_up`/`temp_down` IR presses and tracks an assumed value (no feedback from the AC, so it can drift if the physical remote is also used).
- New `number` platform (`Platform.NUMBER`).

### Changed
- The Tristar AC now exposes **3 buttons** (power, mode, speed) plus the temperature number, rather than 5 buttons.

## [0.11.0] - 2026-06-22

### Changed
- **Tristar PD-8779 reimplemented correctly.** Real Broadlink captures of the remote revealed it is a plain **NEC** remote (address `0x04`) sending discrete button codes — not the stateful ZH/LT-01 AC protocol assumed in 0.10.0. It is now exposed as **5 button entities** (power `0x04`, temp_up `0x05`, temp_down `0x01`, mode `0x0D`, speed `0x06`), decoded from packets with valid NEC checksums.

### Removed
- The `climate` platform, the `zhlt01.py` encoder, and all ZH/LT-01 constants — they were based on a wrong assumption about this unit and never worked. `Platform.CLIMATE` is no longer registered.

### Upgrade note
- If you added the Tristar device on 0.10.0, reload the integration (or restart HA) after updating: the old (non-functional) climate entity is replaced by the button entities.

## [0.10.0] - 2026-06-21

### Added
- **Tristar PD-8779 Air Conditioner** device type (IR — ZH/LT-01 protocol) exposed as a new **`climate`** platform/entity
  - HVAC modes: off, cool, dry, fan_only, auto (heat omitted — cooling-only unit)
  - Target temperature 16–32 °C (1° steps), fan auto/low/medium/high, vertical swing on/off
  - Stateful protocol: every change re-sends the full 12-byte ZH/LT-01 frame (power, mode, temp, fan, swing); state is assumed/optimistic
- New `zhlt01.py` encoder (`ZHLT01Command`) and `climate.py` platform; `Platform.CLIMATE` added to the integration's platforms
- New ZH/LT-01 constants in `const.py` (timings, mode/fan/swing/power values, temp range)

### Changed
- Bumped DeviceInfo `sw_version` to 0.10.0 across all platforms (also corrects `fan`/`light`, which still read 0.8.1)

### Notes
- **The ZH/LT-01 encoder is untested on real hardware.** It is ported faithfully from the ESPHome `zhlt01` component and ToniA's HeatpumpIR ZHLT01, but has not been verified against an actual Tristar PD-8779. If a field is wrong, open an issue with a Broadlink-learned capture so the encoding can be corrected.

## [0.9.0] - 2026-06-15

### Added
- **Audioengine A5+ Speakers** device type (IR — extended NEC, 16-bit address 0x00FD, 3 commands: volume up/down, mute)
  - Exposed as a `media_player` entity (volume step + mute, assumed "on" state) plus 3 buttons
  - No power command: the A5+ powers on/off via the front volume knob, not the IR remote
  - Codes verified against the Flipper Zero IR database and the JP1 Remotes forum
- `NECCommand` now supports **extended NEC** via a new `address_high` argument. When set, the second address byte is sent verbatim instead of as the complement of the low byte — required for the Audioengine address (0xFD is not ~0x00). Standard NEC behaviour is unchanged when `address_high` is omitted.

### Changed
- Bumped DeviceInfo `sw_version` to 0.9.0.

## [0.8.1] - 2026-05-06

### Fixed
- **Command classes now inherit from the official HA ABCs.** `NECCommand`, `SharpCommand`, `DenonCommand`, `RawBroadlinkCommand`, `RawTestCommand` all extend `homeassistant.components.infrared.InfraredCommand`. `RawBroadlinkRFCommand` extends `homeassistant.components.radio_frequency.RadioFrequencyCommand`. Previously they were duck-typed and only worked with our `broadlink_emitter`'s permissive entity — now they work with **any** compliant emitter, including the Broadlink integration in HA core 2026.5+ (`infrared.IR_emitter` / `radio_frequency.RF_emitter`) and ESPHome.
- `get_raw_timings()` now returns the official flat `list[int]` of signed microseconds (positive = pulse, negative = space), matching `infrared_protocols.Command.get_raw_timings()`. Removed the local `Timing(high_us, low_us)` dataclass — there is no `Timing` type in HA's official API.

### Changed
- `broadlink_decode.decode_broadlink_b64_to_timings()` returns `list[int]` instead of `list[Timing]`.
- Bumped DeviceInfo `sw_version` to 0.8.1.

### Migration
- No user action required. Existing IR devices configured against our `broadlink_emitter` still work (its converter now also accepts the new format). You can also now point them at the HA-core-provided `infrared.IR_emitter` / `radio_frequency.RF_emitter` entities and they'll work — no need for our `broadlink_emitter` for IR.

### Requires
- `broadlink_emitter` v0.4.1+ if you're using it (the matching converter update is shipped in that release).

## [0.8.0] - 2026-05-06

### Added
- **RF (radio frequency) device support** via the new HA 2026.5 `radio_frequency` platform
- **Airwit Plafondventilator (ceiling fan)** device type — RF 433 MHz, OOK modulation
  - 13 captured commands: lamp toggle, fan speeds 1-6, natural wind preset, brightness up/down, fan off, all off, fan direction
  - Exposed as a `fan` entity (speed + preset + direction), a `light` entity (lamp toggle), and 3 buttons (brightness_up, brightness_down, all_off)
  - Voice control, Lovelace fan/light cards, scenes, and automations all work natively
- New `rf_commands.py` with `RawBroadlinkRFCommand` — mirrors the IR `RawBroadlinkCommand` pattern but produces `RadioFrequencyCommand` objects with frequency + OOK modulation
- New `broadlink_decode.py` shared helper extracted from `nec.py` — used by both IR and RF raw-command classes
- Pre-decoding: every Airwit code is decoded once at module import (i7-class HA, no point paying the cost on every press)
- Two-step config flow: pick device type first, then the integration shows only the protocol-matching emitters (IR or RF)

### Changed
- **Renamed integration domain `infrared_remote` → `remote_devices`** (breaking; existing users must remove and re-add config entries)
- Renamed integration title from "Infrared Remote" to "Remote Devices"
- `manifest.json` adds `radio_frequency` to dependencies and bumps minimum HA to 2026.5
- Renamed config key `CONF_INFRARED_ENTITY_ID` → `CONF_EMITTER_ENTITY_ID` (and stored value `infrared_entity_id` → `emitter_entity_id`) since emitters are no longer IR-only
- `button.py`: extracted `_RemoteButtonBase`; `IRButton` and `RFButton` subclasses dispatch to the right HA platform
- DeviceInfo `manufacturer` is now "Remote Devices" (was "Infrared Remote") and `sw_version` reflects the integration version

### Migration from 0.7.x
- Remove existing "Infrared Remote" config entries
- Update via HACS or replace the custom_components folder
- Add the new "Remote Devices" integration; re-create your TVs, receivers, lamps, etc.

## [0.7.0] - 2026-04-03

### Added
- **Philips RGBIC Ambient Floor Lamp** device type (NEC protocol, address 0x00, 11 commands: on/off, brightness, 6 colors, night mode)
- **Amino Kamai 7X Set-top Box** device type (RC6 protocol, raw Broadlink-learned codes, 8 commands: power, channel up/down, play/pause/stop, forward/rewind)
- New `RawBroadlinkCommand` class for devices using protocols too complex to encode (decodes learned Broadlink packets to raw timings)

## [0.6.0] - 2026-04-03

### Added
- **Reconfigure flow**: "Configure" button on integration entries in Settings > Devices & Services
  - Shows which infrared emitter is currently linked
  - Allows changing emitter, device type, and device name after setup
  - Works for both standalone and attach-to-device entries
- Added Denon AVR "Stereo" surround mode button (code 230)

## [0.5.4] - 2026-04-03

### Added
- Denon AVR: expanded from 7 to 15 commands — added input_cd, input_tuner, input_vcr, input_v_aux, input_cdr_tape, pure_direct, standard, multi_channel
- Renamed input_opt1/opt2 to proper names (input_tv_dbs, input_dvd)

## [0.5.3] - 2026-04-03

### Fixed
- **Denon AVR command codes were wrong**: IRDB codes didn't match the actual AVR-2106 remote. Decoded real Broadlink-learned codes to get correct values (e.g., volume_up was 76 in IRDB but 241 in reality).

### Changed
- Replaced IRDB-sourced Denon commands with codes decoded from actual remote: power_on (225), power_off (226), volume_up (241), volume_down (242), mute (240), input_opt1 (201), input_opt2 (227)

## [0.5.2] - 2026-04-03

### Fixed
- **Denon still not working**: Removed incorrect header pulse — Denon protocol has NO header, data starts immediately with address bits. Also corrected timing to exact multiples of 264µs base unit (792µs/1848µs spaces, 43560µs frame gap).

## [0.5.1] - 2026-04-03

### Fixed
- **Denon AVR not working**: Denon uses different timing from Sharp (264µs vs 320µs base unit) and requires a header pulse. Split into separate `DenonCommand` encoder with correct timing: 264µs mark, 789µs/1841µs spaces, header pulse, and proper 2-bit extension frame structure.

## [0.5.0] - 2026-04-03

### Added
- **Sharp TV (Aquos)** device type with Sharp protocol encoder (address 1, 20 commands)
- **Denon AVR Receiver** device type with Sharp/Denon protocol encoder (address 2, 12 commands including discrete power on/off and input selection)
- New `sharp.py` protocol encoder supporting the Sharp/Denon IR protocol family (5-bit address + 8-bit command, two-frame transmission with inversion check)
- Denon AVR media player entity shows as "Receiver" with discrete power on/off commands
- Button icons for number keys, Denon inputs (CD, DVD, Tuner, Phono), surround modes

## [0.4.0] - 2026-04-02

### Added
- **Attach to existing device** option in config flow — IR button entities merge into an existing device (e.g., your LG WebOS TV) instead of creating a separate device
- Media player entity is skipped in attach mode (the target device already has one)
- New config flow with setup mode choice: "Create new device" or "Attach to existing device"

## [0.3.3] - 2026-04-02

### Fixed
- Added icon URL to hacs.json so HACS displays the integration icon

## [0.3.2] - 2026-04-02

### Fixed
- Added error handling around IR send calls in button and media_player platforms (logs and re-raises `HomeAssistantError`)
- Fixed `sw_version` mismatch in button and media_player `DeviceInfo` (was `0.3.0`, now matches manifest)

## [0.3.1] - 2026-04-02

### Fixed
- Fixed repository link in README (`your-repo` → `SurfHost`)

## [0.3.0] - 2026-04-02

### Added
- Support for the official `infrared-protocols` library (`home-assistant-libs/infrared-protocols`)
  - Uses `make_lg_tv_command()` from the library for LG TV commands when available
  - Automatic fallback to built-in NEC encoder if the library is not installed
- New `ir_commands.py` module as unified command factory layer

### Fixed
- Brand icons now in `brand/` directory with both `icon.png` and `logo.png` (HA 2026.3+ requirement)
- Removed SVG from brand folder (HA only supports PNG)

### Changed
- Button and media_player platforms now use `ir_commands` factory instead of directly instantiating NEC commands
- Updated documentation URL to GitHub repository
- Added `@SurfHost` as codeowner

## [0.2.0] - 2026-04-01

### Added
- Integration icon in PNG and PNG@2x formats
- Proper `DeviceInfo` on all entities so buttons and media_player group under one device
- Optional device name field in config flow (e.g., "Woonkamer TV")

### Changed
- Renamed from `ir_test_remote` to `infrared_remote`

### Fixed
- Entities not grouping under a device in the HA device registry

## [0.1.0] - 2026-04-01

### Added
- Initial release (as `ir_test_remote`)
- Built-in NEC protocol encoder (no external dependencies)
- LG TV device type with 18 NEC commands (address 0x04)
- Samsung TV device type with 15 NEC commands (address 0x07)
- Raw Test Signal mode for verifying the IR chain
- `media_player` entity with assumed state (turn on/off, volume, mute)
- `button` entities for each remote command with MDI icons
- Config flow with emitter selection and device type dropdown
- Tested with Broadlink RM4 Pro as emitter and LG TV as target
