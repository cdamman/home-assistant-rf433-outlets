"""Sensor platform for RF433 Outlets.

The outlets have no metering hardware, so consumption is *simulated* from the
switch state and a per-outlet power value configured by the user:

* a power sensor reporting that value while the outlet is on, 0 W otherwise;
* a daily energy sensor integrating that power and resetting at local midnight.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import CONF_POWER, DEFAULT_POWER, DOMAIN
from .runtime import RF433OutletRuntimeData

# How often the daily energy sensor integrates the current power. Switching the
# outlet integrates immediately too, so this only bounds how stale the total
# gets while the outlet stays in the same state. Ticks that do not move the
# published value (outlet off, or a sub-Wh increment) write nothing, so idle
# outlets cost the recorder nothing.
_ENERGY_UPDATE_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the consumption sensors for this outlet."""
    async_add_entities(
        [RF433OutletPowerSensor(entry), RF433OutletDailyEnergySensor(entry)]
    )


class RF433OutletSensorBase(SensorEntity):
    """Common wiring: same device as the switch, follows its state."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the sensor from its config entry."""
        self._entry = entry
        self._runtime: RF433OutletRuntimeData = entry.runtime_data

        # Attached to the device created by the switch platform.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="RF433 Outlets",
            model="RF 433 MHz controlled outlet",
        )

    @property
    def _power(self) -> float:
        """Configured power draw while the outlet is on, in watts."""
        return float(self._entry.options.get(CONF_POWER, DEFAULT_POWER))

    @property
    def _current_power(self) -> float:
        """Power drawn right now: the configured value, or 0 W when off."""
        return self._power if self._runtime.is_on else 0.0


class RF433OutletPowerSensor(RF433OutletSensorBase):
    """Simulated instantaneous consumption of the outlet."""

    _attr_translation_key = "current_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the power sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_power"

    async def async_added_to_hass(self) -> None:
        """Follow the switch state."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._runtime.async_add_listener(self._async_outlet_changed)
        )

    @callback
    def _async_outlet_changed(self) -> None:
        """Republish the power after the outlet was switched."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        """Current simulated power draw."""
        return self._current_power


class RF433OutletDailyEnergySensor(RF433OutletSensorBase, RestoreEntity):
    """Energy consumed since local midnight, integrated from the power value.

    Exposed as a diagnostic entity: the figure is derived from a user-declared
    power, not measured, so it belongs with the device diagnostics rather than
    with its controls.
    """

    _attr_translation_key = "today_energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    # TOTAL (not TOTAL_INCREASING) with an explicit last_reset: the daily reset
    # is scheduled by us, so we can state exactly when the meter restarted
    # instead of letting the statistics engine guess from a value drop.
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 3
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the daily energy counter."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_energy_today"
        self._energy_kwh = 0.0
        self._attr_last_reset = dt_util.start_of_local_day()
        # Instant of the last integration step, in UTC (monotonic across DST
        # changes, unlike local time).
        self._last_integrated = dt_util.utcnow()
        # Power level in effect since that instant. Held separately from
        # _current_power because the switch notifies us *after* flipping its
        # state: the elapsed slice must be billed at the level that was in
        # force during it, not at the one that just took over.
        self._integrated_power = 0.0
        # Last value handed to the state machine, so a tick that changes
        # nothing (outlet off) does not write an identical state.
        self._published_value = 0.0

    async def async_added_to_hass(self) -> None:
        """Restore today's total, then start integrating."""
        await super().async_added_to_hass()

        today = dt_util.start_of_local_day()
        if (last_state := await self.async_get_last_state()) is not None:
            # The stored total is only meaningful if it was accumulated during
            # the current day; anything older belongs to a day already over.
            last_reset = dt_util.parse_datetime(
                last_state.attributes.get("last_reset") or ""
            )
            if last_reset is not None and dt_util.as_local(last_reset) >= today:
                try:
                    self._energy_kwh = float(last_state.state)
                except ValueError:
                    # unknown/unavailable after a restart: start the day over.
                    self._energy_kwh = 0.0
                self._attr_last_reset = last_reset

        self._last_integrated = dt_util.utcnow()
        self._integrated_power = self._current_power
        self._published_value = self.native_value

        self.async_on_remove(
            self._runtime.async_add_listener(self._async_outlet_changed)
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_periodic_update, _ENERGY_UPDATE_INTERVAL
            )
        )
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_daily_reset, hour=0, minute=0, second=0
            )
        )

    @callback
    def _async_integrate(self) -> None:
        """Add the energy consumed since the previous integration step."""
        now = dt_util.utcnow()
        elapsed = (now - self._last_integrated).total_seconds()
        self._last_integrated = now
        if elapsed > 0:
            # W * s -> kWh
            self._energy_kwh += self._integrated_power * elapsed / 3_600_000
        # From now on, time is billed at whatever the outlet draws today.
        self._integrated_power = self._current_power

    @callback
    def _async_outlet_changed(self) -> None:
        """Close the slice at the previous power level, then publish."""
        self._async_integrate()
        self._async_publish()

    @callback
    def _async_periodic_update(self, now: datetime) -> None:
        """Integrate on a timer so the total stays fresh."""
        self._async_integrate()
        if self.native_value != self._published_value:
            self._async_publish()

    @callback
    def _async_daily_reset(self, now: datetime) -> None:
        """Close the day at local midnight and restart from zero."""
        self._async_integrate()
        self._energy_kwh = 0.0
        self._attr_last_reset = dt_util.start_of_local_day()
        self._async_publish()

    @callback
    def _async_publish(self) -> None:
        """Push the current total to the state machine."""
        self._published_value = self.native_value
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        """Energy consumed since the last reset."""
        return round(self._energy_kwh, 6)
