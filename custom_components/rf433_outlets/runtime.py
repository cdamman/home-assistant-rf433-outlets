"""Runtime state shared between the platforms of a single outlet.

The switch owns the outlet state; the sensors only observe it. Rather than
having the sensors watch the switch entity through the state machine (which
would mean resolving its entity id and reacting one event loop later), the
switch pushes every state change into this small object and the sensors
subscribe to it. One instance per config entry, stored in
``entry.runtime_data``.
"""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import callback


class RF433OutletRuntimeData:
    """Shared on/off state of one outlet, with change notifications."""

    def __init__(self) -> None:
        """Start out off: the switch pushes the restored state when it loads."""
        self._is_on = False
        self._listeners: list[Callable[[], None]] = []

    @property
    def is_on(self) -> bool:
        """Last state commanded to (or restored for) the outlet."""
        return self._is_on

    @callback
    def async_set_is_on(self, is_on: bool) -> None:
        """Record the outlet state and notify the subscribers if it changed."""
        if is_on == self._is_on:
            return
        self._is_on = is_on
        # Iterate over a copy: a listener is free to unsubscribe itself.
        for listener in list(self._listeners):
            listener()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to state changes and return a callable to unsubscribe."""
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove
