# FreeCAD Macros

This project includes standalone FreeCAD macros that work independently of the MCP server, plus MCP tools for creating and managing macros programmatically.

---

## Included Macros

### CutObjectForMagnets

Cut an object along a plane and add aligned magnet holes with surface collision detection. Perfect for creating 3D printed parts that snap together with embedded magnets.

**Features:**

- Interactive plane selection via GUI
- Automatic magnet hole placement with configurable grid
- Surface collision detection to avoid invalid hole positions
- Configurable magnet dimensions and tolerances

**Usage:**

1. Select an object in FreeCAD
1. Run the macro
1. Define the cutting plane interactively
1. Configure magnet parameters
1. The macro creates two halves with aligned magnet holes

See [CutObjectForMagnets documentation](https://github.com/spkane/freecad-robust-mcp-and-more/tree/main/macros/Cut_Object_for_Magnets) for detailed usage.

### MultiExport

Export selected bodies to multiple file formats simultaneously with configurable mesh options.

**Supported Formats:**

- STL (ASCII and Binary)
- STEP
- 3MF
- OBJ
- IGES
- BREP
- PLY
- AMF

**Usage:**

1. Select one or more bodies/parts
1. Run the macro
1. Select output formats and configure mesh options
1. Choose output directory
1. All exports are created with consistent naming

See [MultiExport documentation](https://github.com/spkane/freecad-robust-mcp-and-more/tree/main/macros/Multi_Export) for detailed usage.

---

## Installing Macros

### Via FreeCAD Addon Manager

When you install the "FreeCAD Robust MCP Suite" addon, the macros are installed automatically.

### Manual Installation

1. Download macros from [GitHub Releases](https://github.com/spkane/freecad-robust-mcp-and-more/releases)
1. Copy `.FCMacro` files to your macro directory:
   - **Linux:** `~/.local/share/FreeCAD/Macro/`
   - **macOS:** `~/Library/Application Support/FreeCAD/Macro/`
   - **Windows:** `%APPDATA%\FreeCAD\Macro\`

---

## MCP Macro Tools

The MCP server provides tools for working with macros programmatically:

### list_macros

List available macros in FreeCAD's macro directories.

```python
list_macros() -> list[dict]
```

**Returns:** List of macros with name, path, description, and whether it's a system macro.

### run_macro

Execute a macro by name with optional arguments.

```python
run_macro(
    macro_name: str,
    args: dict | None = None
) -> dict
```

**Example prompt:**

```text
"Run the MultiExport macro"
```

### create_macro

Create a new macro programmatically.

```python
create_macro(
    name: str,
    code: str,
    description: str = ""
) -> dict
```

**Example prompt:**

```text
"Create a macro called 'CreateBox' that makes a 10x10x10 box"
```

### read_macro

Read the source code of an existing macro.

```python
read_macro(macro_name: str) -> dict
```

**Example prompt:**

```text
"Show me the code for the MultiExport macro"
```

### delete_macro

Delete a user macro (system macros are protected).

```python
delete_macro(macro_name: str) -> dict
```

### create_macro_from_template

Create a macro from predefined templates.

```python
create_macro_from_template(
    name: str,
    template: str = "basic",
    description: str = ""
) -> dict
```

**Available templates:**

| Template    | Description                       |
| ----------- | --------------------------------- |
| `basic`     | Minimal macro with imports        |
| `part`      | Part workbench operations         |
| `sketch`    | Sketcher operations               |
| `gui`       | GUI/dialog template               |
| `selection` | Selection handling template       |

**Example prompt:**

```text
"Create a new macro from the 'sketch' template called 'DrawGear'"
```

---

## Macro Development with AI

The MCP server excels at helping develop FreeCAD macros. Example workflows:

### Debugging an Existing Macro

```text
"Read the macro 'MyMacro' and explain what it does"
```

```text
"Run the macro and show me any errors from the FreeCAD console"
```

### Creating a New Macro

```text
"Create a macro that:
1. Gets all selected objects
2. Calculates their combined bounding box
3. Creates a box around them with 5mm clearance"
```

### Modifying a Macro

```text
"Read the 'ExportSTL' macro and modify it to also export STEP files"
```

---

## Best Practices for Macro Development

1. **Use templates** - Start from `create_macro_from_template` for proper imports
1. **Test incrementally** - Use `execute_python` for testing snippets before creating full macros
1. **Check console output** - Use `get_console_output` to debug issues
1. **Document your macros** - Add docstrings that explain parameters and usage
1. **Handle errors gracefully** - Wrap operations in try/except blocks

---

## Next Steps

- [Tools Reference](tools.md) - Complete API for all MCP tools
- [Workbench](workbench.md) - Robust MCP Bridge Workbench details
