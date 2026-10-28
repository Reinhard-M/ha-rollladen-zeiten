# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Sensors: day/night (text) and morning/evening drive times (time or timestamp)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RollladenZeitenConfigEntry
from .const import STATE_DAY, STATE_NIGHT
from .coordinator import RollladenZeitenCoordinator
from .entity import RollladenZeitenEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RollladenZeitenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            DayNightSensor(coordinator, entry),
            MorningTimeSensor(coordinator, entry),
            EveningTimeSensor(coordinator, entry),
            MorningTimestampSensor(coordinator, entry),
            EveningTimestampSensor(coordinator, entry),
        ]
    )


class DayNightSensor(RollladenZeitenEntity, SensorEntity):
    """State 'day' or 'night' (translated as Tag/Nacht in the UI)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_DAY, STATE_NIGHT]

    def __init__(self, coordinator: RollladenZeitenCoordinator, entry) -> None:
        super().__init__(coordinator, entry, "day_night")

    @property
    def native_value(self) -> str:
        return STATE_DAY if self.coordinator.data.is_day else STATE_NIGHT

    @property
    def icon(self) -> str:
        return "mdi:weather-sunny" if self.coordinator.data.is_day else "mdi:weather-night"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        t = self.coordinator.data.times
        return {"polar": t.polar, "spans_midnight": t.spans_midnight}


class _TimeSensor(RollladenZeitenEntity, SensorEntity):
    """Base for the drive-time sensors (today, local time).

    Default: only the time of day as text "HH:MM:SS" (without date), like an
    input_datetime with "time only". The *_timestamp variants deliver the
    full timestamp (e.g. for `trigger: time` with `at: sensor.…`).
    """

    _timestamp = False

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP if self._timestamp else None

    def _final(self) -> datetime | None:
        raise NotImplementedError

    def _sun(self) -> datetime | None:
        raise NotImplementedError

    def _overridden(self) -> bool:
        raise NotImplementedError

    def _sun_off(self) -> bool:
        raise NotImplementedError

    @property
    def native_value(self) -> datetime | str | None:
        value = self._final()
        if value is None or self._timestamp:
            return value
        if value.date() > self.coordinator.data.times.date:
            return "23:59:00"  # show the end of the day (00:00 of the next day) as 23:59:00
        return value.strftime("%H:%M:%S")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sun = self._sun()
        final = self._final()
        return {
            "timestamp": final.isoformat() if final and not self._timestamp else None,
            # pure sun position, without earliest/latest limit (ISO string, like a state)
            "sun_time": sun.isoformat() if sun and not self._sun_off() else None,
            "overridden": self._overridden(),  # True = a limit applies
            "polar": self.coordinator.data.times.polar,
        }


class MorningTimeSensor(_TimeSensor):
    """Morning drive time = max(sun position, earliest time)."""

    _attr_icon = "mdi:blinds-open"

    def __init__(self, coordinator: RollladenZeitenCoordinator, entry) -> None:
        super().__init__(coordinator, entry, "morning")

    def _final(self) -> datetime | None:
        return self.coordinator.data.times.morning

    def _sun(self) -> datetime | None:
        return self.coordinator.data.times.sun_morning

    def _sun_off(self) -> bool:
        return self.coordinator.data.times.morning_off

    def _overridden(self) -> bool:
        return self.coordinator.data.times.morning_overridden


class EveningTimeSensor(_TimeSensor):
    """Evening drive time = min(sun position, latest time)."""

    _attr_icon = "mdi:blinds"

    def __init__(self, coordinator: RollladenZeitenCoordinator, entry) -> None:
        super().__init__(coordinator, entry, "evening")

    def _final(self) -> datetime | None:
        return self.coordinator.data.times.evening

    def _sun(self) -> datetime | None:
        return self.coordinator.data.times.sun_evening

    def _sun_off(self) -> bool:
        return self.coordinator.data.times.evening_off

    def _overridden(self) -> bool:
        return self.coordinator.data.times.evening_overridden


class MorningTimestampSensor(MorningTimeSensor):
    """Like the morning drive time, but as a timestamp (disabled by default)."""

    _timestamp = True
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RollladenZeitenCoordinator, entry) -> None:
        RollladenZeitenEntity.__init__(self, coordinator, entry, "morning_timestamp")


class EveningTimestampSensor(EveningTimeSensor):
    """Like the evening drive time, but as a timestamp (disabled by default)."""

    _timestamp = True
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RollladenZeitenCoordinator, entry) -> None:
        RollladenZeitenEntity.__init__(self, coordinator, entry, "evening_timestamp")
