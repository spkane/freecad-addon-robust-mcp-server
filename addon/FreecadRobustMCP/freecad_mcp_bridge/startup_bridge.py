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

import os
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
from bridge_utils import get_running_plugin  # noqa: E402

if get_running_plugin() is None:
    try:
        from server import FreecadMCPPlugin

        # Get configuration from environment variables (with defaults)
        try:
            socket_port = int(os.environ.get("FREECAD_SOCKET_PORT", "9876"))
            xmlrpc_port = int(os.environ.get("FREECAD_XMLRPC_PORT", "9875"))
        except ValueError as e:
            FreeCAD.Console.PrintError(f"Invalid port configuration: {e}\n")
            FreeCAD.Console.PrintError(
                "FREECAD_SOCKET_PORT and FREECAD_XMLRPC_PORT must be integers.\n"
            )
            raise

        plugin = FreecadMCPPlugin(
            host="localhost",
            port=socket_port,  # JSON-RPC socket port
            xmlrpc_port=xmlrpc_port,  # XML-RPC port
            enable_xmlrpc=True,
        )
        plugin.start()
        FreeCAD.Console.PrintMessage("\nMCP Bridge started!\n")
        FreeCAD.Console.PrintMessage(f"  - XML-RPC: localhost:{xmlrpc_port}\n")
        FreeCAD.Console.PrintMessage(f"  - Socket: localhost:{socket_port}\n\n")
    except Exception as e:
        FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\n")
