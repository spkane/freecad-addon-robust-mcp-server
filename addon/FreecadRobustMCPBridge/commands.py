"""MCP Bridge commands for the FreeCAD workbench.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module defines the GUI commands for starting, stopping, and
checking the status of the MCP bridge server.
"""

from __future__ import annotations

from typing import Any

import FreeCAD
from path_utils import get_addon_path, get_icon_path

# FreeCADGui is imported lazily in methods that need it, as this module
# may be imported during headless operation where FreeCADGui is not available

# Re-export for any modules that might import from commands
__all__ = ["get_addon_path", "get_icon_path"]

# Global reference to the plugin instance
_mcp_plugin: Any = None

# Track current running configuration for restart detection
_running_config: dict[str, int] | None = None


def is_bridge_running() -> bool:
    """Check if the MCP bridge is currently running.

    This is a public helper to encapsulate access to the private _mcp_plugin state.

    Returns:
        True if the bridge is running, False otherwise.
    """
    return _mcp_plugin is not None and _mcp_plugin.is_running


class StartMCPBridgeCommand:
    """Command to start the MCP bridge server."""

    def GetResources(self) -> dict[str, str]:
        """Return the command resources (icon, menu text, tooltip)."""
        # Get configured ports for tooltip (fall back to defaults if import fails)
        try:
            from preferences import get_socket_port, get_xmlrpc_port

            xmlrpc_port = get_xmlrpc_port()
            socket_port = get_socket_port()
        except Exception:
            xmlrpc_port = 9875
            socket_port = 9876

        return {
            "Pixmap": get_icon_path("icons/mcp_start.svg"),
            "MenuText": "Start MCP Bridge",
            "ToolTip": (
                "Start the MCP bridge server for AI assistant integration.\n"
                f"Listens on XML-RPC (port {xmlrpc_port}) and Socket (port {socket_port})."
            ),
        }

    def IsActive(self) -> bool:
        """Return True if the command can be executed."""
        return _mcp_plugin is None or not _mcp_plugin.is_running

    def Activated(self) -> None:
        """Execute the command to start the MCP bridge."""
        global _mcp_plugin, _running_config

        if _mcp_plugin is not None and _mcp_plugin.is_running:
            FreeCAD.Console.PrintWarning("MCP Bridge is already running.\n")
            return

        try:
            from freecad_mcp_bridge.server import FreecadMCPPlugin
            from preferences import (
                get_socket_port,
                get_status_bar_enabled,
                get_xmlrpc_port,
            )
            from status_widget import (
                update_status_error,
                update_status_running,
                update_status_starting,
            )

            # Update status bar widget if enabled
            if get_status_bar_enabled():
                update_status_starting()

            xmlrpc_port = get_xmlrpc_port()
            socket_port = get_socket_port()

            # Create plugin in a local variable first to avoid leaving
            # a partially initialized instance in _mcp_plugin if start() fails
            plugin = FreecadMCPPlugin(
                host="localhost",
                port=socket_port,
                xmlrpc_port=xmlrpc_port,
                enable_xmlrpc=True,
            )
            plugin.start()

            # Only assign to globals after start() succeeds
            _mcp_plugin = plugin
            _running_config = {
                "xmlrpc_port": xmlrpc_port,
                "socket_port": socket_port,
            }

            # Update status bar widget
            if get_status_bar_enabled():
                update_status_running(
                    xmlrpc_port, socket_port, _mcp_plugin.request_count
                )

            FreeCAD.Console.PrintMessage("\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")
            FreeCAD.Console.PrintMessage("MCP Bridge started!\n")
            FreeCAD.Console.PrintMessage(f"  - XML-RPC: localhost:{xmlrpc_port}\n")
            FreeCAD.Console.PrintMessage(f"  - Socket:  localhost:{socket_port}\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")
            FreeCAD.Console.PrintMessage(
                "\nYou can now connect your MCP client (Claude Code, etc.) to FreeCAD.\n"
            )

        except ImportError as e:
            # Clear any stale state to ensure clean retry
            _mcp_plugin = None
            _running_config = None
            FreeCAD.Console.PrintError(f"Failed to import MCP Bridge module: {e}\n")
            FreeCAD.Console.PrintError(
                "Ensure the FreecadRobustMCPBridge addon is properly installed.\n"
            )
            try:
                from preferences import get_status_bar_enabled
                from status_widget import update_status_error

                if get_status_bar_enabled():
                    update_status_error(str(e))
            except Exception:
                pass
        except Exception as e:
            # Clear any stale state to ensure clean retry
            _mcp_plugin = None
            _running_config = None
            FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\n")
            try:
                from preferences import get_status_bar_enabled
                from status_widget import update_status_error

                if get_status_bar_enabled():
                    update_status_error(str(e))
            except Exception:
                pass


