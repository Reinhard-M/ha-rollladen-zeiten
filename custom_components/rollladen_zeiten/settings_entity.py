# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Base for the adjustable entities (select / number / time), with state restore."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import RollladenZeitenCoordinator
from .entity import RollladenZeitenEntity


class SettingEntity(RollladenZeitenEntity, RestoreEntity):
    """The value lives in the coordinator (coordinator.settings[setting_key])."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: RollladenZeitenCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._setting_key = key

    @property
    def _value(self):
        return self.coordinator.settings[self._setting_key]

    def _parse_restored(self, state: str):
        """Convert a stored state into the setting value (None = discard)."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unknown", "unavailable"):
            try:
                value = self._parse_restored(last.state)
            except (ValueError, TypeError):
                value = None
            if value is not None:
                # without recalculation; __init__ recalculates once after all platforms are loaded
                self.coordinator.set_setting(self._setting_key, value, refresh=False)

    @callback
    def _apply(self, value) -> None:
        self.coordinator.set_setting(self._setting_key, value)
        self.async_write_ha_state()
