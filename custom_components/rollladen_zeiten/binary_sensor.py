# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Binary sensors: day (on) / night (off) and day off."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RollladenZeitenConfigEntry
from .coordinator import RollladenZeitenCoordinator
from .entity import RollladenZeitenEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RollladenZeitenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    c = entry.runtime_data
    async_add_entities([IsDayBinarySensor(c, entry), FreeDayBinarySensor(c, entry)])


class IsDayBinarySensor(RollladenZeitenEntity, BinarySensorEntity):
    """On = day, off = night."""

    def __init__(self, coordinator: RollladenZeitenCoordinator, entry) -> None:
        super().__init__(coordinator, entry, "is_day")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_day

    @property
    def icon(self) -> str:
        return "mdi:weather-sunny" if self.is_on else "mdi:weather-night"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"spans_midnight": self.coordinator.data.times.spans_midnight}


class FreeDayBinarySensor(RollladenZeitenEntity, BinarySensorEntity):
    """On = weekend or an event in one of the selected calendars (holiday, vacation, ...)."""

    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator: RollladenZeitenCoordinator, entry) -> None:
        super().__init__(coordinator, entry, "free_day")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.free_day

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        return {"reasons": d.free_reasons, "calendars_ok": d.calendars_ok}
