#!/usr/bin/env python3
"""Headless FreeCAD MCP Bridge Server.

This script starts the MCP bridge server in FreeCAD's headless mode.
It should be run with FreeCADCmd (the headless FreeCAD executable).

Usage:
    FreeCADCmd headless_server.py
    # or
    freecadcmd headless_server.py

Note: In headless mode, GUI features like screenshots are not available.
For full functionality, use the StartMCPBridge macro in FreeCAD's GUI.
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
    print("  just run-headless")
    print("  # or")
    print("  FreeCADCmd headless_server.py")
    print("  freecadcmd headless_server.py")
    print("")
    print("On macOS:")
    print(
        "  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd headless_server.py"
    )
    print("")
    print("On Linux:")
    print("  freecadcmd headless_server.py")
    sys.exit(1)

# Import the plugin server directly from the module file
# We avoid importing through the package hierarchy (freecad_mcp.freecad_plugin.server)
# because freecad_mcp/__init__.py imports the MCP SDK which isn't available
# in FreeCAD's embedded Python environment
script_dir = str(Path(__file__).resolve().parent)
# Import directly from server.py in the same directory
sys.path.insert(0, script_dir)
from server import FreecadMCPPlugin  # noqa: E402

# Create and run the plugin
plugin = FreecadMCPPlugin(
    host="localhost",
    port=9876,  # JSON-RPC socket port
    xmlrpc_port=9875,  # XML-RPC port (neka-nat compatible)
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
