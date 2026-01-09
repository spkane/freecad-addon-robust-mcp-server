#!/usr/bin/env python3
r"""Blocking FreeCAD MCP Bridge Server.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This script starts the MCP bridge server and blocks with run_forever().
It works with both FreeCAD GUI and FreeCADCmd (headless) modes.

Use this script when you need FreeCAD to keep running (CI, background servers).
For interactive GUI sessions, use startup_bridge.py instead (non-blocking).

Usage:
    # Headless mode (no GUI features):
    FreeCADCmd ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py

    # GUI mode (full features including screenshots):
    freecad ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py

    # On macOS:
    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
        ~/Library/Application\ Support/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py

Note: In headless mode (FreeCADCmd), GUI features like screenshots are not available.
For full functionality, run with FreeCAD GUI executable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Check if we're running inside FreeCAD
try:
    import FreeCAD

    print(f"FreeCAD version: {FreeCAD.Version()[0]}.{FreeCAD.Version()[1]}")
except ImportError:
    print("ERROR: This script must be run with FreeCAD or FreeCADCmd.")
    print("")
    print("Usage:")
    print(
        "  FreeCADCmd /path/to/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py"
    )
    print("")
    print("On macOS (if workbench installed):")
    print("  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \\")
    print(
        "    ~/Library/Application\\ Support/FreeCAD/Mod/FreecadRobustMCP/"
        "freecad_mcp_bridge/blocking_bridge.py"
    )
    print("")
    print("On Linux (if workbench installed):")
    print(
        "  freecadcmd ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/"
        "freecad_mcp_bridge/blocking_bridge.py"
    )
    sys.exit(1)

# Import the plugin server directly from the module file in the same directory
script_dir = str(Path(__file__).resolve().parent)
sys.path.insert(0, script_dir)
from bridge_utils import get_running_plugin  # noqa: E402
from server import FreecadMCPPlugin  # noqa: E402

# Check if bridge is already running (from auto-start in Init.py)
plugin = get_running_plugin()

if plugin is None:
    # Get configuration from environment variables (with defaults)
    socket_port = int(os.environ.get("FREECAD_SOCKET_PORT", "9876"))
    xmlrpc_port = int(os.environ.get("FREECAD_XMLRPC_PORT", "9875"))

    # Create and run the plugin
    plugin = FreecadMCPPlugin(
        host="localhost",
        port=socket_port,  # JSON-RPC socket port
        xmlrpc_port=xmlrpc_port,  # XML-RPC port
        enable_xmlrpc=True,
    )

    # Start the plugin
    plugin.start()

# Print status messages with flush to ensure they appear immediately
# (FreeCAD's Python may have buffered stdout)
# Use configured ports from plugin or defaults if plugin existed before
actual_xmlrpc_port = getattr(plugin, "xmlrpc_port", 9875) if plugin else 9875
actual_socket_port = getattr(plugin, "port", 9876) if plugin else 9876

print("", flush=True)
print("=" * 60, flush=True)
gui_mode = "GUI" if FreeCAD.GuiUp else "headless"
print(f"MCP Bridge started in {gui_mode} mode!", flush=True)
print(f"  - XML-RPC: localhost:{actual_xmlrpc_port}", flush=True)
print(f"  - Socket: localhost:{actual_socket_port}", flush=True)
print("", flush=True)
if not FreeCAD.GuiUp:
    print(
        "Note: Screenshot and view features are not available in headless mode.",
        flush=True,
    )
print("Press Ctrl+C to stop.", flush=True)
print("=" * 60, flush=True)
print("", flush=True)

# Run forever (blocks until Ctrl+C)
if plugin is not None:
    plugin.run_forever()
else:
    print("ERROR: Failed to initialize MCP Bridge plugin.", flush=True)
    sys.exit(1)
