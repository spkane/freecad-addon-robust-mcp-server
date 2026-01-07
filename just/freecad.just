# FreeCAD workbench and macro commands
# Usage: just freecad::run-gui, just freecad::install-workbench, etc.

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# =============================================================================
# Running FreeCAD with MCP Bridge
# =============================================================================

# Run MCP bridge server in FreeCAD headless mode
run-headless:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"
    # Use the headless server from the addon directory (source of truth)
    SCRIPT_PATH="${PROJECT_DIR}/addon/FreecadRobustMCP/freecad_mcp_bridge/headless_server.py"

    # Find FreeCADCmd executable based on OS
    FREECAD_CMD=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: Check common locations
        if [[ -x "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd" ]]; then
            FREECAD_CMD="/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
        elif [[ -x "$HOME/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd" ]]; then
            FREECAD_CMD="$HOME/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux: Check common locations and PATH
        if command -v freecadcmd &> /dev/null; then
            FREECAD_CMD="freecadcmd"
        elif command -v FreeCADCmd &> /dev/null; then
            FREECAD_CMD="FreeCADCmd"
        elif [[ -x "/usr/bin/freecadcmd" ]]; then
            FREECAD_CMD="/usr/bin/freecadcmd"
        elif [[ -x "/usr/local/bin/freecadcmd" ]]; then
            FREECAD_CMD="/usr/local/bin/freecadcmd"
        elif [[ -x "/opt/freecad/bin/FreeCADCmd" ]]; then
            FREECAD_CMD="/opt/freecad/bin/FreeCADCmd"
        fi
    else
        # Windows: Check common locations
        if [[ -x "$PROGRAMFILES/FreeCAD 1.0/bin/FreeCADCmd.exe" ]]; then
            FREECAD_CMD="$PROGRAMFILES/FreeCAD 1.0/bin/FreeCADCmd.exe"
        elif [[ -x "$PROGRAMFILES/FreeCAD/bin/FreeCADCmd.exe" ]]; then
            FREECAD_CMD="$PROGRAMFILES/FreeCAD/bin/FreeCADCmd.exe"
        fi
    fi

    if [[ -z "$FREECAD_CMD" ]]; then
        echo "ERROR: FreeCADCmd not found!"
        echo ""
        echo "Please install FreeCAD or set FREECAD_CMD environment variable:"
        echo "  export FREECAD_CMD=/path/to/FreeCADCmd"
        echo "  just freecad::run-headless"
        echo ""
        echo "Common locations:"
        echo "  macOS:   /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
        echo "  Linux:   /usr/bin/freecadcmd or freecadcmd"
        echo "  Windows: C:\\Program Files\\FreeCAD 1.0\\bin\\FreeCADCmd.exe"
        exit 1
    fi

    echo "Using FreeCAD: $FREECAD_CMD"
    echo ""

    # Run FreeCADCmd with the headless server script
    "$FREECAD_CMD" "$SCRIPT_PATH"

# Run MCP bridge with custom FreeCAD path
run-headless-custom freecad_cmd:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"
    SCRIPT_PATH="${PROJECT_DIR}/addon/FreecadRobustMCP/freecad_mcp_bridge/headless_server.py"

    if [[ ! -x "{{freecad_cmd}}" ]]; then
        echo "ERROR: FreeCADCmd not found or not executable: {{freecad_cmd}}"
        exit 1
    fi

    echo "Using FreeCAD: {{freecad_cmd}}"
    echo ""

    # Run FreeCADCmd with the headless server script
    "{{freecad_cmd}}" "$SCRIPT_PATH"

