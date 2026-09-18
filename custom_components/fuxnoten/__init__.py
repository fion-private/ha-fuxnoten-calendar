"""FuxNoten Elternportal integration.

Syncs graded assignments / tests from the Elternportal calendar into a
Home Assistant calendar, once per day at a configurable time.
"""

from __future__ import annotations

import logging
from datetime import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_SYNC_TIME, DEFAULT_SYNC_TIME, DOMAIN
from .coordinator import FuxNotenCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


def _parse_sync_time(value: str) -> time:
    """Parse an "HH:MM:SS" (or "HH:MM") string into a time object."""
    parts = [int(p) for p in value.split(":")]
    while len(parts) < 3:
        parts.append(0)
    hour, minute, second = parts[:3]
    return time(hour=hour, minute=minute, second=second)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    coordinator = FuxNotenCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    sync_time = _parse_sync_time(entry.data.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME))

    async def _handle_scheduled_sync(_now) -> None:
        _LOGGER.debug("Running scheduled FuxNoten sync for entry %s", entry.entry_id)
        await coordinator.async_refresh()

    unsub = async_track_time_change(
        hass,
        _handle_scheduled_sync,
        hour=sync_time.hour,
        minute=sync_time.minute,
        second=sync_time.second,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "unsub_time_trigger": unsub,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_time_trigger"]()
    return unload_ok
