"""Thin client for the (unofficial) FuxNoten Elternportal JSON API.

Encapsulates the exact flow reverse-engineered via browser devtools:

    1. GET  /?fux-channel=beta                       -> set channel cookie
    2. GET  /elternportal?page=login                  -> session cookie + nonce
    3. POST /ajaxRequest/ajax-elternportal/?action=login
    4. GET  /elternportal?page=calendar                -> new nonce + children
    5. GET  /ajaxRequest/ajax-elternportal/?action=calendar&child_id=...
    6. POST /ajaxRequest/ajax-elternportal/?action=logout

Used as an async context manager, so login and logout are always
paired:

    async with FuxNotenClient(base_url, username, password) as client:
        children = client.children
        events = await client.async_get_events(child_id, start, end)

This class has no knowledge of Home Assistant - it is intentionally
standalone and testable on its own.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from types import TracebackType
from typing import Any, Self

import aiohttp

_LOGGER = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


class FuxNotenError(Exception):
    """Generic error while accessing the Elternportal."""


class FuxNotenAuthError(FuxNotenError):
    """Login with the configured credentials failed."""


def _extract_ep_boot(html: str) -> dict[str, Any]:
    """Extract the embedded ep-boot JSON blob from a portal page."""
    marker = '<script type="application/json" id="ep-boot">'
    start = html.find(marker)
    if start == -1:
        raise FuxNotenError("ep-boot block not found in HTML - has the portal changed?")
    start += len(marker)
    end = html.find("</script>", start)
    if end == -1:
        raise FuxNotenError("ep-boot block is not properly terminated.")
    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError as exc:
        raise FuxNotenError(f"ep-boot is not valid JSON: {exc}") from exc


class FuxNotenClient:
    """Performs exactly one login-sync-logout cycle."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._nonce: str | None = None
        self.children: list[dict[str, Any]] = []

    async def __aenter__(self) -> Self:
        self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        try:
            await self._ensure_beta_channel()
            await self._login()
            await self._load_children()
        except BaseException:
            await self._session.close()
            self._session = None
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            await self._logout()
        except FuxNotenError:
            # A failed logout should not mask the original error (if
            # any) - just log it.
            _LOGGER.warning("Logout from FuxNoten portal failed.", exc_info=True)
        finally:
            await self._session.close()
            self._session = None

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise FuxNotenError("FuxNotenClient must be used as an 'async with' context manager.")
        return self._session

    async def _ensure_beta_channel(self) -> None:
        """Set fux-channel=beta.

        Without this cookie the server routes to the legacy admin UI
        instead of the Elternportal and returns a 404 for portal
        routes.
        """
        session = self._require_session()
        async with session.get(
            self._base_url, params={"fux-channel": "beta"}, headers=_HEADERS
        ) as resp:
            resp.raise_for_status()

        if "fux-channel" not in {c.key for c in session.cookie_jar}:
            raise FuxNotenError(
                "fux-channel cookie was not set - the mechanism has probably changed."
            )

    async def _login(self) -> None:
        session = self._require_session()

        async with session.get(
            f"{self._base_url}/elternportal",
            params={"page": "login"},
            headers=_HEADERS,
        ) as resp:
            resp.raise_for_status()
            html = await resp.text()

        boot = _extract_ep_boot(html)
        login_nonce = boot.get("nonce")
        if not login_nonce:
            raise FuxNotenError("No nonce found on the login page.")

        async with session.post(
            f"{self._base_url}/ajaxRequest/ajax-elternportal/",
            params={"action": "login", "_nonce": login_nonce},
            json={"identifier": self._username, "password": self._password},
            headers=_HEADERS,
        ) as resp:
            body_text = await resp.text()

            if resp.status in (401, 403):
                raise FuxNotenAuthError("Login rejected - username or password incorrect.")
            if resp.status != 200:
                raise FuxNotenError(f"Login failed (status {resp.status}): {body_text[:200]}")

            try:
                body = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError:
                body = {}

            if body.get("success") is False:
                raise FuxNotenAuthError(
                    "Login rejected by the server (success=false) - "
                    "username or password is probably wrong."
                )

    async def _load_children(self) -> None:
        """Load the calendar page to obtain the nonce and children list.

        The calendar page is used deliberately (not the dashboard after
        login), because it returns exactly the nonce we need for the
        subsequent calendar requests.
        """
        session = self._require_session()

        async with session.get(
            f"{self._base_url}/elternportal",
            params={"page": "calendar"},
            headers=_HEADERS,
        ) as resp:
            resp.raise_for_status()
            html = await resp.text()

        boot = _extract_ep_boot(html)

        if boot.get("parent") is None:
            raise FuxNotenAuthError(
                "Calendar page does not show a logged-in user - login probably did not take effect."
            )

        self._nonce = boot.get("nonce")
        self.children = boot.get("children", [])

        if not self._nonce:
            raise FuxNotenError("No nonce found on the calendar page.")
        if not self.children:
            raise FuxNotenError("No children found in the Elternportal account.")

    async def async_get_events(self, child_id: int, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch calendar events for a child within a date range."""
        session = self._require_session()
        if self._nonce is None:
            raise FuxNotenError("No active nonce - login probably failed.")

        async with session.get(
            f"{self._base_url}/ajaxRequest/ajax-elternportal/",
            params={
                "action": "calendar",
                "_nonce": self._nonce,
                "child_id": str(child_id),
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            headers=_HEADERS,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        return data.get("events", [])

    async def _logout(self) -> None:
        session = self._require_session()
        if self._nonce is None:
            return
        async with session.post(
            f"{self._base_url}/ajaxRequest/ajax-elternportal/",
            params={"action": "logout", "_nonce": self._nonce},
            data=b"{}",
            headers={**_HEADERS, "Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                raise FuxNotenError(f"Logout failed (status {resp.status}).")
