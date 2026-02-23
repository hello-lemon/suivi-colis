"""Config flow for Lemon Tracker."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .api_17track import Api17TrackClient, Api17TrackError
from .const import (
    CONF_API_KEY,
    CONF_ARCHIVE_AFTER_DAYS,
    CONF_EMAIL_INTERVAL,
    CONF_IMAP_FOLDER,
    CONF_IMAP_PASSWORD,
    CONF_IMAP_PORT,
    CONF_IMAP_SERVER,
    CONF_IMAP_SSL,
    CONF_IMAP_USER,
    DEFAULT_ARCHIVE_AFTER_DAYS,
    DEFAULT_EMAIL_INTERVAL,
    DEFAULT_IMAP_FOLDER,
    DEFAULT_IMAP_PORT,
    DEFAULT_IMAP_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class LemonTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemon Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._api_key: str = ""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: 17track API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()

            # Validate API key
            try:
                async with aiohttp.ClientSession() as session:
                    client = Api17TrackClient(session, api_key)
                    await client.validate_api_key()
            except Api17TrackError:
                errors["base"] = "invalid_api_key"
            except Exception:
                errors["base"] = "cannot_connect"

            if not errors:
                self._api_key = api_key
                self._data[CONF_API_KEY] = api_key
                return await self.async_step_imap()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_imap(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: IMAP configuration (optional)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(CONF_IMAP_SERVER):
                # Skip IMAP
                return self.async_create_entry(
                    title="Lemon Tracker",
                    data=self._data,
                    options={
                        CONF_ARCHIVE_AFTER_DAYS: DEFAULT_ARCHIVE_AFTER_DAYS,
                        CONF_EMAIL_INTERVAL: DEFAULT_EMAIL_INTERVAL,
                    },
                )

            # Test IMAP connection
            from functools import partial

            from .email_parser import check_imap_connection

            server = user_input[CONF_IMAP_SERVER]
            port = user_input.get(CONF_IMAP_PORT, DEFAULT_IMAP_PORT)
            imap_user = user_input[CONF_IMAP_USER]
            password = user_input[CONF_IMAP_PASSWORD]
            ssl = user_input.get(CONF_IMAP_SSL, DEFAULT_IMAP_SSL)

            connected = await self.hass.async_add_executor_job(
                partial(check_imap_connection, server, port, imap_user, password, ssl)
            )
            if not connected:
                errors["base"] = "imap_connection_failed"
            else:
                self._data.update(
                    {
                        CONF_IMAP_SERVER: server,
                        CONF_IMAP_PORT: port,
                        CONF_IMAP_USER: imap_user,
                        CONF_IMAP_PASSWORD: password,
                        CONF_IMAP_FOLDER: user_input.get(
                            CONF_IMAP_FOLDER, DEFAULT_IMAP_FOLDER
                        ),
                        CONF_IMAP_SSL: ssl,
                    }
                )
                return self.async_create_entry(
                    title="Lemon Tracker",
                    data=self._data,
                    options={
                        CONF_ARCHIVE_AFTER_DAYS: DEFAULT_ARCHIVE_AFTER_DAYS,
                        CONF_EMAIL_INTERVAL: DEFAULT_EMAIL_INTERVAL,
                    },
                )

        return self.async_show_form(
            step_id="imap",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_IMAP_SERVER, default=""): str,
                    vol.Optional(CONF_IMAP_PORT, default=DEFAULT_IMAP_PORT): int,
                    vol.Optional(CONF_IMAP_USER, default=""): str,
                    vol.Optional(CONF_IMAP_PASSWORD, default=""): str,
                    vol.Optional(
                        CONF_IMAP_FOLDER, default=DEFAULT_IMAP_FOLDER
                    ): str,
                    vol.Optional(CONF_IMAP_SSL, default=DEFAULT_IMAP_SSL): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LemonTrackerOptionsFlow:
        """Get options flow."""
        return LemonTrackerOptionsFlow(config_entry)


class LemonTrackerOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Lemon Tracker."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ARCHIVE_AFTER_DAYS,
                        default=self.config_entry.options.get(
                            CONF_ARCHIVE_AFTER_DAYS, DEFAULT_ARCHIVE_AFTER_DAYS
                        ),
                    ): vol.All(int, vol.Range(min=0, max=30)),
                    vol.Optional(
                        CONF_EMAIL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_EMAIL_INTERVAL, DEFAULT_EMAIL_INTERVAL
                        ),
                    ): vol.All(int, vol.Range(min=5, max=120)),
                }
            ),
        )
