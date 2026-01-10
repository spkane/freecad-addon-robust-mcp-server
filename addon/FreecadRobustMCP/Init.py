"""Robust MCP Bridge Workbench - Initialization.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module is executed when FreeCAD starts up. It handles initialization
tasks for the Robust MCP Bridge workbench, including auto-start of the
MCP bridge if configured. Works in both GUI and headless modes.

Note: Status bar updates are handled by InitGui.py since Qt operations
must run on the main thread.
"""

import FreeCAD

FreeCAD.Console.PrintMessage("Robust MCP Bridge: Init loaded\n")

# Global reference to timer to prevent garbage collection
_auto_start_timer = None


def _auto_start_bridge() -> None:
    """Auto-start the MCP bridge if configured in preferences.

    This function is called via a deferred timer (GUI mode) or directly
    (headless mode) after FreeCAD finishes loading. It starts the bridge
    without requiring the workbench to be selected.
    """
    try:
        from preferences import get_auto_start

        if not get_auto_start():
            return

        # Check if bridge is already running
        from commands import _mcp_plugin

        if _mcp_plugin is not None and _mcp_plugin.is_running:
            return

        FreeCAD.Console.PrintMessage(
            "Auto-starting MCP Bridge (configured in preferences)...\n"
        )

        # Import and start the bridge directly
        import commands
        from freecad_mcp_bridge.server import FreecadMCPPlugin
        from preferences import get_socket_port, get_xmlrpc_port

        xmlrpc_port = get_xmlrpc_port()
        socket_port = get_socket_port()

        commands._mcp_plugin = FreecadMCPPlugin(
            host="localhost",
            port=socket_port,
            xmlrpc_port=xmlrpc_port,
            enable_xmlrpc=True,
        )
        commands._mcp_plugin.start()

        # Track running configuration for restart detection
        commands._running_config = {
            "xmlrpc_port": xmlrpc_port,
            "socket_port": socket_port,
        }

        FreeCAD.Console.PrintMessage("\n")
        FreeCAD.Console.PrintMessage("=" * 50 + "\n")
        FreeCAD.Console.PrintMessage("MCP Bridge started!\n")
        FreeCAD.Console.PrintMessage(f"  - XML-RPC: localhost:{xmlrpc_port}\n")
        FreeCAD.Console.PrintMessage(f"  - Socket:  localhost:{socket_port}\n")
        FreeCAD.Console.PrintMessage("=" * 50 + "\n")
        FreeCAD.Console.PrintMessage(
            "\nYou can now connect your MCP client (Claude Code, etc.) to FreeCAD.\n"
        )

    except Exception as e:
        FreeCAD.Console.PrintError(f"Failed to auto-start MCP Bridge: {e}\n")


# Schedule auto-start after FreeCAD finishes loading
# Strategy:
# - If FreeCAD.GuiUp is True: Qt event loop is running, use timer for deferred start
# - If FreeCAD.GuiUp is False but Qt is available: Start bridge directly
#   (GUI mode starting up - InitGui.py will handle status bar later)
# - If Qt is not available: Pure headless mode, start bridge directly
try:
    from preferences import get_auto_start

    if get_auto_start():
        # Try to import Qt
        import contextlib

        QtCore = None
        try:
            from PySide2 import QtCore  # type: ignore[assignment, no-redef]
        except ImportError:
            with contextlib.suppress(ImportError):
                from PySide6 import QtCore  # type: ignore[assignment, no-redef]

        if FreeCAD.GuiUp:
            # GUI is already up - use timer for deferred start
            if QtCore is not None:
                _auto_start_timer = QtCore.QTimer()
                _auto_start_timer.setSingleShot(True)
                _auto_start_timer.timeout.connect(_auto_start_bridge)
                _auto_start_timer.start(1000)
            else:
                # GUI is up but Qt import failed - start directly
                _auto_start_bridge()
        elif QtCore is not None:
            # GUI not ready yet, but Qt is available (FreeCAD starting in GUI mode)
            # Start bridge directly - InitGui.py will handle status bar update
            _auto_start_bridge()
        else:
            # True headless mode - no Qt, no GUI
            _auto_start_bridge()
except Exception as e:
    FreeCAD.Console.PrintWarning(f"Could not set up auto-start: {e}\n")
