# MCP Macro Tools

The MCP server provides tools for working with FreeCAD macros programmatically.

---

## Available Tools

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
"Run the ExportSTL macro"
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
"Show me the code for my custom macro"
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
