"""Shared utilities for the FreeCAD Robust MCP Bridge.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module provides common functionality used by both blocking_bridge.py,
startup_bridge.py, and Init.py to avoid code duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    from server import FreecadMCPPlugin

# Default timing constants for GUI waiting
DEFAULT_GUI_CHECK_INTERVAL_MS: int = 100  # How often to check if GUI is ready
DEFAULT_GUI_DEFER_START_MS: int = 2000  # Delay before starting bridge after GUI ready
DEFAULT_GUI_WAIT_MAX_RETRIES: int = 600  # Max retries (600 * 100ms = 60s timeout)


class GuiWaiter:
    """Helper class to wait for FreeCAD GUI to be ready before starting the bridge.

    This class encapsulates the logic for waiting for FreeCAD.GuiUp to become True
    before invoking a callback. It uses Qt timers to poll the GUI state and defers
    the callback after the GUI is ready to allow FreeCAD to fully stabilize.

    CRITICAL: Starting the MCP bridge before FreeCAD.GuiUp is True causes the bridge
    to use a background thread for queue processing, which leads to crashes when
    executing Qt operations from that thread.

    Usage:
        waiter = GuiWaiter(
            callback=my_start_function,
            log_prefix="My Component",
        )
        waiter.start()

    The waiter will:
    1. Poll FreeCAD.GuiUp every check_interval_ms milliseconds
    2. Log progress every 5 seconds
    3. Once GuiUp is True, defer the callback by defer_ms milliseconds
    4. If timeout is reached, log an error without starting (to prevent crashes)
    """

    def __init__(
        self,
        callback: Callable[[], None],
        log_prefix: str = "Bridge",
        check_interval_ms: int = DEFAULT_GUI_CHECK_INTERVAL_MS,
        defer_ms: int = DEFAULT_GUI_DEFER_START_MS,
        max_retries: int = DEFAULT_GUI_WAIT_MAX_RETRIES,
        timeout_error_extra: str = "",
    ) -> None:
        """Initialize the GUI waiter.

        Args:
            callback: Function to call when GUI is ready (after defer delay).
            log_prefix: Prefix for log messages (e.g., "Startup Bridge").
            check_interval_ms: How often to check FreeCAD.GuiUp (milliseconds).
            defer_ms: Delay after GUI ready before calling callback (milliseconds).
            max_retries: Maximum number of check attempts before timeout.
            timeout_error_extra: Additional text to include in timeout error message.
        """
        self.callback = callback
        self.log_prefix = log_prefix
        self.check_interval_ms = check_interval_ms
        self.defer_ms = defer_ms
        self.max_retries = max_retries
        self.timeout_error_extra = timeout_error_extra

        # Timer references use Any since they could be from PySide2 or PySide6
        self._check_timer: Any | None = None
        self._defer_timer: Any | None = None
        self._retry_count: int = 0
        self._qtcore: ModuleType | None = None

    def start(self) -> None:
        """Start waiting for GUI to be ready.

        This method sets up a repeating timer that checks FreeCAD.GuiUp.
        The timer reference is stored to prevent garbage collection.
        The QtCore module is resolved once and stored for later use.
        """
        import FreeCAD

        # Resolve QtCore once and store for later use
        try:
            from PySide2 import QtCore  # type: ignore[import]
        except ImportError:
            try:
                from PySide6 import QtCore  # type: ignore[import]
            except ImportError:
                FreeCAD.Console.PrintError(
                    f"{self.log_prefix}: Neither PySide2 nor PySide6 is available. "
                    "Cannot wait for GUI - Qt is required for timer-based waiting.\n"
                )
                return

        self._qtcore = QtCore
        self._check_timer = QtCore.QTimer()
        self._check_timer.setSingleShot(False)  # Repeating timer
        self._check_timer.timeout.connect(self._check_gui)
        self._check_timer.start(self.check_interval_ms)
        FreeCAD.Console.PrintMessage(
            f"{self.log_prefix}: Waiting for GUI to be ready...\n"
        )

    def _check_gui(self) -> None:
        """Check if GUI is ready and handle the result.

        Called repeatedly by the check timer. When GUI is ready, stops the timer
        and schedules the callback with a defer delay.
        """
        import FreeCAD

        self._retry_count += 1

        # Log progress every 50 checks (5 seconds at default interval)
        if self._retry_count % 50 == 0:
            elapsed = self._retry_count * (self.check_interval_ms / 1000.0)
            FreeCAD.Console.PrintMessage(
                f"{self.log_prefix}: Still waiting for GUI... ({elapsed:.1f}s elapsed)\n"
            )

        if FreeCAD.GuiUp:
            self._on_gui_ready()
        elif self._retry_count >= self.max_retries:
            self._on_timeout()

    def _on_gui_ready(self) -> None:
        """Handle GUI becoming ready."""
        import FreeCAD

        # Stop the check timer
        if self._check_timer is not None:
            self._check_timer.stop()
            self._check_timer = None

        elapsed = self._retry_count * (self.check_interval_ms / 1000.0)
        FreeCAD.Console.PrintMessage(
            f"{self.log_prefix}: GUI ready after {elapsed:.1f}s, "
            "deferring bridge start...\n"
        )

        # IMPORTANT: Don't start the bridge immediately from this timer callback!
        # Even though GuiUp is True, FreeCAD may still be initializing internally.
        # Use a single-shot timer to defer the actual start to a later, more stable
        # point in the event loop.
        # Note: self._qtcore was resolved in start() so we don't need to re-import
        if self._qtcore is None:
            # This should never happen if start() was called, but handle gracefully
            FreeCAD.Console.PrintError(
                f"{self.log_prefix}: QtCore not initialized - start() was not called\n"
            )
            return
        self._defer_timer = self._qtcore.QTimer()
        self._defer_timer.setSingleShot(True)
        self._defer_timer.timeout.connect(self.callback)
        self._defer_timer.start(self.defer_ms)

    def _on_timeout(self) -> None:
        """Handle timeout - GUI did not become ready in time."""
        import FreeCAD

        # Stop the check timer
        if self._check_timer is not None:
            self._check_timer.stop()
            self._check_timer = None

        timeout_seconds = self.max_retries * (self.check_interval_ms / 1000.0)
        FreeCAD.Console.PrintError(
            f"\n{'=' * 60}\n"
            f"{self.log_prefix.upper()} ERROR: GUI did not become ready "
            f"within {timeout_seconds:.0f}s!\n"
            f"{'=' * 60}\n\n"
            f"The bridge was NOT started because starting with a background\n"
            f"thread would cause FreeCAD to crash when executing Qt operations.\n\n"
            f"Possible causes:\n"
            f"  - FreeCAD is running in headless mode\n"
            f"  - FreeCAD GUI initialization is extremely slow\n"
            f"  - There's an issue with the FreeCAD installation\n"
            f"{self.timeout_error_extra}"
            f"{'=' * 60}\n"
        )
        # Do NOT call callback here - it would use background thread and crash


def register_mcp_plugin(
    plugin: FreecadMCPPlugin,
    xmlrpc_port: int,
    socket_port: int,
) -> None:
    """Register an MCP plugin with the workbench commands module.

    This centralizes plugin registration so both Init.py auto-start and
    startup_bridge.py use the same logic. Registration allows the workbench
    to detect if a bridge is already running.

    Args:
        plugin: The FreecadMCPPlugin instance to register.
        xmlrpc_port: The XML-RPC port the plugin is using.
        socket_port: The JSON-RPC socket port the plugin is using.

    Note:
        If the commands module isn't available (workbench not loaded yet),
        registration silently fails. The bridge will still work but won't
        be visible to the workbench UI.
    """
    try:
        import commands

        commands._mcp_plugin = plugin
        commands._running_config = {
            "xmlrpc_port": xmlrpc_port,
            "socket_port": socket_port,
        }
    except ImportError:
        # Commands module not available (workbench not loaded yet)
        pass


def get_running_plugin() -> FreecadMCPPlugin | None:
    """Check if an MCP bridge plugin is already running.

    This function checks if the workbench commands module has an active
    plugin instance (typically started via auto-start in Init.py).

    Returns:
        The running FreecadMCPPlugin instance if one exists and is running,
        None otherwise.

    Note:
        This function requires FreeCAD to be available in the environment.
        It will print status messages to FreeCAD.Console when a running
        plugin is found.
    """
    try:
        import FreeCAD
    except ImportError:
        return None

    try:
        # Check if the workbench commands module has a running plugin
        import commands

        plugin = getattr(commands, "_mcp_plugin", None)
        if plugin is not None and plugin.is_running:
            # Get actual ports from running config, with sensible defaults
            config = getattr(commands, "_running_config", {})
            xmlrpc_port = config.get("xmlrpc_port", 9875)
            socket_port = config.get("socket_port", 9876)

            FreeCAD.Console.PrintMessage(
                "\nMCP Bridge already running (from auto-start).\n"
            )
            FreeCAD.Console.PrintMessage(f"  - XML-RPC: localhost:{xmlrpc_port}\n")
            FreeCAD.Console.PrintMessage(f"  - Socket: localhost:{socket_port}\n\n")
            return plugin
    except ImportError:
        # Workbench commands module not available
        pass
    except AttributeError as e:
        # _mcp_plugin exists but is malformed (missing is_running, etc.)
        FreeCAD.Console.PrintWarning(f"MCP plugin state check failed: {e}\n")

    return None
