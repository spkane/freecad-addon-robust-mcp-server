"""FreeCAD Robust MCP Workbench - GUI Initialization.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module defines the workbench class and GUI commands for the
MCP Bridge. It provides toolbar buttons and menu items to start
and stop the MCP bridge server.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import FreeCAD
import FreeCADGui
from FreeCAD import Gui

# Global reference to the plugin instance
_mcp_plugin: Any = None


def get_addon_path() -> str:
    """Get the path to this addon's directory."""
    return str(Path(__file__).resolve().parent)


def get_icon_path(icon_name: str) -> str:
    """Get the full path to an icon file.

    Args:
        icon_name: Name of the icon file (e.g., "FreecadRobustMCP.svg")

    Returns:
        Full path to the icon file.
    """
    return str(Path(get_addon_path()) / icon_name)


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
        # Can only start if not already running
        return _mcp_plugin is None or not _mcp_plugin._running

    def Activated(self) -> None:
        """Execute the command to start the MCP bridge."""
        global _mcp_plugin

        if _mcp_plugin is not None and _mcp_plugin._running:
            FreeCAD.Console.PrintWarning("MCP Bridge is already running.\n")
            return

        try:
            # Import the server module from the bundled code
            from freecad_mcp_bridge.server import FreecadMCPPlugin

            # Create and start the plugin
            _mcp_plugin = FreecadMCPPlugin(
                host="localhost",
                port=9876,  # JSON-RPC socket port
                xmlrpc_port=9875,  # XML-RPC port
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
        # Can only stop if currently running
        return _mcp_plugin is not None and _mcp_plugin._running

    def Activated(self) -> None:
        """Execute the command to stop the MCP bridge."""
        global _mcp_plugin

        if _mcp_plugin is None or not _mcp_plugin._running:
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
        # Always active - can always show status
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
        elif not _mcp_plugin._running:
            FreeCAD.Console.PrintMessage("Status: Stopped\n")
        else:
            FreeCAD.Console.PrintMessage("Status: Running\n")
            FreeCAD.Console.PrintMessage(f"  Instance ID: {_mcp_plugin._instance_id}\n")
            FreeCAD.Console.PrintMessage(
                f"  XML-RPC Port: {_mcp_plugin._xmlrpc_port}\n"
            )
            FreeCAD.Console.PrintMessage(f"  Socket Port: {_mcp_plugin._port}\n")
            FreeCAD.Console.PrintMessage(
                f"  Requests processed: {_mcp_plugin._request_count}\n"
            )

        FreeCAD.Console.PrintMessage("=" * 50 + "\n")


class FreecadRobustMCPWorkbench(Gui.Workbench):
    """FreeCAD Robust MCP Workbench.

    Provides toolbar and menu commands to start, stop, and monitor
    the MCP bridge server for AI assistant integration.
    """

    MenuText = "MCP Bridge"
    ToolTip = "MCP Bridge for AI assistant integration with FreeCAD"
    Icon = get_icon_path("FreecadRobustMCP.svg")

    def Initialize(self) -> None:
        """Initialize the workbench - called once when first activated."""
        # Register commands
        FreeCADGui.addCommand("Start_MCP_Bridge", StartMCPBridgeCommand())
        FreeCADGui.addCommand("Stop_MCP_Bridge", StopMCPBridgeCommand())
        FreeCADGui.addCommand("MCP_Bridge_Status", MCPBridgeStatusCommand())

        # Create toolbar and menu
        commands = ["Start_MCP_Bridge", "Stop_MCP_Bridge", "MCP_Bridge_Status"]
        self.appendToolbar("MCP Bridge", commands)
        self.appendMenu("MCP Bridge", commands)

        FreeCAD.Console.PrintMessage("FreeCAD Robust MCP workbench initialized\n")

    def Activated(self) -> None:
        """Called when the workbench is activated."""
        pass

    def Deactivated(self) -> None:
        """Called when the workbench is deactivated."""
        pass

    def ContextMenu(self, recipient: Any) -> None:
        """Called when right-clicking in the view or object tree."""
        pass

    def GetClassName(self) -> str:
        """Return the C++ class name for this workbench."""
        return "Gui::PythonWorkbench"


# Register the workbench
Gui.addWorkbench(FreecadRobustMCPWorkbench())
