# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Config and options flow: name, device type, weekend days and calendars for days off.

All other settings (sun position, offset, time limits) are entities of the device.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    docs_url,
    CONF_DEVICE_TYPE,
    DEVICE_TYPES,
    TYPE_SHUTTER,
    CONF_FREE_CALENDARS,
    CONF_WEEKEND_DAYS,
    DEFAULT_WEEKEND,
    DOMAIN,
    WEEKDAYS,
)


def _free_day_fields(defaults: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_DEVICE_TYPE, default=defaults.get(CONF_DEVICE_TYPE, TYPE_SHUTTER)
        ): SelectSelector(
            SelectSelectorConfig(
                options=DEVICE_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="device_type",
            )
        ),
        vol.Required(
            CONF_WEEKEND_DAYS, default=defaults.get(CONF_WEEKEND_DAYS, DEFAULT_WEEKEND)
        ): SelectSelector(
            SelectSelectorConfig(
                options=WEEKDAYS,
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key="weekday",
            )
        ),
        vol.Optional(
            CONF_FREE_CALENDARS,
            description={"suggested_value": defaults.get(CONF_FREE_CALENDARS)},
        ): EntitySelector(EntitySelectorConfig(domain="calendar", multiple=True)),
    }


class RollladenZeitenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a new instance (possible any number of times)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = dict(user_input)
            title = options.pop(CONF_NAME).strip() or "Rollladen Zeiten"
            return self.async_create_entry(title=title, data={}, options=options)
        schema = vol.Schema({vol.Required(CONF_NAME): TextSelector(), **_free_day_fields({})})
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={"docs_url": docs_url(self.hass.config.language)},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RollladenZeitenOptionsFlow()


class RollladenZeitenOptionsFlow(OptionsFlow):
    """Change device type, weekend days and calendars afterwards."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # An empty calendar field is missing in user_input -> no calendars.
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(_free_day_fields(dict(self.config_entry.options))),
            description_placeholders={"docs_url": docs_url(self.hass.config.language)},
        )
