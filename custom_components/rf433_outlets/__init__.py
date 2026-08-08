"""RF433 Outlets integration.

Each config entry represents one outlet: it creates a dedicated device holding
a switch entity plus the consumption sensors derived from its state.
"""

from __future__ import annotations

import logging
import stat
from dataclasses import dataclass
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CODESEND_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR]

# Executable bits, for everyone. codesend is a shipped binary, not a secret.
_EXECUTABLE = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


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


def ensure_executable(path: Path) -> bool:
    """Add the executable bits to `path` if they are missing.

    Returns True if the file was changed. Blocking: call from an executor.

    HACS installs an integration by downloading its files one by one and
    writing them fresh, so the mode recorded in git does not survive the
    install — codesend lands as 0644 and the first command fails with
    "codesend is not executable". Rather than asking every user to chmod the
    file again after each update, the bit is restored at startup.

    A failure here is not fatal: it is reported, and if the file really cannot
    be made executable, sending a code raises the error that says so.
    """
    try:
        mode = path.stat().st_mode
    except OSError:
        # Missing or unreadable: sending a code reports that with a better
        # message than anything this function could say at startup.
        return False

    if mode & _EXECUTABLE == _EXECUTABLE:
        return False

    try:
        path.chmod(mode | _EXECUTABLE)
    except OSError as err:
        _LOGGER.warning(
            "Could not restore the executable bit on %s: %s. "
            "Sending a code will fail until it is set (chmod +x)",
            path,
            err,
        )
        return False

    _LOGGER.info("Restored the executable bit on %s", path)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an outlet from a config entry."""
    await hass.async_add_executor_job(ensure_executable, Path(CODESEND_PATH))
    # Must exist before the platforms are forwarded: they read it on setup.
    entry.runtime_data = RF433OutletRuntimeData()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Reload the entry whenever the options change (codes, pulse length, powers).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an outlet."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options have been updated."""
    await hass.config_entries.async_reload(entry.entry_id)
