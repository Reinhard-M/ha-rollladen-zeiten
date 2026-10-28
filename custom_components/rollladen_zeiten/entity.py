# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Common base class."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, docs_url
from .coordinator import RollladenZeitenCoordinator


class RollladenZeitenEntity(CoordinatorEntity[RollladenZeitenCoordinator]):
    """Base for all entities of an instance (one device per instance)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RollladenZeitenCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            # Shown as "Visit service" link on the device page -> README
            configuration_url=docs_url(coordinator.hass.config.language),
        )