class StopMCPBridgeCommand:
    """Command to stop the MCP bridge server."""

    def GetResources(self) -> dict[str, str]:
        """Return the command resources (icon, menu text, tooltip)."""
        return {
            "Pixmap": get_icon_path("icons/mcp_stop.svg"),
            "MenuText": "Stop MCP Bridge",
            "ToolTip": "Stop the running MCP bridge server.",
        }

    def IsActive(self) -> bool:
        """Return True if the command can be executed."""
        return _mcp_plugin is not None and _mcp_plugin.is_running

    def Activated(self) -> None:
        """Execute the command to stop the MCP bridge."""
        global _mcp_plugin, _running_config

        if _mcp_plugin is None or not _mcp_plugin.is_running:
            FreeCAD.Console.PrintWarning("MCP Bridge is not running.\n")
            return

        try:
            _mcp_plugin.stop()
            _mcp_plugin = None
            _running_config = None

            # Update status bar widget
            try:
                from preferences import get_status_bar_enabled
                from status_widget import update_status_stopped

                if get_status_bar_enabled():
                    update_status_stopped()
            except Exception:
                pass

            FreeCAD.Console.PrintMessage("\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")
            FreeCAD.Console.PrintMessage("MCP Bridge stopped.\n")
            FreeCAD.Console.PrintMessage("=" * 50 + "\n")

        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to stop MCP Bridge: {e}\n")


class MCPBridgeStatusCommand:
    """Command to show MCP bridge status."""

    def GetResources(self) -> dict[str, str]:
        """Return the command resources (icon, menu text, tooltip)."""
        return {
            "Pixmap": get_icon_path("icons/mcp_status.svg"),
            "MenuText": "MCP Bridge Status",
            "ToolTip": "Show the current status of the MCP bridge server.",
        }

    def IsActive(self) -> bool:
        """Return True if the command can be executed."""
        return True

    def Activated(self) -> None:
        """Execute the command to show MCP bridge status."""
        FreeCAD.Console.PrintMessage("\n")
        FreeCAD.Console.PrintMessage("=" * 50 + "\n")
        FreeCAD.Console.PrintMessage("MCP Bridge Status\n")
        FreeCAD.Console.PrintMessage("=" * 50 + "\n")

        if _mcp_plugin is None:
            FreeCAD.Console.PrintMessage("Status: Not initialized\n")
        elif not _mcp_plugin.is_running:
            FreeCAD.Console.PrintMessage("Status: Stopped\n")
        else:
            FreeCAD.Console.PrintMessage("Status: Running\n")
            FreeCAD.Console.PrintMessage(f"  Instance ID: {_mcp_plugin.instance_id}\n")
            FreeCAD.Console.PrintMessage(f"  XML-RPC Port: {_mcp_plugin.xmlrpc_port}\n")
            FreeCAD.Console.PrintMessage(f"  Socket Port: {_mcp_plugin.socket_port}\n")
            FreeCAD.Console.PrintMessage(
                f"  Requests processed: {_mcp_plugin.request_count}\n"
            )

        FreeCAD.Console.PrintMessage("=" * 50 + "\n")


def restart_bridge_if_running() -> bool:
    """Restart the bridge if it's currently running.

    Returns:
        True if bridge was restarted, False if it wasn't running.
    """
    global _mcp_plugin, _running_config

    if _mcp_plugin is None or not _mcp_plugin.is_running:
        return False

    FreeCAD.Console.PrintMessage("Restarting MCP Bridge with new configuration...\n")

    # Update status bar widget
    try:
        from preferences import get_status_bar_enabled
        from status_widget import update_status_starting

        if get_status_bar_enabled():
            update_status_starting()
    except Exception:
        pass

    # Stop the current bridge
    try:
        _mcp_plugin.stop()
        _mcp_plugin = None
        _running_config = None
    except Exception as e:
        FreeCAD.Console.PrintError(f"Failed to stop MCP Bridge: {e}\n")
        try:
            from preferences import get_status_bar_enabled
            from status_widget import update_status_error

            if get_status_bar_enabled():
                update_status_error(str(e))
        except Exception:
            pass
        return False

    # Start with new configuration
    try:
        from freecad_mcp_bridge.server import FreecadMCPPlugin
        from preferences import get_socket_port, get_status_bar_enabled, get_xmlrpc_port
        from status_widget import update_status_running

        xmlrpc_port = get_xmlrpc_port()
        socket_port = get_socket_port()

        _mcp_plugin = FreecadMCPPlugin(
            host="localhost",
            port=socket_port,
            xmlrpc_port=xmlrpc_port,
            enable_xmlrpc=True,
        )
        _mcp_plugin.start()

        _running_config = {
            "xmlrpc_port": xmlrpc_port,
            "socket_port": socket_port,
        }

        # Update status bar widget
        if get_status_bar_enabled():
            update_status_running(xmlrpc_port, socket_port, _mcp_plugin.request_count)

        FreeCAD.Console.PrintMessage("MCP Bridge restarted successfully.\n")
        FreeCAD.Console.PrintMessage(f"  - XML-RPC: localhost:{xmlrpc_port}\n")
        FreeCAD.Console.PrintMessage(f"  - Socket:  localhost:{socket_port}\n")
        return True

    except Exception as e:
        FreeCAD.Console.PrintError(f"Failed to restart MCP Bridge: {e}\n")
        try:
            from preferences import get_status_bar_enabled
            from status_widget import update_status_error

            if get_status_bar_enabled():
                update_status_error(str(e))
        except Exception:
            pass
        return False


