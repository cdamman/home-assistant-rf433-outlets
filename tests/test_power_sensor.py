"""Tests for the simulated instantaneous consumption sensor."""

from __future__ import annotations


def test_reports_nothing_while_the_outlet_is_off(power_sensor):
    outlet = power_sensor(power=1500)
    assert outlet.sensor.native_value == 0.0


def test_reports_the_declared_power_while_the_outlet_is_on(power_sensor):
    outlet = power_sensor(power=1500)
    outlet.switch(True)
    assert outlet.sensor.native_value == 1500.0


def test_falls_back_to_zero_when_no_power_was_declared(power_sensor):
    outlet = power_sensor()
    outlet.switch(True)
    assert outlet.sensor.native_value == 0.0


def test_publishes_a_new_value_when_the_outlet_is_switched(power_sensor):
    outlet = power_sensor(power=60)
    outlet.switch(True)
    outlet.switch(False)
    assert outlet.sensor.writes == [60.0, 0.0]


def test_follows_a_power_value_edited_through_the_options(power_sensor):
    outlet = power_sensor(power=100)
    outlet.switch(True)
    # The options flow reloads the entry, but the sensor reads the option on
    # every access, so an edit is picked up even without a reload.
    outlet.entry.options["power"] = 250
    assert outlet.sensor.native_value == 250.0


def test_carries_the_metadata_home_assistant_needs(power_sensor):
    sensor = power_sensor(power=100).sensor
    assert sensor.native_unit_of_measurement == "W"
    assert sensor.device_class == "power"
    assert sensor.state_class == "measurement"
    assert sensor.unique_id == "01JABCDEF_power"
    assert sensor.translation_key == "current_power"


def test_reports_the_standby_power_while_the_outlet_is_off(power_sensor):
    outlet = power_sensor(power=1500, standby=2.5)
    assert outlet.sensor.native_value == 2.5


def test_switches_between_the_two_declared_levels(power_sensor):
    outlet = power_sensor(power=1500, standby=2.5)
    outlet.switch(True)
    assert outlet.sensor.native_value == 1500.0
    outlet.switch(False)
    assert outlet.sensor.native_value == 2.5


def test_standby_defaults_to_zero(power_sensor):
    outlet = power_sensor(power=1500)
    assert outlet.sensor.native_value == 0.0
