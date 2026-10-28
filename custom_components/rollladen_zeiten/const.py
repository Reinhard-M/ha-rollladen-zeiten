# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Constants for Rollladen Zeiten."""
from __future__ import annotations

DOMAIN = "rollladen_zeiten"

# Documentation (README) shown as a link in the config / options dialogs
DOCS_BASE = "https://github.com/Reinhard-M/ha-rollladen-zeiten"


def docs_url(language: str | None) -> str:
    """Return the README URL: German README for German UI, English README otherwise."""
    if language and language.lower().startswith("de"):
        return f"{DOCS_BASE}#readme"
    return f"{DOCS_BASE}/blob/main/README.en.md"

CONF_MORNING_PRESET = "morning_preset"
CONF_MORNING_OFFSET = "morning_offset"
CONF_EVENING_PRESET = "evening_preset"
CONF_EVENING_OFFSET = "evening_offset"
CONF_EARLIEST_MORNING = "earliest_morning"
CONF_LATEST_EVENING = "latest_evening"
CONF_EARLIEST_MORNING_FREE = "earliest_morning_free"  # weekend / holiday / calendar

# Options (config/options flow)
CONF_DEVICE_TYPE = "device_type"
TYPE_SHUTTER = "shutter"  # shutter/blind
TYPE_AWNING = "awning"  # awning: only different names of the time limits
DEVICE_TYPES = [TYPE_SHUTTER, TYPE_AWNING]
CONF_FREE_CALENDARS = "free_calendars"
CONF_WEEKEND_DAYS = "weekend_days"

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # index = datetime.weekday()
DEFAULT_WEEKEND = ["sat", "sun"]

PRESET_OFF = "off"  # sun position disabled: only the time limits apply
PRESETS = ["sunrise", "civil", "nautical", "astronomical", PRESET_OFF]
DEFAULT_PRESET = "sunrise"
DEFAULT_OFFSET = 0.0
# Neutral limits = no override
DEFAULT_EARLIEST = "00:00:00"
DEFAULT_LATEST = "23:59:00"

STATE_DAY = "day"
STATE_NIGHT = "night"
