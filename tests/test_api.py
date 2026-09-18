"""Tests for custom_components.fuxnoten.api.

Only the pure parsing helper is covered here. The network-facing
FuxNotenClient methods are exercised manually against the real portal
(see the project README) rather than mocked in CI, since the portal's
undocumented AJAX API could change at any time.
"""

import pytest

from .conftest import load_fuxnoten_module

api = load_fuxnoten_module("api")
FuxNotenError = api.FuxNotenError
_extract_ep_boot = api._extract_ep_boot


def test_extract_ep_boot_valid() -> None:
    html = (
        "<html><head>"
        '<script type="application/json" id="ep-boot">'
        '{"nonce": "abc123", "children": []}'
        "</script>"
        "</head></html>"
    )
    boot = _extract_ep_boot(html)
    assert boot == {"nonce": "abc123", "children": []}


def test_extract_ep_boot_missing_block() -> None:
    with pytest.raises(FuxNotenError, match="ep-boot block not found"):
        _extract_ep_boot("<html><head></head></html>")


def test_extract_ep_boot_invalid_json() -> None:
    html = '<script type="application/json" id="ep-boot">{not valid json</script>'
    with pytest.raises(FuxNotenError, match="not valid JSON"):
        _extract_ep_boot(html)
