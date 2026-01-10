# Configuration

Configure the FreeCAD Robust MCP Server using environment variables and MCP client settings.

---

## Environment Variables

| Variable              | Description                                          | Default     |
| --------------------- | ---------------------------------------------------- | ----------- |
| `FREECAD_MODE`        | Connection mode: `xmlrpc`, `socket`, or `embedded`   | `xmlrpc`    |
| `FREECAD_PATH`        | Path to FreeCAD's lib directory (embedded mode only) | Auto-detect |
| `FREECAD_SOCKET_HOST` | Socket/XML-RPC server hostname                       | `localhost` |
| `FREECAD_SOCKET_PORT` | JSON-RPC socket server port                          | `9876`      |
| `FREECAD_XMLRPC_PORT` | XML-RPC server port                                  | `9875`      |
| `FREECAD_TIMEOUT_MS`  | Execution timeout in ms                              | `30000`     |

---

## Connection Modes

The Robust MCP Server supports three connection modes:

| Mode       | Description                                 | Platform Support                          |
| ---------- | ------------------------------------------- | ----------------------------------------- |
| `xmlrpc`   | Connects to FreeCAD via XML-RPC (port 9875) | **All platforms** (recommended)           |
| `socket`   | Connects via JSON-RPC socket (port 9876)    | **All platforms**                         |
| `embedded` | Imports FreeCAD directly into process       | **Linux only** (crashes on macOS/Windows) |

### XML-RPC Mode (Recommended)

The default and recommended mode. Works on all platforms.

```bash
export FREECAD_MODE=xmlrpc
freecad-mcp
```

### Socket Mode

Alternative to XML-RPC using JSON-RPC over TCP sockets.

```bash
export FREECAD_MODE=socket
freecad-mcp
```

### Embedded Mode (Linux Only)

!!! warning "Linux Only"
Embedded mode only works on Linux. On macOS and Windows, it will crash because FreeCAD's `FreeCAD.so` library links to its bundled Python, which conflicts with external Python interpreters.

Embedded mode imports FreeCAD directly into the Robust MCP Server process for fastest execution.

```bash
export FREECAD_MODE=embedded
export FREECAD_PATH=/usr/lib/freecad/lib
freecad-mcp
```

**Note:** Embedded mode testing is minimal. For production use, prefer `xmlrpc` or `socket` modes.

---

## MCP Client Configuration

### Claude Code / Claude Desktop

Add to `~/.claude/claude_desktop_config.json` or a project `.mcp.json` file:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "freecad-mcp",
      "env": {
        "FREECAD_MODE": "xmlrpc"
      }
    }
  }
}
```

If installed from source with mise/uv:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "/path/to/mise/shims/uv",
      "args": ["run", "--project", "/path/to/freecad-robust-mcp-and-more", "freecad-mcp"],
      "env": {
        "FREECAD_MODE": "xmlrpc"
      }
    }
  }
}
```

### Docker Configuration

```json
{
  "mcpServers": {
    "freecad": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "FREECAD_MODE=xmlrpc",
        "-e", "FREECAD_SOCKET_HOST=host.docker.internal",
        "spkane/freecad-robust-mcp"
      ]
    }
  }
}
```

---

## GUI vs Headless Mode

FreeCAD can run in two modes, and the Robust MCP Server works with both:

| Feature                  | Headless Mode | GUI Mode |
| ------------------------ | ------------- | -------- |
| Object creation          | Yes           | Yes      |
| Boolean operations       | Yes           | Yes      |
| Export (STEP, STL, etc.) | Yes           | Yes      |
| Save documents           | Yes           | Yes      |
| Screenshots              | No            | Yes      |
| Object colors            | No            | Yes      |
| Object visibility        | No            | Yes      |
| Camera control           | No            | Yes      |
| Interactive selection    | No            | Yes      |

### Starting FreeCAD

**GUI Mode** (for interactive work with visual feedback):

```bash
# Using just commands (from source)
just freecad::run-gui

# Or start FreeCAD normally and click "Start Bridge" in the workbench
```

**Headless Mode** (for automation, CI/CD, or when you don't need visual feedback):

```bash
# Using just commands (from source)
just freecad::run-headless

# Or run directly with FreeCADCmd
FreeCADCmd ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py
```

---

## Next Steps

- [Quick Start](quickstart.md) - Create your first model with AI assistance
- [Connection Modes](../guide/connection-modes.md) - Detailed guide on different connection modes
