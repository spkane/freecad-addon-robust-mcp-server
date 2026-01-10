# FreeCAD GUI Binary Hangs in Headless CI Environments Without Window Manager

Bug Report: [github.com/FreeCAD/FreeCAD/issues/26817](https://github.com/FreeCAD/FreeCAD/issues/26817)

---

## TL;DR (GitHub Issue Version)

**Bug**: `freecad --version` hangs indefinitely when run with Xvfb but without a window manager. `freecadcmd --version` works fine.

**Environment**: FreeCAD 1.0.2 AppImage, Ubuntu 22.04, Xvfb

**Reproduce**:

```bash
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
./FreeCAD.AppImage --appimage-extract
./squashfs-root/AppRun freecad --version  # HANGS
./squashfs-root/AppRun freecadcmd --version  # Works
```

**Cause**: FreeCAD GUI requires window manager events to display any window (including the `--version` dialog box). Without a WM, Qt waits indefinitely for `ConfigureNotify`/`Expose` events that never arrive.

**Note**: Unlike most CLI tools, `freecad --version` displays a **GUI dialog**, not console output.

**Workaround**: Run `openbox &` before FreeCAD, or use `freecadcmd` for headless operations.

---

## Detailed Report

## Summary

The FreeCAD GUI binary (`freecad`) hangs indefinitely during Qt initialization when run in a headless environment with Xvfb but **without a window manager**. This affects all command-line operations including `freecad --version` and `freecad --help`. The headless binary (`freecadcmd`) works correctly in the same environment.

## Environment

- **FreeCAD versions tested**: 1.0.2 (stable), 1.1.0 (weekly-2025.09.03)
- **Platform**: Linux (Ubuntu 22.04, both x86_64 and aarch64)
- **AppImage**: `FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage`
- **Display**: Xvfb virtual framebuffer (`:99`, 1920x1080x24)
- **Qt platform**: xcb
- **Context**: GitHub Actions CI, Docker containers

## Steps to Reproduce

### Easiest reproduction using Docker (hangs)

This one-liner reproduces the bug in an isolated container:

```bash
# Run this on any system with Docker installed (Linux, macOS, Windows)
# Automatically selects the correct AppImage for your architecture (x86_64 or aarch64)
docker run --rm -it ubuntu:22.04 bash -c '
  apt-get update && apt-get install -y xvfb curl libfuse2 libgl1 libegl1 openbox >/dev/null 2>&1
  cd /tmp
  ARCH=$(uname -m)
  if [ "$ARCH" = "aarch64" ]; then
    APPIMAGE="FreeCAD_1.0.2-conda-Linux-aarch64-py311.AppImage"
  else
    APPIMAGE="FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage"
  fi
  echo "Downloading FreeCAD AppImage for $ARCH..."
  curl -sLO "https://github.com/FreeCAD/FreeCAD/releases/download/1.0.2/$APPIMAGE"
  chmod +x "$APPIMAGE"
  echo "Extracting AppImage..."
  ./"$APPIMAGE" --appimage-extract > /dev/null
  ls -la /tmp/squashfs-root/AppRun
  export XDG_RUNTIME_DIR=/tmp/runtime-root
  echo "Starting freecadcmd with xvfb-run (should work fine)..."
  xvfb-run -a /tmp/squashfs-root/AppRun freecadcmd --version || echo "This should have worked"
  echo "Starting FreeCAD with xvfb-run (will hang without window manager)..."
  timeout 10 xvfb-run -a /tmp/squashfs-root/AppRun freecad --version || echo "HUNG as expected (timeout after 10s)"
  Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
  sleep 2
  export DISPLAY=:99
  openbox &
  xvfb-run -a /tmp/squashfs-root/AppRun freecad --version
'
```

### Simplest reproduction using xvfb-run (hangs)

```bash
# Download FreeCAD AppImage
curl -LO "https://github.com/FreeCAD/FreeCAD/releases/download/1.0.2/FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage"
chmod +x FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage

# Extract AppImage (required because xvfb-run doesn't work well with FUSE)
./FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage --appimage-extract

# This hangs indefinitely - xvfb-run provides Xvfb but no window manager
xvfb-run --auto-servernum ./squashfs-root/AppRun freecad --version
```

The `xvfb-run` wrapper is commonly used in CI environments to run GUI applications headlessly. It starts Xvfb automatically, but does **not** start a window manager, causing FreeCAD to hang.

### Manual Xvfb reproduction (hangs)

```bash
# Start Xvfb without a window manager
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 2
export DISPLAY=:99
export QT_QPA_PLATFORM=xcb

# Extract and run FreeCAD AppImage
./FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage --appimage-extract
./squashfs-root/AppRun freecad --version  # HANGS INDEFINITELY
```

### Variants that also hang

```bash
# All of these hang:
./squashfs-root/AppRun freecad --help
./squashfs-root/AppRun freecad --version
./squashfs-root/AppRun freecad -c "print('hello')"
QT_QPA_PLATFORM=offscreen ./squashfs-root/AppRun freecad --version
QT_QPA_PLATFORM=minimal ./squashfs-root/AppRun freecad --version
```

### What works correctly

```bash
# Headless binary works fine:
./squashfs-root/AppRun freecadcmd --version  # Works immediately
./squashfs-root/AppRun freecadcmd -c "import FreeCAD; print(FreeCAD.Version())"  # Works
```

## Expected Behavior

FreeCAD GUI should work in headless CI environments with just Xvfb, allowing:

1. Display of version/help dialogs (FreeCAD uses GUI dialogs, not console output)
2. Execution of Python scripts
3. Basic GUI operations for automated testing

**Note**: Unlike most CLI tools, `freecad --version` and `freecad --help` display **GUI dialog boxes** rather than printing to the console. This is by design, but it means they require a functioning GUI environment.

## Actual Behavior

The `freecad` binary:

1. Connects to X11 display successfully
2. Initializes Qt's QApplication
3. Attempts to create/display a window (version dialog, main window, etc.)
4. Waits indefinitely for X11 window manager events that never arrive
5. Hangs before the dialog/window can be displayed

## Technical Analysis

### Process State During Hang

Using `strace` and `/proc` inspection, we found:

```text
Process state: S (sleeping)
Threads: 2
Thread 1 (main): waiting in do_sys_poll on eventfd
Thread 2 (X11 reader): waiting in do_sys_poll on X11 socket
```

### Strace Output

The final syscalls before the hang show both threads blocked on `ppoll()`:

```text
# Thread 21 (main Qt event loop) - waiting on eventfd with 30s timeout
[pid 21] ppoll([{fd=6, events=POLLIN}], 1, {tv_sec=29, tv_nsec=541000000}, NULL, 8

# Thread 22 (X11 reader) - waiting on X11 socket indefinitely
[pid 22] ppoll([{fd=4, events=POLLIN}], 1, NULL, NULL, 0 <unfinished ...>
```

The file descriptors are:

- fd 4: X11 socket connection (successfully established)
- fd 6: eventfd for Qt thread synchronization

### Root Cause

FreeCAD's GUI requires window manager events to display any window or dialog (including the `--version` dialog). In a bare Xvfb environment without a window manager:

1. FreeCAD creates a window and waits for it to be mapped/configured
2. No window manager means no `ConfigureNotify`, `Expose`, or `MapNotify` events
3. Qt's event loop waits for these events before the window can be displayed
4. The main thread blocks waiting for signals from the X11 reader thread
5. The X11 reader thread blocks waiting for X11 events that never arrive
6. Deadlock: both threads wait indefinitely for events that will never come

### Why `freecadcmd` Works

The `freecadcmd` binary does not initialize Qt's GUI components, so it never enters this blocking state.

## Workaround

Running a lightweight window manager (like `openbox`) alongside Xvfb resolves the issue:

```bash
# Start Xvfb
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 2
export DISPLAY=:99

# Start a window manager (this is the key fix)
openbox &
sleep 1

# Now FreeCAD GUI works
./squashfs-root/AppRun freecad --version  # Works!
```

Additionally, sending synthetic X11 events with `xdotool` can help:

```bash
# In a loop while FreeCAD starts:
xdotool mousemove 500 500 click 1 key Escape
```

## Suggested Fixes

Several approaches could improve FreeCAD's headless CI compatibility:

### Option 1: Add timeout/fallback for window manager events

FreeCAD could detect when no window manager responds within a reasonable timeout (e.g., 5 seconds) and either:

- Fall back to a minimal mode
- Exit with a clear error message instead of hanging indefinitely
- Use `QT_QPA_PLATFORM=offscreen` automatically when no WM is detected

### Option 2: Console output for `--version`/`--help` (CI-friendly)

For CI environments, having `--version` and `--help` output to console (like most CLI tools) would be helpful. This could be:

- A separate flag like `--version-console`
- Automatic when `DISPLAY` is not set or in a detected CI environment
- Controlled by an environment variable

### Option 3: Document the window manager requirement

At minimum, clearly document that the FreeCAD GUI binary requires a window manager (not just Xvfb) for any operation, including `--version`.

## Impact

This bug affects:

- **CI/CD pipelines** using FreeCAD in headless environments
- **Docker containers** running FreeCAD without a display manager
- **Automated testing** of FreeCAD-based applications
- **Server-side rendering** or batch processing with GUI features

The workaround (adding `openbox`) increases container size and complexity for CI environments.

## Additional Context

### Test Script

Here's a complete test script that demonstrates both the bug and the workaround:

```bash
#!/bin/bash
set -e

# Setup
apt-get update && apt-get install -y xvfb openbox xdotool curl
curl -LO "https://github.com/FreeCAD/FreeCAD/releases/download/1.0.2/FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage"
chmod +x FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage
./FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage --appimage-extract

export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 2

echo "=== Test 1: Without window manager (will hang) ==="
timeout 10 ./squashfs-root/AppRun freecad --version || echo "HUNG as expected"

echo "=== Test 2: With window manager (works) ==="
openbox &
sleep 1
timeout 10 ./squashfs-root/AppRun freecad --version && echo "SUCCESS"
```

### Related

- This may be related to how FreeCAD integrates with PySide6/Qt6
- The `freecadcmd` binary correctly avoids this issue by not initializing GUI
- Other Qt applications (like `qmlscene --help`) typically handle this correctly

## System Information

```text
FreeCAD 1.0.2, Libs: 1.0.2R39319 (Git)
OS: Ubuntu 22.04 (Docker/GitHub Actions)
Python: 3.11.13 (conda-forge)
Qt: 6.x (bundled in AppImage)
```
