# Installation commands for users
# Usage: just install::mcp-server, just install::mcp-bridge-workbench, etc.
#
# This module installs components for end users:
# - Robust MCP Server (as a uv tool, available system-wide)
# - Robust MCP Bridge Workbench (FreeCAD addon)
#
# For developer setup (Python dependencies in virtualenv), use: just dev::install-deps

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()
export FREECAD_MCP_INVOCATION_DIR := invocation_directory()

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
# FreeCAD 1.x uses versioned directories (v1-1, v1-2, etc.) for user data.
# This helper detects the latest versioned directory if present.
[private]
_freecad-dirs:
    #!/usr/bin/env bash
    cat << 'DIRS_EOF'
    # Use the installer's profile selection, including XDG and numeric versions.
    if [[ -n "${FREECAD_INSTALL_MOD_DIR:-}" ]]; then
        MOD_DIR="$FREECAD_INSTALL_MOD_DIR"
    else
        MOD_DIR=$(cd "{{project_root}}" && uv run python -c 'from scripts.install_workbench import default_mod_directory; print(default_mod_directory())') || exit 1
    fi
    MACRO_DIR="$(dirname "$MOD_DIR")/Macro"
    DIRS_EOF

# =============================================================================
# Robust MCP Server Installation
# =============================================================================

# Install the Robust MCP Server as a user tool (available system-wide via uv)
# Uses cached builds for faster installation. For development with uncommitted
# changes, use mcp-server-clean instead.
mcp-server:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT_DIR="{{project_root}}"

    echo "Installing Robust MCP Server as a uv tool..."
    echo ""

    # Install from the local project directory
    # --force handles reinstallation automatically, no need to uninstall first
    uv tool install --force "$PROJECT_DIR"

    echo ""
    echo "=========================================="
    echo "Robust MCP Server installed!"
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
    echo "Note: If you have uncommitted local changes, use 'just install::mcp-server-clean'"
    echo ""

# Install with cache clearing (for development with uncommitted changes)
# Clears uv cache first to ensure the build picks up all local changes.
mcp-server-clean:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Clearing uv cache for fresh build..."
    uv cache clean --force 2>/dev/null || true
    just install::mcp-server

# Uninstall the Robust MCP Server tool
uninstall-mcp-server:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Uninstalling Robust MCP Server..."
    uv tool uninstall freecad-robust-mcp || echo "Robust MCP Server was not installed as a uv tool"

# =============================================================================
# Robust MCP Bridge Workbench Installation
# =============================================================================

# Install the FreeCAD Robust MCP workbench addon to FreeCAD's Mod directory
# Uses new-style namespace package format: Mod/RobustMCPBridge/freecad/RobustMCPBridge/
[script("uv", "run", "python")]
mcp-bridge-workbench $FREECAD_INSTALL_MOD_DIR="":
    import os
    import runpy
    import sys
    from pathlib import Path
    sys.path.insert(0, "../scripts")
    if os.environ["FREECAD_INSTALL_MOD_DIR"]:
        selected = Path(os.environ["FREECAD_INSTALL_MOD_DIR"])
        selected = Path(os.environ["FREECAD_MCP_INVOCATION_DIR"]) / selected
        sys.argv = ["install_workbench.py", "--mod-dir", str(selected)]
    runpy.run_path("../scripts/install_workbench.py", run_name="__main__")

