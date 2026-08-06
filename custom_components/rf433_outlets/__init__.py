"""RF433 Outlets integration.

Each config entry represents one outlet: it creates a dedicated device holding
a switch entity plus the consumption sensors derived from its state.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .runtime import RF433OutletRuntimeData

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an outlet from a config entry."""
    # Shared between the platforms: the switch publishes its state here and the
    # sensors read it. Must exist before the platforms are forwarded.
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
