# Cut Object for Magnets Macro Release Notes

## Version 0.6.1 (2026-01-12)

Release notes for changes between v0.5.0-beta and v0.6.1.

### Added

- **FreeCAD Addon Manager metadata**: Macro now includes standard metadata fields for better Addon Manager integration
- **FreeCAD Wiki page**: Official wiki documentation at [Macro Cut Object for Magnets](https://wiki.freecad.org/Macro_Cut_Object_for_Magnets)
- **Example images**: Added screenshots showing the dialog and example output

### Changed

- **Version tracking**: Version now managed via `__Version__` metadata field instead of inline comment

### Fixed

- **Ring-shaped objects**: Improved handling of inset point calculation for hollow/ring-shaped cut faces where the inset point could land in the hole
- **Code formatting**: Minor cleanup for consistent code style

### No Functional Changes

The core cutting algorithm, magnet hole placement, and collision detection remain unchanged from the beta release. This macro is stable for production use.

### Installation

**Via FreeCAD Addon Manager:**

1. Open FreeCAD
2. Go to Macro > Macros...
3. Click "Download" tab
4. Search for "Cut Object for Magnets"
5. Click Install

**Manual Installation:**

Copy `CutObjectForMagnets.FCMacro` to your FreeCAD macro directory:

- **macOS**: `~/Library/Application Support/FreeCAD/Macro/`
- **Linux**: `~/.local/share/FreeCAD/Macro/`
- **Windows**: `%APPDATA%/FreeCAD/Macro/`
