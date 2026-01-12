# FreeCAD Robust MCP Suite

Welcome to the FreeCAD Robust MCP Suite documentation.

This project provides an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server, FreeCAD workbench, and standalone macros that enable integration between AI assistants (Claude, GPT, and other MCP-compatible tools) and [FreeCAD](https://www.freecadweb.org/), allowing AI-assisted development and debugging of 3D models, macros, and workbenches.

---

## Features

- **82+ MCP Tools** - Comprehensive CAD operations including primitives, PartDesign, booleans, export
- **Multiple Connection Modes** - XML-RPC (recommended), JSON-RPC socket, or embedded (Linux only)
- **GUI & Headless Support** - Full modeling in headless mode, plus screenshots/colors in GUI mode
- **Macro Development** - Create, edit, run, and template FreeCAD macros via MCP
- **Standalone Macros** - Useful FreeCAD macros that work independently of the Robust MCP Server

---

## Quick Start

```bash
# Install the Robust MCP Server
pip install freecad-robust-mcp

# Install the workbench via FreeCAD Addon Manager
# (search for "Robust MCP" - the package is "FreeCAD Robust MCP Suite")

# Start FreeCAD and switch to the "Robust MCP Bridge" workbench
# Click "Start Bridge" in the toolbar

# Configure your MCP client and start building!
```

See [Installation](getting-started/installation.md) for detailed setup instructions.

---

## Connection Modes

| Mode       | Description                  | Platform                    |
| ---------- | ---------------------------- | --------------------------- |
| `xmlrpc`   | XML-RPC protocol (port 9875) | All platforms (recommended) |
| `socket`   | JSON-RPC socket (port 9876)  | All platforms               |
| `embedded` | In-process FreeCAD           | Linux only                  |

See [Connection Modes](guide/connection-modes.md) for details on choosing the right mode.

---

## GUI vs Headless Mode

The Robust MCP Server works with FreeCAD in both GUI and headless mode:

| Feature                  | Headless | GUI |
| ------------------------ | -------- | --- |
| Object creation          | Yes      | Yes |
| Boolean operations       | Yes      | Yes |
| Export (STEP, STL, etc.) | Yes      | Yes |
| Screenshots              | No       | Yes |
| Object colors/visibility | No       | Yes |
| Camera control           | No       | Yes |

---

## FreeCAD Macros

This project includes standalone FreeCAD macros:

- **[CutObjectForMagnets](guide/macros.md#cutobjectformagnets)** - Cuts objects along planes with automatic magnet hole placement
- **[MultiExport](guide/macros.md#multiexport)** - Export objects to multiple formats simultaneously

---

## Documentation

| Section                                            | Description                                       |
| -------------------------------------------------- | ------------------------------------------------- |
| [Getting Started](getting-started/installation.md) | Installation, configuration, and quick start      |
| [User Guide](guide/connection-modes.md)            | Connection modes, workbench, macros, and tools    |
| [Tools Reference](MCP_TOOLS_REFERENCE.md)          | Complete API reference for all 82+ MCP tools      |
| [API Reference](api/server.md)                     | Python API documentation                          |
| [Development](development/contributing.md)         | Contributing, architecture, and development setup |
| [Comparison](COMPARISON.md)                        | Compare with other FreeCAD MCP implementations    |

---

## Links

- [GitHub Repository](https://github.com/spkane/freecad-robust-mcp-and-more) - Source code and issue tracker
- [PyPI Package](https://pypi.org/project/freecad-robust-mcp/) - Python package for pip installation
- [Docker Hub](https://hub.docker.com/r/spkane/freecad-robust-mcp) - Pre-built Docker images

---

!!! tip "Share This Documentation"
    Direct link: **[https://spkane.github.io/freecad-robust-mcp-and-more/](https://spkane.github.io/freecad-robust-mcp-and-more/)**
