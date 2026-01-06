#!/usr/bin/env python3
r"""Headless FreeCAD MCP Bridge Server.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This script starts the MCP bridge server in FreeCAD's headless mode.
It should be run with FreeCADCmd (the headless FreeCAD executable).

Usage:
    # If workbench is installed via FreeCAD Addon Manager:
    FreeCADCmd ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/headless_server.py

    # On macOS:
    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
        ~/Library/Application\ Support/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/headless_server.py

Note: In headless mode, GUI features like screenshots are not available.
For full functionality, use the workbench in FreeCAD's GUI.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Check if we're running inside FreeCAD
try:
    import FreeCAD

    print(f"FreeCAD version: {FreeCAD.Version()[0]}.{FreeCAD.Version()[1]}")
except ImportError:
    print("ERROR: This script must be run with FreeCADCmd or inside FreeCAD.")
    print("")
    print("Usage:")
    print(
        "  FreeCADCmd /path/to/FreecadRobustMCP/freecad_mcp_bridge/headless_server.py"
    )
    print("")
    print("On macOS (if workbench installed):")
    print("  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \\")
    print(
        "    ~/Library/Application\\ Support/FreeCAD/Mod/FreecadRobustMCP/"
        "freecad_mcp_bridge/headless_server.py"
    )
    print("")
    print("On Linux (if workbench installed):")
    print(
        "  freecadcmd ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/"
        "freecad_mcp_bridge/headless_server.py"
    )
    sys.exit(1)

# Import the plugin server directly from the module file in the same directory
script_dir = str(Path(__file__).resolve().parent)
sys.path.insert(0, script_dir)
from server import FreecadMCPPlugin  # noqa: E402

# Create and run the plugin
plugin = FreecadMCPPlugin(
    host="localhost",
    port=9876,  # JSON-RPC socket port
    xmlrpc_port=9875,  # XML-RPC port
    enable_xmlrpc=True,
)

# Start the plugin
plugin.start()

# Print status messages with flush to ensure they appear immediately
# (FreeCAD's Python may have buffered stdout)
print("", flush=True)
print("=" * 60, flush=True)
print("MCP Bridge started in headless mode!", flush=True)
print("  - XML-RPC: localhost:9875", flush=True)
print("  - Socket: localhost:9876", flush=True)
print("", flush=True)
print(
    "Note: Screenshot and view features are not available in headless mode.", flush=True
)
print("Press Ctrl+C to stop.", flush=True)
print("=" * 60, flush=True)
print("", flush=True)

# Run forever (blocks until Ctrl+C)
plugin.run_forever()
