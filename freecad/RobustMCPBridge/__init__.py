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

import sys
from pathlib import Path

# Add the workbench directory to sys.path so the sibling modules (preferences,
# commands, freecad_mcp_bridge, etc.) can be imported by their bare names.
# FreeCAD loads this file as the namespace package freecad.RobustMCPBridge and
# only puts Mod/RobustMCPBridge on sys.path, not this directory.
_workbenchDir = str(Path(__file__).resolve().parent)
if _workbenchDir not in sys.path:
    sys.path.insert(0, _workbenchDir)

# Import FreeCAD first so we can log early
import FreeCAD  # noqa: E402

FreeCAD.Console.PrintMessage("Robust MCP Bridge: Init.py loaded\n")

from typing import TYPE_CHECKING, Any  # noqa: E402

if TYPE_CHECKING:
    from freecad_mcp_bridge.bridge_utils import GuiWaiter

try:
    from freecad_mcp_bridge.qt_compat import load_qt_core_widgets
except ImportError:
    # Repository tests import this module through freecad.RobustMCPBridge, while
    # FreeCAD installs freecad_mcp_bridge as a top-level package.
    from .freecad_mcp_bridge.qt_compat import load_qt_core_widgets

FreeCAD.Console.PrintMessage("Robust MCP Bridge: Init loaded\n")

# Global reference to GuiWaiter and auto-start timer to prevent garbage collection
# Type annotations use Any for timer since it could be QTimer from PySide6 or PySide2
_auto_start_timer: Any | None = None
_gui_waiter: GuiWaiter | None = None


