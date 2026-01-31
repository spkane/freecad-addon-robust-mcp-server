"""Qt/PySide UI components for the Robust MCP Bridge workbench.

This module contains Qt-based user interface components:
- status_widget: Status bar widget showing bridge connection state
- preferences_page: Preferences dialog for configuring the bridge
"""

from .preferences_page import MCPBridgePreferencesPage
from .status_widget import MCPStatusWidget

__all__ = [
    "MCPBridgePreferencesPage",
    "MCPStatusWidget",
]
