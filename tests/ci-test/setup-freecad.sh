#!/bin/bash
# Setup FreeCAD AppImage - replicates .github/actions/setup-freecad/action.yaml
set -euo pipefail

# Validate required variables have safe defaults
FREECAD_TAG="${FREECAD_TAG:-1.0.2}"
APPIMAGE_DIR="${APPIMAGE_DIR:-$HOME/freecad-appimage}"
FREECAD_BIN_DIR="${FREECAD_BIN_DIR-/usr/local/bin}"
FREECAD_APPIMAGE_URL="${FREECAD_APPIMAGE_URL:-}"
# Optional SHA256 checksum for verification (if provided, download will be verified)
APPIMAGE_SHA256="${FREECAD_APPIMAGE_SHA256:-${APPIMAGE_SHA256:-}}"

# Validate APPIMAGE_DIR is set and non-empty after defaults
if [[ -z "$APPIMAGE_DIR" ]]; then
    echo "ERROR: APPIMAGE_DIR is empty - cannot determine installation path"
    exit 1
fi

if [[ -z "$FREECAD_BIN_DIR" ]]; then
    echo "ERROR: FREECAD_BIN_DIR is empty - cannot determine wrapper path"
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

# Verify the cached AppImage when a digest is available. Callers decide whether
# a mismatch should trigger reinstall or stop the setup.
verify_appimage_checksum() {
    if [[ ! -f "$APPIMAGE_PATH" ]]; then
        echo "ERROR: AppImage not found at $APPIMAGE_PATH"
        return 1
    fi

    if [[ -z "$APPIMAGE_SHA256" ]]; then
        echo "Note: No APPIMAGE_SHA256 provided, skipping checksum verification"
        return 0
    fi

    echo "Verifying SHA256 checksum..."
    local computed_sha256
    computed_sha256=$(sha256sum "$APPIMAGE_PATH" | awk '{print $1}')
    if [[ "$computed_sha256" != "$APPIMAGE_SHA256" ]]; then
        echo "ERROR: SHA256 checksum mismatch!"
        echo "  Expected: $APPIMAGE_SHA256"
        echo "  Computed: $computed_sha256"
        return 1
    fi

    echo "SHA256 checksum verified successfully"
}

echo "=== Setting up FreeCAD $FREECAD_TAG ==="

# Create directory for lock file
mkdir -p "$APPIMAGE_DIR"

# Use flock for atomic marker file operations (prevents race conditions in parallel CI)
# The lock is held for the entire installation process
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "Another installation is in progress, waiting for lock..."
    flock 200
fi

# CI must never accept or install an AppImage that cannot be authenticated.
# Checked-in CI callers resolve the digest before invoking this script; local
# callers may still resolve it from the release API below.
if is_ci_environment && [[ -z "$APPIMAGE_SHA256" ]]; then
    echo "ERROR: A SHA256 digest is required in CI environments"
    exit 1
fi

# Check for complete setup using marker file. This also re-checks after waiting
# for the lock, because another process may have completed the installation.
if [[ -f "$MARKER_FILE" ]]; then
    # Verify marker file contains expected version
    if grep -q "^${FREECAD_TAG}$" "$MARKER_FILE" 2>/dev/null; then
        if verify_appimage_checksum; then
            if [[ -x "$FREECAD_BIN_DIR/freecad" ]] \
                && [[ -x "$FREECAD_BIN_DIR/freecadcmd" ]]; then
                echo "FreeCAD $FREECAD_TAG already set up (marker file present), skipping"
                exit 0
            fi
            echo "Cached FreeCAD AppImage verified but wrappers are missing, will recreate"
        else
            echo "Cached FreeCAD AppImage failed verification, will reinstall"
            rm -f "$APPIMAGE_PATH" "$MARKER_FILE"
            rm -rf "$APPIMAGE_DIR/squashfs-root"
        fi
    else
        echo "Different FreeCAD version detected, will reinstall"
        rm -f "$APPIMAGE_PATH" "$MARKER_FILE"
        rm -rf "$APPIMAGE_DIR/squashfs-root"
    fi
fi

# Check for and clean up partial installations
PARTIAL_INSTALL=false
if [[ -f "$FREECAD_BIN_DIR/freecad" ]] && [[ ! -f "$FREECAD_BIN_DIR/freecadcmd" ]]; then
    echo "Warning: Partial installation detected (freecad exists but freecadcmd missing)"
    PARTIAL_INSTALL=true
elif [[ ! -f "$FREECAD_BIN_DIR/freecad" ]] && [[ -f "$FREECAD_BIN_DIR/freecadcmd" ]]; then
    echo "Warning: Partial installation detected (freecadcmd exists but freecad missing)"
    PARTIAL_INSTALL=true
