# Installation commands for users
# Usage: just install::mcp-server, just install::mcp-bridge-workbench, etc.
#
# This module installs components for end users:
# - MCP Server (as a uv tool, available system-wide)
# - MCP Bridge Workbench (FreeCAD addon)
# - FreeCAD Macros (CutObjectForMagnets, MultiExport)
#
# For developer setup (Python dependencies in virtualenv), use: just dev::install-deps

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# =============================================================================
# Helper: FreeCAD Directory Detection
# =============================================================================
# This function sets MOD_DIR and MACRO_DIR based on the current OS.
# Source it at the start of any recipe that needs FreeCAD paths.
#
# Usage in recipes:
#   eval "$(just install::_freecad-dirs)"
#   echo "Mod directory: $MOD_DIR"
#   echo "Macro directory: $MACRO_DIR"

# Private recipe that outputs shell code to set FreeCAD directories
[private]
_freecad-dirs:
    #!/usr/bin/env bash
    cat << 'DIRS_EOF'
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MOD_DIR="$HOME/Library/Application Support/FreeCAD/Mod"
        MACRO_DIR="$HOME/Library/Application Support/FreeCAD/Macro"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        MOD_DIR="$HOME/.local/share/FreeCAD/Mod"
        MACRO_DIR="$HOME/.local/share/FreeCAD/Macro"
    else
        # Windows: validate APPDATA or use fallback
        if [[ -n "$APPDATA" ]]; then
            FREECAD_BASE="$APPDATA"
        elif [[ -n "$HOME" ]]; then
            # Fallback to standard Windows location under HOME
            FREECAD_BASE="$HOME/AppData/Roaming"
            echo "Warning: APPDATA not set, using fallback: $FREECAD_BASE" >&2
        else
            echo "Error: Neither APPDATA nor HOME is set. Cannot determine FreeCAD directory." >&2
            exit 1
        fi
        MOD_DIR="$FREECAD_BASE/FreeCAD/Mod"
        MACRO_DIR="$FREECAD_BASE/FreeCAD/Macro"
    fi
    DIRS_EOF

# =============================================================================
# MCP Server Installation
# =============================================================================

# Install the MCP server as a user tool (available system-wide via uv)
mcp-server:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    echo "Installing MCP server as a uv tool..."
    echo ""

    # Install from the local project directory
    uv tool install --force "$PROJECT_DIR"

    echo ""
    echo "=========================================="
    echo "MCP Server installed!"
    echo "=========================================="
    echo ""
    echo "The 'freecad-mcp' command is now available system-wide."
    echo ""
    echo "To run:"
    echo "  freecad-mcp                    # stdio mode (for Claude Code)"
    echo "  freecad-mcp --help             # show all options"
    echo ""
    echo "To configure Claude Code, add to your MCP settings:"
    echo '  "freecad": {'
    echo '    "command": "freecad-mcp"'
    echo '  }'
    echo ""

# Uninstall the MCP server tool
uninstall-mcp-server:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Uninstalling MCP server..."
    uv tool uninstall freecad-robust-mcp || echo "MCP server was not installed as a uv tool"

# =============================================================================
# MCP Bridge Workbench Installation
# =============================================================================

# Install the FreeCAD Robust MCP workbench addon to FreeCAD's Mod directory
mcp-bridge-workbench:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"
    ADDON_NAME="FreecadRobustMCP"

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    ADDON_DEST="$MOD_DIR/$ADDON_NAME"

    # Create Mod directory if it doesn't exist
    mkdir -p "$MOD_DIR"

    # Remove existing installation if present
    if [[ -d "$ADDON_DEST" ]]; then
        echo "Removing existing installation at: $ADDON_DEST"
        rm -rf "$ADDON_DEST"
    fi

    # Verify source exists before copying
    ADDON_SRC="${PROJECT_DIR}/addon/$ADDON_NAME"
    if [[ ! -d "$ADDON_SRC" ]]; then
        echo "Error: Addon source directory not found: $ADDON_SRC" >&2
        exit 1
    fi

    # Copy the addon directory
    cp -r "$ADDON_SRC" "$ADDON_DEST"

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
uninstall-mcp-bridge-workbench:
    #!/usr/bin/env bash
    set -euo pipefail
    ADDON_NAME="FreecadRobustMCP"

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    ADDON_DEST="$MOD_DIR/$ADDON_NAME"

    if [[ -d "$ADDON_DEST" ]]; then
        rm -rf "$ADDON_DEST"
        echo "FreeCAD Robust MCP Workbench uninstalled from: $ADDON_DEST"
    else
        echo "Workbench not found at: $ADDON_DEST"
    fi

# =============================================================================
# Macro Installation
# =============================================================================

