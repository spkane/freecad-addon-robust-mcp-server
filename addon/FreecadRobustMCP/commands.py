"""MCP Bridge commands for the FreeCAD workbench.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module defines the GUI commands for starting, stopping, and
checking the status of the MCP bridge server.

NOTE: Using os.path instead of pathlib throughout this module due to
FreeCAD's module loading behavior which can have issues with some
Python features at load time.
"""

from __future__ import annotations

import os  # noqa: PTH
from typing import Any

import FreeCAD
import FreeCADGui  # noqa: F401 - needed for command registration

# Global reference to the plugin instance
_mcp_plugin: Any = None

# Cache for addon path
_addon_path_cache: str | None = None


def get_addon_path() -> str:
    """Get the path to this addon's directory."""
    global _addon_path_cache
    if _addon_path_cache is not None:
        return _addon_path_cache

    # Method 1: Try __file__
    try:
        _addon_path_cache = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
        return _addon_path_cache
    except NameError:
        pass

    # Method 2: Use FreeCAD's Mod path + our addon name
    try:
        mod_path = os.path.join(  # noqa: PTH118
            FreeCAD.getUserAppDataDir(), "Mod", "FreecadRobustMCP"
        )
        if os.path.exists(mod_path):  # noqa: PTH110
            _addon_path_cache = mod_path
            return _addon_path_cache
    except Exception:
        pass

    # Method 3: Try versioned FreeCAD directory (FreeCAD 1.x)
    try:
        base_path = FreeCAD.getUserAppDataDir()
        for item in os.listdir(base_path):  # noqa: PTH208
            if item.startswith("v1-"):
                versioned_mod = os.path.join(  # noqa: PTH118
                    base_path, item, "Mod", "FreecadRobustMCP"
                )
                if os.path.exists(versioned_mod):  # noqa: PTH110
                    _addon_path_cache = versioned_mod
                    return _addon_path_cache
    except Exception:
        pass

    return ""


def get_icon_path(icon_name: str) -> str:
    """Get the full path to an icon file."""
    return os.path.join(get_addon_path(), icon_name)  # noqa: PTH118


class StartMCPBridgeCommand:
    """Command to start the MCP bridge server."""

    def GetResources(self) -> dict[str, str]:
        """Return the command resources (icon, menu text, tooltip)."""
        return {
            "Pixmap": get_icon_path("FreecadRobustMCP.svg"),
            "MenuText": "Start MCP Bridge",
            "ToolTip": (
                "Start the MCP bridge server for AI assistant integration.\n"
                "Listens on XML-RPC (port 9875) and Socket (port 9876)."
            ),
        }

    def IsActive(self) -> bool:
        """Return True if the command can be executed."""
        global _mcp_plugin  # noqa: PLW0602
        return _mcp_plugin is None or not _mcp_plugin.is_running

    def Activated(self) -> None:
        """Execute the command to start the MCP bridge."""
        global _mcp_plugin

        if _mcp_plugin is not None and _mcp_plugin.is_running:
            FreeCAD.Console.PrintWarning("MCP Bridge is already running.\n")
            return

        try:
            from freecad_mcp_bridge.server import FreecadMCPPlugin

            _mcp_plugin = FreecadMCPPlugin(
                host="localhost",
                port=9876,
                xmlrpc_port=9875,
                enable_xmlrpc=True,
            )
            _mcp_plugin.start()

            FreeCAD.Console.PrintMessage("\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")
            FreeCAD.Console.PrintMessage("MCP Bridge started!\n")
            FreeCAD.Console.PrintMessage("  - XML-RPC: localhost:9875\n")
            FreeCAD.Console.PrintMessage("  - Socket:  localhost:9876\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")
            FreeCAD.Console.PrintMessage(
                "\nYou can now connect your MCP client (Claude Code, etc.) to FreeCAD.\n"
            )

        except ImportError as e:
            FreeCAD.Console.PrintError(f"Failed to import MCP Bridge module: {e}\n")
            FreeCAD.Console.PrintError(
                "Ensure the FreecadRobustMCP addon is properly installed.\n"
            )
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\n")


class StopMCPBridgeCommand:
    """Command to stop the MCP bridge server."""

    def GetResources(self) -> dict[str, str]:
        """Return the command resources (icon, menu text, tooltip)."""
        return {
            "Pixmap": get_icon_path("FreecadRobustMCP.svg"),
            "MenuText": "Stop MCP Bridge",
            "ToolTip": "Stop the running MCP bridge server.",
        }

    def IsActive(self) -> bool:
        """Return True if the command can be executed."""
        global _mcp_plugin  # noqa: PLW0602
        return _mcp_plugin is not None and _mcp_plugin.is_running

    def Activated(self) -> None:
        """Execute the command to stop the MCP bridge."""
        global _mcp_plugin

        if _mcp_plugin is None or not _mcp_plugin.is_running:
            FreeCAD.Console.PrintWarning("MCP Bridge is not running.\n")
            return

        try:
            _mcp_plugin.stop()
            _mcp_plugin = None

            FreeCAD.Console.PrintMessage("\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")
            FreeCAD.Console.PrintMessage("MCP Bridge stopped.\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")

        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to stop MCP Bridge: {e}\n")


class MCPBridgeStatusCommand:
    """Command to show MCP bridge status."""

    def GetResources(self) -> dict[str, str]:
        """Return the command resources (icon, menu text, tooltip)."""
        return {
            "Pixmap": get_icon_path("FreecadRobustMCP.svg"),
            "MenuText": "MCP Bridge Status",
            "ToolTip": "Show the current status of the MCP bridge server.",
        }

    def IsActive(self) -> bool:
        """Return True if the command can be executed."""
        return True

    def Activated(self) -> None:
        """Execute the command to show MCP bridge status."""
        global _mcp_plugin  # noqa: PLW0602

        FreeCAD.Console.PrintMessage("\n")
        FreeCAD.Console.PrintMessage("=" * 50 + "\n")
        FreeCAD.Console.PrintMessage("MCP Bridge Status\n")
        FreeCAD.Console.PrintMessage("=" * 50 + "\n")

        if _mcp_plugin is None:
            FreeCAD.Console.PrintMessage("Status: Not initialized\n")
        elif not _mcp_plugin.is_running:
            FreeCAD.Console.PrintMessage("Status: Stopped\n")
        else:
            FreeCAD.Console.PrintMessage("Status: Running\n")
            FreeCAD.Console.PrintMessage(f"  Instance ID: {_mcp_plugin.instance_id}\n")
            FreeCAD.Console.PrintMessage(f"  XML-RPC Port: {_mcp_plugin.xmlrpc_port}\n")
            FreeCAD.Console.PrintMessage(f"  Socket Port: {_mcp_plugin.socket_port}\n")
            FreeCAD.Console.PrintMessage(
                f"  Requests processed: {_mcp_plugin.request_count}\n"
            )

        FreeCAD.Console.PrintMessage("=" * 50 + "\n")
