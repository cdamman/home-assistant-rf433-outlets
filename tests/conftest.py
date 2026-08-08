"""Fixtures for the RF433 Outlets tests."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ha_stubs  # noqa: E402

# The fake Home Assistant must exist before the integration is imported.
ha_stubs.install()

from custom_components.rf433_outlets import (  # noqa: E402
    RF433OutletRuntimeData,
    signal_outlet_state,
)
from custom_components.rf433_outlets.const import (  # noqa: E402
    CONF_POWER,
    CONF_STANDBY_POWER,
)


@pytest.fixture(autouse=True)
def _reset_stubs():
    """Give every test a fresh clock and empty callback registries."""
    ha_stubs.reset()
    yield
    ha_stubs.reset()


class FakeConfigEntry:
    """Just the parts of a ConfigEntry the entities read."""

    def __init__(
        self,
        power: float | None = None,
        standby: float | None = None,
        name: str = "Lampe salon",
    ) -> None:
        self.entry_id = "01JABCDEF"
        self.data = {"name": name}
        self.options = {}
        if power is not None:
            self.options[CONF_POWER] = power
        if standby is not None:
            self.options[CONF_STANDBY_POWER] = standby
        self.runtime_data = RF433OutletRuntimeData()


class Outlet:
    """Drives one sensor the way Home Assistant and the switch would."""

    def __init__(self, entry: FakeConfigEntry, sensor) -> None:
        self.entry = entry
        self.sensor = sensor
        # Remember which callbacks this sensor registered, so several sensors
        # can coexist in one test without firing each other's timers.
        before_interval = len(ha_stubs.TIME_INTERVAL_CALLBACKS)
        before_change = len(ha_stubs.TIME_CHANGE_CALLBACKS)
        asyncio.run(sensor.async_added_to_hass())
        self._ticks = ha_stubs.TIME_INTERVAL_CALLBACKS[before_interval:]
        self._resets = ha_stubs.TIME_CHANGE_CALLBACKS[before_change:]

    def switch(self, is_on: bool) -> None:
        """Do what RF433OutletSwitch._publish_state does."""
        if self.entry.runtime_data.is_on == is_on:
            return
        self.entry.runtime_data.is_on = is_on
        ha_stubs.dispatcher_send(None, signal_outlet_state(self.entry.entry_id))

    def advance(self, seconds: float) -> None:
        """Move the clock without firing anything."""
        ha_stubs.advance(seconds)

    def tick(self, seconds: float | None = None) -> None:
        """Advance the clock, then fire the periodic integration."""
        if seconds is not None:
            self.advance(seconds)
        for target in self._ticks:
            target(ha_stubs.utcnow())

    def midnight(self) -> None:
        """Fire the scheduled local-midnight reset."""
        for target in self._resets:
            target(ha_stubs.utcnow())


@pytest.fixture
def make_entry():
    """Build a config entry with a declared power draw."""
    return FakeConfigEntry


@pytest.fixture
def power_sensor():
    """Build a started power sensor and its driver."""
    from custom_components.rf433_outlets.sensor import RF433OutletPowerSensor

    def _build(
        power: float | None = None,
        standby: float | None = None,
        entry: FakeConfigEntry | None = None,
    ):
        entry = entry or FakeConfigEntry(power, standby)
        return Outlet(entry, RF433OutletPowerSensor(entry))

    return _build


@pytest.fixture
def energy_sensor():
    """Build a started daily energy sensor and its driver.

    `restore` stages the state Home Assistant would hand back after a restart.
    """
    from custom_components.rf433_outlets.sensor import RF433OutletDailyEnergySensor

    def _build(
        power: float | None = None,
        standby: float | None = None,
        restore: ha_stubs.State | None = None,
        already_on: bool = False,
    ):
        entry = FakeConfigEntry(power, standby)
        entry.runtime_data.is_on = already_on
        sensor = RF433OutletDailyEnergySensor(entry)
        sensor.last_state = restore
        return Outlet(entry, sensor)

    return _build