# Uninstall the FreeCAD Robust MCP workbench addon
uninstall-mcp-bridge-workbench $FREECAD_INSTALL_MOD_DIR="":
    #!/usr/bin/env bash
    set -euo pipefail
    # New-style namespace package: Mod/RobustMCPBridge/freecad/RobustMCPBridge/
    ADDON_NAMESPACE="freecad"
    ADDON_NAME="RobustMCPBridge"

    # Resolve explicit paths before the nested just invocation changes directories.
    if [[ -n "$FREECAD_INSTALL_MOD_DIR" ]]; then
        FREECAD_INSTALL_MOD_DIR=$(uv run python -c 'import os; from pathlib import Path; print(Path(os.environ["FREECAD_MCP_INVOCATION_DIR"]) / os.environ["FREECAD_INSTALL_MOD_DIR"])')
        export FREECAD_INSTALL_MOD_DIR
    fi
    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    # Current correct location: Mod/RobustMCPBridge/
    ADDON_DEST="$MOD_DIR/$ADDON_NAME"

    if [[ -d "$ADDON_DEST" ]]; then
        rm -rf "$ADDON_DEST"
        echo "FreeCAD Robust MCP Workbench uninstalled from: $ADDON_DEST"
    else
        echo "Workbench not found at: $ADDON_DEST"
    fi

    # Also remove incorrect namespace installation (Mod/freecad/RobustMCPBridge)
    WRONG_NS_DEST="$MOD_DIR/$ADDON_NAMESPACE/$ADDON_NAME"
    if [[ -d "$WRONG_NS_DEST" ]]; then
        rm -rf "$WRONG_NS_DEST"
        echo "Incorrect namespace installation uninstalled from: $WRONG_NS_DEST"
        # Clean up empty freecad directory if it exists
        if [[ -d "$MOD_DIR/$ADDON_NAMESPACE" ]] && [[ -z "$(ls -A "$MOD_DIR/$ADDON_NAMESPACE")" ]]; then
            rmdir "$MOD_DIR/$ADDON_NAMESPACE"
        fi
    fi

    # Also remove old-style installation if present
    OLD_STYLE_DEST="$MOD_DIR/FreecadRobustMCPBridge"
    if [[ -d "$OLD_STYLE_DEST" ]]; then
        rm -rf "$OLD_STYLE_DEST"
        echo "Legacy old-style workbench uninstalled from: $OLD_STYLE_DEST"
    fi

# =============================================================================
# Status Check
# =============================================================================

