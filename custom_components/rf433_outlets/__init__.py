"""RF433 Outlets integration.

Each config entry represents one outlet: it creates a dedicated device holding
a switch entity plus the consumption sensors derived from its state.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR]


@dataclass
class RF433OutletRuntimeData:
    """State shared between the platforms of one outlet.

    The switch owns the outlet state; the sensors only derive consumption from
    it. Rather than having them watch the switch entity through the state
    machine (which would mean resolving its entity id, and the platforms are
    set up concurrently so it may not exist yet), the switch keeps this value
    up to date and fires signal_outlet_state(). Sensors read it when they are
    added and are woken by the signal afterwards.
    """

    is_on: bool = False


def signal_outlet_state(entry_id: str) -> str:
    """Dispatcher signal fired when an outlet's state changed."""
    return f"{DOMAIN}_state_{entry_id}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an outlet from a config entry."""
    # Must exist before the platforms are forwarded: they read it on setup.
    entry.runtime_data = RF433OutletRuntimeData()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Reload the entry whenever the options change (codes, pulse length, power).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an outlet."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options have been updated."""
    await hass.config_entries.async_reload(entry.entry_id)
