#!/bin/bash
# Setup FreeCAD AppImage - replicates .github/actions/setup-freecad/action.yaml
set -euo pipefail

# Validate required variables have safe defaults
FREECAD_TAG="${FREECAD_TAG:-1.0.2}"
APPIMAGE_DIR="${APPIMAGE_DIR:-$HOME/freecad-appimage}"
# Optional SHA256 checksum for verification (if provided, download will be verified)
APPIMAGE_SHA256="${APPIMAGE_SHA256:-}"

# Validate APPIMAGE_DIR is set and non-empty after defaults
if [[ -z "$APPIMAGE_DIR" ]]; then
    echo "ERROR: APPIMAGE_DIR is empty - cannot determine installation path"
    exit 1
fi

# Marker file to indicate complete installation
MARKER_FILE="$APPIMAGE_DIR/.freecad_installed"
# Lock file for atomic operations (prevents race conditions in parallel CI)
LOCK_FILE="$APPIMAGE_DIR/.freecad_install.lock"
# Derive APPIMAGE_PATH early for cleanup function
APPIMAGE_PATH="$APPIMAGE_DIR/FreeCAD.AppImage"

# Track whether installation completed successfully
INSTALL_SUCCESSFUL=false

# Cleanup function to remove partial artifacts on failure
cleanup_on_error() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]] && [[ "$INSTALL_SUCCESSFUL" != "true" ]]; then
        echo "ERROR: Installation failed (exit code $exit_code), cleaning up partial artifacts..."
        rm -f "$MARKER_FILE" 2>/dev/null || true
        rm -f "$APPIMAGE_PATH" 2>/dev/null || true
        rm -rf "$APPIMAGE_DIR/squashfs-root" 2>/dev/null || true
        rm -f "$LOCK_FILE" 2>/dev/null || true
    fi
}
trap cleanup_on_error EXIT

# Detect if running in CI environment
is_ci_environment() {
    # Check common CI environment variables
    [[ -n "${CI:-}" ]] || \
    [[ -n "${GITHUB_ACTIONS:-}" ]] || \
    [[ -n "${GITLAB_CI:-}" ]] || \
    [[ -n "${TRAVIS:-}" ]] || \
    [[ -n "${CIRCLECI:-}" ]] || \
    [[ -n "${JENKINS_URL:-}" ]] || \
    [[ -n "${BUILDKITE:-}" ]]
}

# In CI, require SHA256 checksum for security
if is_ci_environment && [[ -z "$APPIMAGE_SHA256" ]]; then
    echo "ERROR: APPIMAGE_SHA256 is required in CI environments for security verification"
    echo "Set the APPIMAGE_SHA256 environment variable to the expected checksum"
    exit 1
fi

echo "=== Setting up FreeCAD $FREECAD_TAG ==="

# Create directory for lock file
mkdir -p "$APPIMAGE_DIR"

# Use flock for atomic marker file operations (prevents race conditions in parallel CI)
# The lock is held for the entire installation process
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "Another installation is in progress, waiting for lock..."
    flock 200
    # Re-check marker file after acquiring lock (another process may have completed)
    if [[ -f "$MARKER_FILE" ]] && grep -q "^${FREECAD_TAG}$" "$MARKER_FILE" 2>/dev/null; then
        echo "FreeCAD $FREECAD_TAG already set up by another process, skipping"
        exit 0
    fi
fi

# Check for complete setup using marker file
if [[ -f "$MARKER_FILE" ]]; then
    # Verify marker file contains expected version
    if grep -q "^${FREECAD_TAG}$" "$MARKER_FILE" 2>/dev/null; then
        echo "FreeCAD $FREECAD_TAG already set up (marker file present), skipping"
        exit 0
    else
        echo "Different FreeCAD version detected, will reinstall"
    fi
fi

# Check for and clean up partial installations
PARTIAL_INSTALL=false
if [[ -f "/usr/local/bin/freecad" ]] && [[ ! -f "/usr/local/bin/freecadcmd" ]]; then
    echo "Warning: Partial installation detected (freecad exists but freecadcmd missing)"
    PARTIAL_INSTALL=true
elif [[ ! -f "/usr/local/bin/freecad" ]] && [[ -f "/usr/local/bin/freecadcmd" ]]; then
    echo "Warning: Partial installation detected (freecadcmd exists but freecad missing)"
    PARTIAL_INSTALL=true
