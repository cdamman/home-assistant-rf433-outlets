"""Minimal stand-ins for the Home Assistant modules the integration imports.

Home Assistant is a heavy dependency pinned to a recent Python, while the
consumption sensors are arithmetic over a clock and an on/off flag. What is
worth testing here is that arithmetic — not Home Assistant itself — so these
stubs expose just enough of the framework for the platform modules to import
and run, and hand the tests a clock they control plus the callbacks the
entities register.

They deliberately do *not* emulate the state machine, the entity registry or
the config entry lifecycle: hassfest and the HACS action validate the metadata
side, and anything relying on real Home Assistant behaviour belongs in a suite
built on pytest-homeassistant-custom-component instead.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone

# A fixed offset stands in for the local time zone. Any non-UTC zone works; a
# non-zero offset is the point, so a bug that confuses local and UTC midnight
# cannot pass unnoticed.
LOCAL_TZ = timezone(timedelta(hours=2))

# Time as the stubs see it. Tests move it through the `clock` fixture; nothing
# here ever reads the real wall clock.
NOW = datetime(2026, 8, 6, 10, 0, 0, tzinfo=timezone.utc)

# Callbacks registered through the event helpers, in registration order.
TIME_INTERVAL_CALLBACKS: list = []
TIME_CHANGE_CALLBACKS: list = []

# Dispatcher signal -> connected callbacks.
SIGNALS: dict[str, list] = {}


def reset() -> None:
    """Return the stubs to their initial state (called before each test)."""
    global NOW
    NOW = datetime(2026, 8, 6, 10, 0, 0, tzinfo=timezone.utc)
    TIME_INTERVAL_CALLBACKS.clear()
    TIME_CHANGE_CALLBACKS.clear()
    SIGNALS.clear()


def advance(seconds: float) -> None:
    """Move the stub clock forward."""
    global NOW
    NOW += timedelta(seconds=seconds)


def utcnow() -> datetime:
    """Stub of homeassistant.util.dt.utcnow."""
    return NOW


def start_of_local_day(value: datetime | None = None) -> datetime:
    """Stub of homeassistant.util.dt.start_of_local_day."""
    local = (value or NOW).astimezone(LOCAL_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


class Entity:
    """Stands in for Home Assistant's Entity base class.

    Home Assistant entities never call super().__init__(), so this class must
    work without having been initialised: the recorded writes are created on
    first use rather than in a constructor.
    """

    hass = None
    entity_id = "sensor.stub"

    def __getattr__(self, name: str):
        """Resolve `foo` to `_attr_foo`, the way Home Assistant entities do.

        Home Assistant declares a property per entity attribute, each falling
        back to the matching `_attr_` class variable. Reproducing that here in
        one place lets the tests read `sensor.device_class` rather than reach
        for the private attribute.
        """
        if name.startswith("_attr_"):  # stop the lookup recursing
            raise AttributeError(name)
        try:
            return self.__getattribute__(f"_attr_{name}")
        except AttributeError:
            raise AttributeError(name) from None

    @property
    def writes(self) -> list:
        """Values handed to the state machine, oldest first."""
        return self.__dict__.setdefault("_writes", [])

    async def async_added_to_hass(self) -> None:
        """No-op: the real one wires the entity into the state machine."""

    def async_write_ha_state(self) -> None:
        """Record what the entity would have published."""
        self.writes.append(self.native_value)

    def async_on_remove(self, func) -> None:
        """Record an unsubscribe callback."""
        self.__dict__.setdefault("_removers", []).append(func)

    @property
    def last_reset(self):
        """Mirror of SensorEntity.last_reset."""
        return getattr(self, "_attr_last_reset", None)


class RestoreEntity:
    """Stands in for RestoreEntity; tests set `last_state` directly."""

    last_state = None

    async def async_added_to_hass(self) -> None:
        """No-op."""

    async def async_get_last_state(self):
        """Return whatever the test staged as the previous state."""
        return self.last_state


class State:
    """A restored state: a string value plus its attributes."""

    def __init__(self, state: str, attributes: dict | None = None) -> None:
        self.state = state
        self.attributes = attributes or {}


def dispatcher_connect(hass, signal: str, target):
    """Stub of async_dispatcher_connect."""
    SIGNALS.setdefault(signal, []).append(target)

    def _remove() -> None:
        SIGNALS[signal].remove(target)

    return _remove


def dispatcher_send(hass, signal: str, *args) -> None:
    """Stub of async_dispatcher_send."""
    for target in list(SIGNALS.get(signal, [])):
        target(*args)


def _module(name: str, **attrs) -> types.ModuleType:
    """Register a fake module under `name` and return it."""
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def install() -> None:
    """Put the fake homeassistant package into sys.modules.

    Must run before the integration is imported, i.e. from conftest.
    """
    _module("homeassistant")
    _module("homeassistant.components")
    _module(
        "homeassistant.components.sensor",
        SensorEntity=Entity,
        SensorDeviceClass=types.SimpleNamespace(POWER="power", ENERGY="energy"),
        SensorStateClass=types.SimpleNamespace(
            MEASUREMENT="measurement", TOTAL="total"
        ),
    )
    _module(
        "homeassistant.components.switch",
        SwitchEntity=Entity,
        SwitchDeviceClass=types.SimpleNamespace(OUTLET="outlet"),
    )
    _module("homeassistant.config_entries", ConfigEntry=object)
    _module(
        "homeassistant.const",
        CONF_NAME="name",
        STATE_ON="on",
        EntityCategory=types.SimpleNamespace(DIAGNOSTIC="diagnostic"),
        Platform=types.SimpleNamespace(SWITCH="switch", SENSOR="sensor"),
        UnitOfEnergy=types.SimpleNamespace(KILO_WATT_HOUR="kWh"),
        UnitOfPower=types.SimpleNamespace(WATT="W"),
    )
    _module("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
    _module("homeassistant.exceptions", HomeAssistantError=Exception)
    _module("homeassistant.helpers")
    _module("homeassistant.helpers.device_registry", DeviceInfo=dict)
    _module(
        "homeassistant.helpers.dispatcher",
        async_dispatcher_connect=dispatcher_connect,
        async_dispatcher_send=dispatcher_send,
    )
    _module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    _module(
        "homeassistant.helpers.event",
        async_track_time_interval=lambda hass, target, interval: (
            TIME_INTERVAL_CALLBACKS.append(target) or (lambda: None)
        ),
        async_track_time_change=lambda hass, target, **kwargs: (
            TIME_CHANGE_CALLBACKS.append(target) or (lambda: None)
        ),
    )
    _module("homeassistant.helpers.restore_state", RestoreEntity=RestoreEntity)
    _module(
        "homeassistant.util",
        dt=_module(
            "homeassistant.util.dt",
            utcnow=utcnow,
            start_of_local_day=start_of_local_day,
            parse_datetime=lambda value: (
                datetime.fromisoformat(value) if value else None
            ),
            as_local=lambda value: value.astimezone(LOCAL_TZ),
            now=lambda: NOW.astimezone(LOCAL_TZ),
        ),
    )
