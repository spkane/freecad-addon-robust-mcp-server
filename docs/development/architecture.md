# Architecture

This document provides a technical overview of the FreeCAD MCP Server architecture.

For the full architecture document with design decisions and rationale, see [Detailed Architecture](architecture-detailed.md).

---

## Overview

The FreeCAD MCP Server follows a **Bridge with Adapter** pattern:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         MCP Server Layer                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     FastMCP Application                             │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │ │
│  │  │  Tools   │  │ Resources│  │  Prompts │  │ Lifecycle│           │ │
│  │  │ (82+)    │  │          │  │          │  │ Manager  │           │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    FreeCAD Bridge Interface                         │ │
│  │                    (Abstract Base Class)                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│           ╱               │               ╲                              │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐              │
│  │ EmbeddedBridge │ │  SocketBridge  │ │  XMLRPCBridge  │              │
│  │ (Linux only)   │ │ (JSON-RPC)     │ │ (Recommended)  │              │
│  └────────────────┘ └────────────────┘ └────────────────┘              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Module Structure

```text
src/freecad_mcp/
├── __init__.py            # Package entry point
├── _version.py            # Version info (auto-generated)
├── server.py              # Main MCP server entry point
├── config.py              # Configuration management
├── py.typed               # PEP 561 marker for type hints
│
├── bridge/                # FreeCAD communication layer
│   ├── __init__.py        # Bridge factory
│   ├── base.py            # Abstract bridge interface
│   ├── embedded.py        # In-process FreeCAD (Linux only)
│   ├── socket.py          # JSON-RPC socket bridge
│   └── xmlrpc.py          # XML-RPC bridge (recommended)
│
├── tools/                 # MCP tool implementations
│   ├── __init__.py
│   ├── execution.py       # Python execution & debugging
│   ├── documents.py       # Document management
│   ├── objects.py         # Object creation/manipulation
│   ├── partdesign.py      # PartDesign parametric modeling
│   ├── view.py            # View, camera, display
│   ├── export.py          # Export/import operations
│   └── macros.py          # Macro management
│
├── resources/             # MCP resource implementations
│   ├── __init__.py
│   └── freecad.py         # Document, console, capabilities
│
├── prompts/               # MCP prompt templates
│   ├── __init__.py
│   └── freecad.py         # Modeling and debugging prompts
│
└── utils/                 # Utility modules
    └── __init__.py
```

---

## Bridge Architecture

### Base Interface

All bridges implement `FreecadBridge`:

```python
class FreecadBridge(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def is_connected(self) -> bool: ...

    @abstractmethod
    async def execute_python(
        self, code: str, timeout_ms: int = 30000
    ) -> ExecutionResult: ...
```

### XML-RPC Bridge (Recommended)

- Connects to FreeCAD via XML-RPC on port 9875
- Proven, reliable protocol
- Works on all platforms

### Socket Bridge

- Uses JSON-RPC over TCP sockets on port 9876
- Lower overhead than XML-RPC
- Easier to debug (JSON format)

### Embedded Bridge

- Imports FreeCAD directly into the MCP server process
- **Linux only** (crashes on macOS/Windows)
- Fastest execution (no IPC overhead)
- Headless mode only

---

## Workbench Addon Architecture

The workbench addon runs inside FreeCAD:

```text
addon/FreecadRobustMCP/
├── Init.py                # Module initialization
├── InitGui.py             # GUI initialization (workbench)
├── FreecadRobustMCP.svg   # Workbench icon
└── freecad_mcp_bridge/    # Bridge plugin
    ├── __init__.py
    ├── server.py          # XML-RPC/JSON-RPC server
    └── headless_server.py # Headless mode launcher

package.xml                # FreeCAD addon metadata (in project root)
```

Note: The `package.xml` file is in the project root, not inside the addon directory. This is because it defines metadata for multiple components (workbench and macros) in a single manifest.

### Thread Safety

The workbench uses a queue-based system for thread-safe GUI operations:

```python
# Operations queued from network thread
request_queue.put(operation)

# Executed on main GUI thread via QTimer
def process_queue():
    while not request_queue.empty():
        op = request_queue.get()
        result = op()
        response_queue.put(result)
```

---

## Data Flow

### Tool Execution

```text
1. AI Assistant sends tool request
   ↓
2. MCP Server receives request
   ↓
3. Tool handler prepares Python code
   ↓
4. Bridge.execute_python() sends code
   ↓
5. FreeCAD executes code (main thread)
   ↓
6. Result returned via bridge
   ↓
7. MCP Server formats response
   ↓
8. AI Assistant receives result
```

### Code Execution Pattern

Tools generate Python code that runs in FreeCAD:

```python
@mcp.tool()
async def create_box(length: float = 10.0, ...) -> dict:
    bridge = await get_bridge()

    code = f'''
doc = FreeCAD.ActiveDocument or FreeCAD.newDocument("Unnamed")
obj = doc.addObject("Part::Box", "Box")
obj.Length = {length}
doc.recompute()
_result_ = {{"name": obj.Name, "volume": obj.Shape.Volume}}
'''

    result = await bridge.execute_python(code)
    return result.result
```

---

## GUI Detection

Tools check `FreeCAD.GuiUp` to handle headless mode:

```python
code = f'''
if not FreeCAD.GuiUp:
    _result_ = {{"success": False, "error": "GUI not available"}}
else:
    # GUI-only operations
    obj.ViewObject.Visibility = True
    _result_ = {{"success": True}}
'''
```

---

## Configuration

Configuration via environment variables:

| Variable              | Default     | Description                 |
| --------------------- | ----------- | --------------------------- |
| `FREECAD_MODE`        | `xmlrpc`    | Connection mode             |
| `FREECAD_PATH`        | auto        | FreeCAD lib path (embedded) |
| `FREECAD_SOCKET_HOST` | `localhost` | Socket/XML-RPC host         |
| `FREECAD_SOCKET_PORT` | `9876`      | JSON-RPC socket port        |
| `FREECAD_XMLRPC_PORT` | `9875`      | XML-RPC port                |
| `FREECAD_TIMEOUT_MS`  | `30000`     | Execution timeout           |

---

## Testing Strategy

### Unit Tests

- Mock FreeCAD module
- Test bridge logic in isolation
- Run on all platforms

### Integration Tests

- Use FreeCAD AppImage in CI
- Test actual FreeCAD operations
- Run in headless mode

### Embedded Mode Testing

Embedded mode receives **minimal testing**:

- Unit tests with mocked FreeCAD
- No CI integration tests (would require Linux + FreeCAD in-process)
- Recommended to use xmlrpc/socket modes for production

---

## Next Steps

- [Contributing](contributing.md) - How to contribute
- [Detailed Architecture](architecture-detailed.md) - Complete design details