# Check installation status of all components
status $FREECAD_INSTALL_MOD_DIR="":
    #!/usr/bin/env bash
    set -euo pipefail

    # Resolve explicit paths before the nested just invocation changes directories.
    if [[ -n "$FREECAD_INSTALL_MOD_DIR" ]]; then
        FREECAD_INSTALL_MOD_DIR=$(uv run python -c 'import os; from pathlib import Path; print(Path(os.environ["FREECAD_MCP_INVOCATION_DIR"]) / os.environ["FREECAD_INSTALL_MOD_DIR"])')
        export FREECAD_INSTALL_MOD_DIR
    fi
    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    # Helper function to get file modification time (cross-platform)
    get_mod_time() {
        local file="$1"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$file" 2>/dev/null || echo "unknown"
        else
            stat -c "%y" "$file" 2>/dev/null | cut -d'.' -f1 || echo "unknown"
        fi
    }

    echo "=========================================="
    echo "Installation Status"
    echo "=========================================="
    echo ""

    # Check Robust MCP Server (installed as uv tool)
    if command -v freecad-mcp &> /dev/null; then
        MCP_VERSION=$(freecad-mcp --version 2>/dev/null || echo "unknown")
        MCP_PATH=$(command -v freecad-mcp)
        MCP_MOD_TIME=$(get_mod_time "$MCP_PATH")
        echo "✓ Robust MCP Server: INSTALLED (as uv tool)"
        echo "  Version: $MCP_VERSION"
        echo "  Updated: $MCP_MOD_TIME"
        echo "  Run: freecad-mcp"
    elif [[ -f "{{project_root}}/pyproject.toml" ]] && grep -q 'name = "freecad-robust-mcp"' "{{project_root}}/pyproject.toml" 2>/dev/null; then
        # Dev environment exists - check if synced by looking for .venv
        if [[ -d "{{project_root}}/.venv" ]]; then
            DEV_VERSION=$(cd "{{project_root}}" && uv run python -c "from freecad_mcp import __version__; print(__version__)" 2>/dev/null || echo "unknown")
            echo "✓ Robust MCP Server: AVAILABLE (via dev environment)"
            echo "  Version: $DEV_VERSION"
            echo "  Run: just mcp::run"
            echo "  For system-wide install: just install::mcp-server"
        else
            echo "○ Robust MCP Server: DEV SOURCE AVAILABLE (needs setup)"
            echo "  Setup: uv sync --all-extras"
            echo "  Then run: just mcp::run"
        fi
    else
        echo "✗ Robust MCP Server: NOT INSTALLED"
        echo "  Install: just install::mcp-server"
    fi
    echo ""

    # Helper function to extract version from package.xml files
    # Uses environment variable to pass file path safely to Python (avoids shell interpolation)
    extract_package_version() {
        local package_file="$1"
        PACKAGE_FILE="$package_file" python3 -c '
    import os
    import xml.etree.ElementTree as ET
    try:
        package_file = os.environ.get("PACKAGE_FILE", "")
        tree = ET.parse(package_file)
        root = tree.getroot()
        ns = {"pkg": "https://wiki.freecad.org/Package_Metadata"}
        # Try with namespace first, then without (use is not None, not truthiness)
        ver = root.find("pkg:version", ns)
        if ver is None:
            ver = root.find("version")
        print(ver.text if ver is not None else "unknown")
    except Exception:
        print("unknown")
    ' 2>/dev/null || echo "unknown"
    }

    # Check workbench (new-style namespace package: Mod/RobustMCPBridge/freecad/RobustMCPBridge/)
    WB_PATH="$MOD_DIR/RobustMCPBridge"
    WB_CODE_PATH="$WB_PATH/freecad/RobustMCPBridge"
    if [[ -d "$WB_PATH" ]]; then
        WB_VERSION="unknown"
        if [[ -f "$WB_PATH/package.xml" ]]; then
            WB_VERSION=$(extract_package_version "$WB_PATH/package.xml")
        fi
        WB_MOD_TIME=$(get_mod_time "$WB_CODE_PATH/init_gui.py")
        echo "✓ Robust MCP Bridge Workbench: INSTALLED"
        echo "  Version: $WB_VERSION"
        echo "  Updated: $WB_MOD_TIME"
        echo "  Path: $WB_PATH"
    # Check for incorrect namespace installation (Mod/freecad/RobustMCPBridge)
    elif [[ -d "$MOD_DIR/freecad/RobustMCPBridge" ]]; then
        WB_VERSION="unknown"
        if [[ -f "$MOD_DIR/freecad/RobustMCPBridge/package.xml" ]]; then
            WB_VERSION=$(extract_package_version "$MOD_DIR/freecad/RobustMCPBridge/package.xml")
        fi
        WB_MOD_TIME=$(get_mod_time "$MOD_DIR/freecad/RobustMCPBridge/init_gui.py")
        echo "⚠ Robust MCP Bridge Workbench: INSTALLED (incorrect namespace format)"
        echo "  Version: $WB_VERSION"
        echo "  Updated: $WB_MOD_TIME"
        echo "  Path: $MOD_DIR/freecad/RobustMCPBridge"
        echo "  Note: Reinstall to fix: just install::mcp-bridge-workbench"
    # Also check old-style installation
    elif [[ -d "$MOD_DIR/FreecadRobustMCPBridge" ]]; then
        WB_VERSION="unknown"
        if [[ -f "$MOD_DIR/FreecadRobustMCPBridge/package.xml" ]]; then
            WB_VERSION=$(extract_package_version "$MOD_DIR/FreecadRobustMCPBridge/package.xml")
        fi
        WB_MOD_TIME=$(get_mod_time "$MOD_DIR/FreecadRobustMCPBridge/InitGui.py")
        echo "⚠ Robust MCP Bridge Workbench: INSTALLED (legacy format)"
        echo "  Version: $WB_VERSION"
        echo "  Updated: $WB_MOD_TIME"
        echo "  Path: $MOD_DIR/FreecadRobustMCPBridge"
        echo "  Note: Reinstall to upgrade to new format: just install::mcp-bridge-workbench"
    else
        echo "✗ Robust MCP Bridge Workbench: NOT INSTALLED"
        echo "  Install: just install::mcp-bridge-workbench"
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

# =============================================================================
# Convenience Commands
# =============================================================================

# Uninstall all components (MCP server and workbench)
uninstall:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Uninstalling all Robust MCP components..."
    echo ""
    just install::uninstall-mcp-server
    echo ""
    just install::uninstall-mcp-bridge-workbench
    echo ""
    echo "All components uninstalled."

# Clean up everything (uninstall all + remove legacy installations)
cleanup:
    #!/usr/bin/env bash
    set -euo pipefail

    # Set FreeCAD directories
    eval "$(just install::_freecad-dirs)"

    echo "Cleaning up all Robust MCP installations..."
    echo ""

    # Uninstall current components
    just install::uninstall

    echo ""
    echo "Removing legacy installations..."

    # Remove legacy MCPBridge if present
    if [[ -d "$MOD_DIR/MCPBridge" ]]; then
        rm -rf "$MOD_DIR/MCPBridge"
        echo "  Removed: $MOD_DIR/MCPBridge"
    fi

    # Remove legacy macro if present
    if [[ -f "$MACRO_DIR/StartMCPBridge.FCMacro" ]]; then
        rm "$MACRO_DIR/StartMCPBridge.FCMacro"
        echo "  Removed: $MACRO_DIR/StartMCPBridge.FCMacro"
    fi

    echo ""
    echo "Cleanup complete."
