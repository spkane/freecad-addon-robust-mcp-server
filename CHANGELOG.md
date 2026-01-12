# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This is a multi-component project. Each component has its own versioning and release cycle:

| Component                      | Tag Format                            | Distribution             |
| ------------------------------ | ------------------------------------- | ------------------------ |
| Robust MCP Server              | `robust-mcp-server-vX.Y.Z`            | PyPI, Docker Hub, GitHub |
| Robust MCP Bridge Workbench    | `robust-mcp-workbench-vX.Y.Z`         | GitHub Release           |
| Cut Object for Magnets Macro   | `macro-cut-object-for-magnets-vX.Y.Z` | GitHub Release           |
| Multi Export Macro             | `macro-multi-export-vX.Y.Z`           | GitHub Release           |

---

## [Unreleased]

### Robust MCP Server

#### Removed

- Docker detection fields (`in_docker`, `docker_container_id`) from `get_mcp_server_environment()` tool

### Robust MCP Bridge Workbench

#### Fixed

- Fixed GUI crashes during auto-start by deferring bridge initialization 2 seconds after `FreeCAD.GuiUp` becomes True
- Increased GUI wait timeout from 3 seconds to 60 seconds to accommodate slow FreeCAD startups on macOS
- Bridge no longer attempts to start on timeout (prevents crash from background thread usage)
- `startup_bridge.py` now has same defensive GUI wait logic as `Init.py`

### Cut Object for Magnets Macro

### Multi Export Macro

---

## Initial Public Beta - 2026-01-05

### Robust MCP Server v0.5.0-beta

Initial public beta release.

#### Added

- **Document management**: Create, open, save, close, recompute documents
- **Object manipulation**: Create primitives (box, cylinder, sphere, cone, torus, wedge, helix), boolean operations, transforms (scale, rotate, copy, mirror)
- **PartDesign workflow**: Bodies, sketches, pads, pockets, revolutions, fillets, chamfers, holes, patterns, lofts, sweeps
- **Import/Export**: STEP, STL, 3MF, OBJ, IGES, BREP formats
- **View control**: Screenshots, camera positioning, zoom, visibility, display modes
- **Macro support**: List, run, create, and manage FreeCAD macros
- **Undo/Redo**: Full undo/redo support with status queries
- **Connection modes**: XML-RPC (recommended), Socket, and Embedded (Linux only)

#### Installation

- **PyPI**: `pip install freecad-robust-mcp`
- **Docker**: `docker pull ghcr.io/spkane/freecad-robust-mcp`
- **Source**: Clone and install with `uv sync --all-extras`

#### Known Limitations

- Embedded mode only works on Linux (macOS/Windows must use xmlrpc or socket)
- Python 3.11 required (must match FreeCAD's bundled Python for ABI compatibility)
- GUI features (screenshots, visibility) not available in headless mode

---

### Robust MCP Bridge Workbench v0.5.0-beta

Initial public beta release.

#### Added

- **FreeCAD Workbench**: Installable via FreeCAD Addon Manager
- **XML-RPC server**: Runs on port 9875 for Robust MCP Server communication
- **Socket server**: Alternative JSON-RPC on port 9876
- **Auto-start option**: Configure bridge to start with FreeCAD
- **GUI mode support**: Full 3D view integration with screenshots
- **Headless mode support**: Console-only operation for automation

---

### Cut Object for Magnets Macro v0.5.0-beta

Initial public beta release.

#### Added

- **Smart cutting**: Cut objects in half with aligned magnet holes for easy reassembly
- **Hole placement**: Automatic hole placement with overlap detection
- **Object support**: Works with solid and hollow objects
- **Hole methods**: Parametric PartDesign::Hole or boolean hole methods
- **GUI dialog**: Interactive parameter configuration

---

### Multi Export Macro v0.5.0-beta

Initial public beta release.

#### Added

- **Multi-format export**: Export selected objects to multiple formats simultaneously
- **Format support**: STL, STEP, 3MF, OBJ, IGES, BREP, PLY, AMF
- **Mesh control**: Configurable mesh tolerance for STL/3MF
- **Batch export**: Export multiple objects with progress feedback
- **GUI dialog**: Interactive format and option selection

---

## Project Infrastructure (v0.5.0-beta)

### Added

- **CI/CD**: GitHub Actions workflows for testing, Docker builds, and PyPI releases
- **Quality**: Pre-commit hooks with Ruff, MyPy, Bandit, and secrets detection
- **Dependencies**: Dependabot for automated dependency updates
- **Security**: CodeQL security scanning
- **Documentation**: Comprehensive README, CLAUDE.md, and architecture docs
