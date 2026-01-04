#!/usr/bin/env python3
"""FreeCAD MCP Bridge Auto-Start Script for GUI mode.

This script is run automatically when FreeCAD GUI starts via `just run-gui`.
It starts the MCP bridge servers to allow AI assistants to communicate with FreeCAD.

Usage:
    This script is passed to FreeCAD as a startup script:
    /Applications/FreeCAD.app/Contents/Resources/bin/freecad gui_startup.py

Note: This script imports FreecadMCPPlugin directly from server.py to avoid
triggering the MCP SDK import in freecad_mcp/__init__.py (which isn't available
in FreeCAD's embedded Python environment).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Check if we're running inside FreeCAD
try:
    import FreeCAD
except ImportError:
    print("ERROR: This script must be run inside FreeCAD.")
    sys.exit(1)

# Import the plugin server directly from the module file
# We avoid importing through the package hierarchy (freecad_mcp.freecad_plugin.server)
# because freecad_mcp/__init__.py imports the MCP SDK which isn't available
# in FreeCAD's embedded Python environment
script_dir = str(Path(__file__).resolve().parent)
sys.path.insert(0, script_dir)

# Import and start the plugin
try:
    from server import FreecadMCPPlugin  # Direct import from same directory

    # Create and start the plugin
    plugin = FreecadMCPPlugin(
        host="localhost",
        port=9876,  # JSON-RPC socket port
        xmlrpc_port=9875,  # XML-RPC port (neka-nat compatible)
        enable_xmlrpc=True,
    )
    plugin.start()

    FreeCAD.Console.PrintMessage("\n")
    FreeCAD.Console.PrintMessage("=" * 60 + "\n")
    FreeCAD.Console.PrintMessage("MCP Bridge started!\n")
    FreeCAD.Console.PrintMessage("  - XML-RPC: localhost:9875\n")
    FreeCAD.Console.PrintMessage("  - Socket: localhost:9876\n")
    FreeCAD.Console.PrintMessage("\n")
    FreeCAD.Console.PrintMessage(
        "You can now connect your MCP client (Claude Code, etc.) to FreeCAD.\n"
    )
    FreeCAD.Console.PrintMessage("=" * 60 + "\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\n")
    import traceback

    traceback.print_exc()
