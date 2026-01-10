"""Status bar widget for MCP Bridge status display.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module provides a permanent status widget for FreeCAD's status bar
that shows the current MCP bridge connection status without being
overwritten by other FreeCAD messages.

NOTE: All GUI operations in this module MUST be performed on the main Qt thread.
The functions in this module check for thread safety and will silently return
if called from a non-main thread to prevent crashes.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide import QtWidgets

# Global reference to the status widget (protected by _status_widget_lock)
_status_widget: MCPStatusWidget | None = None
_status_widget_lock = threading.Lock()


def _is_main_thread() -> bool:
    """Check if the current thread is the main Qt/GUI thread.

    Uses Qt's QApplication.instance().thread() to reliably detect the main thread,
    rather than relying on which thread first imports this module.

    Returns:
        True if on main thread, False otherwise.
    """
    try:
        # Try to import Qt (PySide6 first, then PySide2 as fallback)
        try:
            from PySide6 import QtCore, QtWidgets
        except ImportError:
            from PySide2 import QtCore, QtWidgets

        # Get the QApplication instance
        app = QtWidgets.QApplication.instance()
        if app is None:
            # No QApplication - can't determine main thread, assume safe
            return True

        # Check if current thread is the application's main thread
        return QtCore.QThread.currentThread() == app.thread()

    except Exception:
        # If Qt check fails, fall back to threading module check
        # This is less reliable but better than nothing
        current_thread = threading.current_thread()
        return current_thread is threading.main_thread()


def _check_main_thread(operation: str) -> bool:
    """Check if we're on the main thread and log warning if not.

    Args:
        operation: Name of the operation being attempted.

    Returns:
        True if on main thread (safe to proceed), False otherwise.
    """
    if not _is_main_thread():
        try:
            import FreeCAD

            FreeCAD.Console.PrintWarning(
                f"MCP status widget: {operation} called from non-main thread, "
                "skipping to prevent crash\n"
            )
        except Exception:
            pass
        return False
    return True


class MCPStatusWidget:
    """Manages the MCP Bridge status display in FreeCAD's status bar."""

    def __init__(self) -> None:
        """Initialize the status widget."""
        self._widget: QtWidgets.QLabel | None = None
        self._installed = False

    def install(self) -> bool:
        """Install the status widget into FreeCAD's status bar.

        Returns:
            True if successfully installed, False otherwise.

        Note:
            This method must be called from the main Qt thread.
            If called from another thread, it will return False to prevent crashes.
        """
        if self._installed:
            return True

        # Thread safety check - GUI operations must be on main thread
        if not _check_main_thread("install"):
            return False

        try:
            import FreeCADGui
            from PySide import QtWidgets  # type: ignore[import-not-found]

            # Get the main window and status bar
            main_window = FreeCADGui.getMainWindow()
            if main_window is None:
                return False

            status_bar = main_window.statusBar()
            if status_bar is None:
                return False

            # Create the status label widget
            self._widget = QtWidgets.QLabel()
            self._widget.setObjectName("mcp_bridge_status_widget")
            self._widget.setToolTip("MCP Bridge Status")

            # Style it to stand out slightly
            self._widget.setStyleSheet(
                "QLabel { padding: 2px 6px; border-radius: 3px; font-size: 11px; }"
            )

            # Add as a permanent widget (won't be hidden by temporary messages)
            status_bar.addPermanentWidget(self._widget)

            self._installed = True
            self.set_stopped()
            return True

        except Exception as e:
            import FreeCAD

            FreeCAD.Console.PrintWarning(f"Could not install MCP status widget: {e}\n")
            return False

    def remove(self) -> None:
        """Remove the status widget from the status bar.

        Note:
            This method must be called from the main Qt thread.
            If called from another thread, it will silently return.
        """
        if self._widget is None:
            return

        # Thread safety check - GUI operations must be on main thread
        if not _check_main_thread("remove"):
            return

        try:
            self._widget.setParent(None)
            self._widget.deleteLater()
        except Exception:
            pass
        self._widget = None
        self._installed = False

    def set_running(
        self, xmlrpc_port: int, socket_port: int, request_count: int = 0
    ) -> None:
        """Update the widget to show running status.

        Args:
            xmlrpc_port: The XML-RPC port number.
            socket_port: The socket port number.
            request_count: Number of requests processed this session.
        """
        if self._widget is None:
            return

        # Thread safety check
        if not _check_main_thread("set_running"):
            return

        self._widget.setText(f"MCP: Running ({xmlrpc_port}/{socket_port})")
        self._widget.setStyleSheet(
            "QLabel { "
            "background-color: #2e7d32; "
            "color: white; "
            "padding: 2px 6px; "
            "border-radius: 3px; "
            "font-size: 11px; "
            "}"
        )
        self._widget.setToolTip(
            f"MCP Bridge is running\n"
            f"XML-RPC: localhost:{xmlrpc_port}\n"
            f"Socket: localhost:{socket_port}\n"
            f"Requests processed: {request_count}"
        )

    def set_stopped(self) -> None:
        """Update the widget to show stopped status."""
        if self._widget is None:
            return

        # Thread safety check
        if not _check_main_thread("set_stopped"):
            return

        self._widget.setText("MCP: Stopped")
        self._widget.setStyleSheet(
            "QLabel { "
            "background-color: #757575; "
            "color: white; "
            "padding: 2px 6px; "
            "border-radius: 3px; "
            "font-size: 11px; "
            "}"
        )
        self._widget.setToolTip("MCP Bridge is not running")

    def set_starting(self) -> None:
        """Update the widget to show starting status."""
        if self._widget is None:
            return

        # Thread safety check
        if not _check_main_thread("set_starting"):
            return

        self._widget.setText("MCP: Starting...")
        self._widget.setStyleSheet(
            "QLabel { "
            "background-color: #f57c00; "
            "color: white; "
            "padding: 2px 6px; "
            "border-radius: 3px; "
            "font-size: 11px; "
            "}"
        )
        self._widget.setToolTip("MCP Bridge is starting...")

    def set_error(self, message: str) -> None:
        """Update the widget to show error status.

        Args:
            message: Error message to display in tooltip.
        """
        if self._widget is None:
            return

        # Thread safety check
        if not _check_main_thread("set_error"):
            return

        self._widget.setText("MCP: Error")
        self._widget.setStyleSheet(
            "QLabel { "
            "background-color: #c62828; "
            "color: white; "
            "padding: 2px 6px; "
            "border-radius: 3px; "
            "font-size: 11px; "
            "}"
        )
        self._widget.setToolTip(f"MCP Bridge Error: {message}")


