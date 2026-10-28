# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Horizon offset in degrees for morning and evening."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RollladenZeitenConfigEntry
from .const import CONF_EVENING_OFFSET, CONF_MORNING_OFFSET
from .settings_entity import SettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RollladenZeitenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [OffsetNumber(c, entry, CONF_MORNING_OFFSET), OffsetNumber(c, entry, CONF_EVENING_OFFSET)]
    )


class OffsetNumber(SettingEntity, NumberEntity):
    _attr_native_min_value = -30.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:angle-acute"

    @property
    def native_value(self) -> float:
        return float(self._value)

    def _parse_restored(self, state: str):
        return float(state)

    async def async_set_native_value(self, value: float) -> None:
        self._apply(round(float(value), 1))
