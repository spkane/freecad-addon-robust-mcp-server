"""Robust MCP Bridge Workbench - GUI Initialization.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module defines the workbench class for the Robust MCP Bridge.
It provides toolbar buttons and menu items to start and stop the
MCP bridge server. Commands are defined in the commands module.
"""

from __future__ import annotations

import FreeCAD
import FreeCADGui


class FreecadRobustMCPWorkbench(FreeCADGui.Workbench):
    """FreeCAD Robust MCP Workbench.

    Provides toolbar and menu commands to start, stop, and monitor
    the MCP bridge server for AI assistant integration.
    """

    MenuText = "Robust MCP Bridge"
    ToolTip = "Robust MCP Bridge for AI assistant integration with FreeCAD"

    def __init__(self) -> None:
        """Initialize workbench with icon path."""
        # NOTE: Using os.path instead of pathlib due to FreeCAD's module loading
        # behavior which can have issues with some Python features at load time
        import os as _os  # noqa: PTH

        icon_path = ""
        # Try versioned FreeCAD directory first (FreeCAD 1.x)
        try:
            base = FreeCAD.getUserAppDataDir()
            for item in _os.listdir(base):  # noqa: PTH208
                if item.startswith("v1-"):
                    candidate = _os.path.join(  # noqa: PTH118
                        base, item, "Mod", "FreecadRobustMCP", "FreecadRobustMCP.svg"
                    )
                    if _os.path.exists(candidate):  # noqa: PTH110
                        icon_path = candidate
                        break
        except Exception:
            pass

        # Fallback to non-versioned path
        if not icon_path:
            try:
                candidate = _os.path.join(  # noqa: PTH118
                    FreeCAD.getUserAppDataDir(),
                    "Mod",
                    "FreecadRobustMCP",
                    "FreecadRobustMCP.svg",
                )
                if _os.path.exists(candidate):  # noqa: PTH110
                    icon_path = candidate
            except Exception:
                pass

        self.Icon = icon_path

    def Initialize(self) -> None:
        """Initialize the workbench - called once when first activated."""
        # Import commands module here (not at top level) to ensure
        # it's available during FreeCAD's module loading process
        from commands import (
            MCPBridgeStatusCommand,
            StartMCPBridgeCommand,
            StopMCPBridgeCommand,
        )

        # Register commands
        FreeCADGui.addCommand("Start_MCP_Bridge", StartMCPBridgeCommand())
        FreeCADGui.addCommand("Stop_MCP_Bridge", StopMCPBridgeCommand())
        FreeCADGui.addCommand("MCP_Bridge_Status", MCPBridgeStatusCommand())

        # Create toolbar and menu
        commands = ["Start_MCP_Bridge", "Stop_MCP_Bridge", "MCP_Bridge_Status"]
        self.appendToolbar("Robust MCP Bridge", commands)
        self.appendMenu("Robust MCP Bridge", commands)

        FreeCAD.Console.PrintMessage("Robust MCP Bridge workbench initialized\n")

    def Activated(self) -> None:
        """Called when the workbench is activated."""
        pass

    def Deactivated(self) -> None:
        """Called when the workbench is deactivated."""
        pass

    def GetClassName(self) -> str:
        """Return the C++ class name for this workbench."""
        return "Gui::PythonWorkbench"


# Register the workbench
FreeCADGui.addWorkbench(FreecadRobustMCPWorkbench())
