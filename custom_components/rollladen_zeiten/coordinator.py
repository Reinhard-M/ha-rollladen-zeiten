# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Coordinator: calculates the times and schedules the next update exactly at the switching points."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from astral import Observer

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .calc import DayTimes, compute_day
from .const import (
    CONF_EARLIEST_MORNING,
    CONF_EARLIEST_MORNING_FREE,
    CONF_EVENING_OFFSET,
    CONF_DEVICE_TYPE,
    CONF_EVENING_PRESET,
    CONF_FREE_CALENDARS,
    CONF_LATEST_EVENING,
    CONF_MORNING_OFFSET,
    CONF_MORNING_PRESET,
    CONF_WEEKEND_DAYS,
    DEFAULT_EARLIEST,
    DEFAULT_LATEST,
    DEFAULT_OFFSET,
    DEFAULT_PRESET,
    DEFAULT_WEEKEND,
    DOMAIN,
    TYPE_AWNING,
    WEEKDAYS,
)

_LOGGER = logging.getLogger(__name__)

CALENDAR_RETRY_SECONDS = 60


@dataclass(frozen=True)
class CoordinatorData:
    """State at the time of the last calculation."""

    times: DayTimes
    is_day: bool
    free_day: bool = False
    free_reasons: list[str] = field(default_factory=list)  # "weekend" / calendar entity IDs
    calendars_ok: bool = True


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(value)


def _limit(value: str | None, neutral: str) -> time | None:
    """The neutral value (00:00:00 or 23:59:00) means: no override."""
    # "23:59:59" (default of earlier versions) still counts as "no limit"
    if not value or value in (neutral, "23:59:59"):
        return None
    return _parse_time(value)


class RollladenZeitenCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Calculates day/night and drive times without cyclic polling of the sun."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=None,
        )
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._unsub_retry: CALLBACK_TYPE | None = None
        # Last known calendar result per entity (for outages at startup): (day, has_event)
        self._calendar_cache: dict[str, tuple[date, bool]] = {}
        # Last "day off" result: changing a setting does not need to query the calendars again
        self._free_cache: tuple[date, bool, list[str], bool] | None = None
        self._reuse_free = False
        # The settings live in the select/number/time entities (which restore them).
        # Options from older versions only serve as start values.
        self.settings: dict[str, Any] = {
            CONF_MORNING_PRESET: DEFAULT_PRESET,
            CONF_MORNING_OFFSET: DEFAULT_OFFSET,
            CONF_EARLIEST_MORNING: DEFAULT_EARLIEST,
            CONF_EARLIEST_MORNING_FREE: DEFAULT_EARLIEST,
            CONF_EVENING_PRESET: DEFAULT_PRESET,
            CONF_EVENING_OFFSET: DEFAULT_OFFSET,
            CONF_LATEST_EVENING: DEFAULT_LATEST,
            **entry.options,
        }

    @property
    def is_awning(self) -> bool:
        return self.config_entry.options.get(CONF_DEVICE_TYPE) == TYPE_AWNING

    @property
    def has_calendars(self) -> bool:
        return bool(self.config_entry.options.get(CONF_FREE_CALENDARS))

    @callback
    def set_setting(self, key: str, value: Any, *, refresh: bool = True) -> None:
        """Change a setting and recalculate (immediately)."""
        self.settings[key] = value
        if refresh:
            self._reuse_free = True  # only recalculate the times, do not query the calendars again
            self.hass.async_create_task(self.async_refresh())

    async def _async_calendar_has_event(
        self, entity_id: str, day_start: datetime, day_end: datetime
    ) -> bool | None:
        """True/False = event today yes/no, None = calendar cannot be queried."""
        try:
            response = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "entity_id": entity_id,
                    "start_date_time": day_start.isoformat(),
                    "end_date_time": day_end.isoformat(),
                },
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - a calendar can be missing at startup
            _LOGGER.debug("Kalender %s nicht abfragbar: %s", entity_id, err)
            return None
        events = (response or {}).get(entity_id, {}).get("events", [])
        return bool(events)

    async def _async_free_day(self, now: datetime) -> tuple[bool, list[str], bool]:
        """Day off = weekend or an event in one of the selected calendars."""
        opts = self.config_entry.options
        day = now.date()
        reasons: list[str] = []

        weekend = opts.get(CONF_WEEKEND_DAYS, DEFAULT_WEEKEND)
        if WEEKDAYS[day.weekday()] in weekend:
            reasons.append("weekend")

        calendars_ok = True
        day_start = datetime.combine(day, time.min, tzinfo=now.tzinfo)
        # End deliberately 23:59:59 (the holiday calendar compares the end date inclusively)
        day_end = day_start + timedelta(days=1) - timedelta(seconds=1)
        for entity_id in opts.get(CONF_FREE_CALENDARS, []):
            has_event = await self._async_calendar_has_event(entity_id, day_start, day_end)
            if has_event is None:
                calendars_ok = False
                cached = self._calendar_cache.get(entity_id)
                has_event = bool(cached and cached[0] == day and cached[1])
            else:
                self._calendar_cache[entity_id] = (day, has_event)
            if has_event:
                reasons.append(entity_id)
        return bool(reasons), reasons, calendars_ok

    async def _async_update_data(self) -> CoordinatorData:
        opts = self.settings
        now = dt_util.now()
        observer = Observer(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            elevation=self.hass.config.elevation,
        )
        cache = self._free_cache
        if self._reuse_free and cache and cache[0] == now.date() and cache[3]:
            _, free, reasons, calendars_ok = cache
        else:
            free, reasons, calendars_ok = await self._async_free_day(now)
            self._free_cache = (now.date(), free, list(reasons), calendars_ok)
        self._reuse_free = False

        # On days off the weekend limit (if set) replaces the normal one.
        earliest = _limit(opts.get(CONF_EARLIEST_MORNING), DEFAULT_EARLIEST)
        if free:
            free_limit = _limit(opts.get(CONF_EARLIEST_MORNING_FREE), DEFAULT_EARLIEST)
            if free_limit is not None:
                earliest = free_limit

        times = compute_day(
            observer,
            now.tzinfo,  # type: ignore[arg-type]
            now.date(),
            morning_preset=opts.get(CONF_MORNING_PRESET, DEFAULT_PRESET),
            morning_offset=float(opts.get(CONF_MORNING_OFFSET, DEFAULT_OFFSET)),
            evening_preset=opts.get(CONF_EVENING_PRESET, DEFAULT_PRESET),
            evening_offset=float(opts.get(CONF_EVENING_OFFSET, DEFAULT_OFFSET)),
            earliest_morning=earliest,
            latest_evening=_limit(opts.get(CONF_LATEST_EVENING), DEFAULT_LATEST),
        )
        data = CoordinatorData(
            times=times,
            is_day=times.is_day(now),
            free_day=free,
            free_reasons=reasons,
            calendars_ok=calendars_ok,
        )
        self._schedule_next(now, times)
        self._schedule_retry(calendars_ok)
        return data

    @callback
    def _schedule_next(self, now: datetime, times: DayTimes) -> None:
        """Next switching point: morning, evening or midnight (new day)."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

        midnight = datetime.combine(
            times.date + timedelta(days=1), time.min, tzinfo=now.tzinfo
        )
        candidates = [
            t for t in (times.morning, times.evening, midnight) if t is not None and t > now
        ]
        next_run = min(candidates)
        self._unsub_timer = async_track_point_in_time(
            self.hass, self._handle_timer, next_run
        )

    @callback
    def _schedule_retry(self, calendars_ok: bool) -> None:
        """Calendars are often not ready at startup -> try again shortly afterwards."""
        if self._unsub_retry is not None:
            self._unsub_retry()
            self._unsub_retry = None
        if not calendars_ok:
            self._unsub_retry = async_call_later(
                self.hass, CALENDAR_RETRY_SECONDS, self._handle_retry
            )

    @callback
    def _handle_timer(self, _now: datetime) -> None:
        self._unsub_timer = None
        self.hass.async_create_task(self.async_refresh())

    @callback
    def _handle_retry(self, _now: datetime) -> None:
        self._unsub_retry = None
        self.hass.async_create_task(self.async_refresh())

    async def async_shutdown(self) -> None:
        for attr in ("_unsub_timer", "_unsub_retry"):
            unsub = getattr(self, attr)
            if unsub is not None:
                unsub()
                setattr(self, attr, None)
        await super().async_shutdown()
