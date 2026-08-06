"""Constants for the RF433 Outlets integration."""

from __future__ import annotations

from pathlib import Path

DOMAIN = "rf433_outlets"

# Configuration keys
CONF_ON_CODE = "on_code"
CONF_OFF_CODE = "off_code"
CONF_PULSE_LENGTH = "pulse_length"
CONF_POWER = "power"

# Defaults
DEFAULT_PULSE_LENGTH = 180
# Declared power draw of the appliance plugged into the outlet, in watts. The
# outlet has no metering hardware: this value is what the power sensor reports
# while the outlet is on, and what the daily energy sensor integrates over time.
DEFAULT_POWER = 100.0

# The codesend executable is shipped inside the integration folder, next to
# __init__.py. The path is not configurable.
CODESEND_PATH = str(Path(__file__).parent / "codesend")

# The PIN code passed to codesend is always 0 (2nd positional argument).
PIN_CODE = "0"