class MCPBridgePreferencesCommand:
    """Command to open MCP bridge preferences dialog."""

    def GetResources(self) -> dict[str, str]:
        """Return the command resources (icon, menu text, tooltip)."""
        return {
            "Pixmap": get_icon_path("icons/preferences-robust_mcp_bridge.svg"),
            "MenuText": "MCP Bridge Preferences...",
            "ToolTip": "Configure MCP Bridge settings (ports, auto-start, etc.)",
        }

    def IsActive(self) -> bool:
        """Return True if the command can be executed."""
        return True

    def Activated(self) -> None:
        """Execute the command to show preferences dialog."""
        if not FreeCAD.GuiUp:
            FreeCAD.Console.PrintError(
                "MCP Bridge Preferences requires FreeCAD GUI mode.\n"
            )
            return
        # Import here to avoid issues during module loading
        import FreeCADGui
        from preferences import (
            get_auto_start,
            get_socket_port,
            get_status_bar_enabled,
            get_xmlrpc_port,
            set_auto_start,
            set_socket_port,
            set_status_bar_enabled,
            set_xmlrpc_port,
        )

        # Import QtWidgets with fallback for different PySide versions
        try:
            from PySide6 import QtWidgets
        except ImportError:
            try:
                from PySide2 import QtWidgets
            except ImportError:
                from PySide import QtWidgets  # type: ignore[import-not-found]

        # Create the dialog
        dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
        dialog.setWindowTitle("MCP Bridge Preferences")
        dialog.setMinimumWidth(400)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Startup group
        startup_group = QtWidgets.QGroupBox("Startup")
        startup_layout = QtWidgets.QVBoxLayout(startup_group)

        auto_start_cb = QtWidgets.QCheckBox("Auto-start bridge when FreeCAD launches")
        auto_start_cb.setChecked(get_auto_start())
        startup_layout.addWidget(auto_start_cb)

        layout.addWidget(startup_group)

        # Display group
        display_group = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QVBoxLayout(display_group)

        status_bar_cb = QtWidgets.QCheckBox("Show status indicator in status bar")
        status_bar_cb.setChecked(get_status_bar_enabled())
        display_layout.addWidget(status_bar_cb)

        layout.addWidget(display_group)

        # Ports group
        ports_group = QtWidgets.QGroupBox("Network Ports")
        ports_layout = QtWidgets.QFormLayout(ports_group)

        xmlrpc_spin = QtWidgets.QSpinBox()
        xmlrpc_spin.setRange(1024, 65535)
        xmlrpc_spin.setValue(get_xmlrpc_port())
        xmlrpc_spin.setToolTip("Port for XML-RPC connections (default: 9875)")
        ports_layout.addRow("XML-RPC Port:", xmlrpc_spin)

        socket_spin = QtWidgets.QSpinBox()
        socket_spin.setRange(1024, 65535)
        socket_spin.setValue(get_socket_port())
        socket_spin.setToolTip("Port for JSON-RPC socket connections (default: 9876)")
        ports_layout.addRow("Socket Port:", socket_spin)

        # Warning label for ports
        port_warning = QtWidgets.QLabel(
            "<i>Note: If the bridge is running, changing ports will restart it.</i>"
        )
        port_warning.setWordWrap(True)
        ports_layout.addRow(port_warning)

        layout.addWidget(ports_group)

        # Current status info
        status_group = QtWidgets.QGroupBox("Current Status")
        status_layout = QtWidgets.QVBoxLayout(status_group)

        if _mcp_plugin is not None and _mcp_plugin.is_running:
            status_label = QtWidgets.QLabel(
                f"<b>Bridge is running</b><br>"
                f"XML-RPC: localhost:{_mcp_plugin.xmlrpc_port}<br>"
                f"Socket: localhost:{_mcp_plugin.socket_port}"
            )
        else:
            status_label = QtWidgets.QLabel("<b>Bridge is not running</b>")
        status_layout.addWidget(status_label)

        layout.addWidget(status_group)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog (use exec() not exec_() which is deprecated in PySide6)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            # Save preferences
            old_xmlrpc = get_xmlrpc_port()
            old_socket = get_socket_port()

            set_auto_start(auto_start_cb.isChecked())
            set_status_bar_enabled(status_bar_cb.isChecked())
            set_xmlrpc_port(xmlrpc_spin.value())
            set_socket_port(socket_spin.value())

            FreeCAD.Console.PrintMessage("MCP Bridge preferences saved.\n")

            # Check if ports changed and bridge is running
            new_xmlrpc = xmlrpc_spin.value()
            new_socket = socket_spin.value()

            ports_changed = old_xmlrpc != new_xmlrpc or old_socket != new_socket
            bridge_running = _mcp_plugin is not None and _mcp_plugin.is_running
            if ports_changed and bridge_running:
                restart_bridge_if_running()
