"""Status sensor for the FuxNoten integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CHILD_NAME, DOMAIN
from .coordinator import FuxNotenCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the status sensor for a config entry."""
    coordinator: FuxNotenCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([FuxNotenLastSyncSensor(coordinator, entry)])


class FuxNotenLastSyncSensor(CoordinatorEntity[FuxNotenCoordinator], SensorEntity):
    """Shows the timestamp of the last successful sync run."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: FuxNotenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_sync"
        child_name = entry.data.get(CONF_CHILD_NAME, "")
        self._attr_name = f"FuxNoten {child_name} - Last sync".strip()

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.last_sync

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return {}
        return {
            "fetched_graded_assignments": self.coordinator.data.fetched_count,
            "newly_created_events": self.coordinator.data.created_count,
        }
