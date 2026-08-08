"""Constants for the RF433 Outlets integration."""

from __future__ import annotations

from pathlib import Path

DOMAIN = "rf433_outlets"

# Configuration keys
CONF_ON_CODE = "on_code"
CONF_OFF_CODE = "off_code"
CONF_PULSE_LENGTH = "pulse_length"
CONF_POWER = "power"
CONF_STANDBY_POWER = "standby_power"

# Defaults
DEFAULT_PULSE_LENGTH = 180
# Declared power draw of the appliance plugged into the outlet, in watts. The
# outlet has no metering hardware: this value is what the power sensor reports
# while the outlet is on, and what the daily energy sensor integrates over time.
# Defaults to 0: nothing is declared until the user states what is plugged in,
# so the sensors read 0 W / 0 kWh rather than inventing a consumption.
DEFAULT_POWER = 0.0
# Power the appliance keeps drawing while the outlet is off — a wall wart, a
# TV on standby, an LED. Same reasoning for the default: nothing is assumed
# until the user declares it.
DEFAULT_STANDBY_POWER = 0.0

# The codesend executable is shipped inside the integration folder, next to
# __init__.py. The path is not configurable.
CODESEND_PATH = str(Path(__file__).parent / "codesend")

# The PIN code passed to codesend is always 0 (2nd positional argument).
PIN_CODE = "0"
