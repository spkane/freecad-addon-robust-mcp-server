#!/bin/bash
# Run GUI tests with Xvfb + openbox - for testing FreeCAD GUI functionality
#
# FreeCAD GUI requires a window manager to generate expose/configure events.
# Without a WM, the GUI binary hangs during Qt initialization.
#
# Solution: Xvfb + openbox + xdotool events
#
set -e

echo "========================================"
echo "FreeCAD GUI Test Runner"
echo "========================================"

# Setup XDG_RUNTIME_DIR to avoid Qt warnings
export XDG_RUNTIME_DIR=/tmp/runtime-root
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Start Xvfb if not already running
if ! pgrep -x Xvfb > /dev/null; then
    echo "Starting Xvfb..."
    Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
    XVFB_PID=$!
    sleep 2
    if ! ps -p $XVFB_PID > /dev/null; then
        echo "ERROR: Xvfb failed to start"
        exit 1
    fi
    echo "Xvfb started on display :99 (PID: $XVFB_PID)"
else
    echo "Xvfb already running"
fi

export DISPLAY=:99
export QT_QPA_PLATFORM=xcb
export LIBGL_ALWAYS_SOFTWARE=1

# Start openbox window manager (required for FreeCAD GUI)
if ! pgrep -x openbox > /dev/null; then
    echo "Starting openbox window manager..."
    openbox &
    sleep 1
    echo "openbox started"
else
    echo "openbox already running"
fi

echo ""
echo "=== Environment ==="
echo "DISPLAY=$DISPLAY"
echo "QT_QPA_PLATFORM=$QT_QPA_PLATFORM"
echo "LIBGL_ALWAYS_SOFTWARE=$LIBGL_ALWAYS_SOFTWARE"
echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"

echo ""
echo "=== Test 1: Verify X11 display ==="
xdpyinfo -display :99 | head -5 || echo "Cannot connect to display :99"

echo ""
echo "=== Test 2: freecadcmd --version (headless) ==="
timeout 30 freecadcmd --version 2>&1 || echo "freecadcmd version check failed"

echo ""
echo "=== Test 3: FreeCAD GUI mode with openbox ==="
# Helper function to run FreeCAD GUI with xdotool events
run_freecad_gui() {
    local SCRIPT="$1"
    local TIMEOUT="${2:-30}"

    # Start FreeCAD
    if [ -n "$SCRIPT" ]; then
        freecad "$SCRIPT" > /tmp/fc_stdout.log 2>&1 &
    else
        freecad --version > /tmp/fc_stdout.log 2>&1 &
    fi
    local FC_PID
    FC_PID=$!

    # Send xdotool events to help initialization
    local START
    START=$(date +%s)
    while ps -p "$FC_PID" > /dev/null 2>&1; do
        local NOW
        NOW=$(date +%s)
        local ELAPSED=$((NOW - START))
        if [ "$ELAPSED" -gt "$TIMEOUT" ]; then
            echo "Timeout after ${TIMEOUT}s"
            kill "$FC_PID" 2>/dev/null || true
            return 124
        fi

        # Send synthetic events
        xdotool mousemove $((400 + ELAPSED*5)) $((300 + ELAPSED*5)) click 1 key Escape 2>/dev/null || true
        sleep 0.5
    done

    wait "$FC_PID" 2>/dev/null
    return $?
}

# Test basic GUI initialization
cat > /tmp/gui_test.py << 'PYEOF'
import FreeCAD
import sys

with open("/tmp/gui_result.txt", "w") as f:
    f.write(f"GuiUp: {FreeCAD.GuiUp}\n")
    f.write(f"Version: {FreeCAD.Version()}\n")

    if FreeCAD.GuiUp:
        import FreeCADGui
        f.write("GUI is available!\n")
        f.write(f"Workbenches: {len(FreeCADGui.listWorkbenches())}\n")
    else:
        f.write("GUI is NOT available\n")

sys.exit(0)
PYEOF

echo "Running GUI initialization test..."
run_freecad_gui /tmp/gui_test.py 30 || true  # FreeCAD may crash on exit, check result file
echo ""
echo "=== GUI Test Result ==="
if [ -f /tmp/gui_result.txt ]; then
    cat /tmp/gui_result.txt
    if grep -q "GUI is available" /tmp/gui_result.txt; then
        echo "GUI initialization test PASSED"
    else
        echo "GUI initialization test FAILED - GUI not available"
    fi
else
    echo "No result file (test failed to run)"
fi

echo ""
echo "=== Test 4: Full GUI functionality (screenshot, objects, etc.) ==="

cat > /tmp/full_gui_test.py << 'PYEOF'
import FreeCAD
import sys

results = []

