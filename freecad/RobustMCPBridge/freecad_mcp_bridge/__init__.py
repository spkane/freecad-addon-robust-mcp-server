"""FreeCAD Robust MCP Bridge - Bundled server module for the workbench addon.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module provides the MCP bridge server that runs inside FreeCAD.
It is bundled with the workbench addon for self-contained installation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .server import FreecadMCPPlugin

__version__ = "0.6.2"  # Updated by release workflow
__all__ = ["FreecadMCPPlugin", "__version__"]


def __getattr__(name: str) -> Any:
    """Lazily expose the bridge plugin without loading the server for utilities."""
    if name == "FreecadMCPPlugin":
        from .server import FreecadMCPPlugin

        return FreecadMCPPlugin
    raise AttributeError(name)
