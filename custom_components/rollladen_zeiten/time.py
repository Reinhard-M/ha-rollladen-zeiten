# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Earliest drive time in the morning / latest drive time in the evening."""
from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RollladenZeitenConfigEntry
from .const import CONF_EARLIEST_MORNING, CONF_EARLIEST_MORNING_FREE, CONF_LATEST_EVENING
from .settings_entity import SettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RollladenZeitenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            LimitTime(c, entry, CONF_EARLIEST_MORNING),
            LimitTime(c, entry, CONF_EARLIEST_MORNING_FREE),
            LimitTime(c, entry, CONF_LATEST_EVENING),
        ]
    )


class LimitTime(SettingEntity, TimeEntity):
    """Neutral: earliest 00:00:00 / latest 23:59:00 = no override.

    The weekend/day-off variant replaces the normal limit on days off;
    00:00:00 there means: the normal limit also applies on days off.
    """

    _attr_icon = "mdi:clock-edit-outline"

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator, entry, key)
        if coordinator.is_awning:
            # awning: different name (key + "_awning"), same entity/unique_id
            self._attr_translation_key = f"{key}_awning"

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Short hint on what the abbreviations in the name mean."""
        if self._setting_key != CONF_EARLIEST_MORNING_FREE:
            return None
        german = (self.hass.config.language or "en").startswith("de")
        return {
            "comment": "WE = Wochenende, FT = Freie Tage"
            if german
            else "WE = weekend, DO = days off"
        }

    @property
    def native_value(self) -> dt_time:
        return dt_time.fromisoformat(self._value)

    def _parse_restored(self, state: str):
        return dt_time.fromisoformat(state).replace(second=0, microsecond=0).isoformat()

    async def async_set_value(self, value: dt_time) -> None:
        # seconds always 00: the time dialog would otherwise keep e.g. the 59 of 23:59:59
        self._apply(value.replace(second=0, microsecond=0).isoformat())
