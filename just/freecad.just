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

    # Use the server from the addon directory
    cat > "$STARTUP_SCRIPT" << 'PYTHON_EOF'
    # FreeCAD MCP Bridge Auto-Start Script
    import sys
    from pathlib import Path

    # Find the addon directory - check both installed location and dev location
    addon_paths = []

    # Check development location first (addon in project)
    dev_addon = Path(__file__).resolve().parent.parent / "addon" / "FreecadRobustMCP" / "freecad_mcp_bridge"
    if dev_addon.exists():
        addon_paths.append(str(dev_addon))

    # Check installed workbench locations
    import os
    if sys.platform == "darwin":
        installed = Path.home() / "Library" / "Application Support" / "FreeCAD" / "Mod" / "FreecadRobustMCP" / "freecad_mcp_bridge"
    elif sys.platform == "win32":
        installed = Path(os.environ.get("APPDATA", "")) / "FreeCAD" / "Mod" / "FreecadRobustMCP" / "freecad_mcp_bridge"
    else:
        installed = Path.home() / ".local" / "share" / "FreeCAD" / "Mod" / "FreecadRobustMCP" / "freecad_mcp_bridge"

    if installed.exists():
        addon_paths.append(str(installed))

    # Try to import and start
    started = False
    for addon_path in addon_paths:
        try:
            if addon_path not in sys.path:
                sys.path.insert(0, addon_path)
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
            started = True
            break
        except Exception:
            continue

    if not started:
        import FreeCAD
        FreeCAD.Console.PrintError("Failed to start MCP Bridge.\n")
        FreeCAD.Console.PrintError("Install the workbench first: just freecad::install-workbench\n")
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
# Macro Installation (MultiExport, CutObjectForMagnets)
# =============================================================================

# Install the CutObjectForMagnets macro to FreeCAD's macro directory
install-cut-macro:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    # Determine macro directory based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MACRO_DIR="$HOME/Library/Application Support/FreeCAD/Macro"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MACRO_DIR="$HOME/.local/share/FreeCAD/Macro"
    else
        MACRO_DIR="$APPDATA/FreeCAD/Macro"
    fi

    mkdir -p "$MACRO_DIR"

    # Copy the macro file
    cp "${PROJECT_DIR}/macros/Cut_Object_for_Magnets/CutObjectForMagnets.FCMacro" "$MACRO_DIR/"

    # Optionally copy the icon if it exists
    if [[ -f "${PROJECT_DIR}/macros/Cut_Object_for_Magnets/CutObjectForMagnets.svg" ]]; then
        cp "${PROJECT_DIR}/macros/Cut_Object_for_Magnets/CutObjectForMagnets.svg" "$MACRO_DIR/"
    fi

    echo "CutObjectForMagnets macro installed to: $MACRO_DIR"
    echo ""
    echo "To use:"
    echo "  1. Start FreeCAD"
    echo "  2. Select an object to cut"
    echo "  3. Go to: Macro → Macros → CutObjectForMagnets → Execute"
    echo ""
    echo "For angled cuts:"
    echo "  1. Create a datum plane at your desired angle (Part Design → Create datum plane)"
    echo "  2. Select 'Model Plane' in the macro dialog"
    echo "  3. Choose your datum plane from the dropdown"

# Uninstall the CutObjectForMagnets macro
uninstall-cut-macro:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MACRO_DIR="$HOME/Library/Application Support/FreeCAD/Macro"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MACRO_DIR="$HOME/.local/share/FreeCAD/Macro"
    else
        MACRO_DIR="$APPDATA/FreeCAD/Macro"
    fi
    rm -f "$MACRO_DIR/CutObjectForMagnets.FCMacro"
    rm -f "$MACRO_DIR/CutObjectForMagnets.svg"
    echo "CutObjectForMagnets macro uninstalled"

# Install the MultiExport macro to FreeCAD's macro directory
install-export-macro:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    # Determine macro directory based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MACRO_DIR="$HOME/Library/Application Support/FreeCAD/Macro"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MACRO_DIR="$HOME/.local/share/FreeCAD/Macro"
    else
        MACRO_DIR="$APPDATA/FreeCAD/Macro"
    fi

    mkdir -p "$MACRO_DIR"

    # Copy the macro file
    cp "${PROJECT_DIR}/macros/Multi_Export/MultiExport.FCMacro" "$MACRO_DIR/"

    # Optionally copy the icon if it exists
    if [[ -f "${PROJECT_DIR}/macros/Multi_Export/MultiExport.svg" ]]; then
        cp "${PROJECT_DIR}/macros/Multi_Export/MultiExport.svg" "$MACRO_DIR/"
    fi

    echo "MultiExport macro installed to: $MACRO_DIR"
    echo ""
    echo "To use:"
    echo "  1. Start FreeCAD"
    echo "  2. Select one or more objects to export"
    echo "  3. Go to: Macro → Macros → MultiExport → Execute"
    echo "  4. Choose export formats (STL, STEP, 3MF selected by default)"
    echo "  5. Set output directory and filename"
    echo "  6. Click Export"

# Uninstall the MultiExport macro
uninstall-export-macro:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MACRO_DIR="$HOME/Library/Application Support/FreeCAD/Macro"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MACRO_DIR="$HOME/.local/share/FreeCAD/Macro"
    else
        MACRO_DIR="$APPDATA/FreeCAD/Macro"
    fi
    rm -f "$MACRO_DIR/MultiExport.FCMacro"
    rm -f "$MACRO_DIR/MultiExport.svg"
    echo "MultiExport macro uninstalled"

