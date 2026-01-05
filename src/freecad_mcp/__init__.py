"""FreeCAD MCP Server - AI assistant integration for FreeCAD.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This package provides an MCP (Model Context Protocol) server that enables
integration between AI assistants (Claude, GPT, etc.) and FreeCAD, allowing
AI-assisted development and debugging of 3D models, macros, and workbenches.

Example:
    Run the MCP server::

        $ freecad-mcp

    Or with Python::

        >>> from freecad_mcp.server import main
        >>> main()
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("freecad-robust-mcp")
except PackageNotFoundError:
    # Package is not installed (running from source without pip install -e)
    # Fall back to the generated _version.py if available
    try:
        from freecad_mcp._version import __version__
    except ImportError:
        __version__ = "0.0.0.dev0+unknown"

__author__ = "Sean P. Kane"
__email__ = "spkane@gmail.com"

from freecad_mcp.server import mcp

__all__ = ["__version__", "mcp"]
