"""Tests for the daily energy sensor.

1000 W for one hour is 1 kWh, which makes the expected totals below readable.
"""

from __future__ import annotations

import ha_stubs

HOUR = 3600


def test_starts_the_day_at_zero(energy_sensor):
    outlet = energy_sensor(power=1000)
    assert outlet.sensor.native_value == 0.0
    assert outlet.sensor.last_reset == ha_stubs.start_of_local_day()


def test_accumulates_nothing_while_the_outlet_is_off(energy_sensor):
    outlet = energy_sensor(power=1000)
    outlet.tick(HOUR)
    assert outlet.sensor.native_value == 0.0


def test_accumulates_while_the_outlet_is_on(energy_sensor):
    outlet = energy_sensor(power=1000)
    outlet.switch(True)
    outlet.tick(HOUR / 2)
    assert outlet.sensor.native_value == 0.5


def test_bills_a_switch_off_at_the_level_that_was_in_force(energy_sensor):
    """The switch notifies *after* flipping, so the level must be remembered."""
    outlet = energy_sensor(power=1000)
    outlet.switch(True)
    outlet.advance(HOUR / 2)  # half an hour at 1000 W, no tick in between
    outlet.switch(False)
    assert outlet.sensor.native_value == 0.5


def test_bills_a_switch_on_at_zero_for_the_idle_period(energy_sensor):
    outlet = energy_sensor(power=1000)
    outlet.advance(HOUR)  # an hour off
    outlet.switch(True)
    outlet.advance(HOUR / 4)
    outlet.switch(False)
    assert outlet.sensor.native_value == 0.25


def test_accumulates_across_several_on_periods(energy_sensor):
    outlet = energy_sensor(power=1000)
    for _ in range(3):
        outlet.switch(True)
        outlet.advance(HOUR / 4)
        outlet.switch(False)
        outlet.advance(HOUR)
    assert outlet.sensor.native_value == 0.75


def test_declares_zero_consumption_by_default(energy_sensor):
    outlet = energy_sensor()
    outlet.switch(True)
    outlet.tick(HOUR)
    assert outlet.sensor.native_value == 0.0


def test_writes_nothing_when_the_total_does_not_move(energy_sensor):
    """An outlet left off must not fill the recorder with identical states."""
    outlet = energy_sensor(power=1000)
    for _ in range(10):
        outlet.tick(60)
    assert outlet.sensor.writes == []


def test_writes_the_total_while_the_outlet_draws_power(energy_sensor):
    outlet = energy_sensor(power=1000)
    outlet.switch(True)
    outlet.tick(60)
    assert outlet.sensor.writes[-1] > 0


def test_resets_at_local_midnight(energy_sensor):
    outlet = energy_sensor(power=1000)
    outlet.switch(True)
    outlet.tick(HOUR)
    assert outlet.sensor.native_value == 1.0

    outlet.midnight()
    assert outlet.sensor.native_value == 0.0
    assert outlet.sensor.last_reset == ha_stubs.start_of_local_day()


def test_keeps_counting_after_the_reset(energy_sensor):
    outlet = energy_sensor(power=1000)
    outlet.switch(True)
    outlet.tick(HOUR)
    outlet.midnight()
    outlet.tick(HOUR)
    assert outlet.sensor.native_value == 1.0


def test_restores_a_total_from_the_same_day(energy_sensor):
    reset_at = ha_stubs.start_of_local_day()
    outlet = energy_sensor(
        power=1000,
        restore=ha_stubs.State("1.25", {"last_reset": reset_at.isoformat()}),
    )
    assert outlet.sensor.native_value == 1.25
    assert outlet.sensor.last_reset == reset_at


def test_drops_a_total_left_over_from_a_previous_day(energy_sensor):
    yesterday = ha_stubs.start_of_local_day().replace(day=5)
    outlet = energy_sensor(
        power=1000,
        restore=ha_stubs.State("7.5", {"last_reset": yesterday.isoformat()}),
    )
    assert outlet.sensor.native_value == 0.0
    assert outlet.sensor.last_reset == ha_stubs.start_of_local_day()


def test_ignores_a_restored_state_that_is_not_a_number(energy_sensor):
    outlet = energy_sensor(
        power=1000,
        restore=ha_stubs.State(
            "unknown", {"last_reset": ha_stubs.start_of_local_day().isoformat()}
        ),
    )
    assert outlet.sensor.native_value == 0.0


def test_ignores_a_restored_state_without_a_reset_stamp(energy_sensor):
    outlet = energy_sensor(power=1000, restore=ha_stubs.State("3.0"))
    assert outlet.sensor.native_value == 0.0


def test_integrates_an_outlet_that_was_already_on_at_startup(energy_sensor):
    """The switch restores its state before the sensor is added."""
    outlet = energy_sensor(power=2000, already_on=True)
    outlet.tick(HOUR)
    assert outlet.sensor.native_value == 2.0


def test_carries_the_metadata_long_term_statistics_need(energy_sensor):
    sensor = energy_sensor(power=1000).sensor
    assert sensor.native_unit_of_measurement == "kWh"
    assert sensor.device_class == "energy"
    # TOTAL rather than TOTAL_INCREASING: the reset is scheduled, so its
    # timestamp is stated instead of being guessed from a drop in value.
    assert sensor.state_class == "total"
    assert sensor.entity_category == "diagnostic"
    assert sensor.unique_id == "01JABCDEF_energy_today"
    assert sensor.translation_key == "today_energy"
