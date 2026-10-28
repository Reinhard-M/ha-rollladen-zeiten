# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Choice of the sun position (preset) for morning and evening."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RollladenZeitenConfigEntry
from .const import CONF_EVENING_PRESET, CONF_MORNING_PRESET, PRESETS
from .settings_entity import SettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RollladenZeitenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [PresetSelect(c, entry, CONF_MORNING_PRESET), PresetSelect(c, entry, CONF_EVENING_PRESET)]
    )


class PresetSelect(SettingEntity, SelectEntity):
    _attr_options = PRESETS

    @property
    def current_option(self) -> str:
        return self._value

    def _parse_restored(self, state: str):
        return state if state in PRESETS else None

    async def async_select_option(self, option: str) -> None:
        self._apply(option)
