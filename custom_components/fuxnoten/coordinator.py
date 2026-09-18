"""Coordinates the sync FuxNoten -> HA calendar.

Unlike a typical DataUpdateCoordinator, this one does not poll on a
fixed interval. It is refreshed once at startup and then externally,
once per day at a configurable time (see __init__.py, which registers
a homeassistant.helpers.event.async_track_time_change callback).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp
import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FuxNotenAuthError, FuxNotenClient, FuxNotenError
from .const import (
    CATEGORY_ID_LEISTUNGEN,
    CONF_CHILD_ID,
    CONF_PASSWORD,
    CONF_SCHOOL_NUMBER,
    CONF_TARGET_CALENDAR,
    CONF_USERNAME,
    DEFAULT_LOOKAHEAD_DAYS,
    DEFAULT_LOOKBACK_DAYS,
    DOMAIN,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    build_base_url,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FuxNotenSyncResult:
    """Result of a sync run, used for diagnostics/sensor purposes."""

    last_sync: datetime
    fetched_count: int
    created_count: int


class FuxNotenCoordinator(DataUpdateCoordinator[FuxNotenSyncResult]):
    """Fetches graded assignments from the Elternportal and creates new
    calendar events for them. Refreshed on a daily schedule, not on a
    fixed polling interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            # No update_interval: refreshes are triggered explicitly,
            # once at startup and then daily via async_track_time_change.
            update_interval=None,
        )
        self._entry = entry
        self._store: Store[dict[str, list[int]]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry.entry_id}"
        )

    async def _async_update_data(self) -> FuxNotenSyncResult:
        entry_data = self._entry.data
        base_url = build_base_url(entry_data[CONF_SCHOOL_NUMBER])

        start = dt_util.now().date() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        end = dt_util.now().date() + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)

        try:
            async with FuxNotenClient(
                base_url,
                entry_data[CONF_USERNAME],
                entry_data[CONF_PASSWORD],
            ) as client:
                events = await client.async_get_events(entry_data[CONF_CHILD_ID], start, end)
        except FuxNotenAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FuxNotenError as err:
            raise UpdateFailed(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Network error while contacting FuxNoten: {err}") from err

        graded_assignments = [e for e in events if e.get("category_id") == CATEGORY_ID_LEISTUNGEN]
        created_count = await self._async_sync_to_calendar(graded_assignments)

        return FuxNotenSyncResult(
            last_sync=dt_util.utcnow(),
            fetched_count=len(graded_assignments),
            created_count=created_count,
        )

    async def _async_sync_to_calendar(self, events: list[dict[str, Any]]) -> int:
        """Create new events in the target calendar, skip already-known ones."""
        target_calendar = self._entry.data[CONF_TARGET_CALENDAR]

        stored = await self._store.async_load() or {"ids": []}
        known_ids: set[int] = set(stored.get("ids", []))

        new_ids: list[int] = []

        for event in events:
            event_id = event.get("id")
            if not event_id or event_id in known_ids:
                continue

            start_str = event.get("start")
            if not start_str:
                continue

            start_date = date.fromisoformat(start_str)
            # calendar.create_event expects an exclusive end date for
            # all-day events (like iCal) - for a single-day event that
            # means start + 1 day.
            end_str = event.get("end")
            end_date = date.fromisoformat(end_str) if end_str else start_date + timedelta(days=1)

            try:
                await self.hass.services.async_call(
                    "calendar",
                    "create_event",
                    {
                        "entity_id": target_calendar,
                        "summary": event.get("title", "FuxNoten event"),
                        "description": (
                            f"Category: {event.get('category', '')}\nFuxNoten ID: {event_id}"
                        ),
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    },
                    blocking=True,
                )
            except Exception:  # noqa: BLE001 - one failed entry should not
                # prevent the rest from being created, just log it.
                _LOGGER.exception(
                    "Failed to create FuxNoten event %s ('%s') in calendar %s",
                    event_id,
                    event.get("title"),
                    target_calendar,
                )
                continue

            new_ids.append(event_id)

        if new_ids:
            known_ids.update(new_ids)
            await self._store.async_save({"ids": sorted(known_ids)})
            _LOGGER.info(
                "Created %d new FuxNoten event(s) in calendar %s",
                len(new_ids),
                target_calendar,
            )

        return len(new_ids)
