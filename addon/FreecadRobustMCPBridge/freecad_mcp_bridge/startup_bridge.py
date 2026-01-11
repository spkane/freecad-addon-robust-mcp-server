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

# Global reference to timers to prevent garbage collection
_startup_timer: Any | None = None
_deferred_start_timer: Any | None = None

# Counter for GUI wait retries
_gui_wait_retries: int = 0
# Increase timeout to 60 seconds (600 retries * 100ms) - FreeCAD GUI can take
# 10-30 seconds to fully initialize on macOS, especially on first launch
_GUI_WAIT_MAX_RETRIES: int = 600


def _start_bridge() -> None:
    """Start the MCP bridge if not already running."""
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
        try:
            import commands

            commands._mcp_plugin = plugin
            commands._running_config = {
                "xmlrpc_port": xmlrpc_port,
                "socket_port": socket_port,
            }
        except ImportError:
            # Commands module not available (workbench not loaded yet)
            # The bridge will still work, but won't be visible to workbench
            pass

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
        import traceback

        FreeCAD.Console.PrintError(traceback.format_exc())


def _wait_for_gui_and_start() -> None:
    """Wait for FreeCAD GUI to be ready, then start the bridge.

    This function is called repeatedly by a timer when Qt is available but
    FreeCAD.GuiUp is not yet True. It waits for the GUI to initialize before
    starting the bridge, ensuring the bridge uses Qt timer for queue processing
    instead of a background thread.

    This prevents crashes caused by executing Qt operations from background threads.
    """
    global _startup_timer, _deferred_start_timer, _gui_wait_retries

    _gui_wait_retries += 1

    # Log progress every 50 checks (5 seconds)
    if _gui_wait_retries % 50 == 0:
        elapsed = _gui_wait_retries * 0.1
        FreeCAD.Console.PrintMessage(
            f"Startup Bridge: Still waiting for GUI... ({elapsed:.1f}s elapsed)\n"
        )

    if FreeCAD.GuiUp:
        # GUI is ready! Stop the repeating timer
        if _startup_timer is not None:
            _startup_timer.stop()
            _startup_timer = None
        elapsed = _gui_wait_retries * 0.1
        FreeCAD.Console.PrintMessage(
            f"Startup Bridge: GUI ready after {elapsed:.1f}s, "
            "deferring bridge start...\n"
        )
        # IMPORTANT: Don't start the bridge immediately from this timer callback!
        # Even though GuiUp is True, FreeCAD may still be initializing internally.
        # Use a single-shot timer to defer the actual start to a later, more stable
        # point in the event loop. This mimics the behavior of manual start via
        # toolbar buttons, which works reliably.
        try:
            from PySide2 import QtCore as DeferQtCore  # type: ignore[import]
        except ImportError:
            from PySide6 import QtCore as DeferQtCore  # type: ignore[import]
        _deferred_start_timer = DeferQtCore.QTimer()
        _deferred_start_timer.setSingleShot(True)
        _deferred_start_timer.timeout.connect(_start_bridge)
        _deferred_start_timer.start(2000)  # 2 second delay for FreeCAD to stabilize
    elif _gui_wait_retries >= _GUI_WAIT_MAX_RETRIES:
        # Timeout - DO NOT start with background thread, it will crash!
        if _startup_timer is not None:
            _startup_timer.stop()
            _startup_timer = None
        FreeCAD.Console.PrintError(
            "\n" + "=" * 60 + "\n"
            "STARTUP BRIDGE ERROR: GUI did not become ready within 60s!\n"
            "=" * 60 + "\n\n"
            "The bridge was NOT started because starting with a background\n"
            "thread would cause FreeCAD to crash when executing Qt operations.\n\n"
            "Possible causes:\n"
            "  - FreeCAD is running in headless mode (use freecadcmd instead)\n"
            "  - FreeCAD GUI initialization is extremely slow\n"
            "  - There's an issue with the FreeCAD installation\n\n"
            "To start the bridge in headless mode, use:\n"
            "  just freecad::run-headless\n"
            "=" * 60 + "\n"
        )
        # Do NOT call _start_bridge() here - it would use background thread and crash
    # Otherwise, timer will fire again and we'll check again


# Schedule bridge start after FreeCAD finishes loading
# Strategy:
# - If FreeCAD.GuiUp is True: Qt event loop is running, start bridge directly
# - If FreeCAD.GuiUp is False but Qt is available: FreeCAD GUI is initializing.
#   Use a repeating timer to wait for GuiUp to become True before starting.
#   This ensures the bridge uses Qt timer (not background thread) for queue processing.
# - If Qt is not available: Pure headless mode, start bridge directly
#
# CRITICAL: We must wait for FreeCAD.GuiUp to be True before starting the bridge
# in GUI mode. If we start when GuiUp is False, the bridge's _start_queue_processor()
# will see GuiUp=False and use a background thread. Later, code executed on that
# thread will try to do Qt operations, causing crashes (SIGABRT in QCocoaWindow).
try:
    # Try to import Qt
    QtCore = None
    try:
        from PySide2 import QtCore  # type: ignore[assignment, no-redef]
    except ImportError:
        with contextlib.suppress(ImportError):
            from PySide6 import QtCore  # type: ignore[assignment, no-redef]

    if FreeCAD.GuiUp:
        # GUI is already up - start bridge directly
        FreeCAD.Console.PrintMessage("Startup Bridge: GUI already up, starting...\n")
        _start_bridge()
    elif QtCore is not None:
        # GUI not ready yet, but Qt is available (FreeCAD starting in GUI mode)
        # Use a repeating timer to wait for GuiUp to become True
        # This prevents starting the bridge with a background thread that will
        # later crash when executing Qt operations
        _startup_timer = QtCore.QTimer()
        _startup_timer.setSingleShot(False)  # Repeating timer
        _startup_timer.timeout.connect(_wait_for_gui_and_start)
        _startup_timer.start(100)  # Check every 100ms
        FreeCAD.Console.PrintMessage("Startup Bridge: Waiting for GUI to be ready...\n")
    else:
        # True headless mode - no Qt, no GUI
        FreeCAD.Console.PrintMessage(
            "Startup Bridge: Headless mode, starting directly...\n"
        )
        _start_bridge()
except Exception as e:
    FreeCAD.Console.PrintError(f"Startup Bridge: Failed to initialize: {e}\n")
