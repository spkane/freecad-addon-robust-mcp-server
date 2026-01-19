# Robust MCP Server Release Notes

## Version 0.6.2 (2026-01-18)

No changes to the MCP server code itself. This release includes Docker image security improvements and repository restructuring.

### Changed

- **Repository restructured**: The standalone macros (Cut Object for Magnets, Multi Export) have been moved to dedicated repositories for independent release cycles and FreeCAD Addon Manager submission.
- **Docker image**: Now uses `uv.lock` for reproducible builds with locked dependency versions

### Fixed

- **Docker security (CVE-2025-8869)**: Removed pip from runtime image (was vulnerable)
- **Docker security (GHSA-58pv-8j8x-9vj2)**: Removed setuptools from runtime image (jaraco.context vulnerability)

### Removed

- **Standalone macros**: `macros/Cut_Object_for_Magnets/` and `macros/Multi_Export/` moved to:
  - [freecad-macro-cut-for-magnets](https://github.com/spkane/freecad-macro-cut-for-magnets)
  - [freecad-macro-3d-print-multi-export](https://github.com/spkane/freecad-macro-3d-print-multi-export)

---

## Version 0.6.1 (2026-01-12)

Release notes for changes between v0.5.0-beta and v0.6.1.

### Added

- **Instance ID tracking**: Each server instance now has a unique UUID for identifying connections
- **Lifespan management**: Proper async lifecycle handling for bridge connections
- **Enhanced logging**: Improved startup logging with connection mode, transport type, and FreeCAD version
- **Connection validation**: Server validates FreeCAD bridge connection at startup with clear error messages

### Changed

- **Renamed from "FreeCAD MCP" to "Robust MCP Server"**: Reflects the broader scope and stability improvements
- **Bridge architecture refactored**: Cleaner separation between MCP server and FreeCAD bridge components
- **Plugin code moved to workbench**: The embedded FreeCAD plugin (`freecad_plugin/`) is now part of the separate Robust MCP Bridge Workbench addon
- **Simplified tool registration**: Tools now use consistent async patterns with typed callbacks
- **Export tools improved**: Better error handling and format validation for STEP, STL, 3MF, OBJ, IGES exports

### Removed

- **Docker detection fields**: Removed `in_docker` and `docker_container_id` from `get_mcp_server_environment()` tool (unreliable detection)
- **Embedded plugin code**: The `freecad_plugin/` directory moved to the workbench addon for cleaner separation

### Fixed

- **XML-RPC connection handling**: Improved timeout and retry logic for bridge connections
- **Console output capture**: More reliable capture of FreeCAD console messages
- **Type annotations**: Added proper type hints throughout for better IDE support

### Installation

```bash
# PyPI (recommended)
pip install freecad-robust-mcp

# Or with uv
uv tool install freecad-robust-mcp

# Docker (use 'latest' or a specific version tag)
docker pull spkane/freecad-robust-mcp:latest
```

### Upgrade Notes

- The server now requires the **Robust MCP Bridge Workbench** to be installed in FreeCAD (replaces the old Start MCP Bridge macro)
- Environment variable names unchanged (`FREECAD_MODE`, `FREECAD_SOCKET_HOST`, etc.)
- All existing MCP tools remain compatible
