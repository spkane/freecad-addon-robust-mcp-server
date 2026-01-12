"""Shared path utilities for the Robust MCP Bridge addon.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module provides centralized path-finding functions for locating
the addon directory, icons, and other resources. All path-related
logic is consolidated here to avoid duplication across modules.

NOTE: Using os.path instead of pathlib throughout this module due to
FreeCAD's module loading behavior which can have issues with some
Python features at load time.
"""

from __future__ import annotations

import os  # noqa: PTH

import FreeCAD

# Addon directory name - single source of truth for renames
_ADDON_DIRNAME = "FreecadRobustMCPBridge"

# Cache for addon path to avoid repeated filesystem lookups
_addon_path_cache: str | None = None


def get_addon_path() -> str:
    """Get the path to this addon's directory.

    Uses multiple fallback methods to locate the addon directory:
    1. __file__ if available
    2. FreeCAD's Mod path + addon name
    3. Versioned FreeCAD directory (FreeCAD 1.x: v1-*)

    Returns:
        The absolute path to the addon directory, or empty string if not found.
        Once found, the path is cached for subsequent calls.
    """
    global _addon_path_cache
    if _addon_path_cache is not None:
        return _addon_path_cache

    # Method 1: Try __file__
    try:
        _addon_path_cache = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
        return _addon_path_cache
    except NameError:
        pass

    # Method 2: Use FreeCAD's Mod path + our addon name
    try:
        mod_path = os.path.join(  # noqa: PTH118
            FreeCAD.getUserAppDataDir(), "Mod", _ADDON_DIRNAME
        )
        if os.path.exists(mod_path):  # noqa: PTH110
            _addon_path_cache = mod_path
            return _addon_path_cache
    except (OSError, PermissionError) as e:
        FreeCAD.Console.PrintWarning(f"Could not access Mod directory: {e}\n")

    # Method 3: Try versioned FreeCAD directory (FreeCAD 1.x)
    try:
        base_path = FreeCAD.getUserAppDataDir()
        for item in os.listdir(base_path):  # noqa: PTH208
            if item.startswith("v1-"):
                versioned_mod = os.path.join(  # noqa: PTH118
                    base_path, item, "Mod", _ADDON_DIRNAME
                )
                if os.path.exists(versioned_mod):  # noqa: PTH110
                    _addon_path_cache = versioned_mod
                    return _addon_path_cache
    except (OSError, PermissionError) as e:
        FreeCAD.Console.PrintWarning(f"Could not scan versioned directories: {e}\n")

    return ""


def get_icon_path(icon_name: str) -> str:
    """Get the full path to an icon file.

    Args:
        icon_name: The icon filename or relative path (e.g., "icons/mcp_start.svg")

    Returns:
        The absolute path to the icon file, or empty string if addon path not found.
    """
    addon_path = get_addon_path()
    if not addon_path:
        return ""
    return os.path.join(addon_path, icon_name)  # noqa: PTH118


def get_icons_dir() -> str:
    """Get the path to the addon's icons directory.

    Returns:
        The absolute path to the icons directory, or empty string if not found.
    """
    addon_path = get_addon_path()
    if addon_path:
        icons_dir = os.path.join(addon_path, "icons")  # noqa: PTH118
        if os.path.isdir(icons_dir):  # noqa: PTH112
            return icons_dir
    return ""


def get_workbench_icon() -> str:
    """Get the path to the workbench's main icon (FreecadRobustMCPBridge.svg).

    Returns:
        The absolute path to the workbench icon, or empty string if not found.
    """
    addon_path = get_addon_path()
    if addon_path:
        icon_path = os.path.join(addon_path, f"{_ADDON_DIRNAME}.svg")  # noqa: PTH118
        if os.path.exists(icon_path):  # noqa: PTH110
            return icon_path
    return ""
