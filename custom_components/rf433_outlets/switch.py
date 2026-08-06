"""Switch platform for RF433 Outlets."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import RF433OutletRuntimeData, signal_outlet_state
from .const import (
    CODESEND_PATH,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_PULSE_LENGTH,
    DEFAULT_PULSE_LENGTH,
    DOMAIN,
    PIN_CODE,
)

_LOGGER = logging.getLogger(__name__)

# Serialises RF transmissions across every outlet. The 433 MHz transmitter is a
# single shared medium, so two codesend calls running at once would collide on
# the air. This lock is module-level on purpose: there is one physical
# transmitter (one CODESEND_PATH), so every entity, across every config entry,
# must take turns on it. Only the transmission itself is held under the lock;
# the optimistic state write happens before acquiring it, so tiles still update
# immediately and commands merely go out one after another.
_RF_TX_LOCK = asyncio.Lock()

# Minimum gap kept between two consecutive RF transmissions, in seconds. The
# lock already prevents overlap; this gap adds breathing room so a receiver is
# not still settling from the previous burst when the next one starts. Held
# under the lock (after codesend), so it only ever spaces transmissions apart.
# Tune if grouped commands are occasionally missed.
_RF_TX_GAP = 0.3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the switch entity for this outlet."""
    async_add_entities([RF433OutletSwitch(entry)])


class RF433OutletSwitch(SwitchEntity, RestoreEntity):
    """An RF433 outlet driven by the codesend executable."""

    # The real outlet state cannot be read back (one-way RF). We nevertheless
    # report a concrete state instead of an assumed one: Home Assistant caches
    # the last commanded state and treats it as authoritative. This is what lets
    # Google Home display and track on/off (an assumed_state entity is reported
    # to Google as commandOnlyOnOff, i.e. state cannot be queried). The caveat
    # is that this cached state is a belief, not a measurement: if the outlet is
    # toggled by any other means, or an RF command fails to reach it, the
    # displayed state will be wrong until the next command from HA.
    _attr_assumed_state = False
    _attr_has_entity_name = True
    _attr_name = None  # the entity takes the device name
    # Exposes the entity as a plug/outlet (not a switch) to Home Assistant and,
    # through the google_assistant integration, to Google Home. The mapping
    # (switch, OUTLET) -> action.devices.types.OUTLET is what Google uses.
    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_icon = "mdi:power-socket-eu"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the outlet from its config entry."""
        self._entry = entry
        self._runtime: RF433OutletRuntimeData = entry.runtime_data
        # Codes are editable through the options; fall back to the initial data.
        self._on_code = str(entry.options.get(CONF_ON_CODE, entry.data[CONF_ON_CODE]))
        self._off_code = str(
            entry.options.get(CONF_OFF_CODE, entry.data[CONF_OFF_CODE])
        )
        self._attr_unique_id = entry.entry_id
        self._attr_is_on = False

        # Each outlet is a dedicated device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="RF433 Outlets",
            model="RF 433 MHz controlled outlet",
        )

    @property
    def _pulse_length(self) -> int:
        """Current pulse length (editable through the options)."""
        return self._entry.options.get(CONF_PULSE_LENGTH, DEFAULT_PULSE_LENGTH)

    async def async_added_to_hass(self) -> None:
        """Restore the state cached when Home Assistant last shut down."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON
        self._publish_state(bool(self._attr_is_on))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the outlet on."""
        await self._set_state(True, self._on_code)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the outlet off."""
        await self._set_state(False, self._off_code)

    async def _set_state(self, is_on: bool, code: str) -> None:
        """Update the cached state first, then transmit the RF code.

        The state is written *before* the (comparatively slow) RF transmission.
        With Report State enabled, the google_assistant integration runs the
        turn_on/turn_off service non-blocking and immediately serialises the
        entity state into its EXECUTE response. If we transmitted first and
        wrote the state afterwards, that response would carry the pre-command
        state and Google Home would show the tile flipping on -> off -> on.
        Writing the state up front makes the serialised response already reflect
        the requested value. If the transmission fails, the optimistic state is
        rolled back so we do not report a state the outlet never reached.
        """
        previous = self._attr_is_on
        self._attr_is_on = is_on
        self._publish_state(is_on)
        self.async_write_ha_state()
        try:
            async with _RF_TX_LOCK:
                await self._send_code(code)
                await asyncio.sleep(_RF_TX_GAP)
        except Exception:
            self._attr_is_on = previous
            self._publish_state(bool(previous))
            self.async_write_ha_state()
            raise

    @callback
    def _publish_state(self, is_on: bool) -> None:
        """Share the state with the consumption sensors, if it changed."""
        if self._runtime.is_on == is_on:
            return
        self._runtime.is_on = is_on
        async_dispatcher_send(self.hass, signal_outlet_state(self._entry.entry_id))

    async def _send_code(self, code: str) -> None:
        """Run codesend and verify the transmission succeeded.

        Command: codesend <code> <PIN=0> <pulse_length>
        Expected success line on stdout: "sending code[<code>]"
        """
        args = [CODESEND_PATH, code, PIN_CODE, str(self._pulse_length)]
        _LOGGER.debug("Running codesend: %s", " ".join(args))

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
        except FileNotFoundError as err:
            # ENOENT from exec does not always mean the file is missing. When
            # the file is present, it almost always means the OS cannot find
            # something needed to run it: for a script, a wrong shebang or CRLF
            # line endings; for a binary, a missing dynamic loader or shared
            # library (e.g. built for a different architecture/libc than the
            # Home Assistant container it runs in).
            if Path(CODESEND_PATH).is_file():
                raise HomeAssistantError(
                    f"codesend exists at {CODESEND_PATH} but could not be "
                    "executed (No such file or directory). This usually means "
                    "its interpreter or a shared library is missing: check the "
                    "shebang and line endings for a script, or the architecture "
                    "and linked libraries for a binary."
                ) from err
            raise HomeAssistantError(
                f"codesend executable not found: {CODESEND_PATH}"
            ) from err
        except PermissionError as err:
            raise HomeAssistantError(
                f"codesend is not executable: {CODESEND_PATH} (run: chmod +x)"
            ) from err
        except OSError as err:
            raise HomeAssistantError(f"Failed to run codesend: {err}") from err

        output = stdout.decode(errors="replace").strip()
        expected = f"sending code[{code}]"

        if proc.returncode != 0 or expected not in output:
            err_out = output or stderr.decode(errors="replace").strip()
            raise HomeAssistantError(
                f"codesend failed (return code {proc.returncode}). "
                f"Output: {err_out!r}"
            )

        _LOGGER.debug("codesend OK: %s", output)
