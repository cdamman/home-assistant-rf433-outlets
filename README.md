# RF433 Outlets

[![HACS: custom repository](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

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
  architecture or libc, rebuild `codesend` from
  [433Utils](https://github.com/ninjablocks/433Utils) and replace the binary.
* The ON and OFF codes of each outlet. Capture them with `RFSniffer` (also from
  433Utils) using a 433 MHz *receiver*, while pressing the buttons on the
  original remote.

## Installation

### HACS (custom repository)

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

**Settings → Devices & services → Add integration → RF433 Outlets**, once per
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

## Repository

<https://github.com/cdamman/home-assistant-rf433-outlets>