# Install all macros to FreeCAD's macro directory
install-all-macros: install-cut-macro install-export-macro
    @echo "All macros installed successfully!"

# Uninstall all macros from FreeCAD's macro directory
uninstall-all-macros: uninstall-cut-macro uninstall-export-macro
    @echo "All macros uninstalled successfully!"

# =============================================================================
# Workbench Addon Installation
# =============================================================================

# Install the FreeCAD Robust MCP workbench addon to FreeCAD's Mod directory
install-workbench:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"
    ADDON_NAME="FreecadRobustMCP"

    # Determine FreeCAD Mod directory based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MOD_DIR="$HOME/Library/Application Support/FreeCAD/Mod"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MOD_DIR="$HOME/.local/share/FreeCAD/Mod"
    else
        MOD_DIR="$APPDATA/FreeCAD/Mod"
    fi

    ADDON_DEST="$MOD_DIR/$ADDON_NAME"

    # Create Mod directory if it doesn't exist
    mkdir -p "$MOD_DIR"

    # Remove existing installation if present
    if [[ -d "$ADDON_DEST" ]]; then
        echo "Removing existing installation at: $ADDON_DEST"
        rm -rf "$ADDON_DEST"
    fi

    # Copy the addon directory
    cp -r "${PROJECT_DIR}/addon/$ADDON_NAME" "$ADDON_DEST"

    echo ""
    echo "=========================================="
    echo "FreeCAD Robust MCP Workbench installed!"
    echo "=========================================="
    echo ""
    echo "Installation path: $ADDON_DEST"
    echo ""
    echo "To use:"
    echo "  1. Start FreeCAD"
    echo "  2. Select the 'MCP Bridge' workbench from the workbench selector"
    echo "  3. Click 'Start MCP Bridge' in the toolbar"
    echo "  4. Connect your MCP client (Claude Code, etc.) to FreeCAD"
    echo ""

# Uninstall the FreeCAD Robust MCP workbench addon
uninstall-workbench:
    #!/usr/bin/env bash
    set -euo pipefail
    ADDON_NAME="FreecadRobustMCP"

    if [[ "$OSTYPE" == "darwin"* ]]; then
        MOD_DIR="$HOME/Library/Application Support/FreeCAD/Mod"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MOD_DIR="$HOME/.local/share/FreeCAD/Mod"
    else
        MOD_DIR="$APPDATA/FreeCAD/Mod"
    fi

    ADDON_DEST="$MOD_DIR/$ADDON_NAME"

    if [[ -d "$ADDON_DEST" ]]; then
        rm -rf "$ADDON_DEST"
        echo "FreeCAD Robust MCP Workbench uninstalled from: $ADDON_DEST"
    else
        echo "Workbench not found at: $ADDON_DEST"
    fi

# Check workbench installation status
mcp-status:
    #!/usr/bin/env bash
    set -euo pipefail

    # Determine directories based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MOD_DIR="$HOME/Library/Application Support/FreeCAD/Mod"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MOD_DIR="$HOME/.local/share/FreeCAD/Mod"
    else
        MOD_DIR="$APPDATA/FreeCAD/Mod"
    fi

    echo "=========================================="
    echo "MCP Bridge Installation Status"
    echo "=========================================="
    echo ""

    # Check workbench
    if [[ -d "$MOD_DIR/FreecadRobustMCP" ]]; then
        echo "✓ Workbench addon: INSTALLED"
        echo "  Path: $MOD_DIR/FreecadRobustMCP"
        echo ""
        echo "To use:"
        echo "  1. Start FreeCAD"
        echo "  2. Select 'MCP Bridge' workbench"
        echo "  3. Click 'Start MCP Bridge' in toolbar"
    else
        echo "✗ Workbench addon: NOT INSTALLED"
        echo ""
        echo "To install:"
        echo "  just freecad::install-workbench"
    fi
    echo ""

    # Check for legacy installations that should be cleaned up
    LEGACY_COUNT=0

    if [[ -d "$MOD_DIR/MCPBridge" ]]; then
        echo "⚠ Legacy plugin found: $MOD_DIR/MCPBridge"
        echo "  Run: rm -rf \"$MOD_DIR/MCPBridge\""
        ((LEGACY_COUNT++)) || true
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        MACRO_DIR="$HOME/Library/Application Support/FreeCAD/Macro"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MACRO_DIR="$HOME/.local/share/FreeCAD/Macro"
    else
        MACRO_DIR="$APPDATA/FreeCAD/Macro"
    fi

    if [[ -f "$MACRO_DIR/StartMCPBridge.FCMacro" ]]; then
        echo "⚠ Legacy macro found: $MACRO_DIR/StartMCPBridge.FCMacro"
        echo "  Run: rm \"$MACRO_DIR/StartMCPBridge.FCMacro\""
        ((LEGACY_COUNT++)) || true
    fi

    if [[ $LEGACY_COUNT -gt 0 ]]; then
        echo ""
        echo "Note: Legacy installations can be removed. The workbench replaces them."
    fi

    echo "=========================================="

# Check if the workbench addon is installed (alias for mcp-status)
workbench-status: mcp-status
