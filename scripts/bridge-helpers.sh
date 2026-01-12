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
