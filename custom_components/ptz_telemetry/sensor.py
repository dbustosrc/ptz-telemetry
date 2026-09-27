"""Show the last physical measurement and observation state."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([PTZPositionSensor(hass.data[DOMAIN][entry.entry_id], entry)])


class PTZPositionSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "PTZ telemetry"
    _attr_should_poll = False

    def __init__(self, runtime, entry: ConfigEntry) -> None:
        self._runtime = runtime
        self._attr_unique_id = f"{entry.unique_id}_position"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": entry.title,
            "manufacturer": "Reolink",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._runtime.sensor = self

    async def async_will_remove_from_hass(self) -> None:
        self._runtime.sensor = None
        await super().async_will_remove_from_hass()

    @property
    def native_value(self) -> str:
        return self._runtime.status

    @property
    def extra_state_attributes(self) -> dict:
        position = self._runtime.position
        return {
            "last_pan": position.pan,
            "last_tilt": position.tilt,
            "last_measured_at": position.measured_at.isoformat(),
        }
