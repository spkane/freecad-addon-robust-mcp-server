# FreeCAD `--no-splash` Flag Causes Immediate Exit When Running Scripts

---

## TL;DR (GitHub Issue Version)

**Bug**: `freecad --no-splash script.py` exits immediately with code 1 without executing the script. Without `--no-splash`, the same command works correctly.

**Environment**: FreeCAD 1.0.2 AppImage, Ubuntu 22.04, Xvfb + openbox

**Reproduce**:

```bash
# This exits immediately with code 1 (script never runs):
freecad --no-splash /path/to/script.py

# This works correctly:
freecad /path/to/script.py
```

**Workaround**: Don't use `--no-splash` when running Python scripts with FreeCAD GUI.

---

## Detailed Report

## Summary

The `--no-splash` flag causes FreeCAD GUI to exit immediately (exit code 1) when a Python script is passed as an argument. The script is never executed. Removing the `--no-splash` flag allows the script to run normally.

This was discovered while debugging FreeCAD GUI tests in CI environments.

## Environment

- **FreeCAD version**: 1.0.2 (conda AppImage)
- **Platform**: Linux (Ubuntu 22.04)
- **AppImage**: `FreeCAD_1.0.2-conda-Linux-x86_64-py311.AppImage`
- **Display**: Xvfb + openbox window manager
- **Context**: GitHub Actions CI, Docker containers

## Steps to Reproduce

### Setup

```bash
# Start Xvfb and openbox (required for FreeCAD GUI)
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 2
export DISPLAY=:99
openbox &
sleep 1

# Create a simple test script
cat > /tmp/test.py << 'EOF'
import FreeCAD
print(f"FreeCAD loaded, GuiUp={FreeCAD.GuiUp}")
with open("/tmp/result.txt", "w") as f:
    f.write("SUCCESS\n")
import sys
sys.exit(0)
EOF
```

### Reproduction (fails)

```bash
freecad --no-splash /tmp/test.py
echo "Exit code: $?"
cat /tmp/result.txt  # File doesn't exist - script never ran
```

**Output**:

```text
Exit code: 1
cat: /tmp/result.txt: No such file or directory
```

### Working alternative

```bash
freecad /tmp/test.py
echo "Exit code: $?"
cat /tmp/result.txt
```

**Output**:

```text
FreeCAD 1.0.2, Libs: 1.0.2R39319 (Git)
...
FreeCAD loaded, GuiUp=1
Exit code: 0  (or non-zero due to exit crash, but script ran)
SUCCESS
```

## Expected Behavior

`freecad --no-splash script.py` should:

1. Suppress the splash screen
2. Execute the Python script
3. Exit with the script's exit code

## Actual Behavior

`freecad --no-splash script.py`:

1. Exits immediately with code 1
2. Does not execute the Python script
3. Produces no output or error message

## Notes

- `freecad --no-splash --version` also appears to have issues
- `freecad --no-splash -c "print('hello')"` may also be affected
- The `freecadcmd` (headless) binary does not have this issue
- This is separate from the window manager hang bug (which affects bare Xvfb without openbox)

## Workaround

Simply omit the `--no-splash` flag when running scripts:

```bash
# Instead of:
freecad --no-splash /path/to/script.py  # FAILS

# Use:
freecad /path/to/script.py  # WORKS
```

The splash screen will appear briefly but the script will execute correctly.

## Impact

This affects:

- CI/CD pipelines that use `--no-splash` for cleaner output
- Automated scripts that suppress the splash screen
- Docker containers running FreeCAD with scripts

## Related

- This is a separate issue from the FreeCAD GUI hang without window manager
- The `freecadcmd` binary is not affected (it has no splash screen)
