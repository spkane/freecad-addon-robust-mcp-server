# FreeCAD Robust MCP Server Comparison Analysis

This document analyzes existing FreeCAD Robust MCP server implementations to identify best practices and improvements for our architecture.

## Existing Implementations

### 1. [neka-nat/freecad-mcp](https://github.com/neka-nat/freecad-mcp) (380+ stars)

**Architecture:**

- XML-RPC server running inside FreeCAD (port 9875)
- Queue-based GUI communication for thread safety
- FastMCP-based MCP server connecting via XML-RPC

**Key Features:**

- `create_object()` supports Part::, Draft::, PartDesign::, Fem:: types
- `get_view()` captures screenshots with multiple perspectives
- `insert_part_from_library()` for part library access
- Smart screenshot handling (detects unsupported views like TechDraw)

**Strengths:**

- Thread-safe queue system for GUI operations
- Comprehensive object type support
- Screenshot capabilities with view selection
- Parts library integration

**Weaknesses:**

- XML-RPC only (no embedded/headless mode)
- No macro development tools
- Limited debugging capabilities

---

### 2. [jango-blockchained/mcp-freecad](https://github.com/jango-blockchained/mcp-freecad)

**Architecture:**

- 6 connection modes: Launcher, Server, Bridge, RPC, Wrapper, Mock
- FastMCP 2.13.0+ with FastAPI integration
- Multi-provider AI support (Claude, OpenAI, Google, OpenRouter)

**Key Features:**

- AppImage/AppRun launcher integration
- Connection recovery mechanisms
- Resource caching and performance diagnostics
- Modern GUI addon with real-time diagnostics

**Strengths:**

- Most flexible connection options
- Multi-AI provider support
- Performance monitoring
- Connection recovery/resilience

**Weaknesses:**

- Complex setup with many moving parts
- Heavier dependency footprint

---

### 3. [contextform/freecad-mcp](https://github.com/contextform/freecad-mcp)

**Architecture:**

- Node.js-based MCP bridge (`working_bridge.py`)
- AICopilot workbench integrated into FreeCAD
- Cross-platform installer (`freecad-mcp-setup`)

**Key Features:**

- 13 PartDesign operations (Pad, Revolution, Fillet, Chamfer, etc.)
- 18 Part operations (Primitives, Booleans, Transforms)
- 14 View control tools
- Automated installer with OS detection

**Strengths:**

- Most comprehensive CAD operation coverage
- Excellent PartDesign/Part workbench integration
- Easy installation process
- Demo showcasing full workflow (house modeling)

**Weaknesses:**

- Node.js dependency adds complexity
- Less focus on debugging/development workflows

---

### 4. [ATOI-Ming/FreeCAD-MCP](https://github.com/ATOI-Ming/FreeCAD-MCP)

**Architecture:**

- Server-client with stdio/TCP (port 9876)
- GUI control panel inside FreeCAD
- Macro-centric workflow

**Key Features:**

- Macro templates (default, basic, part, sketch)
- Automatic import injection in macros
- Macro validation before execution
- View control (front, top, right, axonometric)
- Log management and report browser

**Strengths:**

- Focus on macro development workflow
- GUI panel for easy control
- Automatic boilerplate injection
- Comprehensive logging

**Weaknesses:**

- Macro-only focus (no direct object creation)
- Windows-centric paths in documentation

---

### 5. [bonninr/freecad_mcp](https://github.com/bonninr/freecad_mcp)

**Architecture:**

- Simple socket-based server
- Two primary tools: `get_scene_info` and `run_script`

**Key Features:**

- Comprehensive scene information retrieval
- Arbitrary Python code execution
- Minimal, focused API

**Strengths:**

- Simple, easy to understand
- Full Python access via `run_script`
- Lightweight

**Weaknesses:**

- Very minimal tool set
- No specialized CAD operations

---

## Feature Comparison Matrix

| Feature             | neka-nat | jango | contextform | ATOI-Ming | bonninr | **Ours** |
| ------------------- | -------- | ----- | ----------- | --------- | ------- | -------- |
| Headless mode       | No       | Yes   | No          | No        | No      | **Yes**  |
| GUI mode            | Yes      | Yes   | Yes         | Yes       | Yes     | **Yes**  |
| XML-RPC             | Yes      | Yes   | No          | No        | No      | **Yes**  |
| Socket/TCP          | No       | Yes   | No          | Yes       | Yes     | **Yes**  |
| Embedded Python     | No       | No    | No          | No        | No      | **Yes**  |
| Screenshot capture  | Yes      | Yes   | Yes         | No        | No      | **Yes**  |
| Parts library       | Yes      | No    | No          | No        | No      | **Yes**  |
| Macro support       | No       | No    | No          | Yes       | No      | **Yes**  |
| PartDesign tools    | Basic    | Yes   | Yes         | Via macro | No      | **Yes**  |
| Boolean operations  | Yes      | Yes   | Yes         | Via macro | No      | **Yes**  |
| FEM support         | Yes      | No    | No          | No        | No      | **Yes**  |
| Multi-AI provider   | No       | Yes   | No          | No        | No      | No       |
| Connection recovery | No       | Yes   | No          | No        | No      | **Yes**  |
| Thread-safe GUI ops | Yes      | Yes   | Unknown     | Unknown   | Unknown | **Yes**  |
| MCP Resources       | No       | No    | No          | No        | No      | **Yes**  |
| MCP Prompts         | No       | No    | No          | No        | No      | **Yes**  |

