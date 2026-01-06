"""FreeCAD MCP Bridge - Bundled server module for the workbench addon.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This module provides the MCP bridge server that runs inside FreeCAD.
It is bundled with the workbench addon for self-contained installation.
"""

from .server import FreecadMCPPlugin

__all__ = ["FreecadMCPPlugin"]
