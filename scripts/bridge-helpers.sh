#!/usr/bin/env bash
# Shared helper functions for FreeCAD MCP Bridge management
# Source this file in Just recipes: . ./scripts/bridge-helpers.sh

# Helper function to kill process on a port (with fallback for systems without lsof)
# Usage: kill_port PORT [SIGNAL]
# Examples: kill_port 9875      (sends SIGTERM)
#           kill_port 9875 -9   (sends SIGKILL)
kill_port() {
    local port=$1
    local signal=${2:--TERM}  # Default to SIGTERM if no signal specified
    local pids=""

    if command -v lsof &>/dev/null; then
        # Collect PIDs first, then kill only if non-empty
        pids=$(lsof -ti:"$port" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            echo "$pids" | xargs kill "$signal" 2>/dev/null || true
        fi
    elif command -v fuser &>/dev/null; then
        # fuser -k sends SIGKILL by default; use --signal for others
        # Check if port is in use first
        if fuser "$port/tcp" 2>/dev/null; then
            if [ "$signal" = "-9" ] || [ "$signal" = "-KILL" ]; then
                fuser -k "$port/tcp" 2>/dev/null || true
            else
                fuser -k --signal "${signal#-}" "$port/tcp" 2>/dev/null || true
            fi
        fi
    else
        echo "Warning: Neither lsof nor fuser available, cannot kill port $port"
    fi
}

# Check if the MCP bridge is running and responsive
# Returns 0 (true) if bridge is running, 1 (false) otherwise
is_bridge_running() {
    local port=${1:-9875}  # Default to port 9875
    curl -s --connect-timeout 1 --max-time 1 "http://localhost:$port" > /dev/null 2>&1 && \
    uv run python -c "import socket; socket.setdefaulttimeout(2); import xmlrpc.client; print(xmlrpc.client.ServerProxy('http://localhost:$port').ping())" 2>/dev/null | grep -q "pong"
}

# Force kill any processes on the default MCP bridge ports
# Usage: force_kill_bridge_ports
force_kill_bridge_ports() {
    kill_port 9875 -9
    kill_port 9876 -9
}

# Graceful shutdown of bridge ports (SIGTERM first, then SIGKILL)
# Usage: graceful_kill_bridge_ports
graceful_kill_bridge_ports() {
    kill_port 9875
    kill_port 9876
    sleep 1
    kill_port 9875 -9
    kill_port 9876 -9
}

# Check if a port is in use (has a process listening on it)
# Returns 0 (true) if port is in use, 1 (false) otherwise
# Usage: is_port_in_use PORT
is_port_in_use() {
    local port=$1
    if command -v lsof &>/dev/null; then
        lsof -ti:"$port" &>/dev/null
    elif command -v fuser &>/dev/null; then
        fuser "$port/tcp" &>/dev/null
    elif command -v ss &>/dev/null; then
        ss -tlnp "sport = :${port}" 2>/dev/null | grep -q "$port"
    else
        # Fall back to attempting a connection
        (echo >/dev/tcp/localhost/"$port") 2>/dev/null
    fi
}

# Wait until the bridge ports are free (no process listening)
# Usage: wait_for_ports_free [TIMEOUT_SECONDS]
wait_for_ports_free() {
    local timeout=${1:-30}
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if ! is_port_in_use 9875 && ! is_port_in_use 9876; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
        if [ $((elapsed % 5)) -eq 0 ]; then
            echo "  Waiting for bridge ports to be free... ($elapsed/${timeout}s)"
        fi
    done
    echo "WARNING: Bridge ports still in use after ${timeout}s timeout"
    return 1
}

# Wait until no FreeCAD processes are running.
# On macOS, FreeCAD's GUI process can linger after releasing ports
# (saving preferences, tearing down 3D viewer, deregistering from app services).
# Starting a new FreeCAD before the old one fully exits causes:
#   "Tried to run Gui::Application::initApplication() twice!" → SIGSEGV
# If the process is still alive after the timeout, send SIGTERM then SIGKILL.
# Usage: wait_for_freecad_exit [TIMEOUT_SECONDS]
wait_for_freecad_exit() {
    local timeout=${1:-30}
    local elapsed=0

    # Match by process name only (pgrep -i, without -f).
    # -f would match the full command line, falsely catching unrelated
    # processes whose arguments or cwd contain "freecad" (e.g. the calling
    # just recipe, shell scripts, or pytest).  Without -f, pgrep checks only
    # the executable basename: "freecad", "freecadcmd", "FreeCADCmd", etc.
    while [ $elapsed -lt $timeout ]; do
        if ! pgrep -i "freecad" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
        if [ $((elapsed % 5)) -eq 0 ]; then
            echo "  Waiting for FreeCAD process to exit... ($elapsed/${timeout}s)"
        fi
    done

    # Timed out — force-stop the lingering process.  This handles the case
    # where blocking_bridge.py releases its ports (so graceful_kill_bridge_ports
    # can no longer find it via lsof) but freecadcmd itself hasn't exited.
    echo "WARNING: FreeCAD process still running after ${timeout}s, sending SIGTERM..."
    pkill -i "freecad" 2>/dev/null || true
    sleep 2

    if pgrep -i "freecad" > /dev/null 2>&1; then
        echo "WARNING: FreeCAD still alive after SIGTERM, sending SIGKILL..."
        pkill -9 -i "freecad" 2>/dev/null || true
        sleep 1
    fi

    if pgrep -i "freecad" > /dev/null 2>&1; then
        echo "ERROR: Could not stop FreeCAD process"
        return 1
    fi
    return 0
}