---

## Key Learnings & Improvements for Our Architecture

### 1. Communication Protocol

**Learning:** neka-nat uses XML-RPC which is proven and reliable.

**Improvement:** Support both XML-RPC (for compatibility) and JSON-RPC over sockets (simpler, more modern). Add embedded mode for true headless operation.

### 2. Thread-Safe GUI Operations

**Learning:** neka-nat's queue-based system is essential for GUI stability.

**Improvement:** Implement similar queue system with Qt timer for main thread execution:

```python
# Queue-based GUI communication
rpc_request_queue = queue.Queue()
rpc_response_queue = queue.Queue()

def process_gui_tasks():
    """Execute queued operations on main GUI thread."""
    while not rpc_request_queue.empty():
        task = rpc_request_queue.get()
        result = task()
        rpc_response_queue.put(result)
```

### 3. Screenshot Capabilities

**Learning:** neka-nat handles unsupported view types gracefully.

**Improvement:** Add comprehensive view support with intelligent fallbacks:

- Multiple view angles (Isometric, Front, Top, Right, etc.)
- View type detection (skip TechDraw, Spreadsheet)
- Configurable resolution and format

### 4. Macro Development Focus

**Learning:** ATOI-Ming's macro-centric approach is unique and valuable.

**Improvement:** Add dedicated macro tools:

- `create_macro` with templates
- `validate_macro` for syntax checking
- `run_macro` with parameter passing
- Automatic import injection

### 5. PartDesign Integration

**Learning:** contextform has the most comprehensive PartDesign coverage.

**Improvement:** Add specialized PartDesign tools:

- Pad, Pocket, Revolution, Groove
- Fillet, Chamfer
- Hole (with standards support)
- LinearPattern, PolarPattern
- Mirrored

### 6. Connection Resilience

**Learning:** jango-blockchained has connection recovery mechanisms.

**Improvement:** Add connection health monitoring and auto-reconnect:

```python
async def maintain_connection(self):
    """Background task to maintain connection health."""
    while self._running:
        if not await self.is_connected():
            await self.reconnect()
        await asyncio.sleep(5)
```

### 7. Parts Library Integration

**Learning:** neka-nat provides access to FreeCAD parts library.

**Improvement:** Expose parts library with search and filtering.

### 8. Comprehensive Logging

**Learning:** ATOI-Ming has excellent logging with GUI browser.

**Improvement:** Add structured logging with levels, rotation, and optional GUI viewer in plugin.

---

## Updated Architecture Decisions

Based on this analysis, our architecture will:

1. **Support 3 connection modes:**

   - Embedded (headless, in-process FreeCAD)
   - XML-RPC (proven, compatible with neka-nat addon)
   - JSON-RPC over socket (modern, simpler)

1. **Implement queue-based GUI thread safety** following neka-nat's pattern

1. **Provide comprehensive tool coverage:**

   - Execution: Python, macros
   - Documents: create, open, save, list
   - Objects: create, edit, delete, query
   - PartDesign: pad, pocket, fillet, chamfer, patterns
   - Part: primitives, booleans, transforms
   - Export: STEP, STL, OBJ, FreeCAD native
   - View: screenshot, camera control

1. **Add unique features:**

   - MCP Resources for document introspection
   - MCP Prompts for guided workflows
   - Macro development toolkit
   - Workbench-specific tools

1. **Focus on developer experience:**

   - Debugging tools
   - Error introspection
   - Console history access
   - Constraint validation

---

## Sources

- [neka-nat/freecad-mcp](https://github.com/neka-nat/freecad-mcp)
- [jango-blockchained/mcp-freecad](https://github.com/jango-blockchained/mcp-freecad)
- [contextform/freecad-mcp](https://github.com/contextform/freecad-mcp)
- [ATOI-Ming/FreeCAD-MCP](https://github.com/ATOI-Ming/FreeCAD-MCP)
- [bonninr/freecad_mcp](https://github.com/bonninr/freecad_mcp)
