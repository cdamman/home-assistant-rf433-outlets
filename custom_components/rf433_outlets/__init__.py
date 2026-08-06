"""RF433 Outlets integration.

Each config entry represents one outlet: it creates a dedicated device holding
a single switch entity.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an outlet from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Reload the entry whenever the options change (codes, pulse length).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an outlet."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options have been updated."""
    await hass.config_entries.async_reload(entry.entry_id)
