# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Rollladen Zeiten: day/night and drive times from the sun position, can be instantiated many times."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, Platform
from datetime import timedelta

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

import logging
import os
from pathlib import Path

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

try:  # the frontend is part of every standard installation
    from homeassistant.components.frontend import add_extra_js_url
except ImportError:  # pragma: no cover
    add_extra_js_url = None

from .const import DOMAIN
from .coordinator import RollladenZeitenCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_FILE = Path(__file__).parent / "frontend" / "rollladen-zeiten-card.js"
CARD_URL = f"/{DOMAIN}/rollladen-zeiten-card.js"
CARD_KEY = f"{DOMAIN}_card_registered"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TIME,
]

type RollladenZeitenConfigEntry = ConfigEntry[RollladenZeitenCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Provide the Lovelace card (once per Home Assistant instance, not per config entry)."""
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the card as a static file and load it automatically in the frontend."""
    if hass.data.get(CARD_KEY):
        return
    http = getattr(hass, "http", None)
    if http is None or add_extra_js_url is None or "frontend" not in hass.config.components:
        _LOGGER.warning(
            "Frontend/HTTP nicht verfügbar, Lovelace-Karte wird (noch) nicht registriert"
        )
        return
    hass.data[CARD_KEY] = True
    try:
        from homeassistant.components.http import StaticPathConfig

        await http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
        )
        # modification time as version marker so browsers reload after updates
        mtime = await hass.async_add_executor_job(os.path.getmtime, CARD_FILE)
        add_extra_js_url(hass, f"{CARD_URL}?v={int(mtime)}")
    except Exception:  # noqa: BLE001 - the card is optional, the integration works without it
        hass.data.pop(CARD_KEY, None)
        _LOGGER.exception("Lovelace-Karte konnte nicht registriert werden")


async def async_setup_entry(
    hass: HomeAssistant, entry: RollladenZeitenConfigEntry
) -> bool:
    await _async_register_card(hass)  # fallback in case async_setup ran too early
    coordinator = RollladenZeitenCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # location / time zone changed in the HA settings -> recalculate
    @callback
    def _core_config_updated(_event: Event) -> None:
        hass.async_create_task(coordinator.async_refresh())

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _core_config_updated)
    )
    # entry renamed -> reload (device name)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    if coordinator.has_calendars:
        # calendar events can change during the day -> check regularly
        @callback
        def _poll_calendars(_now) -> None:
            hass.async_create_task(coordinator.async_refresh())

        entry.async_on_unload(
            async_track_time_interval(hass, _poll_calendars, timedelta(minutes=30))
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # restored settings are in place now -> recalculate once
    await coordinator.async_refresh()
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: RollladenZeitenConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: RollladenZeitenConfigEntry
) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