fi

if [[ "$PARTIAL_INSTALL" == "true" ]]; then
    echo "Cleaning up partial installation..."
    # Remove wrapper scripts if they exist (use sudo if needed)
    if [[ ! -w "$FREECAD_BIN_DIR" ]] && command -v sudo &>/dev/null; then
        sudo rm -f "$FREECAD_BIN_DIR/freecad" "$FREECAD_BIN_DIR/freecadcmd" 2>/dev/null || true
    else
        rm -f "$FREECAD_BIN_DIR/freecad" "$FREECAD_BIN_DIR/freecadcmd" 2>/dev/null || true
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

# CI supplies the release URL and digest resolved by the workflow. Local builds
# resolve the asset from the official release API so both legacy ``conda-``
# names and current stable/weekly names are supported.
if [[ -z "$FREECAD_APPIMAGE_URL" ]]; then
    RELEASE_INFO=$(curl -fsSL --retry 3 --retry-delay 2 --retry-all-errors \
        "https://api.github.com/repos/FreeCAD/FreeCAD/releases/tags/${FREECAD_TAG}")
    ASSET=$(jq -c --arg arch "$ARCH_SUFFIX" \
        '[.assets[] | select(.name | test("Linux-" + $arch + ".*\\.AppImage$"))][0]' \
        <<< "$RELEASE_INFO")
    FREECAD_APPIMAGE_URL=$(jq -r '.browser_download_url' <<< "$ASSET")
    ASSET_DIGEST=$(jq -r '.digest' <<< "$ASSET")

    if [[ -z "$APPIMAGE_SHA256" && "$ASSET_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
        APPIMAGE_SHA256="${ASSET_DIGEST#sha256:}"
    fi
fi

APPIMAGE_URL="$FREECAD_APPIMAGE_URL"
APPIMAGE_NAME=$(basename "$APPIMAGE_URL")

if [[ ! "$APPIMAGE_URL" =~ ^https://github.com/FreeCAD/FreeCAD/releases/download/ ]]; then
    echo "ERROR: Could not resolve an official FreeCAD AppImage for $FREECAD_TAG"
    exit 1
fi

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

fi

# Verify both fresh downloads and pre-existing files from partial setups.
if ! verify_appimage_checksum; then
    echo "Removing corrupted/tampered AppImage..."
    rm -f "$APPIMAGE_PATH"
    exit 1
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
# Uses sudo only when the selected wrapper directory is not writable.
install_wrapper() {
    local wrapper_name="$1"
    local wrapper_content="$2"
    local wrapper_path="$FREECAD_BIN_DIR/$wrapper_name"
    local temp_file

    temp_file=$(mktemp)
    echo "$wrapper_content" > "$temp_file"
    chmod +x "$temp_file"

    # Use direct writes for root or an explicitly writable test/install path.
    if [[ ! -w "$FREECAD_BIN_DIR" ]]; then
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

echo "Wrapper scripts created at $FREECAD_BIN_DIR/freecad{,cmd}"

# Verify installation - fail the script if verification fails
# Use explicit paths to avoid PATH resolution issues
echo "=== Verifying FreeCAD installation ==="

# Check wrapper exists before running
if [[ ! -x "$FREECAD_BIN_DIR/freecadcmd" ]]; then
    echo "ERROR: freecadcmd wrapper not found or not executable at $FREECAD_BIN_DIR/freecadcmd"
    exit 1
fi

echo "--- freecadcmd --version ---"
if ! "$FREECAD_BIN_DIR/freecadcmd" --version; then
    echo "ERROR: freecadcmd version check failed"
    exit 1
fi

echo "--- freecadcmd Python test ---"
if ! "$FREECAD_BIN_DIR/freecadcmd" -c "import sys; print(f'FreeCAD Python: {sys.version}')"; then
    echo "ERROR: FreeCAD Python test failed"
    exit 1
fi

echo "--- FreeCAD module import test ---"
if ! "$FREECAD_BIN_DIR/freecadcmd" -c "import FreeCAD; print(f'FreeCAD version: {FreeCAD.Version()}')"; then
    echo "ERROR: FreeCAD module import failed - FreeCAD bindings may be missing or corrupted"
    exit 1
fi

# Create marker file to indicate successful installation
echo "$FREECAD_TAG" > "$MARKER_FILE"
echo "Created marker file: $MARKER_FILE"

# Mark installation as successful (prevents cleanup_on_error from removing artifacts)
INSTALL_SUCCESSFUL=true

echo "=== FreeCAD setup complete ==="
