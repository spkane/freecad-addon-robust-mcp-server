#!/usr/bin/env python3
"""FreeCAD Robust MCP Bridge Startup Script.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This script starts the MCP bridge in FreeCAD GUI mode. It checks if the bridge
is already running (e.g., from workbench auto-start) before starting a new
instance to avoid port conflicts.

CRITICAL: This script waits for FreeCAD.GuiUp to be True before starting the
bridge. If we start when GuiUp is False, the bridge uses a background thread
for queue processing, which causes crashes when executing Qt operations.

Usage:
    # Passed as argument to FreeCAD GUI on startup
    freecad /path/to/startup_bridge.py

    # Or on macOS:
    open -a FreeCAD.app --args /path/to/startup_bridge.py
"""

from __future__ import annotations

import contextlib
import os
import sys
import traceback
from pathlib import Path
from typing import Any

# Add the script's directory to sys.path so we can import the server module
script_dir = str(Path(__file__).resolve().parent)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Check if we're running inside FreeCAD
try:
    import FreeCAD
except ImportError:
    print("ERROR: This script must be run inside FreeCAD.")
    print("")
    print("Usage:")
    print("  freecad /path/to/startup_bridge.py")
    print("")
    print("Or on macOS:")
    print("  open -a FreeCAD.app --args /path/to/startup_bridge.py")
    sys.exit(1)

# Global reference to GuiWaiter to prevent garbage collection
_gui_waiter: Any | None = None


def _start_bridge() -> None:
    """Start the MCP bridge if not already running.

    This function checks if a bridge is already running (via get_running_plugin)
    and only starts a new bridge if none exists. It reads port configuration from
    environment variables and registers the plugin with the workbench commands
    module for visibility to other components.

    Args:
        None.

    Returns:
        None. Early returns if bridge is already running.

    Environment Variables:
        FREECAD_XMLRPC_PORT: XML-RPC port (default: 9875)
        FREECAD_SOCKET_PORT: JSON-RPC socket port (default: 9876)

    Raises:
        ValueError: If FREECAD_XMLRPC_PORT or FREECAD_SOCKET_PORT contain
            non-integer values. The exception is re-raised after logging.
        Exception: Any exception from FreecadMCPPlugin initialization or start()
            is caught, logged to FreeCAD.Console, and suppressed.

    Side Effects:
        - Creates and starts a FreecadMCPPlugin instance
        - Registers the plugin with the workbench commands module
        - Prints status messages to FreeCAD.Console

    Example:
        This function is typically called via GuiWaiter callback or directly::

            _gui_waiter = GuiWaiter(callback=_start_bridge)
            _gui_waiter.start()
    """
    # Check if bridge is already running (from auto-start in Init.py)
    from bridge_utils import get_running_plugin

    if get_running_plugin() is not None:
        FreeCAD.Console.PrintMessage(
            "MCP Bridge already running (started by workbench auto-start)\n"
        )
        return

    try:
        from server import FreecadMCPPlugin

        # Get configuration from environment variables (with defaults)
        try:
            socket_port = int(os.environ.get("FREECAD_SOCKET_PORT", "9876"))
            xmlrpc_port = int(os.environ.get("FREECAD_XMLRPC_PORT", "9875"))
        except ValueError as e:
            FreeCAD.Console.PrintError(f"Invalid port configuration: {e}\n")
            FreeCAD.Console.PrintError(
                "FREECAD_SOCKET_PORT and FREECAD_XMLRPC_PORT must be integers.\n"
            )
            raise

        plugin = FreecadMCPPlugin(
            host="localhost",
            port=socket_port,  # JSON-RPC socket port
            xmlrpc_port=xmlrpc_port,  # XML-RPC port
            enable_xmlrpc=True,
        )
        plugin.start()

        # Register plugin with commands module so Init.py auto-start can see it
        # This prevents both scripts from trying to start separate bridges
        from bridge_utils import register_mcp_plugin

        register_mcp_plugin(plugin, xmlrpc_port, socket_port)

        FreeCAD.Console.PrintMessage("\n")
        FreeCAD.Console.PrintMessage("=" * 50 + "\n")
        FreeCAD.Console.PrintMessage("MCP Bridge started (via startup script)!\n")
        FreeCAD.Console.PrintMessage(f"  - XML-RPC: localhost:{xmlrpc_port}\n")
        FreeCAD.Console.PrintMessage(f"  - Socket:  localhost:{socket_port}\n")
        FreeCAD.Console.PrintMessage(
            f"  - Mode:    {'GUI' if FreeCAD.GuiUp else 'Headless'}\n"
        )
        FreeCAD.Console.PrintMessage("=" * 50 + "\n\n")
    except Exception as e:
        FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\n")
        FreeCAD.Console.PrintError(traceback.format_exc())


