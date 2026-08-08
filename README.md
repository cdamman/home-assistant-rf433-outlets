# RF433 Outlets

[![HACS: custom repository](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![License: MIT](https://img.shields.io/badge/license-MIT-41BDF5.svg)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/cdamman/home-assistant-rf433-outlets?display_name=tag&sort=semver&color=41BDF5)](https://github.com/cdamman/home-assistant-rf433-outlets/releases/latest)
[![Validate](https://github.com/cdamman/home-assistant-rf433-outlets/actions/workflows/validate.yml/badge.svg)](https://github.com/cdamman/home-assistant-rf433-outlets/actions/workflows/validate.yml)
[![Tests](https://github.com/cdamman/home-assistant-rf433-outlets/actions/workflows/tests.yml/badge.svg)](https://github.com/cdamman/home-assistant-rf433-outlets/actions/workflows/tests.yml)

Home Assistant integration for cheap 433 MHz remote-controlled outlets (the kind
sold with a plastic remote, no metering, no feedback). It drives them through
the `codesend` utility bundled with the integration, and adds a simulated
consumption reading so the outlets can appear in energy statistics.

Each outlet is a separate device, added from the UI, holding:

| Entity | Type | Unit | Notes |
| --- | --- | --- | --- |
| *(device name)* | Switch | — | Device class `outlet`, exposed to Google Home as an outlet |
| Current consumption | Sensor | W | Declared power while on, `0` while off |
| Today's consumption | Sensor | kWh | Diagnostic, resets at local midnight |

## Requirements

* A 433 MHz transmitter wired to the Raspberry Pi GPIO. The transmitter pin is
  **wiringPi pin 0** and is not configurable.
* The bundled `codesend` binary is built for **aarch64 with musl**, i.e. a
  64-bit Home Assistant OS / Container install on a Raspberry Pi. It links
  against the `libwiringPi.so.3.16` shipped next to it (via `RUNPATH=$ORIGIN`),
  so wiringPi does not need to be installed separately. On any other
  architecture or libc, rebuild it — see
  [How `codesend` was built](#how-codesend-was-built).
* The ON and OFF codes of each outlet. Capture them with `RFSniffer` (also from
  433Utils) using a 433 MHz *receiver*, while pressing the buttons on the
  original remote.

## Installation

### HACS (custom repository)

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cdamman&repository=home-assistant-rf433-outlets&category=integration)

The button opens this repository straight in your own HACS. Otherwise, by hand:

1. HACS → three-dot menu → **Custom repositories**.
2. Repository: `https://github.com/cdamman/home-assistant-rf433-outlets`,
   type **Integration**.
3. Install **RF433 Outlets**, then restart Home Assistant.

### Manual

Copy `custom_components/rf433_outlets` into your Home Assistant `config/custom_components/`
directory and restart Home Assistant.

Either way, make sure `codesend` is executable once installed:

```bash
chmod +x config/custom_components/rf433_outlets/codesend
```

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rf433_outlets)

Or **Settings → Devices & services → Add integration → RF433 Outlets**, once per
outlet.

| Field | Default | Meaning |
| --- | --- | --- |
| Outlet name | — | Names the device; must be unique |
| ON code | — | Decimal code transmitted to switch the outlet on |
| OFF code | — | Decimal code transmitted to switch the outlet off |
| Pulse length | 180 | Pulse length in µs, passed to `codesend` |
| Power draw when on | 0 | Declared consumption of the appliance, in watts |

Every field except the name can be changed later through the integration's
**Configure** button; the outlet reloads itself when you save.

## About the consumption figures

These outlets have no metering hardware. Both sensors are **derived from the
switch state and the power value you declare**, not measured:

* **Current consumption** reports the declared power while the outlet is on and
  `0 W` while it is off.
* **Today's consumption** integrates that power over time and resets at local
  midnight. It is published as a diagnostic entity, since the figure is declared
  rather than measured, and carries the metadata long-term statistics need
  (device class `energy`, state class `total` with an explicit `last_reset`).

The daily total is integrated once a minute and immediately on every switch, so
a toggle is billed at the level that was in force before it. It survives Home
Assistant restarts and integration reloads, and is dropped when the stored reset
timestamp belongs to a day already over. Left at the default of 0 W, the sensors
simply read zero and write nothing.

Changing the declared power does not rewrite the past: the day's total keeps
what was already accumulated at the previous level.

## Known behaviour

**The reported state is a belief, not a measurement.** 433 MHz is one-way: the
outlet cannot be queried. Home Assistant caches the last commanded state and
treats it as authoritative — this is deliberate, as it is what lets Google Home
display and track on/off. If an outlet is toggled by its original remote, or an
RF command fails to reach it, the displayed state will be wrong until the next
command from Home Assistant. When a transmission fails, the optimistic state is
rolled back so the entity does not claim a state the outlet never reached.

**Transmissions are serialised.** There is one physical transmitter, so commands
across all outlets take turns, with a short gap between them. Switching several
outlets at once therefore takes a moment longer, but avoids collisions on the
air.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `codesend is not executable` | Missing `+x` bit — see the `chmod` above |
| `codesend exists ... but could not be executed (No such file or directory)` | The binary cannot be run by this OS: wrong architecture or libc. Rebuild it for your platform |
| `codesend executable not found` | The integration folder was copied incompletely |
| `codesend failed (return code ...)` | `codesend` ran but did not report the expected `sending code[...]` line; check GPIO wiring and permissions |
| Commands are occasionally missed | Increase the pulse length, or check the transmitter's power and antenna |

Debug logging:

```yaml
logger:
  logs:
    custom_components.rf433_outlets: debug
```

## How `codesend` was built

`codesend` comes from [433Utils](https://github.com/ninjablocks/433Utils) and was
compiled **inside the Home Assistant container**, so that it matches the
environment it has to run in. That matters: the Home Assistant image is
Alpine-based, so a binary built on a regular Debian/Raspberry Pi OS host links
against glibc and will not start inside the container — it fails with
*"No such file or directory"* even though the file is plainly there.

What the shipped binary reports about itself:

| | |
| --- | --- |
| Architecture | ARM aarch64, position-independent executable |
| Interpreter | `/lib/ld-musl-aarch64.so.1` (musl, i.e. Alpine) |
| Linked against | `libwiringPi.so.3.16`, `libc.musl-aarch64.so.1` |
| `RUNPATH` | `$ORIGIN` — it looks for wiringPi next to itself |

That last line is why `libwiringPi.so.3.16` is shipped in the same folder and
why nothing has to be installed system-wide.

To reproduce it, from a shell inside the container (the *Advanced SSH & Web
Terminal* add-on with protection mode off, or `docker exec -it homeassistant sh`):

```sh
apk add --no-cache build-base git

# wiringPi — the maintained fork; 3.16 is the version shipped here
git clone https://github.com/WiringPi/WiringPi.git
cd WiringPi && ./build && cd ..

# codesend, from 433Utils (rc-switch comes in as a submodule)
git clone --recursive https://github.com/ninjablocks/433Utils.git
cd 433Utils/RPi_utils
g++ -o codesend codesend.cpp ../rc-switch/RCSwitch.cpp \
    -I../rc-switch -lwiringPi -Wl,-rpath,'$ORIGIN'
```

Then copy `codesend` and `libwiringPi.so.3.16` into
`custom_components/rf433_outlets/`, keeping the executable bit on `codesend`.
Only the versioned library name is needed: the plain `libwiringPi.so` is the
link-time name, while the loader resolves the `SONAME` recorded in the binary —
`libwiringPi.so.3.16`.
The build tools do not need to stay installed — they are gone after the next
container update, while the compiled binary is committed to this repository.

## Development

The test suite covers the consumption sensors: the integration arithmetic, the
midnight reset and what survives a restart. It stubs Home Assistant out rather
than installing it, so it needs nothing but `pytest`:

```bash
pip install -r requirements-test.txt
pytest
```

Every pull request runs two workflows: **Tests** (the suite above, on Python
3.12 and 3.13) and **Validate** (`hassfest` plus the HACS action, which check
the integration's metadata the way Home Assistant and HACS do).

## License

[MIT](LICENSE). `codesend` and `libwiringPi` are built from
[433Utils](https://github.com/ninjablocks/433Utils) and
[WiringPi](https://github.com/WiringPi/WiringPi) and keep their own licences.

## Repository

<https://github.com/cdamman/home-assistant-rf433-outlets>
