# Robust MCP Bridge Workbench

The Robust MCP Bridge Workbench is a FreeCAD addon that provides the server-side connection point for the Robust MCP Server. It runs inside FreeCAD and exposes XML-RPC and JSON-RPC interfaces.

---

## Overview

The workbench provides:

- **Toolbar controls** for starting/stopping the MCP bridge
- **Status indicator** showing connection state
- **XML-RPC server** on port 9875 (default)
- **JSON-RPC socket server** on port 9876 (default)
- **Headless mode support** for automation and CI/CD

---

## Installation

### Via FreeCAD Addon Manager (Recommended)

1. Open FreeCAD
1. Go to **Tools > Addon Manager**
1. Search for "FreeCAD MCP and More" or "Robust MCP Bridge"
1. Click **Install**
1. Restart FreeCAD

### Manual Installation

Download from [GitHub Releases](https://github.com/spkane/freecad-robust-mcp-and-more/releases) and extract to your FreeCAD Mod directory:

- **Linux:** `~/.local/share/FreeCAD/Mod/FreecadRobustMCP/`
- **macOS:** `~/Library/Application Support/FreeCAD/Mod/FreecadRobustMCP/`
- **Windows:** `%APPDATA%\FreeCAD\Mod\FreecadRobustMCP\`

---

## GUI Mode Usage

### Starting the Bridge

1. Switch to the **MCP Bridge** workbench in FreeCAD
1. Click **Start Bridge** in the toolbar
1. The status indicator turns green when running

You'll see a confirmation message:

```text
MCP Bridge started!
  - XML-RPC: localhost:9875
  - Socket: localhost:9876
```

### Stopping the Bridge

Click **Stop Bridge** in the toolbar. The status indicator turns red.

### Status Indicator

| Color  | Status                                |
| ------ | ------------------------------------- |
| Green  | Bridge running, accepting connections |
| Red    | Bridge stopped                        |
| Yellow | Bridge starting/stopping              |

---

## Headless Mode Usage

The workbench includes a headless server script for running without the FreeCAD GUI.

### Starting Headless Mode

**Linux:**

```bash
freecadcmd ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/headless_server.py
```

**macOS:**

```bash
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
    ~/Library/Application\ Support/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/headless_server.py
```

**Using just commands (from source):**

```bash
just freecad::run-headless
```

### Headless Output

```text
FreeCAD version: 1.0.0
============================================================
MCP Bridge started in headless mode!
  - XML-RPC: localhost:9875
  - Socket: localhost:9876

Note: Screenshot and view features are not available in headless mode.
Press Ctrl+C to stop.
============================================================
```

---

## Features Available by Mode

| Feature                  | GUI Mode | Headless Mode |
| ------------------------ | -------- | ------------- |
| Object creation          | Yes      | Yes           |
| Boolean operations       | Yes      | Yes           |
| Export (STEP, STL, etc.) | Yes      | Yes           |
| Macro execution          | Yes      | Yes           |
| Document management      | Yes      | Yes           |
| Screenshots              | Yes      | **No**        |
| Object colors            | Yes      | **No**        |
| Object visibility        | Yes      | **No**        |
| Camera/view control      | Yes      | **No**        |
| Interactive selection    | Yes      | **No**        |

!!! info "GUI-Only Features"
When a GUI-only feature is requested in headless mode, the Robust MCP Server returns a structured error response instead of crashing: `{"success": false, "error": "GUI not available - screenshots cannot be captured in headless mode"}`

---

## Configuration

The workbench uses default ports that can be customized in the Robust MCP Server configuration:

| Server  | Default Port | Environment Variable  |
| ------- | ------------ | --------------------- |
| XML-RPC | 9875         | `FREECAD_XMLRPC_PORT` |
| Socket  | 9876         | `FREECAD_SOCKET_PORT` |

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    FreeCAD (GUI or Headless)                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Robust MCP Bridge Workbench/Plugin          │  │
│  │  ┌─────────────────┐  ┌─────────────────┐             │  │
│  │  │ XML-RPC Server  │  │ Socket Server   │             │  │
│  │  │   (port 9875)   │  │   (port 9876)   │             │  │
│  │  └────────┬────────┘  └────────┬────────┘             │  │
│  │           │                    │                       │  │
│  │           └────────┬───────────┘                       │  │
│  │                    │                                   │  │
│  │           ┌────────▼────────┐                          │  │
│  │           │ FreecadMCPPlugin│                          │  │
│  │           │ (Thread-safe    │                          │  │
│  │           │  queue system)  │                          │  │
│  │           └────────┬────────┘                          │  │
│  │                    │                                   │  │
│  │           ┌────────▼────────┐                          │  │
│  │           │ FreeCAD Python  │                          │  │
│  │           │     Console     │                          │  │
│  │           └─────────────────┘                          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ Network (localhost)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           FreeCAD Robust MCP Server (External Process)      │
└─────────────────────────────────────────────────────────────┘
```

The workbench uses a **queue-based thread safety system** to ensure FreeCAD operations run on the main GUI thread, preventing crashes from thread-unsafe operations.

---

## Troubleshooting

### Bridge Won't Start

**Problem:** Clicking "Start Bridge" does nothing or shows an error.

**Solution:**

1. Check the FreeCAD Python console for error messages
1. Ensure no other process is using ports 9875/9876
1. Try restarting FreeCAD

### Connection Refused from Robust MCP Server

**Problem:** Robust MCP Server reports "Connection refused"

**Solution:**

1. Verify the bridge is running (green status indicator)
1. Check that ports match between workbench and Robust MCP Server config
1. If using Docker, ensure you're using `host.docker.internal` as the host

### Headless Mode Hangs

**Problem:** `FreeCADCmd` with headless server never outputs anything

**Solution:**

1. Ensure you're using `FreeCADCmd` (not `freecad`)
1. Check the script path is correct
1. Try running with `-c "print('test')"` first to verify FreeCAD works

---

## Included Macros

The addon bundle also includes standalone FreeCAD macros:

- **MultiExport** - Export objects to multiple formats simultaneously
- **CutObjectForMagnets** - Cut objects with aligned magnet holes for 3D printing

See [Macros](macros.md) for details.