try:
    results.append(f"GuiUp: {FreeCAD.GuiUp}")

    if not FreeCAD.GuiUp:
        results.append("ERROR: GUI not available")
        with open("/tmp/full_gui_result.txt", "w") as f:
            f.write("\n".join(results))
        sys.exit(1)

    import FreeCADGui
    import Part

    # Create a document with objects
    doc = FreeCAD.newDocument("GUITest")
    results.append(f"Document: {doc.Name}")

    # Create objects
    box = doc.addObject("Part::Box", "TestBox")
    box.Length = 50
    box.Width = 30
    box.Height = 20
    doc.recompute()
    results.append(f"Created: {box.Name} ({box.Length}x{box.Width}x{box.Height})")

    # Test view operations
    view = FreeCADGui.ActiveDocument.ActiveView
    results.append(f"ActiveView: {type(view).__name__}")

    FreeCADGui.SendMsgToActiveView("ViewFit")
    view.viewIsometric()
    results.append("ViewFit + Isometric: OK")

    # Screenshot
    view.saveImage("/tmp/screenshot.png", 800, 600, "Current")
    results.append("Screenshot: /tmp/screenshot.png")

    # ViewObject manipulation
    box_view = FreeCADGui.ActiveDocument.getObject("TestBox")
    if box_view:
        box_view.ShapeColor = (1.0, 0.0, 0.0)
        results.append("ShapeColor set to red: OK")

    # Save document
    doc.saveAs("/tmp/gui_test.FCStd")
    results.append("Document saved: /tmp/gui_test.FCStd")

    results.append("ALL TESTS PASSED")

except Exception as e:
    results.append(f"ERROR: {e}")
    import traceback
    results.append(traceback.format_exc())

with open("/tmp/full_gui_result.txt", "w") as f:
    f.write("\n".join(results))

sys.exit(0)
PYEOF

echo "Running full GUI test..."
run_freecad_gui /tmp/full_gui_test.py 45 || true  # FreeCAD may crash on exit, check result file
echo ""
echo "=== Full GUI Test Result ==="
if [ -f /tmp/full_gui_result.txt ]; then
    cat /tmp/full_gui_result.txt
    # Check if test passed
    if grep -q "ALL TESTS PASSED" /tmp/full_gui_result.txt; then
        echo "Full GUI test PASSED"
    else
        echo "Full GUI test FAILED"
    fi
else
    echo "No result file (test failed to run)"
fi

echo ""
echo "=== Files Created ==="
ls -la /tmp/screenshot.png /tmp/gui_test.FCStd 2>/dev/null || echo "Files not created"

echo ""
echo "=== Test 5: Start FreeCAD GUI with MCP bridge ==="
if [ -f "/workspace/addon/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py" ]; then
    echo "Starting FreeCAD with MCP bridge..."

    freecad /workspace/addon/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py > /tmp/freecad_bridge.log 2>&1 &
    FREECAD_PID=$!
    echo "FreeCAD PID: $FREECAD_PID"

    # Start xdotool events in background for this test
    (
        for j in {1..120}; do
            xdotool mousemove $((400 + j*3)) $((300 + j*3)) click 1 key Escape 2>/dev/null
            sleep 0.5
        done
    ) &
    XDOT_PID=$!

    # Wait for bridge to start
    BRIDGE_READY=0
    for i in {1..60}; do
        if ! ps -p "$FREECAD_PID" > /dev/null 2>&1; then
            echo "FreeCAD process died after ${i}s"
            break
        fi

        # Check for bridge
        if curl -s --max-time 1 -X POST \
            -H "Content-Type: text/xml" \
            -d '<?xml version="1.0"?><methodCall><methodName>system.listMethods</methodName></methodCall>' \
            http://localhost:9875 > /dev/null 2>&1; then
            echo "MCP bridge is ready after ${i}s!"
            BRIDGE_READY=1
            break
        fi

        if [ $((i % 10)) -eq 0 ]; then
            echo "Waiting... (${i}s)"
        fi

        sleep 1
    done

    if [ "$BRIDGE_READY" -eq 1 ]; then
        echo "=== Bridge Test: Execute Python ==="
        curl -s -X POST \
            -H "Content-Type: text/xml" \
            -d '<?xml version="1.0"?><methodCall><methodName>execute</methodName><params><param><value><string>_result_ = {"version": str(FreeCAD.Version()), "gui_up": FreeCAD.GuiUp}</string></value></param></params></methodCall>' \
            http://localhost:9875 | head -50
        echo ""
    fi

    echo ""
    echo "=== Bridge Log ==="
    cat /tmp/freecad_bridge.log 2>/dev/null | tail -30

    # Cleanup
    kill "$XDOT_PID" 2>/dev/null || true
    kill "$FREECAD_PID" 2>/dev/null || true
else
    echo "Bridge script not found - mount workspace with: docker run -v \$(pwd):/workspace ..."
fi

echo ""
echo "========================================"
echo "Tests complete"
echo "========================================"
