#!/usr/bin/env python3
"""FreeCAD MCP Bridge Startup Script.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Sean P. Kane (GitHub: spkane)

This script starts the MCP bridge in FreeCAD GUI mode. It checks if the bridge
is already running (e.g., from workbench auto-start) before starting a new
instance to avoid port conflicts.

Usage:
    # Passed as argument to FreeCAD GUI on startup
    freecad /path/to/startup_bridge.py

    # Or on macOS:
    open -a FreeCAD.app --args /path/to/startup_bridge.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the script's directory to sys.path so we can import the server module
script_dir = str(Path(__file__).resolve().parent)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Check if we're running inside FreeCAD
try:
    import FreeCAD
except ImportError:
    print("ERROR: This script must be run inside FreeCAD.")
    print("")
    print("Usage:")
    print("  freecad /path/to/startup_bridge.py")
    print("")
    print("Or on macOS:")
    print("  open -a FreeCAD.app --args /path/to/startup_bridge.py")
    sys.exit(1)

# Check if bridge is already running (from auto-start in Init.py)
bridge_already_running = False
try:
    # Check if the workbench commands module has a running plugin
    from commands import _mcp_plugin

    if _mcp_plugin is not None and _mcp_plugin.is_running:
        bridge_already_running = True
        FreeCAD.Console.PrintMessage(
            "\nMCP Bridge already running (from auto-start).\n"
        )
        FreeCAD.Console.PrintMessage("  - XML-RPC: localhost:9875\n")
        FreeCAD.Console.PrintMessage("  - Socket: localhost:9876\n\n")
except ImportError:
    # Workbench commands module not available, we'll start our own
    pass
except AttributeError as e:
    # _mcp_plugin exists but is malformed (missing is_running, etc.)
    FreeCAD.Console.PrintWarning(f"MCP plugin state check failed: {e}\n")
    pass

if not bridge_already_running:
    try:
        from server import FreecadMCPPlugin

        plugin = FreecadMCPPlugin(
            host="localhost",
            port=9876,  # JSON-RPC socket port
            xmlrpc_port=9875,  # XML-RPC port
            enable_xmlrpc=True,
        )
        plugin.start()
        FreeCAD.Console.PrintMessage("\nMCP Bridge started!\n")
        FreeCAD.Console.PrintMessage("  - XML-RPC: localhost:9875\n")
        FreeCAD.Console.PrintMessage("  - Socket: localhost:9876\n\n")
    except Exception as e:
        FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\n")
