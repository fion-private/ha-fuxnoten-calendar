"""Config flow for the FuxNoten Elternportal integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .api import FuxNotenAuthError, FuxNotenClient, FuxNotenError
from .const import (
    CONF_CHILD_ID,
    CONF_CHILD_NAME,
    CONF_PASSWORD,
    CONF_SCHOOL_NUMBER,
    CONF_SYNC_TIME,
    CONF_TARGET_CALENDAR,
    CONF_USERNAME,
    DEFAULT_SYNC_TIME,
    DOMAIN,
    build_base_url,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHOOL_NUMBER): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


# The `domain=` keyword argument is a Home Assistant class-creation idiom
# (see config_entries.ConfigFlow.__init_subclass__) that mypy can only
# understand with Home Assistant's own type stubs installed, which this
# lightweight lint setup deliberately does not install (see README).
class FuxNotenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Config flow: 1) test credentials, 2) pick child, calendar and sync time."""

    VERSION = 1

    def __init__(self) -> None:
        self._school_number: str | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._children: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            school_number = user_input[CONF_SCHOOL_NUMBER].strip()
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            base_url = build_base_url(school_number)

            try:
                async with FuxNotenClient(base_url, username, password) as client:
                    children = client.children
            except FuxNotenAuthError:
                errors["base"] = "invalid_auth"
            except (FuxNotenError, aiohttp.ClientError, TimeoutError):
                _LOGGER.exception("Connection test to the FuxNoten portal failed")
                errors["base"] = "cannot_connect"
            else:
                self._school_number = school_number
                self._username = username
                self._password = password
                self._children = children
                return await self.async_step_select_options()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_select_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        child_options = [
            selector.SelectOptionDict(
                value=str(child["id"]),
                label=f"{child['firstname']} {child['lastname']}".strip(),
            )
            for child in self._children
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHILD_ID, default=child_options[0]["value"]
                ): selector.SelectSelector(selector.SelectSelectorConfig(options=child_options)),
                vol.Required(CONF_TARGET_CALENDAR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="calendar")
                ),
                vol.Required(CONF_SYNC_TIME, default=DEFAULT_SYNC_TIME): selector.TimeSelector(),
            }
        )

        if user_input is not None:
            child_id = int(user_input[CONF_CHILD_ID])
            child = next(c for c in self._children if c["id"] == child_id)
            child_name = f"{child['firstname']} {child['lastname']}".strip()

            await self.async_set_unique_id(f"{self._school_number}:{self._username}:{child_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"FuxNoten – {child_name}",
                data={
                    CONF_SCHOOL_NUMBER: self._school_number,
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_CHILD_ID: child_id,
                    CONF_CHILD_NAME: child_name,
                    CONF_TARGET_CALENDAR: user_input[CONF_TARGET_CALENDAR],
                    CONF_SYNC_TIME: user_input[CONF_SYNC_TIME],
                },
            )

        return self.async_show_form(step_id="select_options", data_schema=schema, errors=errors)