fi

if [[ "$PARTIAL_INSTALL" == "true" ]]; then
    echo "Cleaning up partial installation..."
    # Remove wrapper scripts if they exist (use sudo if needed)
    if [[ $EUID -ne 0 ]] && command -v sudo &>/dev/null; then
        sudo rm -f /usr/local/bin/freecad /usr/local/bin/freecadcmd 2>/dev/null || true
    else
        rm -f /usr/local/bin/freecad /usr/local/bin/freecadcmd 2>/dev/null || true
    fi
    # Remove marker file to force full reinstall
    rm -f "$MARKER_FILE" 2>/dev/null || true
fi

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        ARCH_SUFFIX="x86_64"
        ;;
    aarch64|arm64)
        ARCH_SUFFIX="aarch64"
        ;;
    *)
        echo "ERROR: Unsupported architecture: $ARCH"
        exit 1
        ;;
esac
echo "Detected architecture: $ARCH -> Linux-$ARCH_SUFFIX"

# Use direct download URL to avoid GitHub API rate limits
# Format: FreeCAD_1.0.2-conda-Linux-aarch64-py311.AppImage
APPIMAGE_URL="https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_TAG}/FreeCAD_${FREECAD_TAG}-conda-Linux-${ARCH_SUFFIX}-py311.AppImage"
APPIMAGE_NAME="FreeCAD_${FREECAD_TAG}-conda-Linux-${ARCH_SUFFIX}-py311.AppImage"
# APPIMAGE_PATH is defined earlier for use in cleanup_on_error trap

echo "FreeCAD release: $FREECAD_TAG"
echo "AppImage URL: $APPIMAGE_URL"
echo "AppImage name: $APPIMAGE_NAME"

# Download
mkdir -p "$APPIMAGE_DIR"
if [ ! -f "$APPIMAGE_PATH" ]; then
    echo "Downloading FreeCAD AppImage..."
    curl -L --retry 3 --retry-delay 5 --retry-all-errors --connect-timeout 30 --max-time 600 \
        -f -o "$APPIMAGE_PATH" \
        "$APPIMAGE_URL"

    # Verify download succeeded and file exists
    if [[ ! -f "$APPIMAGE_PATH" ]]; then
        echo "ERROR: Download failed - file not found at $APPIMAGE_PATH"
        exit 1
    fi

    # Verify SHA256 checksum if provided
    if [[ -n "$APPIMAGE_SHA256" ]]; then
        echo "Verifying SHA256 checksum..."
        COMPUTED_SHA256=$(sha256sum "$APPIMAGE_PATH" | awk '{print $1}')
        if [[ "$COMPUTED_SHA256" != "$APPIMAGE_SHA256" ]]; then
            echo "ERROR: SHA256 checksum mismatch!"
            echo "  Expected: $APPIMAGE_SHA256"
            echo "  Computed: $COMPUTED_SHA256"
            echo "Removing corrupted/tampered download..."
            rm -f "$APPIMAGE_PATH"
            exit 1
        fi
        echo "SHA256 checksum verified successfully"
    else
        echo "Note: No APPIMAGE_SHA256 provided, skipping checksum verification"
    fi
fi
chmod +x "$APPIMAGE_PATH"

# Extract with proper error handling
cd "$APPIMAGE_DIR"
if [ ! -d "squashfs-root" ]; then
    echo "Extracting AppImage..."
    EXTRACTION_ERR=$(mktemp)
    # Capture exit code directly to avoid shell negation issues with $?
    EXTRACTION_EXIT_CODE=0
    ./FreeCAD.AppImage --appimage-extract > /dev/null 2>"$EXTRACTION_ERR" || EXTRACTION_EXIT_CODE=$?
    if [[ $EXTRACTION_EXIT_CODE -ne 0 ]]; then
        echo "ERROR: AppImage extraction failed with exit code $EXTRACTION_EXIT_CODE"
        if [[ -s "$EXTRACTION_ERR" ]]; then
            echo "Extraction stderr:"
            cat "$EXTRACTION_ERR"
        fi
        rm -f "$EXTRACTION_ERR"
        exit 1
    fi
    # Check for any stderr output even on success
    if [[ -s "$EXTRACTION_ERR" ]]; then
        echo "Warning: Extraction produced stderr output:"
        cat "$EXTRACTION_ERR"
    fi
    rm -f "$EXTRACTION_ERR"