def _auto_start_bridge(headless: bool = False) -> None:
    """Auto-start the MCP bridge if configured in preferences.

    This function is called via a deferred timer (GUI mode) or directly
    (headless mode) after FreeCAD finishes loading. It starts the bridge
    without requiring the workbench to be selected.

    Args:
        headless: Select the headless auto-start preference.

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
        from preferences import get_auto_start, get_auto_start_headless

        if not (get_auto_start_headless() if headless else get_auto_start()):
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
# - A console executable or a non-GUI QCoreApplication confirms headless mode
# - If mode is ambiguous, do not start a background queue
#
# IMPORTANT: We check for QApplication.instance() rather than just QtCore availability
# because FreeCAD bundles PySide even in headless mode (freecadcmd). An absent
# QApplication alone is ambiguous while GUI initialization is still in progress.
#
# CRITICAL: We must wait for FreeCAD.GuiUp to be True before starting the bridge
# in GUI mode. If we start when GuiUp is False, the bridge's _start_queue_processor()
# will see GuiUp=False and use a background thread. Later, code executed on that
# thread will try to do Qt operations, causing crashes (SIGABRT in QCocoaWindow).
# Conservative argument classification is shared with the server startup policy.
if __package__:
    try:
        from freecad_mcp_bridge.startup_policy import (
            is_batch_invocation,
            is_console_invocation,
        )
    except ImportError:
        from .freecad_mcp_bridge.startup_policy import (
            is_batch_invocation,
            is_console_invocation,
        )
else:
    from freecad_mcp_bridge.startup_policy import (
        is_batch_invocation,
        is_console_invocation,
    )


try:
    import os

    from preferences import (
        get_auto_start,
        get_auto_start_headless,
        get_auto_start_headless_batch,
    )

    # In testing mode, skip auto-start so the test controls bridge lifecycle
    # via startup_bridge.py (same guard as in init_gui.py).
    if os.environ.get("FREECAD_MCP_TESTING"):
        _autoStartEnabled = False
        FreeCAD.Console.PrintMessage(
            "Robust MCP Bridge: Auto-start skipped (FREECAD_MCP_TESTING set)\n"
        )
    else:
        _autoStartEnabled = get_auto_start() or get_auto_start_headless()
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

        with contextlib.suppress(RuntimeError):
            QtCore, QtWidgets = load_qt_core_widgets()

        # The exact console executable is a positive signal even when no Qt
        # application exists. Missing Qt or GuiUp alone are not sufficient.
        import sys

        _exe_name = sys.executable.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        _batch_run = is_batch_invocation(sys.argv[1:])
        if QtWidgets is not None and QtCore is not None:
            qcore_app = QtCore.QCoreApplication.instance()
            _has_qapp = isinstance(qcore_app, QtWidgets.QApplication)
            _is_true_headless = not _has_qapp and (
                qcore_app is not None
                or is_console_invocation(sys.executable, sys.argv[1:])
            )
        else:
            _is_true_headless = is_console_invocation(sys.executable, sys.argv[1:])
        _is_true_headless = _is_true_headless and not getattr(FreeCAD, "GuiUp", False)

        FreeCAD.Console.PrintMessage(
            f"Robust MCP Bridge: GuiUp={getattr(FreeCAD, 'GuiUp', False)}, "
            f"QtCore={'available' if QtCore else 'unavailable'}, "
            f"QApp={'running' if _has_qapp else 'none'}, "
            f"headless={_is_true_headless}, bin={_exe_name or 'unknown'}, "
            f"batch={_batch_run}\n"
        )

        if getattr(FreeCAD, "GuiUp", False) and get_auto_start():
            # GUI is already up - use timer for deferred start
            FreeCAD.Console.PrintMessage(
                "Robust MCP Bridge: GUI already up, scheduling deferred start...\n"
            )
            if QtCore is not None and QtWidgets is not None:
                _auto_start_timer = QtCore.QTimer()
                _auto_start_timer.setSingleShot(True)
                _auto_start_timer.timeout.connect(_auto_start_bridge)
                _auto_start_timer.start(1000)
            else:
                # Never start a GUI bridge without a main-thread Qt timer.
                FreeCAD.Console.PrintError(
                    "Robust MCP Bridge: GUI is ready, but a PySide binding matching "
                    "FreeCAD's Qt version could not provide QtCore and QtWidgets. "
                    "Auto-start was stopped.\n"
                )
        elif _is_true_headless:
            # Console FreeCAD, no GUI event loop.  Start the bridge for a
            # long-lived session (that is where an MCP client attaches) and use
            # a background thread for queue processing.  Short-lived batch runs
            # are skipped - they would only contend for the bridge ports.
            if not get_auto_start_headless():
                FreeCAD.Console.PrintMessage(
                    "Robust MCP Bridge: headless auto-start disabled "
                    "(AutoStartHeadless=False)\n"
                )
            elif _batch_run and not get_auto_start_headless_batch():
                FreeCAD.Console.PrintMessage(
                    "Robust MCP Bridge: batch console run (script/command given) "
                    "- skipping auto-start (set AutoStartHeadlessBatch to "
                    "enable)\n"
                )
            else:
                FreeCAD.Console.PrintMessage(
                    "Robust MCP Bridge: True headless mode (console FreeCAD), "
                    "starting directly...\n"
                )
                _auto_start_bridge(headless=True)
        elif not get_auto_start():
            FreeCAD.Console.PrintMessage("Robust MCP Bridge: GUI auto-start disabled\n")
        elif QtCore is not None and QtWidgets is not None:
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
            # Without Qt, GuiUp=False cannot distinguish early GUI startup
            # from a genuinely headless process. Refuse the ambiguous path.
            FreeCAD.Console.PrintError(
                "Robust MCP Bridge: No Qt binding is available and headless "
                "mode could not be confirmed. Auto-start was stopped.\n"
            )
except Exception as e:
    FreeCAD.Console.PrintWarning(f"Could not set up auto-start: {e}\n")
    import traceback

    FreeCAD.Console.PrintWarning(f"Traceback: {traceback.format_exc()}\n")


def _release_startup_timers() -> None:
    """Release only bridge-owned timers on their owning Qt thread."""
    import contextlib

    try:
        from freecad_mcp_bridge.qt_compat import load_qt_core
        from freecad_mcp_bridge.server import _get_shiboken_delete

        qtcore = load_qt_core()
        delete = _get_shiboken_delete()
    except (ImportError, RuntimeError):
        return

    def release(timer: Any) -> bool:
        if timer is None:
            return True
        try:
            if timer.thread() != qtcore.QThread.currentThread():
                return False
            timer.stop()
            with contextlib.suppress(RuntimeError, TypeError):
                timer.timeout.disconnect()
            if delete is not None:
                delete(timer)
            return True
        except RuntimeError:
            # A previously destroyed Qt object has nothing left to release.
            return True

    timer = globals().get("_auto_start_timer")
    if release(timer):
        globals()["_auto_start_timer"] = None
    waiter = globals().get("_gui_waiter")
    if waiter is not None:
        for name in ("_check_timer", "_defer_timer"):
            if release(getattr(waiter, name)):
                setattr(waiter, name, None)


# Prefer Qt's shutdown signal while the owner thread and objects still exist.
# The atexit fallback only touches timers whose thread matches the current one.
try:
    import atexit

    atexit.register(_release_startup_timers)
    if QtCore is not None:
        _application = QtCore.QCoreApplication.instance()
        if _application is not None:
            _application.aboutToQuit.connect(_release_startup_timers)
except (NameError, AttributeError, RuntimeError):
    pass