# Install the CutObjectForMagnets macro to FreeCAD's macro directory
macro-cut:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    # Verify source exists before copying
    MACRO_SRC="${PROJECT_DIR}/macros/Cut_Object_for_Magnets/CutObjectForMagnets.FCMacro"
    if [[ ! -f "$MACRO_SRC" ]]; then
        echo "Error: Macro source file not found: $MACRO_SRC" >&2
        exit 1
    fi

    mkdir -p "$MACRO_DIR"

    # Copy the macro file
    cp "$MACRO_SRC" "$MACRO_DIR/"

    # Optionally copy the icon if it exists
    ICON_SRC="${PROJECT_DIR}/macros/Cut_Object_for_Magnets/CutObjectForMagnets.svg"
    if [[ -f "$ICON_SRC" ]]; then
        cp "$ICON_SRC" "$MACRO_DIR/"
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
uninstall-macro-cut:
    #!/usr/bin/env bash
    set -euo pipefail

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    rm -f "$MACRO_DIR/CutObjectForMagnets.FCMacro"
    rm -f "$MACRO_DIR/CutObjectForMagnets.svg"
    echo "CutObjectForMagnets macro uninstalled"

# Install the MultiExport macro to FreeCAD's macro directory
macro-export:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    # Verify source exists before copying
    MACRO_SRC="${PROJECT_DIR}/macros/Multi_Export/MultiExport.FCMacro"
    if [[ ! -f "$MACRO_SRC" ]]; then
        echo "Error: Macro source file not found: $MACRO_SRC" >&2
        exit 1
    fi

    mkdir -p "$MACRO_DIR"

    # Copy the macro file
    cp "$MACRO_SRC" "$MACRO_DIR/"

    # Optionally copy the icon if it exists
    ICON_SRC="${PROJECT_DIR}/macros/Multi_Export/MultiExport.svg"
    if [[ -f "$ICON_SRC" ]]; then
        cp "$ICON_SRC" "$MACRO_DIR/"
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
uninstall-macro-export:
    #!/usr/bin/env bash
    set -euo pipefail

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    rm -f "$MACRO_DIR/MultiExport.FCMacro"
    rm -f "$MACRO_DIR/MultiExport.svg"
    echo "MultiExport macro uninstalled"

# Install all macros to FreeCAD's macro directory
macro-all: macro-cut macro-export
    @echo "All macros installed successfully!"

# Uninstall all macros from FreeCAD's macro directory
uninstall-macro-all: uninstall-macro-cut uninstall-macro-export
    @echo "All macros uninstalled successfully!"

# =============================================================================
# Status Check
# =============================================================================

# Check installation status of all components
status:
    #!/usr/bin/env bash
    set -euo pipefail

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    echo "=========================================="
    echo "Installation Status"
    echo "=========================================="
    echo ""

    # Check MCP Server (installed as uv tool)
    if command -v freecad-mcp &> /dev/null; then
        echo "✓ MCP Server: INSTALLED (as uv tool)"
        echo "  Run: freecad-mcp"
    elif [[ -f "{{project_root}}/pyproject.toml" ]] && grep -q 'name = "freecad-robust-mcp"' "{{project_root}}/pyproject.toml" 2>/dev/null; then
        # Dev environment exists - check if synced by looking for .venv
        if [[ -d "{{project_root}}/.venv" ]]; then
            echo "✓ MCP Server: AVAILABLE (via dev environment)"
            echo "  Run: just mcp::run"
            echo "  For system-wide install: just install::mcp-server"
        else
            echo "○ MCP Server: DEV SOURCE AVAILABLE (needs setup)"
            echo "  Setup: uv sync --all-extras"
            echo "  Then run: just mcp::run"
        fi
    else
        echo "✗ MCP Server: NOT INSTALLED"
        echo "  Install: just install::mcp-server"
    fi
    echo ""

    # Check workbench
    if [[ -d "$MOD_DIR/FreecadRobustMCP" ]]; then
        echo "✓ MCP Bridge Workbench: INSTALLED"
        echo "  Path: $MOD_DIR/FreecadRobustMCP"
    else
        echo "✗ MCP Bridge Workbench: NOT INSTALLED"
        echo "  Install: just install::mcp-bridge-workbench"
    fi
    echo ""

    # Check macros
    echo "Macros:"
    if [[ -f "$MACRO_DIR/CutObjectForMagnets.FCMacro" ]]; then
        echo "  ✓ CutObjectForMagnets: INSTALLED"
    else
        echo "  ✗ CutObjectForMagnets: NOT INSTALLED"
        echo "    Install: just install::macro-cut"
    fi

    if [[ -f "$MACRO_DIR/MultiExport.FCMacro" ]]; then
        echo "  ✓ MultiExport: INSTALLED"
    else
        echo "  ✗ MultiExport: NOT INSTALLED"
        echo "    Install: just install::macro-export"
    fi
    echo ""

    # Check for legacy installations
    LEGACY_COUNT=0

    if [[ -d "$MOD_DIR/MCPBridge" ]]; then
        echo "⚠ Legacy plugin found: $MOD_DIR/MCPBridge"
        echo "  Run: rm -rf \"$MOD_DIR/MCPBridge\""
        ((LEGACY_COUNT++)) || true
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
