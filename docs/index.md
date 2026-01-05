# FreeCAD MCP Server

Welcome to the FreeCAD MCP Server documentation.

This project provides an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that enables integration between AI assistants (Claude, GPT, and other MCP-compatible tools) and [FreeCAD](https://www.freecadweb.org/), allowing AI-assisted development and debugging of 3D models, macros, and workbenches.

## Documentation

| Document                                      | Description                                            |
| --------------------------------------------- | ------------------------------------------------------ |
| [README](../README.md)                        | Project overview, installation, and configuration      |
| [User Guide](USER_GUIDE.md)                   | How to use AI assistants with FreeCAD for CAD modeling |
| [MCP Tools Reference](MCP_TOOLS_REFERENCE.md) | Complete API reference for all 82+ MCP tools           |
| [Architecture](../ARCHITECTURE-MCP.md)        | Technical design and module structure                  |
| [Comparison](COMPARISON.md)                   | Analysis of other FreeCAD MCP implementations          |
| [CLAUDE.md](../CLAUDE.md)                     | AI assistant guidelines for this project               |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/spkane/freecad-robust-mcp-and-more.git
cd freecad-robust-mcp-and-more
mise install
just setup

# Start FreeCAD with MCP bridge
just install-bridge-macro
just run-gui

# Run the MCP server (in another terminal or via your MCP client)
FREECAD_MODE=xmlrpc freecad-mcp
```

See the [README](../README.md) for detailed installation and configuration instructions.

## Features

- **82+ MCP Tools**: Comprehensive CAD operations including primitives, PartDesign, booleans, export
- **Multiple Connection Modes**: XML-RPC (recommended), JSON-RPC socket, or embedded
- **GUI & Headless Support**: Full modeling in headless mode, plus screenshots/colors in GUI mode
- **Macro Development**: Create, edit, run, and template FreeCAD macros
- **PartDesign Workflow**: Parametric modeling with sketches, pads, pockets, fillets, patterns

## Connection Modes

| Mode       | Description                  | Platform                    |
| ---------- | ---------------------------- | --------------------------- |
| `xmlrpc`   | XML-RPC protocol (port 9875) | All platforms (recommended) |
| `socket`   | JSON-RPC socket (port 9876)  | All platforms               |
| `embedded` | In-process FreeCAD           | Linux only                  |

## FreeCAD Macros

This project includes standalone FreeCAD macros:

- **[StartMCPBridge](../macros/Start_MCP_Bridge/)** - Starts the MCP bridge server for AI assistant integration
- **[CutObjectForMagnets](../macros/Cut_Object_for_Magnets/)** - Cuts objects along planes with automatic magnet hole placement
