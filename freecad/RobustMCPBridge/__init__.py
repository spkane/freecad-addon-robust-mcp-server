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
        # - True headless (freecadcmd): console binary, can never bring a GUI up
        # - GUI mode early startup: No app yet, or QApplication being initialized
        # - GUI mode ready: FreeCAD.GuiUp is True
        #
        # Earlier revisions assumed "QCoreApplication exists but is not a
        # QApplication" meant true headless.  That is never true in freecadcmd
        # (there is no Qt application object at all there), so console FreeCAD
        # wrongly took the GUI-wait branch: it waited for a GUI that never
        # appears, and the orphan QTimer it created segfaulted FreeCAD on exit.
        # The console and GUI entry points are distinct executables, so ask the
        # running binary instead (override with FREECAD_MCP_HEADLESS=0/1).
        import os
        import sys

        _console_override = os.environ.get("FREECAD_MCP_HEADLESS")
        _exe_name = os.path.basename(sys.executable or "") or os.path.basename(
            sys.argv[0] or ""
        )
        if _console_override is not None:
            _is_console = _console_override.strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        else:
            _is_console = "cmd" in _exe_name.lower()

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
                elif qcore_app is None and _is_console:
                    # Console FreeCAD with no Qt application at all: no event
                    # loop will ever run here, so start the bridge right away.
                    _is_true_headless = True
                # Otherwise: no app yet, but this is the GUI binary - early GUI
                # startup. InitGui.py schedules the auto-start, so nothing to do.

        FreeCAD.Console.PrintMessage(
            f"Robust MCP Bridge: GuiUp={getattr(FreeCAD, 'GuiUp', False)}, "
            f"QtCore={'available' if QtCore else 'unavailable'}, "
            f"QApp={'running' if _has_qapp else 'none'}, "
            f"headless={_is_true_headless}, bin={_exe_name or 'unknown'}\n"
        )

        if getattr(FreeCAD, "GuiUp", False):
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
            # True headless mode - console FreeCAD, no GUI event loop. Start the
            # bridge directly; it uses a background thread for queue processing.
            FreeCAD.Console.PrintMessage(
                "Robust MCP Bridge: True headless mode (console FreeCAD), "
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


# ---------------------------------------------------------------------------
# LOCAL PATCH (Luminova, 2026-09-22): release the startup timers before the
# interpreter is finalized.
#
# WHY.  FreeCAD segfaulted on every close.  Crash signature (macOS .ips):
#     App::Application::destruct -> InterpreterSingleton::finalize
#       -> Py_FinalizeEx -> finalize_modules -> gc_collect_main
#       -> PySide::onPysideReceiverSlotDestroyed -> QObject::disconnect
#       -> QTimerWrapper::disconnectNotify -> Sbk_GetPyOverride
#       -> _PyType_Lookup on a freed type object  (EXC_BAD_ACCESS at 0x10)
# i.e. a Python-held QTimer wrapper was garbage-collected while the interpreter
# was already tearing down.  The timer is now prevented at the source
# (bridge_utils.GuiWaiter.start no longer creates a timer when no Qt event loop
# exists); this handler is the backstop for any timer this module does start.
# atexit handlers run inside Py_FinalizeEx *before* finalize_modules, i.e.
# before the crash, so releasing them here is early enough.
#
# REMOVAL.  Self-contained block at the end of the file (nothing above
# references it): delete from this marker to the end of file.  An upstream
# update will overwrite this file -- re-apply, or send it upstream.
# ---------------------------------------------------------------------------
def _luminova_release_startup_timers() -> None:
    import gc

    try:
        from freecad_mcp_bridge.server import _get_shiboken_delete

        sbk_delete = _get_shiboken_delete()
    except Exception:
        sbk_delete = None

    def _release(timer) -> None:
        if timer is None:
            return
        for step in (
            lambda: timer.stop(),
            lambda: timer.timeout.disconnect(),
        ):
            try:
                step()
            except Exception:
                pass
        if sbk_delete is not None:
            try:
                sbk_delete(timer)
            except Exception:
                pass

    _release(globals().get("_auto_start_timer"))

    waiter = globals().get("_gui_waiter")
    if waiter is not None:
        _release(getattr(waiter, "_check_timer", None))
        _release(getattr(waiter, "_defer_timer", None))
        for attr in ("_check_timer", "_defer_timer"):
            try:
                setattr(waiter, attr, None)
            except Exception:
                pass

    globals()["_auto_start_timer"] = None

    # Backstop sweep: release any other Python-owned QTimer still alive, so a
    # future code path cannot reintroduce this crash.
    try:
        from PySide2 import QtCore as _QtCore  # type: ignore[import]
    except ImportError:
        try:
            from PySide6 import QtCore as _QtCore  # type: ignore[import]
        except ImportError:
            return

    try:
        surviving = [o for o in gc.get_objects() if isinstance(o, _QtCore.QTimer)]
    except Exception:
        return
    for timer in surviving:
        _release(timer)


try:
    import atexit as _luminova_atexit

    _luminova_atexit.register(_luminova_release_startup_timers)
except Exception:
    pass