# Schedule bridge start after FreeCAD finishes loading
# Strategy:
# - If FreeCAD.GuiUp is True: Qt event loop is running, start bridge directly
# - If FreeCAD.GuiUp is False but QApplication exists: FreeCAD GUI is initializing.
#   Use GuiWaiter to wait for GuiUp to become True before starting.
#   This ensures the bridge uses Qt timer (not background thread) for queue processing.
# - If no QApplication: True headless mode, start bridge directly
#
# IMPORTANT: We check for QApplication.instance() rather than just QtCore availability
# because FreeCAD bundles PySide even in headless mode (freecadcmd), but there's no
# Qt event loop running. Without a QApplication, Qt timers will never fire.
#
# CRITICAL: We must wait for FreeCAD.GuiUp to be True before starting the bridge
# in GUI mode. If we start when GuiUp is False, the bridge's _start_queue_processor()
# will see GuiUp=False and use a background thread. Later, code executed on that
# thread will try to do Qt operations, causing crashes (SIGABRT in QCocoaWindow).
try:
    # Try to import Qt and check for running QApplication
    QtCore = None
    QtWidgets = None
    _has_qapp = False
    _is_true_headless = False

    try:
        from PySide2 import QtCore, QtWidgets  # type: ignore[assignment, no-redef]
    except ImportError:
        with contextlib.suppress(ImportError):
            from PySide6 import QtCore, QtWidgets  # type: ignore[assignment, no-redef]

    # Detect GUI mode vs true headless mode
    # - True headless (freecadcmd): QCoreApplication exists but NOT QApplication
    # - GUI mode early startup: No app yet, or QApplication being initialized
    # - GUI mode ready: FreeCAD.GuiUp is True
    if QtWidgets is not None and QtCore is not None:
        qapp = QtWidgets.QApplication.instance()
        if qapp is not None:
            _has_qapp = True
        else:
            # No QApplication - check if QCoreApplication exists
            # If QCoreApplication exists but is NOT a QApplication, it's true headless
            qcore_app = QtCore.QCoreApplication.instance()
            if qcore_app is not None and not isinstance(
                qcore_app, QtWidgets.QApplication
            ):
                _is_true_headless = True
            # If no app at all, assume early GUI startup (will use GuiWaiter)

    FreeCAD.Console.PrintMessage(
        f"Startup Bridge: GuiUp={FreeCAD.GuiUp}, "
        f"QtCore={'available' if QtCore else 'unavailable'}, "
        f"QApp={'running' if _has_qapp else 'none'}, "
        f"headless={_is_true_headless}\n"
    )

    if FreeCAD.GuiUp:
        # GUI is already up - start bridge directly
        FreeCAD.Console.PrintMessage("Startup Bridge: GUI already up, starting...\n")
        _start_bridge()
    elif _is_true_headless:
        # True headless mode - QCoreApplication exists but not QApplication
        # No Qt event loop for GUI, so start bridge directly with background thread
        FreeCAD.Console.PrintMessage(
            "Startup Bridge: True headless mode (QCoreApplication only), "
            "starting directly...\n"
        )
        _start_bridge()
    elif QtCore is not None:
        # GUI not ready yet (either QApplication exists or no app yet)
        # Use GuiWaiter to wait for GuiUp to become True before starting
        # This ensures the bridge uses Qt timer (not background thread) for queue
        FreeCAD.Console.PrintMessage(
            "Startup Bridge: GUI not ready, using GuiWaiter...\n"
        )
        from bridge_utils import GuiWaiter

        _gui_waiter = GuiWaiter(
            callback=_start_bridge,
            log_prefix="Startup Bridge",
            timeout_error_extra=(
                "\nTo start the bridge in headless mode, use:\n"
                "  just freecad::run-headless\n\n"
            ),
        )
        _gui_waiter.start()
    else:
        # No Qt available at all - unusual state, start directly
        FreeCAD.Console.PrintMessage(
            "Startup Bridge: No Qt available, starting directly...\n"
        )
        _start_bridge()
except Exception as e:
    FreeCAD.Console.PrintError(f"Startup Bridge: Failed to initialize: {e}\n")
    FreeCAD.Console.PrintError(traceback.format_exc())
