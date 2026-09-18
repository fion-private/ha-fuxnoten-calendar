"""Tests for custom_components.fuxnoten.const.

Only the pure-Python helpers are tested here; anything that imports
Home Assistant itself is intentionally left untested in this
lightweight CI setup and should be verified against a running Home
Assistant instance instead.
"""

from .conftest import load_fuxnoten_module

const = load_fuxnoten_module("const")
build_base_url = const.build_base_url


def test_build_base_url() -> None:
    assert build_base_url("100213") == "https://100213.fuxnoten.com"


def test_build_base_url_strips_nothing_unexpected() -> None:
    # School numbers are plain numeric strings; make sure we don't
    # accidentally mangle them.
    assert build_base_url("000001") == "https://000001.fuxnoten.com"
