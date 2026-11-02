# Robust MCP Server Release Notes

## Unreleased

## Version 0.7.0-rc.3 (2026-11-01)

### Added

- **CAM workbench tools**: 23 `cam_*` tools create and inspect CAM jobs,
  generate toolpaths, simulate material removal, and post-process G-code.
  The CAM implementation is installed with the compatible Robust MCP Bridge
  workbench. Availability varies by FreeCAD version and GUI mode: LeadInOut,
  RampEntry, Dragknife, AxisMap and ZCorrect require the GUI; Boundary2,
  Mirror and PlungeMilling require FreeCAD 26.3 or later and the GUI.
  The included simulation is limited to top-down three-axis cuts and does not
  model tool holders or collisions; independently verify machine programs.
- **Symmetric pocket support**: `pocket_sketch` now accepts a `symmetric`
  parameter that distributes the cut on both sides of the sketch plane. It
  uses the same `SideType` → `Midplane` → `Symmetric` property fallback
  chain as `pad_sketch`, `revolution_sketch`, and `groove_sketch`, so it
  works on FreeCAD 1.0.x and 1.1+ without deprecation warnings.

### Changed

- **Symmetric pocket termination guard**: `pocket_sketch(symmetric=True)` with
  a `type` whose termination FreeCAD 1.0.x ignores `Midplane` for (`UpToFirst`,
  `UpToFace`, `UpToLast`) is rejected on the `Midplane` fallback path with a
  clear error instead of silently producing a one-sided cut. FreeCAD 1.1+
  (`SideType`) and `symmetric=False` keep working with every termination mode.

### Fixed

- **Symmetric Part Design operations**: Pad, Revolution, and Groove now inspect
  FreeCAD's declared property list instead of using Python attribute probing,
  which is unreliable for dynamic FreeCAD properties. The tools prefer the
  current `SideType` property and retain `Midplane` and `Symmetric` fallbacks
  for older supported releases and compatible forks.
- **Part Design base-axis resolution**: Revolution and Groove now resolve base
  axes by their stable FreeCAD origin role instead of assuming the document
  object name has no numeric suffix. This keeps repeated-body operations
  compatible with FreeCAD 1.0.x and newer releases.
- **Execution timeout configuration**: `FREECAD_TIMEOUT_MS` now supplies the
  default in XML-RPC, socket, and embedded modes, while per-call values take
  precedence. XML-RPC proxy access is serialized to avoid concurrent use of
  its non-thread-safe transport. Socket connections recover after a timed-out
  response, select current streams only while holding the request lock, and do
  not send work whose execution deadline expired while queued. Socket recovery
  also runs outside the request lock to avoid reconnect deadlocks, and pre-send
  deadline failures explicitly report that code was not executed. Socket write
  backpressure and response reads share one bounded deadline, while the public
  constructor retains its positional `auto_reconnect` argument. XML-RPC retains
  execution compatibility with older workbenches that expose only the
  one-argument `execute(code)` method.

## Version 0.6.2 (2026-01-18)

No changes to the MCP server code itself. This release includes Docker image security improvements and repository restructuring.

### Added

- **Reproducible Docker builds**: Added `uv.lock` to Docker build context to ensure locked dependency versions for reproducible builds

### Changed

- **Repository restructured**: The standalone macros (Cut Object for Magnets, Multi Export) have been moved to dedicated repositories for independent release cycles and FreeCAD Addon Manager submission.

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
