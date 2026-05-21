"""Config flow for OpenLitter — zeroconf discovery + manual entry."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import aiohttp_client

from .api import OpenLitterApi, OpenLitterApiError
from .const import (
    CONF_MQTT_TOPIC_BASE,
    CONF_OTA_PASSWORD,
    CONF_USE_MQTT,
    DEFAULT_MQTT_TOPIC_BASE,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "openlitter.local")): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(CONF_OTA_PASSWORD, default=d.get(CONF_OTA_PASSWORD, "")): str,
            vol.Optional(CONF_USE_MQTT, default=d.get(CONF_USE_MQTT, False)): bool,
            vol.Optional(
                CONF_MQTT_TOPIC_BASE,
                default=d.get(CONF_MQTT_TOPIC_BASE, DEFAULT_MQTT_TOPIC_BASE),
            ): str,
        }
    )


class OpenLitterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenLitter."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}

    # --- Manual entry -----------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = user_input[CONF_HOST].lower()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates=user_input)
            try:
                info = await self._validate(user_input)
            except OpenLitterApiError as err:
                _LOGGER.warning("Validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                title = info.get("network", {}).get("hostname") or user_input[CONF_HOST]
                return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self._discovered or user_input or None),
            errors=errors,
        )

    # --- Zeroconf discovery -----------------------------------------

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        host = (
            discovery_info.hostname.removesuffix(".")
            if discovery_info.hostname
            else str(discovery_info.ip_address)
        )
        port = discovery_info.port or DEFAULT_PORT
        unique_id = host.lower()
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
        self._discovered = {CONF_HOST: host, CONF_PORT: port}
        self.context["title_placeholders"] = {"name": host}
        return await self.async_step_user()

    # --- helpers -----------------------------------------------------

    async def _validate(self, data: dict[str, Any]) -> dict[str, Any]:
        session = aiohttp_client.async_get_clientsession(self.hass)
        api = OpenLitterApi(session, data[CONF_HOST], data[CONF_PORT])
        return await api.get_status()
