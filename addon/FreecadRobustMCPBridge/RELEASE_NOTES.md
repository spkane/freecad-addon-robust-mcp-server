# Robust MCP Bridge Workbench Release Notes

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
