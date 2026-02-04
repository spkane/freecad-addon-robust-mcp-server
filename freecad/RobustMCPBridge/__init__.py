"""Robust MCP Bridge Workbench - Initialization.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module is executed when FreeCAD starts up. It handles initialization
tasks for the Robust MCP Bridge workbench, including auto-start of the
MCP bridge if configured. Works in both GUI and headless modes.

Note: Status bar updates are handled by InitGui.py since Qt operations
must run on the main thread.
"""

from __future__ import annotations

# Import FreeCAD first so we can log early
import FreeCAD

FreeCAD.Console.PrintMessage("Robust MCP Bridge: Init.py loaded\n")

from typing import TYPE_CHECKING, Any  # noqa: E402

if TYPE_CHECKING:
    from freecad_mcp_bridge.bridge_utils import GuiWaiter

FreeCAD.Console.PrintMessage("Robust MCP Bridge: Init loaded\n")

# Global reference to GuiWaiter and auto-start timer to prevent garbage collection
# Type annotations use Any for timer since it could be QTimer from PySide2 or PySide6
_auto_start_timer: Any | None = None
_gui_waiter: GuiWaiter | None = None


def _auto_start_bridge() -> None:
    """Auto-start the MCP bridge if configured in preferences.

    This function is called via a deferred timer (GUI mode) or directly
    (headless mode) after FreeCAD finishes loading. It starts the bridge
    without requiring the workbench to be selected.

    Args:
        None.

    Returns:
        None. Early returns if auto-start is disabled or bridge is already running.

    Raises:
        Exception: Any exception during bridge startup is caught, logged to
            FreeCAD.Console.PrintError with full traceback, and suppressed.

    Side Effects:
        - Imports and checks auto-start preference from preferences module
        - Creates and starts a FreecadMCPPlugin instance if not already running
        - Registers the plugin with the workbench commands module
        - Prints status messages to FreeCAD.Console

    Example:
        This function is typically called via QTimer or GuiWaiter callback::

            QtCore.QTimer.singleShot(1000, _auto_start_bridge)
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

        # Register plugin with commands module for restart detection
        from freecad_mcp_bridge.bridge_utils import register_mcp_plugin

        register_mcp_plugin(plugin, xmlrpc_port, socket_port)

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
        import traceback

        FreeCAD.Console.PrintError(f"Traceback: {traceback.format_exc()}\n")


# Schedule auto-start after FreeCAD finishes loading
# Strategy:
# - If FreeCAD.GuiUp is True: Qt event loop is running, use timer for deferred start
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
    import os

    from preferences import get_auto_start

    # In testing mode, skip auto-start so the test controls bridge lifecycle
    # via startup_bridge.py (same guard as in init_gui.py).
    if os.environ.get("FREECAD_MCP_TESTING"):
        _autoStartEnabled = False
        FreeCAD.Console.PrintMessage(
            "Robust MCP Bridge: Auto-start skipped (FREECAD_MCP_TESTING set)\n"
        )
    else:
        _autoStartEnabled = get_auto_start()
    FreeCAD.Console.PrintMessage(
        f"Robust MCP Bridge: Auto-start preference = {_autoStartEnabled}\n"
    )

    if _autoStartEnabled:
        # Try to import Qt and check for running QApplication
        import contextlib

        QtCore = None
        QtWidgets = None
        _has_qapp = False
        _is_true_headless = False

        try:
            from PySide2 import QtCore, QtWidgets  # type: ignore[assignment, no-redef]
        except ImportError:
            with contextlib.suppress(ImportError):
                from PySide6 import (  # type: ignore[assignment, no-redef]
                    QtCore,
                    QtWidgets,
                )

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
            f"Robust MCP Bridge: GuiUp={FreeCAD.GuiUp}, "
            f"QtCore={'available' if QtCore else 'unavailable'}, "
            f"QApp={'running' if _has_qapp else 'none'}, "
            f"headless={_is_true_headless}\n"
        )

        if FreeCAD.GuiUp:
            # GUI is already up - use timer for deferred start
            FreeCAD.Console.PrintMessage(
                "Robust MCP Bridge: GUI already up, scheduling deferred start...\n"
            )
            if QtCore is not None:
                _auto_start_timer = QtCore.QTimer()
                _auto_start_timer.setSingleShot(True)
                _auto_start_timer.timeout.connect(_auto_start_bridge)
                _auto_start_timer.start(1000)
            else:
                # GUI is up but Qt import failed - start directly
                _auto_start_bridge()
        elif _is_true_headless:
            # True headless mode - QCoreApplication exists but not QApplication
            # No Qt event loop for GUI, so start bridge directly with background thread
            FreeCAD.Console.PrintMessage(
                "Robust MCP Bridge: True headless mode (QCoreApplication only), "
                "starting directly...\n"
            )
            _auto_start_bridge()
        elif QtCore is not None:
            # GUI not ready yet (either QApplication exists or no app yet)
            # Use GuiWaiter to wait for GuiUp to become True before starting
            # This ensures the bridge uses Qt timer (not background thread) for queue
            FreeCAD.Console.PrintMessage(
                "Robust MCP Bridge: GUI not ready, using GuiWaiter...\n"
            )
            from freecad_mcp_bridge.bridge_utils import GuiWaiter

            _gui_waiter = GuiWaiter(
                callback=_auto_start_bridge,
                log_prefix="Robust MCP Bridge",
                timeout_error_extra=(
                    "\nTo start the bridge manually, select the Robust MCP Bridge "
                    "workbench\nand click 'Start MCP Bridge'.\n\n"
                ),
            )
            _gui_waiter.start()
        else:
            # No Qt available at all - unusual state, start directly
            FreeCAD.Console.PrintMessage(
                "Robust MCP Bridge: No Qt available, starting directly...\n"
            )
            _auto_start_bridge()
except Exception as e:
    FreeCAD.Console.PrintWarning(f"Could not set up auto-start: {e}\n")
    import traceback

    FreeCAD.Console.PrintWarning(f"Traceback: {traceback.format_exc()}\n")
