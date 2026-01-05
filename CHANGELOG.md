# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
IMPORTANT: Update this file at the end of any session where repository files are modified.
Group changes under: Added, Changed, Deprecated, Removed, Fixed, Security
-->

## [Unreleased]

<!-- This section captures changes that have been merged but not yet released.
     When preparing a new release, move these entries to a new version section below. -->

## [0.5.0-beta] - 2026-01-05

Initial public beta release of the FreeCAD MCP Server and Macros.

### Added

#### MCP Server for FreeCAD

- **Document management**: Create, open, save, close, recompute documents
- **Object manipulation**: Create primitives (box, cylinder, sphere, cone, torus, wedge, helix), boolean operations, transforms (scale, rotate, copy, mirror)
- **PartDesign workflow**: Bodies, sketches, pads, pockets, revolutions, fillets, chamfers, holes, patterns, lofts, sweeps
- **Import/Export**: STEP, STL, 3MF, OBJ, IGES, BREP formats
- **View control**: Screenshots, camera positioning, zoom, visibility, display modes
- **Macro support**: List, run, create, and manage FreeCAD macros
- **Undo/Redo**: Full undo/redo support with status queries

#### Connection Modes

| Mode       | Description                   | Platform Support            |
| ---------- | ----------------------------- | --------------------------- |
| `xmlrpc`   | XML-RPC protocol (port 9875)  | All platforms (recommended) |
| `socket`   | JSON-RPC socket (port 9876)   | All platforms               |
| `embedded` | In-process FreeCAD            | Linux only                  |

#### FreeCAD Macros

- **CutObjectForMagnets**: Cut objects in half with aligned magnet holes for easy reassembly
  - Smart hole placement with overlap detection
  - Support for solid and hollow objects
  - Parametric PartDesign::Hole or boolean hole methods
- **MultiExport**: Export selected objects to multiple formats simultaneously
  - Supports STL, STEP, 3MF, OBJ, IGES, BREP, PLY, AMF
  - Configurable mesh tolerance for STL/3MF
  - Batch export with progress feedback

#### Installation Options

- **PyPI**: `pip install freecad-robust-mcp`
- **Docker**: `docker pull ghcr.io/spkane/freecad-mcp`
- **Source**: Clone and install with `uv sync --all-extras`

#### CI/CD & Tooling

- GitHub Actions workflows for testing, Docker builds, and PyPI releases
- Pre-commit hooks with Ruff, MyPy, Bandit, and secrets detection
- Dependabot for automated dependency updates
- CodeQL security scanning

#### Documentation

- Comprehensive README with installation and configuration guides
- CLAUDE.md with AI assistant guidelines
- ARCHITECTURE.md with system design documentation
- MCP tools reference with examples

### Known Limitations

- Embedded mode only works on Linux (macOS/Windows must use xmlrpc or socket)
- Python 3.11 required (must match FreeCAD's bundled Python for ABI compatibility)
- GUI features (screenshots, visibility) not available in headless mode
