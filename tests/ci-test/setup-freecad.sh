#!/bin/bash
# Setup FreeCAD AppImage - replicates .github/actions/setup-freecad/action.yaml
set -e

FREECAD_TAG="${FREECAD_TAG:-1.0.2}"
APPIMAGE_DIR="$HOME/freecad-appimage"

echo "=== Setting up FreeCAD $FREECAD_TAG ==="

# Skip if already set up
if [ -d "$APPIMAGE_DIR/squashfs-root/usr/bin" ] && [ -f "/usr/local/bin/freecad" ]; then
    echo "FreeCAD already set up, skipping download"
    exit 0
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

echo "FreeCAD release: $FREECAD_TAG"
echo "AppImage URL: $APPIMAGE_URL"
echo "AppImage name: $APPIMAGE_NAME"

# Download
mkdir -p "$APPIMAGE_DIR"
if [ ! -f "$APPIMAGE_DIR/FreeCAD.AppImage" ]; then
    echo "Downloading FreeCAD AppImage..."
    curl -L --retry 3 --retry-delay 5 --connect-timeout 30 --max-time 600 \
        -f -o "$APPIMAGE_DIR/FreeCAD.AppImage" \
        "$APPIMAGE_URL"
fi
chmod +x "$APPIMAGE_DIR/FreeCAD.AppImage"

# Extract
cd "$APPIMAGE_DIR"
if [ ! -d "squashfs-root" ]; then
    echo "Extracting AppImage..."
    ./FreeCAD.AppImage --appimage-extract > /dev/null 2>&1
fi

# Verify
if [ ! -d "squashfs-root/usr/bin" ]; then
    echo "ERROR: Extracted AppImage missing expected structure"
    exit 1
fi

echo "Checking AppImage structure..."
ls -la "$APPIMAGE_DIR/squashfs-root/" | head -20

# Create wrapper scripts using AppRun
echo "Creating wrapper scripts..."

# Use fixed path for APPDIR (not $HOME which varies)
APPDIR_PATH="/root/freecad-appimage/squashfs-root"

# freecadcmd wrapper
cat > /usr/local/bin/freecadcmd << WRAPPER_EOF
#!/bin/bash
export APPDIR="$APPDIR_PATH"
export APPIMAGE_EXTRACT_AND_RUN=1
if [ -f "\$APPDIR/AppRun" ]; then
    exec "\$APPDIR/AppRun" freecadcmd "\$@"
else
    export LD_LIBRARY_PATH="\$APPDIR/usr/lib:\$LD_LIBRARY_PATH"
    exec "\$APPDIR/usr/bin/freecadcmd" "\$@"
fi
WRAPPER_EOF
chmod +x /usr/local/bin/freecadcmd

# freecad (GUI) wrapper
cat > /usr/local/bin/freecad << WRAPPER_EOF
#!/bin/bash
export APPDIR="$APPDIR_PATH"
export APPIMAGE_EXTRACT_AND_RUN=1
if [ -f "\$APPDIR/AppRun" ]; then
    exec "\$APPDIR/AppRun" freecad "\$@"
else
    export LD_LIBRARY_PATH="\$APPDIR/usr/lib:\$LD_LIBRARY_PATH"
    exec "\$APPDIR/usr/bin/freecad" "\$@"
fi
WRAPPER_EOF
chmod +x /usr/local/bin/freecad

echo "Wrapper scripts created at /usr/local/bin/freecad{,cmd}"

# Verify installation
echo "=== Verifying FreeCAD installation ==="
echo "--- freecadcmd --version ---"
freecadcmd --version || echo "freecadcmd version check failed"

echo "--- freecadcmd Python test ---"
freecadcmd -c "import sys; print(f'FreeCAD Python: {sys.version}')" || echo "Python test failed"

echo "=== FreeCAD setup complete ==="
