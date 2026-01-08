"""Preferences management for the Robust MCP Bridge workbench.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module handles reading and writing workbench preferences using
FreeCAD's parameter system.

NOTE: Using os.path instead of pathlib throughout this module due to
FreeCAD's module loading behavior which can have issues with some
Python features at load time.
"""

from __future__ import annotations

import FreeCAD

# Parameter path for our workbench preferences
PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/RobustMCPBridge"

# Default values
DEFAULT_AUTO_START = False
DEFAULT_STATUS_BAR_ENABLED = True
DEFAULT_XMLRPC_PORT = 9875
DEFAULT_SOCKET_PORT = 9876


def get_param() -> FreeCAD.ParameterGrp:
    """Get the parameter group for our preferences."""
    return FreeCAD.ParamGet(PARAM_PATH)


def get_auto_start() -> bool:
    """Get whether the bridge should auto-start when FreeCAD launches.

    Returns:
        True if bridge should auto-start, False otherwise.
        Default: False
    """
    return get_param().GetBool("AutoStart", DEFAULT_AUTO_START)


def set_auto_start(enabled: bool) -> None:
    """Set whether the bridge should auto-start when FreeCAD launches.

    Args:
        enabled: True to enable auto-start, False to disable.
    """
    get_param().SetBool("AutoStart", enabled)


def get_status_bar_enabled() -> bool:
    """Get whether the status bar indicator is enabled.

    Returns:
        True if status bar indicator should be shown, False otherwise.
        Default: True
    """
    return get_param().GetBool("StatusBarEnabled", DEFAULT_STATUS_BAR_ENABLED)


def set_status_bar_enabled(enabled: bool) -> None:
    """Set whether the status bar indicator is enabled.

    Args:
        enabled: True to show status bar indicator, False to hide.
    """
    get_param().SetBool("StatusBarEnabled", enabled)


def get_xmlrpc_port() -> int:
    """Get the XML-RPC port number.

    Returns:
        Port number for XML-RPC server.
        Default: 9875
    """
    return get_param().GetInt("XMLRPCPort", DEFAULT_XMLRPC_PORT)


def set_xmlrpc_port(port: int) -> None:
    """Set the XML-RPC port number.

    Args:
        port: Port number for XML-RPC server (1024-65535).

    Raises:
        ValueError: If port is out of valid range.
    """
    if not 1024 <= port <= 65535:
        raise ValueError(f"Port must be between 1024 and 65535, got {port}")
    get_param().SetInt("XMLRPCPort", port)


def get_socket_port() -> int:
    """Get the JSON-RPC socket port number.

    Returns:
        Port number for JSON-RPC socket server.
        Default: 9876
    """
    return get_param().GetInt("SocketPort", DEFAULT_SOCKET_PORT)


def set_socket_port(port: int) -> None:
    """Set the JSON-RPC socket port number.

    Args:
        port: Port number for JSON-RPC socket server (1024-65535).

    Raises:
        ValueError: If port is out of valid range.
    """
    if not 1024 <= port <= 65535:
        raise ValueError(f"Port must be between 1024 and 65535, got {port}")
    get_param().SetInt("SocketPort", port)


def get_all_preferences() -> dict:
    """Get all preferences as a dictionary.

    Returns:
        Dictionary with all preference values.
    """
    return {
        "auto_start": get_auto_start(),
        "status_bar_enabled": get_status_bar_enabled(),
        "xmlrpc_port": get_xmlrpc_port(),
        "socket_port": get_socket_port(),
    }


def reset_to_defaults() -> None:
    """Reset all preferences to their default values."""
    set_auto_start(DEFAULT_AUTO_START)
    set_status_bar_enabled(DEFAULT_STATUS_BAR_ENABLED)
    set_xmlrpc_port(DEFAULT_XMLRPC_PORT)
    set_socket_port(DEFAULT_SOCKET_PORT)