def get_status_widget() -> MCPStatusWidget:
    """Get the global status widget instance, creating if needed.

    This function is thread-safe and uses double-checked locking.

    Returns:
        The MCPStatusWidget instance.
    """
    global _status_widget
    # Fast path: if already created, return it without acquiring lock
    if _status_widget is not None:
        return _status_widget

    # Slow path: acquire lock and check again before creating
    with _status_widget_lock:
        if _status_widget is None:
            _status_widget = MCPStatusWidget()
        return _status_widget


def install_status_widget() -> bool:
    """Install the status widget into the status bar.

    Returns:
        True if successfully installed.
    """
    return get_status_widget().install()


def update_status_running(
    xmlrpc_port: int, socket_port: int, request_count: int = 0
) -> None:
    """Update status widget to show running state."""
    widget = get_status_widget()
    widget.install()  # Ensure installed
    widget.set_running(xmlrpc_port, socket_port, request_count)


def update_status_stopped() -> None:
    """Update status widget to show stopped state."""
    widget = get_status_widget()
    widget.install()  # Ensure installed
    widget.set_stopped()


def update_status_starting() -> None:
    """Update status widget to show starting state."""
    widget = get_status_widget()
    widget.install()  # Ensure installed
    widget.set_starting()


def update_status_error(message: str) -> None:
    """Update status widget to show error state."""
    widget = get_status_widget()
    widget.install()  # Ensure installed
    widget.set_error(message)


def sync_status_with_bridge() -> None:
    """Sync status widget with current bridge state.

    This function checks the bridge status and updates the widget accordingly.
    Must be called from the main Qt thread.
    """
    try:
        # Thread safety check
        if not _check_main_thread("sync_status_with_bridge"):
            return

        from commands import _mcp_plugin
        from preferences import get_status_bar_enabled

        if not get_status_bar_enabled():
            return

        widget = get_status_widget()
        if not widget.install():
            return

        if _mcp_plugin is not None and _mcp_plugin.is_running:
            widget.set_running(
                _mcp_plugin.xmlrpc_port,
                _mcp_plugin.socket_port,
                _mcp_plugin.request_count,
            )
        else:
            widget.set_stopped()

    except Exception:
        pass
