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

# Register icons path for preferences page icon
# This must be done at module level, before the preferences page is registered
try:
    from path_utils import get_icons_dir

    _icons_dir = get_icons_dir()
    if _icons_dir:
        FreeCADGui.addIconPath(_icons_dir)
except Exception as e:
    FreeCAD.Console.PrintWarning(f"Could not register icon path: {e}\n")

# Register preferences page with FreeCAD's Preferences dialog
# This must be done at module level, before the workbench is registered
try:
    from preferences_page import MCPBridgePreferencesPage

    FreeCADGui.addPreferencePage(MCPBridgePreferencesPage, "Robust MCP Bridge")
except Exception as e:
    FreeCAD.Console.PrintWarning(
        f"Could not register MCP Bridge preferences page: {e}\n"
    )


class FreecadRobustMCPBridgeWorkbench(FreeCADGui.Workbench):
    """Robust MCP Bridge workbench for FreeCAD.

    Provides toolbar and menu commands to start, stop, and monitor the MCP
    bridge server for AI assistant integration.

    Attributes:
        MenuText: Workbench display name in FreeCAD.
        ToolTip: Short description shown by FreeCAD.
        Icon: Icon path used by FreeCAD.

    Example:
        The workbench is registered at import time by FreeCAD::

            FreeCADGui.addWorkbench(FreecadRobustMCPBridgeWorkbench())
    """

    MenuText = "Robust MCP Bridge"
    ToolTip = "Robust MCP Bridge for AI assistant integration with FreeCAD"

    def __init__(self) -> None:
        """Initialize workbench with icon path."""
        from path_utils import get_workbench_icon

        self.Icon = get_workbench_icon()

    def Initialize(self) -> None:
        """Initialize the workbench - called once when first activated."""
        # Import commands module here (not at top level) to ensure
        # it's available during FreeCAD's module loading process
        from commands import (
            MCPBridgePreferencesCommand,
            MCPBridgeStatusCommand,
            StartMCPBridgeCommand,
            StopMCPBridgeCommand,
        )

        # Register commands
        FreeCADGui.addCommand("Start_MCP_Bridge", StartMCPBridgeCommand())
        FreeCADGui.addCommand("Stop_MCP_Bridge", StopMCPBridgeCommand())
        FreeCADGui.addCommand("MCP_Bridge_Status", MCPBridgeStatusCommand())
        FreeCADGui.addCommand("MCP_Bridge_Preferences", MCPBridgePreferencesCommand())

        # Create toolbar with main commands
        toolbar_commands = [
            "Start_MCP_Bridge",
            "Stop_MCP_Bridge",
            "MCP_Bridge_Status",
        ]
        self.appendToolbar("Robust MCP Bridge", toolbar_commands)

        # Create menu with all commands including preferences
        menu_commands = [
            "Start_MCP_Bridge",
            "Stop_MCP_Bridge",
            "MCP_Bridge_Status",
            "Separator",
            "MCP_Bridge_Preferences",
        ]
        self.appendMenu("Robust MCP Bridge", menu_commands)

        FreeCAD.Console.PrintMessage("Robust MCP Bridge workbench initialized\n")

        # Auto-start bridge if preference is enabled
        # This is a fallback if the module-level timer didn't fire
        # (which can happen if the module isn't loaded until workbench selection)
        try:
            from preferences import get_auto_start

            if get_auto_start():
                # Check if already running (timer might have started it)
                from commands import is_bridge_running

                if not is_bridge_running():
                    FreeCAD.Console.PrintMessage(
                        "Auto-starting MCP Bridge (configured in preferences)...\n"
                    )
                    FreeCADGui.runCommand("Start_MCP_Bridge")
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not auto-start MCP Bridge: {e}\n")

        # Sync status bar widget with current bridge state
        # (bridge may have been started by Init.py before workbench was selected)
        try:
            from status_widget import sync_status_with_bridge

            sync_status_with_bridge()
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not sync status bar: {e}\n")

    def Activated(self) -> None:
        """Called when the workbench is activated."""
        # Sync status bar widget with current bridge state
        try:
            from status_widget import sync_status_with_bridge

            sync_status_with_bridge()
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not sync status bar: {e}\n")

    def Deactivated(self) -> None:
        """Called when the workbench is deactivated."""
        pass

    def GetClassName(self) -> str:
        """Return the C++ class name for this workbench."""
        return "Gui::PythonWorkbench"