# Run FreeCAD GUI with MCP bridge (requires workbench to be installed)
run-gui:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    # Create a temporary startup script that starts the MCP bridge
    STARTUP_SCRIPT=$(mktemp /tmp/freecad_mcp_startup.XXXXXX.py)

    # Use the server from the installed workbench location
    # Note: For development, use run-gui-custom which passes the addon path explicitly
    cat > "$STARTUP_SCRIPT" << 'PYTHON_EOF'
    # FreeCAD MCP Bridge Auto-Start Script
    import sys
    import os
    from pathlib import Path

    # Determine installed workbench location based on platform
    if sys.platform == "darwin":
        addon_path = Path.home() / "Library" / "Application Support" / "FreeCAD" / "Mod" / "FreecadRobustMCP" / "freecad_mcp_bridge"
    elif sys.platform == "win32":
        addon_path = Path(os.environ.get("APPDATA", "")) / "FreeCAD" / "Mod" / "FreecadRobustMCP" / "freecad_mcp_bridge"
    else:
        addon_path = Path.home() / ".local" / "share" / "FreeCAD" / "Mod" / "FreecadRobustMCP" / "freecad_mcp_bridge"

    if not addon_path.exists():
        import FreeCAD
        FreeCAD.Console.PrintError("MCP Bridge workbench not found.\n")
        FreeCAD.Console.PrintError(f"Expected at: {addon_path}\n")
        FreeCAD.Console.PrintError("Install the workbench first: just freecad::install-workbench\n")
    else:
        try:
            addon_path_str = str(addon_path)
            if addon_path_str not in sys.path:
                sys.path.insert(0, addon_path_str)
            from server import FreecadMCPPlugin
            plugin = FreecadMCPPlugin(
                host="localhost",
                port=9876,
                xmlrpc_port=9875,
                enable_xmlrpc=True,
            )
            plugin.start()
            import FreeCAD
            FreeCAD.Console.PrintMessage("\nMCP Bridge started!\n")
            FreeCAD.Console.PrintMessage("  - XML-RPC: localhost:9875\n")
            FreeCAD.Console.PrintMessage("  - Socket: localhost:9876\n\n")
        except Exception as e:
            import FreeCAD
            FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\n")
    PYTHON_EOF

    # Find FreeCAD GUI executable based on OS
    FREECAD_GUI=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: Use 'open' command for .app bundles
        if [[ -d "/Applications/FreeCAD.app" ]]; then
            FREECAD_GUI="/Applications/FreeCAD.app"
        elif [[ -d "$HOME/Applications/FreeCAD.app" ]]; then
            FREECAD_GUI="$HOME/Applications/FreeCAD.app"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux: Check common locations and PATH
        if command -v freecad &> /dev/null; then
            FREECAD_GUI="freecad"
        elif command -v FreeCAD &> /dev/null; then
            FREECAD_GUI="FreeCAD"
        elif [[ -x "/usr/bin/freecad" ]]; then
            FREECAD_GUI="/usr/bin/freecad"
        elif [[ -x "/usr/local/bin/freecad" ]]; then
            FREECAD_GUI="/usr/local/bin/freecad"
        elif [[ -x "/opt/freecad/bin/FreeCAD" ]]; then
            FREECAD_GUI="/opt/freecad/bin/FreeCAD"
        fi
    else
        # Windows: Check common locations
        if [[ -x "$PROGRAMFILES/FreeCAD 1.0/bin/FreeCAD.exe" ]]; then
            FREECAD_GUI="$PROGRAMFILES/FreeCAD 1.0/bin/FreeCAD.exe"
        elif [[ -x "$PROGRAMFILES/FreeCAD/bin/FreeCAD.exe" ]]; then
            FREECAD_GUI="$PROGRAMFILES/FreeCAD/bin/FreeCAD.exe"
        fi
    fi

    if [[ -z "$FREECAD_GUI" ]]; then
        rm -f "$STARTUP_SCRIPT"
        echo "ERROR: FreeCAD not found!"
        echo ""
        echo "Please install FreeCAD or use:"
        echo "  just freecad::run-gui-custom /path/to/FreeCAD"
        echo ""
        echo "Common locations:"
        echo "  macOS:   /Applications/FreeCAD.app"
        echo "  Linux:   /usr/bin/freecad or freecad"
        echo "  Windows: C:\\Program Files\\FreeCAD 1.0\\bin\\FreeCAD.exe"
        exit 1
    fi

    echo "Starting FreeCAD with MCP bridge..."
    echo "Using FreeCAD: $FREECAD_GUI"
    echo ""

    # Launch FreeCAD with the startup script
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: Use 'open' with --args to pass the script
        open -a "$FREECAD_GUI" --args "$STARTUP_SCRIPT"
    else
        # Linux/Windows: Run directly with script as argument
        "$FREECAD_GUI" "$STARTUP_SCRIPT" &
    fi

    echo "FreeCAD is starting..."
    echo "The MCP bridge will start automatically once FreeCAD initializes."
    echo ""
    echo "Note: You can now start/restart your MCP client (Claude Code, etc.) to connect."

# Run FreeCAD GUI with custom path
run-gui-custom freecad_path:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    # Create a temporary startup script
    STARTUP_SCRIPT=$(mktemp /tmp/freecad_mcp_startup.XXXXXX.py)

    # Use the server from the addon directory
    ADDON_PATH="${PROJECT_DIR}/addon/FreecadRobustMCP/freecad_mcp_bridge"

    cat > "$STARTUP_SCRIPT" << EOF
    # FreeCAD MCP Bridge Auto-Start Script
    import sys
    addon_path = "${ADDON_PATH}"
    if addon_path not in sys.path:
        sys.path.insert(0, addon_path)

    try:
        from server import FreecadMCPPlugin
        plugin = FreecadMCPPlugin(
            host="localhost",
            port=9876,
            xmlrpc_port=9875,
            enable_xmlrpc=True,
        )
        plugin.start()
        import FreeCAD
        FreeCAD.Console.PrintMessage("\\nMCP Bridge started!\\n")
        FreeCAD.Console.PrintMessage("  - XML-RPC: localhost:9875\\n")
        FreeCAD.Console.PrintMessage("  - Socket: localhost:9876\\n\\n")
    except Exception as e:
        import FreeCAD
        FreeCAD.Console.PrintError(f"Failed to start MCP Bridge: {e}\\n")
    EOF

    echo "Starting FreeCAD with MCP bridge..."
    echo "Using FreeCAD: {{freecad_path}}"
    echo ""

    if [[ "$OSTYPE" == "darwin"* ]] && [[ "{{freecad_path}}" == *.app ]]; then
        open -a "{{freecad_path}}" --args "$STARTUP_SCRIPT"
    else
        "{{freecad_path}}" "$STARTUP_SCRIPT" &
    fi

    echo "FreeCAD is starting with MCP bridge..."

# =============================================================================
# Deprecated Aliases (use install:: module instead)
# =============================================================================
# These are kept for backwards compatibility but will be removed in a future version.
# Use the new install:: module commands instead:
#   just install::macro-cut           (was: just freecad::install-cut-macro)
#   just install::macro-export        (was: just freecad::install-export-macro)
#   just install::macro-all           (was: just freecad::install-all-macros)
#   just install::mcp-bridge-workbench (was: just freecad::install-workbench)
#   just install::status              (was: just freecad::mcp-status)
