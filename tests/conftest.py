"""Shared pytest fixtures/helpers.

Importing ``custom_components.fuxnoten.<module>`` the normal way would
first execute ``custom_components/fuxnoten/__init__.py``, which imports
Home Assistant - a dependency we deliberately don't install for this
lightweight test suite (see README's "Development" section). Since the
modules under test (``api.py``, ``const.py``) have no relative imports
of their own, we can load them directly from their file path instead,
which skips the package's ``__init__.py`` entirely.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types

_FUXNOTEN_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "fuxnoten"


def load_fuxnoten_module(module_name: str) -> types.ModuleType:
    """Load a single fuxnoten module by file name, without importing the package."""
    file_path = _FUXNOTEN_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"fuxnoten_{module_name}", file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
