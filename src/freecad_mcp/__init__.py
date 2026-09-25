"""FreeCAD Robust MCP Server - AI assistant integration for FreeCAD.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This package provides an MCP (Model Context Protocol) server that enables
integration between AI assistants (Claude, GPT, etc.) and FreeCAD, allowing
AI-assisted development and debugging of 3D models, macros, and workbenches.

Example:
    Run the Robust MCP Server::

        $ freecad-mcp

    Or with Python::

        >>> from freecad_mcp.server import main
        >>> main()
"""

from importlib.metadata import PackageNotFoundError, version

__version__: str
try:
    __version__ = version("freecad-robust-mcp")
except PackageNotFoundError:
    # Package is not installed (running from source without pip install -e)
    # Fall back to the generated _version.py if available
    try:
        from freecad_mcp._version import __version__ as _v

        __version__ = _v
    except ImportError:
        __version__ = "0.0.0.dev0+unknown"

__author__ = "Sean P. Kane"
__email__ = "spkane@gmail.com"

from freecad_mcp.server import get_mcp, mcp

__all__ = ["__version__", "get_mcp", "mcp"]

# ``mcp`` is None until ``server.main()`` creates the FastMCP instance, and
# returns to None once the transport stops. A ``from freecad_mcp import mcp``
# performed before startup captures that None binding and keeps it even after
# main() assigns the real instance.
# Use ``get_mcp()`` instead: it resolves the binding at call time and
# returns the running instance (or raises RuntimeError if not started yet).
