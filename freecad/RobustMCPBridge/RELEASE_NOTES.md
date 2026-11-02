# Robust MCP Bridge Workbench Release Notes

## Unreleased

## Version 0.7.0-rc.3 (2026-11-01)

### Added

- **CAM interface**: A versioned, allowlisted CAM dispatcher provides the
  FreeCAD-side implementation for compatible MCP server CAM tools.

### Fixed

- **Bridge listener startup**: An occupied JSON-RPC or XML-RPC port no longer
  disables the other listener. The bridge reports the affected port and recovery
  steps, and fails cleanly if neither listener can start.

## Version 0.7.0-rc.1 (2026-10-29)

This candidate pairs with the `0.7.0-rc.1` MCP server. The bridge executes
FreeCAD operations with the permissions of the FreeCAD user; pairing protects
against unauthenticated local clients but does not isolate malicious programs
running as the same user.

### Added

- **Authenticated pairing**: XML-RPC and socket bridge access requires a
  paired client credential, and the bridge listens on loopback.
- **Release packaging**: ZIP and tarball archives share the installable
  workbench layout and include the applicable licenses and notices.

### Changed

- **FreeCAD compatibility CI**: GUI integration now runs in parallel against the final Qt5/PySide2 release, the latest stable Qt6/PySide6 release, and a non-blocking latest-weekly Qt6 canary.

### Fixed

- **Installed imports and shutdown**: The workbench uses package-relative
  imports, starts safely in headless mode, and releases its owned Qt timers on
  the correct thread during shutdown.
- **Execution timeout propagation**: XML-RPC and socket requests now receive the
  caller's effective timeout, while one-argument XML-RPC clients retain the
  30-second default. Requests that time out before execution are removed from
  the queue; already-running FreeCAD code reports that it may continue.
- **Qt binding selection**: The bridge now selects PySide6 for Qt 6 FreeCAD builds and PySide2 for Qt 5 builds, prefers PySide6 only when the host version cannot be detected, and refuses unsafe cross-major fallback.
- **GUI thread safety during startup**: A GUI bridge now refuses to start if neither supported Qt binding can provide the main-thread queue timer. Background queue processing remains limited to genuine headless sessions.

## Version 0.6.2 (2026-01-18)

This release fixes some auto-start issues and improves the overall startup experience across all supported modes.

### Added

- No new features in this release.

### Changed

- **Repository restructured**: This addon now focuses solely on the MCP Bridge Workbench. Standalone macros have been moved to dedicated repositories for independent release cycles.
- **Cleaner startup messages**: Removed duplicate success messages when bridge auto-starts.

### Fixed

- **Auto-start not working at FreeCAD startup**: Fixed bug where auto-start only worked when manually selecting the workbench. For FreeCAD workbench addons, `Init.py` does NOT run at startup - only `InitGui.py` module-level code runs. Auto-start logic has been moved to `InitGui.py`.
- **Status bar not appearing after auto-start**: The status bar widget now syncs immediately after the bridge starts, instead of on a timer that ran before the bridge was ready.
- **Integration test crashes**: Fixed race condition where the bridge could start before `FreeCAD.GuiUp` was `True`, causing Qt operations to run on a background thread and crash FreeCAD. Auto-start is now deferred with `QTimer.singleShot()` to allow the GUI to stabilize.

### Note

The standalone macros (Cut Object for Magnets and Multi Export) are now maintained in separate repositories:

- [freecad-macro-cut-for-magnets](https://github.com/spkane/freecad-macro-cut-for-magnets)
- [freecad-macro-3d-print-multi-export](https://github.com/spkane/freecad-macro-3d-print-multi-export)

Each macro can now be installed independently via the FreeCAD Addon Manager.

## Version 0.6.1 (2026-01-12)

Release notes for changes between v0.5.0-beta and v0.6.1.

### Major Change: Macro to Workbench

The MCP Bridge has been completely rewritten from a simple macro (`Start MCP Bridge`) to a full **FreeCAD Workbench**. This provides:

- Native FreeCAD Addon Manager installation
- Integrated toolbar with start/stop/status controls
- Preferences panel for configuration
- Real-time status widget showing connection state
- Proper lifecycle management with FreeCAD

### Added

- **FreeCAD Workbench**: Full workbench with toolbar, icons, and menus
- **Addon Manager support**: Install directly from FreeCAD's Addon Manager
- **Preferences panel**: Configure ports, auto-start, and logging from Edit > Preferences
- **Status widget**: Real-time display of bridge status, connected clients, and uptime
- **Auto-start option**: Optionally start the bridge automatically when FreeCAD launches
- **Start/Stop commands**: Toolbar buttons and menu items to control the bridge
- **Custom icons**: Professional SVG icons for all commands and status indicators
- **GUI mode support**: Full integration with FreeCAD's 3D view for screenshots
- **Headless mode support**: Works with `freecadcmd` for automation pipelines

### Changed

- **Architecture**: Complete rewrite from single macro to modular workbench structure
- **Server code**: Bridge server now lives in `freecad_mcp_bridge/` package within the addon
- **Configuration**: Settings now stored in FreeCAD's preference system instead of environment variables
- **Startup behavior**: Bridge waits for GUI initialization before starting (prevents crashes)

### Fixed

- **GUI crash on macOS**: Fixed race condition where bridge started before Qt event loop was ready
- **Thread safety**: All FreeCAD operations now execute on the main thread via queue processor
- **Startup timeout**: Increased GUI wait timeout to 60 seconds for slow FreeCAD startups
- **Clean shutdown**: Proper cleanup of servers and threads when FreeCAD exits

### Removed

- **Start MCP Bridge macro**: Replaced by the workbench (macro no longer needed)

### Installation

**Via FreeCAD Addon Manager (Recommended):**

1. Open FreeCAD
2. Go to Tools > Addon Manager
3. Search for "Robust MCP Bridge"
4. Click Install
5. Restart FreeCAD

**Manual Installation:**

Copy the `FreecadRobustMCPBridge` folder to your FreeCAD Mod directory:

- **macOS**: `~/Library/Application Support/FreeCAD/Mod/`
- **Linux**: `~/.local/share/FreeCAD/Mod/`
- **Windows**: `%APPDATA%/FreeCAD/Mod/`

### Upgrade Notes

- **Uninstall the old macro**: If you had `StartMCPBridge.FCMacro`, you can delete it
- **Auto-start disabled by default**: Enable in Preferences if you want the bridge to start automatically
- **Same ports**: Default ports remain 9875 (XML-RPC) and 9876 (JSON-RPC Socket)
