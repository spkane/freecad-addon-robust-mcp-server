# Quick Start

Install the server and FreeCAD workbench, pair them once, and connect your AI
assistant. No source checkout or developer tools are required.

> **Stable release availability:** The current stable releases (0.6.2) predate
> bridge pairing. The steps below describe the upcoming pairing-capable stable
> release and will work once it is published. Until then, use the
> [source installation guide](installation.md) for the current development
> version; the stable 0.6.2 packages do not support the pairing steps below.

## What you need

- FreeCAD 1.1.4 or newer is recommended for security.
- An MCP-compatible assistant, such as Codex or Claude Desktop.
- Internet access to install the server and download the workbench.

The MCP server runs on the same computer and user account as FreeCAD. Install
and run software only from sources you trust: the bridge lets your assistant
execute Python with your FreeCAD user's permissions.

## 1. Install the MCP server

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) for your
operating system, then open a new Terminal (macOS/Linux) or PowerShell (Windows)
and run:

```bash
uv tool install freecad-robust-mcp
uv tool update-shell
```

Open a new terminal and check that the command is available:

```bash
freecad-mcp --version
```

If your shell cannot find it, see [uv's executable directory
instructions](https://docs.astral.sh/uv/concepts/tools/#the-executable-directory).
For another installation method, see [Installation](installation.md).

## 2. Install the FreeCAD workbench

1. Quit FreeCAD.
2. Open the [workbench releases](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-workbench),
   select the latest **stable** Robust MCP Bridge workbench release compatible
   with your server, and download its `freecad-mcp-workbench` ZIP file. Avoid
   releases labeled **Pre-release** unless you intend to test one.
3. Extract the ZIP. Open the FreeCAD profile's `Mod` folder, and move the
   extracted workbench folder into it. The folder you move must directly contain
   `package.xml` and the `freecad` folder. If `Mod` does not exist, create it.

   | Operating system | Typical profile folder |
   | --- | --- |
   | macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |
   | Windows | `%APPDATA%\FreeCAD\v1-1\Mod\` |
   | Linux | `~/.local/share/FreeCAD/v1-1/Mod/` |

   These examples are for the FreeCAD 1.1 profile. Use the profile for the
   version you actually start; some installations use an unversioned `Mod`
   folder instead. In Finder, use **Go > Go to Folder** to open the macOS path;
   on Windows, paste the path into File Explorer's address bar.
4. If another Robust MCP Bridge installation is already in that profile, move
   the old folder out of `Mod` so FreeCAD does not load two copies. Restart
   FreeCAD after installing.

The workbench is not currently listed in the public FreeCAD Addon Manager.

## 3. Pair and start the bridge

In a terminal on the same computer and user account that runs FreeCAD, run:

```bash
freecad-mcp --pair-bridge
```

Open FreeCAD, select **Robust MCP Bridge** from the workbench selector, and
click **Start MCP Bridge**. If it is already running, leave it running. Pairing
is shared by compatible workbench installations under your user account; you do
not need to copy a credential into each FreeCAD profile.

If the command is not found, find the executable directory with
`uv tool dir --bin`, and run `freecad-mcp` from that directory. The bridge
cannot start until pairing is complete. See [pairing and security
settings](configuration.md#pairing-the-freecad-bridge) for troubleshooting.

## 4. Connect your assistant

Configure your assistant to launch `freecad-mcp` over **stdio**. If the app
cannot find the command, specify the full executable path: `uv tool dir --bin`
shows its directory. On Windows the executable is `freecad-mcp.exe`. Restart or
reconnect the assistant after changing its settings.

For Codex, add this to `~/.codex/config.toml`, replacing the path with the
actual executable path on your computer:

```toml
[mcp_servers.freecad]
command = "/absolute/path/to/freecad-mcp"
```

On Windows, use the path to `freecad-mcp.exe` and use forward slashes or
escaped backslashes in the TOML string. Keep any existing server entries.

For other clients, the [client configuration guide](configuration.md#mcp-client-configuration)
includes examples. The default connection uses local XML-RPC, so no environment
variables or HTTP API key are needed for this setup. Start FreeCAD and the
bridge before asking your assistant to use the tools.

## 5. Verify the connection

Ask your assistant:

```text
Check the FreeCAD connection and tell me the FreeCAD version.
```

If it cannot connect, verify the bridge is running, that the assistant is using
the installed executable, and that FreeCAD and the assistant run as the same
user. See [Installation](installation.md#verifying-installation) for additional
checks.

---

## Try your first model

Try these example prompts with your AI assistant:

### Simple Box

```text
"Create a new FreeCAD document and add a box that is 20mm x 10mm x 5mm"
```

### Parametric Part with Fillet

```text
"Create a parametric bracket:
1. Start with a 50x30mm rectangular sketch
2. Extrude it 10mm
3. Add a 3mm fillet to all edges"
```

### Export for 3D Printing

```text
"Export the current model to STL format for 3D printing"
```

---

## Explore available tools

The MCP server provides 150+ tools organized into categories:

| Category   | Examples                                             |
| ---------- | ---------------------------------------------------- |
| Primitives | `create_box`, `create_cylinder`, `create_sphere`     |
| PartDesign | `create_sketch`, `pad_sketch`, `pocket_sketch`       |
| Operations | `boolean_operation`, `fillet_edges`, `chamfer_edges` |
| Export     | `export_stl`, `export_step`, `export_3mf`            |
| View (GUI) | `get_screenshot`, `set_object_color`                 |

See the [Tools Reference](../guide/tools.md) for the complete list.

---

## Example Workflows

### Create a Mounting Bracket

```text
"Help me create a mounting bracket with:
- 60x40mm base plate, 5mm thick
- Two mounting holes (5mm diameter) at the corners
- A vertical wall 30mm tall on one edge
- 2mm fillets on all external edges"
```

### Modify an Existing Model

```text
"Open my_part.FCStd and:
1. List all the objects in the document
2. Change the height of the Pad feature from 10mm to 15mm
3. Save the document"
```

### Debug a Macro

```text
"Read the macro 'MyMacro' and explain what it does.
Then run it and show me any errors."
```

---

## Tips for Effective AI-Assisted Modeling

1. **Be specific about dimensions** - Include units (mm, cm, inches) in your requests
1. **Use parametric approaches** - Ask for PartDesign workflows instead of direct Part operations for parts you'll modify
1. **Check console output** - If something goes wrong, ask the AI to check the FreeCAD console for errors
1. **Take screenshots** - In GUI mode, ask for screenshots to verify the model looks correct
1. **Save frequently** - Ask the AI to save your document after significant changes

---

## Next Steps

- [Tools Reference](../guide/tools.md) - Complete API reference for all tools
- [User Guide](../USER_GUIDE.md) - Detailed workflows and best practices
- [Connection Modes](../guide/connection-modes.md) - Understanding connection modes
