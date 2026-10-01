"""Read-only PTZ telemetry with bounded, on-demand destination confirmation."""

from __future__ import annotations

from contextlib import suppress
from collections import deque
import asyncio

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import CONF_BAICHUAN_PORT, CONF_CHANNEL, CONF_CONNECTION, DOMAIN
from .monitor import Confirmation, Position, confirm_destination
from .reader import ReolinkPositionReader


CONFIRM_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("pan"): vol.Coerce(int),
    vol.Required("tilt"): vol.Coerce(int),
    vol.Optional("destination", default=""): vol.All(cv.string, vol.Length(max=100)),
    vol.Optional("tolerance", default=25): vol.All(vol.Coerce(int), vol.Range(min=0, max=200)),
    vol.Optional("interval", default=0.25): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=2)),
    vol.Optional("timeout", default=12): vol.All(vol.Coerce(float), vol.Range(min=1, max=60)),
})


class PTZRuntime:
    def __init__(self, reader: ReolinkPositionReader, initial: Position):
        self.reader = reader
        self.position = initial
        self.status = "ready"
        self.sensor = None
        self.generation = 0
        self.stable_intervals = deque(maxlen=64)
        self.requested_destination = ""

    def update(self, position: Position) -> None:
        self.position = position
        if self.sensor is not None:
            self.sensor.async_write_ha_state()

    async def confirm(self, call: ServiceCall) -> dict:
        self.generation += 1
        generation = self.generation
        self.status = "observing"
        self.requested_destination = call.data["destination"]
        if self.sensor is not None:
            self.sensor.async_write_ha_state()
        try:
            result: Confirmation = await confirm_destination(
                self.reader.async_read,
                pan=call.data["pan"],
                tilt=call.data["tilt"],
                tolerance=call.data["tolerance"],
                interval=call.data["interval"],
                timeout=call.data["timeout"],
                current=lambda: self.generation == generation,
                on_read=self.update,
            )
        except asyncio.CancelledError:
            if self.generation == generation:
                self.status = "cancelled"
                if self.sensor is not None:
                    self.sensor.async_write_ha_state()
            raise
        if self.generation == generation:
            self.status = "confirmed" if result.confirmed else result.reason
            if (result.confirmed and call.data["destination"]
                    and (result.position.measured_at - result.settled_since).total_seconds() <= 3):
                self.stable_intervals.append({
                    "destination": call.data["destination"],
                    "start": result.settled_since.isoformat(),
                    "end": result.position.measured_at.isoformat(),
                    "pan": result.position.pan, "tilt": result.position.tilt,
                })
            if self.sensor is not None:
                self.sensor.async_write_ha_state()
        return {
            "confirmed": result.confirmed,
            "reason": result.reason,
            "pan": result.position.pan if result.position else None,
            "tilt": result.position.tilt if result.position else None,
            "measured_at": result.position.measured_at.isoformat() if result.position else None,
            "samples": result.samples,
            "settled_since": result.settled_since.isoformat() if result.settled_since else None,
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    reader = ReolinkPositionReader(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD],
        data[CONF_BAICHUAN_PORT], data[CONF_CONNECTION], data[CONF_CHANNEL],
    )
    try:
        initial = await reader.async_open()
    except Exception as error:
        with suppress(Exception):
            await reader.async_close()
        raise ConfigEntryNotReady("PTZ position is not available") from error
    runtimes = hass.data.setdefault(DOMAIN, {})
    runtimes[entry.entry_id] = PTZRuntime(reader, initial)

    async def async_confirm(call: ServiceCall) -> dict:
        runtime = next(
            (item for item in hass.data[DOMAIN].values()
             if item.sensor is not None and item.sensor.entity_id == call.data["entity_id"]),
            None,
        )
        if runtime is None:
            raise ServiceValidationError("PTZ telemetry entity is not configured")
        return await runtime.confirm(call)

    if not hass.services.has_service(DOMAIN, "confirm_destination"):
        hass.services.async_register(
            DOMAIN, "confirm_destination", async_confirm,
            schema=CONFIRM_SCHEMA, supports_response=SupportsResponse.ONLY,
        )
    try:
        await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    except Exception:
        runtimes.pop(entry.entry_id, None)
        if not runtimes:
            hass.services.async_remove(DOMAIN, "confirm_destination")
        with suppress(Exception):
            await reader.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, ["sensor"]):
        return False
    runtime = hass.data[DOMAIN].pop(entry.entry_id)
    runtime.generation += 1
    await runtime.reader.async_close()
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "confirm_destination")
    return True
