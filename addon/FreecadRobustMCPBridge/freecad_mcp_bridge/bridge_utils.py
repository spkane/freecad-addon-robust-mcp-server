"""Shared utilities for the FreeCAD MCP Bridge.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module provides common functionality used by both blocking_bridge.py
and startup_bridge.py to avoid code duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server import FreecadMCPPlugin


def get_running_plugin() -> FreecadMCPPlugin | None:
    """Check if an MCP bridge plugin is already running.

    This function checks if the workbench commands module has an active
    plugin instance (typically started via auto-start in Init.py).

    Returns:
        The running FreecadMCPPlugin instance if one exists and is running,
        None otherwise.

    Note:
        This function requires FreeCAD to be available in the environment.
        It will print status messages to FreeCAD.Console when a running
        plugin is found.
    """
    try:
        import FreeCAD
    except ImportError:
        return None

    try:
        # Check if the workbench commands module has a running plugin
        from commands import _mcp_plugin

        if _mcp_plugin is not None and _mcp_plugin.is_running:
            FreeCAD.Console.PrintMessage(
                "\nMCP Bridge already running (from auto-start).\n"
            )
            FreeCAD.Console.PrintMessage("  - XML-RPC: localhost:9875\n")
            FreeCAD.Console.PrintMessage("  - Socket: localhost:9876\n\n")
            return _mcp_plugin
    except ImportError:
        # Workbench commands module not available
        pass
    except AttributeError as e:
        # _mcp_plugin exists but is malformed (missing is_running, etc.)
        FreeCAD.Console.PrintWarning(f"MCP plugin state check failed: {e}\n")

    return None
