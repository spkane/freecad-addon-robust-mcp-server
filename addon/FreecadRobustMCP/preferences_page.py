"""Preferences page for FreeCAD Preferences dialog integration.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module provides a QWidget-based preferences page that integrates
with FreeCAD's main Preferences dialog (Edit → Preferences).

NOTE: This is separate from the preferences.py module which handles
the actual preference storage. This module only handles the UI.
"""

from __future__ import annotations

from PySide import QtCore, QtWidgets  # type: ignore[import-not-found]


class MCPBridgePreferencesPage(QtWidgets.QWidget):
    """Preferences page for FreeCAD's Preferences dialog.

    This widget appears in the FreeCAD Preferences dialog sidebar
    when registered via FreeCADGui.addPreferencePage().

    Required methods:
        - loadSettings(): Load preferences into widgets
        - saveSettings(): Save widget values to preferences
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the preferences page widget."""
        super().__init__(parent)
        # Set window title - this appears in the preferences tree under the category
        self.setWindowTitle("General")
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("<h2>Robust MCP Bridge</h2>")
        layout.addWidget(title)

        description = QtWidgets.QLabel(
            "Configure the MCP Bridge for AI assistant integration with FreeCAD."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addSpacing(10)

        # Startup group
        startup_group = QtWidgets.QGroupBox("Startup")
        startup_layout = QtWidgets.QVBoxLayout(startup_group)

        self.auto_start_cb = QtWidgets.QCheckBox(
            "Auto-start bridge when FreeCAD launches"
        )
        self.auto_start_cb.setToolTip(
            "Automatically start the MCP bridge server when FreeCAD starts.\n"
            "The bridge allows AI assistants like Claude to control FreeCAD."
        )
        startup_layout.addWidget(self.auto_start_cb)

        layout.addWidget(startup_group)

        # Display group
        display_group = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QVBoxLayout(display_group)

        self.status_bar_cb = QtWidgets.QCheckBox("Show status indicator in status bar")
        self.status_bar_cb.setToolTip(
            "Display MCP bridge connection status in FreeCAD's status bar."
        )
        display_layout.addWidget(self.status_bar_cb)

        layout.addWidget(display_group)

        # Network Ports group
        ports_group = QtWidgets.QGroupBox("Network Ports")
        ports_layout = QtWidgets.QFormLayout(ports_group)

        self.xmlrpc_spin = QtWidgets.QSpinBox()
        self.xmlrpc_spin.setRange(1024, 65535)
        self.xmlrpc_spin.setToolTip(
            "Port for XML-RPC connections.\n"
            "Default: 9875\n\n"
            "The MCP server connects to this port to communicate with FreeCAD."
        )
        ports_layout.addRow("XML-RPC Port:", self.xmlrpc_spin)

        self.socket_spin = QtWidgets.QSpinBox()
        self.socket_spin.setRange(1024, 65535)
        self.socket_spin.setToolTip(
            "Port for JSON-RPC socket connections.\n"
            "Default: 9876\n\n"
            "Alternative connection method using raw sockets."
        )
        ports_layout.addRow("Socket Port:", self.socket_spin)

        # Warning about restart
        port_warning = QtWidgets.QLabel(
            "<i>Note: Changing ports requires restarting the bridge.</i>"
        )
        port_warning.setWordWrap(True)
        ports_layout.addRow(port_warning)

        layout.addWidget(ports_group)

        # Server Configuration info
        server_group = QtWidgets.QGroupBox("MCP Server Configuration")
        server_layout = QtWidgets.QVBoxLayout(server_group)

        server_intro = QtWidgets.QLabel(
            "The external MCP server (used by Claude Code, etc.) is configured "
            "separately using environment variables:"
        )
        server_intro.setWordWrap(True)
        server_layout.addWidget(server_intro)

        server_layout.addSpacing(5)

        # Environment variables as a form layout for better alignment
        env_layout = QtWidgets.QFormLayout()
        env_layout.setLabelAlignment(QtCore.Qt.AlignRight)

        env_vars = [
            ("FREECAD_XMLRPC_PORT", "XML-RPC port (default: 9875)"),
            ("FREECAD_SOCKET_PORT", "JSON-RPC socket port (default: 9876)"),
            ("FREECAD_MODE", "Connection mode: xmlrpc, socket, or embedded"),
            ("FREECAD_SOCKET_HOST", "Server hostname (default: localhost)"),
        ]

        for var_name, description in env_vars:
            var_label = QtWidgets.QLabel(f"<code>{var_name}</code>")
            var_label.setTextFormat(QtCore.Qt.RichText)
            desc_label = QtWidgets.QLabel(description)
            env_layout.addRow(var_label, desc_label)

        server_layout.addLayout(env_layout)

        server_layout.addSpacing(5)

        server_note = QtWidgets.QLabel(
            "<i>Ensure these match the ports configured above.</i>"
        )
        server_note.setTextFormat(QtCore.Qt.RichText)
        server_layout.addWidget(server_note)

        layout.addWidget(server_group)

        # Add stretch to push everything to the top
        layout.addStretch()

    def loadSettings(self) -> None:
        """Load settings from FreeCAD preferences into widgets.

        This method is called by FreeCAD when the Preferences dialog opens.
        """
        # Import here to avoid circular imports and ensure module is available
        from preferences import (
            get_auto_start,
            get_socket_port,
            get_status_bar_enabled,
            get_xmlrpc_port,
        )

        self.auto_start_cb.setChecked(get_auto_start())
        self.status_bar_cb.setChecked(get_status_bar_enabled())
        self.xmlrpc_spin.setValue(get_xmlrpc_port())
        self.socket_spin.setValue(get_socket_port())

    def saveSettings(self) -> None:
        """Save settings from widgets to FreeCAD preferences.

        This method is called by FreeCAD when OK or Apply is clicked.
        """
        from preferences import (
            get_socket_port,
            get_xmlrpc_port,
            set_auto_start,
            set_socket_port,
            set_status_bar_enabled,
            set_xmlrpc_port,
        )

        # Track if ports changed for potential restart
        old_xmlrpc = get_xmlrpc_port()
        old_socket = get_socket_port()

        # Save all preferences
        set_auto_start(self.auto_start_cb.isChecked())
        set_status_bar_enabled(self.status_bar_cb.isChecked())
        set_xmlrpc_port(self.xmlrpc_spin.value())
        set_socket_port(self.socket_spin.value())

        # Check if ports changed and notify about restart if needed
        new_xmlrpc = self.xmlrpc_spin.value()
        new_socket = self.socket_spin.value()

        if old_xmlrpc != new_xmlrpc or old_socket != new_socket:
            # Import FreeCAD here to avoid issues at module load time
            import FreeCAD

            FreeCAD.Console.PrintMessage(
                "MCP Bridge ports changed. "
                "If the bridge is running, restart it for changes to take effect.\n"
            )