# Register the workbench
FreeCADGui.addWorkbench(FreecadRobustMCPBridgeWorkbench())

# Schedule status bar sync after a short delay to allow GUI to finish initializing
# This runs on the main thread (InitGui.py is executed on main thread)
try:
    try:
        from PySide2 import QtCore
    except ImportError:
        from PySide6 import QtCore

    def _deferred_status_bar_sync() -> None:
        """Sync status bar with bridge state after GUI is ready."""
        try:
            from commands import is_bridge_running
            from preferences import get_status_bar_enabled
            from status_widget import sync_status_with_bridge

            if get_status_bar_enabled() and is_bridge_running():
                FreeCAD.Console.PrintMessage(
                    "Robust MCP Bridge: Syncing status bar from InitGui...\n"
                )
                sync_status_with_bridge()
        except Exception as e:
            FreeCAD.Console.PrintWarning(
                f"Robust MCP Bridge: Deferred status bar sync failed: {e}\n"
            )

    # Use QTimer.singleShot on the main thread - this should work
    QtCore.QTimer.singleShot(2000, _deferred_status_bar_sync)
    FreeCAD.Console.PrintMessage(
        "Robust MCP Bridge: Status bar sync scheduled from InitGui (2s)\n"
    )

    # Auto-start the MCP bridge if configured in preferences
    # This runs at FreeCAD GUI startup (InitGui.py module-level code)
    # Note: Init.py does NOT run at startup for workbench addons, so auto-start
    # must be triggered from here instead.
    def _deferred_auto_start() -> None:
        """Auto-start bridge after GUI is fully ready."""
        try:
            from preferences import get_auto_start

            if not get_auto_start():
                return

            # Check if bridge is already running
            from commands import is_bridge_running

            if is_bridge_running():
                FreeCAD.Console.PrintMessage(
                    "Robust MCP Bridge: Bridge already running, skipping auto-start\n"
                )
                return

            FreeCAD.Console.PrintMessage(
                "Robust MCP Bridge: Auto-starting from InitGui...\n"
            )

            # Import and start the bridge
            from freecad_mcp_bridge.bridge_utils import register_mcp_plugin
            from freecad_mcp_bridge.server import FreecadMCPPlugin
            from preferences import get_socket_port, get_xmlrpc_port

            xmlrpc_port = get_xmlrpc_port()
            socket_port = get_socket_port()

            plugin = FreecadMCPPlugin(
                host="localhost",
                port=socket_port,
                xmlrpc_port=xmlrpc_port,
                enable_xmlrpc=True,
            )
            plugin.start()

            # Register plugin with commands module
            register_mcp_plugin(plugin, xmlrpc_port, socket_port)

            # Sync status bar now that bridge is running
            try:
                from status_widget import sync_status_with_bridge

                sync_status_with_bridge()
            except Exception as status_err:
                FreeCAD.Console.PrintWarning(
                    f"Could not sync status bar after auto-start: {status_err}\n"
                )
        except Exception as e:
            FreeCAD.Console.PrintError(f"Robust MCP Bridge: Auto-start failed: {e}\n")
            import traceback

            FreeCAD.Console.PrintError(traceback.format_exc())

    # Schedule auto-start after a short delay to ensure GUI is fully ready
    # Use a longer delay than status bar sync to avoid race conditions
    QtCore.QTimer.singleShot(3000, _deferred_auto_start)
    FreeCAD.Console.PrintMessage(
        "Robust MCP Bridge: Auto-start scheduled from InitGui (3s)\n"
    )
except Exception as e:
    FreeCAD.Console.PrintWarning(
        f"Robust MCP Bridge: Could not schedule status bar sync: {e}\n"
    )