fi

# Verify extraction produced expected structure
if [ ! -d "squashfs-root/usr/bin" ]; then
    echo "ERROR: Extracted AppImage missing expected structure (squashfs-root/usr/bin not found)"
    exit 1
fi

echo "Checking AppImage structure..."
# Display directory contents for diagnostic purposes (not parsed programmatically)
# shellcheck disable=SC2012 # ls output piped to head for display only, not parsed
ls -la "$APPIMAGE_DIR/squashfs-root/" 2>/dev/null | head -20

# Create wrapper scripts using AppRun
echo "Creating wrapper scripts..."

# Derive APPDIR_PATH from APPIMAGE_DIR for consistency
APPDIR_PATH="$APPIMAGE_DIR/squashfs-root"

# Helper function to install wrapper script
# Uses sudo only if necessary (not root and sudo exists)
install_wrapper() {
    local wrapper_name="$1"
    local wrapper_content="$2"
    local wrapper_path="/usr/local/bin/$wrapper_name"
    local temp_file

    temp_file=$(mktemp)
    echo "$wrapper_content" > "$temp_file"
    chmod +x "$temp_file"

    # Install with sudo if not root and sudo is available
    if [[ $EUID -ne 0 ]]; then
        if command -v sudo &>/dev/null; then
            sudo mv "$temp_file" "$wrapper_path"
            sudo chmod +x "$wrapper_path"
        else
            echo "ERROR: Not running as root and sudo not available, cannot install to $wrapper_path"
            rm -f "$temp_file"
            exit 1
        fi
    else
        mv "$temp_file" "$wrapper_path"
        chmod +x "$wrapper_path"
    fi
}

# freecadcmd wrapper - avoid trailing colon in LD_LIBRARY_PATH
FREECADCMD_WRAPPER="#!/bin/bash
export APPDIR=\"$APPDIR_PATH\"
export LD_LIBRARY_PATH=\"\$APPDIR/usr/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}\"
exec \"\$APPDIR/usr/bin/freecadcmd\" \"\$@\""

install_wrapper "freecadcmd" "$FREECADCMD_WRAPPER"

# freecad (GUI) wrapper - avoid trailing colon in LD_LIBRARY_PATH
FREECAD_WRAPPER="#!/bin/bash
export APPDIR=\"$APPDIR_PATH\"
export LD_LIBRARY_PATH=\"\$APPDIR/usr/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}\"
exec \"\$APPDIR/usr/bin/freecad\" \"\$@\""

install_wrapper "freecad" "$FREECAD_WRAPPER"

echo "Wrapper scripts created at /usr/local/bin/freecad{,cmd}"

# Verify installation - fail the script if verification fails
# Use explicit paths to avoid PATH resolution issues
echo "=== Verifying FreeCAD installation ==="

# Check wrapper exists before running
if [[ ! -x /usr/local/bin/freecadcmd ]]; then
    echo "ERROR: freecadcmd wrapper not found or not executable at /usr/local/bin/freecadcmd"
    exit 1
fi

echo "--- freecadcmd --version ---"
if ! /usr/local/bin/freecadcmd --version; then
    echo "ERROR: freecadcmd version check failed"
    exit 1
fi

echo "--- freecadcmd Python test ---"
if ! /usr/local/bin/freecadcmd -c "import sys; print(f'FreeCAD Python: {sys.version}')"; then
    echo "ERROR: FreeCAD Python test failed"
    exit 1
fi

echo "--- FreeCAD module import test ---"
if ! /usr/local/bin/freecadcmd -c "import FreeCAD; print(f'FreeCAD version: {FreeCAD.Version()}')"; then
    echo "ERROR: FreeCAD module import failed - FreeCAD bindings may be missing or corrupted"
    exit 1
fi

# Create marker file to indicate successful installation
echo "$FREECAD_TAG" > "$MARKER_FILE"
echo "Created marker file: $MARKER_FILE"

# Mark installation as successful (prevents cleanup_on_error from removing artifacts)
INSTALL_SUCCESSFUL=true

echo "=== FreeCAD setup complete ==="
