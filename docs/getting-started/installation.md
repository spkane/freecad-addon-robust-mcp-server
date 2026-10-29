# Installation

This guide covers installing the FreeCAD Robust MCP Server and connecting it to your AI assistant.

---

## Requirements

- **FreeCAD** 0.21+ or 1.0+ (with Python 3.11)
- **Python 3.11** (must match FreeCAD's bundled Python version)
- An **MCP-compatible AI assistant** (Claude Code, Cursor, etc.)

---

## Installation Methods

### Method 1: pip

The currently published package predates bridge pairing. To use the paired
bridge described below, install matching server and workbench builds from the
same current source checkout using Method 2. After a pairing-capable release is
published, the package can be installed with:

```bash
pip install freecad-robust-mcp
```

### Method 2: From Source (recommended for paired bridge)

```bash
git clone https://github.com/spkane/freecad-addon-robust-mcp-server.git
cd freecad-addon-robust-mcp-server

# Install mise (if not already installed)
curl https://mise.run | sh

mise trust
mise install
just setup
```

Use `uv run freecad-mcp` from this checkout for the server. Install the
workbench from the same checkout using the source installation steps below.

### Method 3: Docker

Run the Robust MCP Server in a container:

```bash
# Pull from Docker Hub
docker pull spkane/freecad-robust-mcp

# Or build locally
docker build -t freecad-robust-mcp .
```

**Note:** The Docker container runs the Robust MCP Server only—it does not include FreeCAD itself. You must run FreeCAD with the Robust MCP Bridge workbench on your host machine (or in a separate container) and configure the Robust MCP Server to connect via `xmlrpc` or `socket` mode.

**Why embedded mode doesn't work with Docker:** Embedded mode requires FreeCAD and the Robust MCP Server to run in the same process, which is impossible when FreeCAD runs on the host and the Robust MCP Server runs inside a Docker container. Additionally, embedded mode fails on macOS due to ABI incompatibility with FreeCAD's bundled Python libraries (`libpython3.11.dylib`). Always use `xmlrpc` or `socket` mode for Docker deployments.

---

## Installing the Robust MCP Bridge Workbench

The Robust MCP Bridge Workbench runs inside FreeCAD and provides the connection point for the Robust MCP Server.

### From the same source checkout

The workbench is not currently in the public Addon Manager catalog. From the
checkout used for the server, run `just install::mcp-bridge-workbench`, then
restart FreeCAD. The command works from PowerShell on Windows using the Rust
`just` command and `uv`; neither Git Bash nor a `python3` wrapper is required.
Alternatively, run `uv run python scripts/install_workbench.py` directly.

To select a specific profile, pass its `Mod` directory to the Python installer:

```powershell
uv run python scripts/install_workbench.py --mod-dir "$env:APPDATA\FreeCAD\v1-1\Mod"
```

With `just`, the Mod directory can also be supplied as an argument. Relative
paths are resolved from the directory where you run `just`:

```powershell
just install::mcp-bridge-workbench "$env:APPDATA\FreeCAD\v1-1\Mod"
```

The source installer creates `Mod/RobustMCPBridge/package.xml` and
`Mod/RobustMCPBridge/freecad/RobustMCPBridge/` in the selected user profile. It
selects the latest versioned FreeCAD profile when one exists; otherwise it uses
the unversioned profile. It prints the selected installation path. The installer
removes recognized older workbench layouts after the new package is installed.
Do not copy the repository itself into `Mod`.

If you selected a profile explicitly, pass the same `Mod` directory to
`just install::status` or `just install::uninstall-mcp-bridge-workbench`. These
status and uninstall recipes require Bash, including on Windows.

### Manual Installation

Existing published workbench archives predate pairing. Use an archive only
when it is from a pairing-capable release that matches the server build.

1. Download the `freecad-mcp-workbench` archive from the latest [workbench release](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-workbench&expanded=true)
1. Extract the archive's top-level package directory into your FreeCAD Mod directory:
   - **Linux:** `~/.local/share/FreeCAD/Mod/`
   - **macOS:** `~/Library/Application Support/FreeCAD/Mod/`
   - **Windows:** `%APPDATA%\FreeCAD\Mod\`
1. Restart FreeCAD

The archive package directory contains `package.xml` and the nested
`freecad/RobustMCPBridge/` workbench. Select the `Mod` directory belonging to
the FreeCAD profile you actually use; versioned profiles can have a separate
directory such as `v1-1/Mod`.

---

## Verifying Installation

These instructions describe the current development version. The latest published
server and workbench releases predate bridge pairing; use matching builds that
support pairing when following this guide.

After installation, verify everything is working:

### Step 1: Pair the bridge

Run the pairing command on the same computer and user account as FreeCAD:

```bash
# With pip installation
freecad-mcp --pair-bridge

# From the source checkout
uv run freecad-mcp --pair-bridge
```

A server running in a container or under a different account needs access to the
same pairing credential; pairing the host account alone does not provision it
there. For credential storage and alternative setups, see [Configuration](configuration.md).

### Step 2: Start FreeCAD with the Robust MCP Bridge

1. **Start FreeCAD** and select the **Robust MCP Bridge** workbench from the workbench selector dropdown
1. **Click "Start MCP Bridge"** in the toolbar (or use the MCP Bridge menu)
1. Check the FreeCAD console for confirmation messages:

```text
MCP Bridge started!
  - XML-RPC: localhost:9875
  - Socket:  localhost:9876
```

### Step 3: Verify the Robust MCP Server

Test that the Robust MCP Server command is available:

```bash
# With pip installation
freecad-mcp --help

# With source installation
uv run freecad-mcp --help
```

### Step 4: Test the Connection

With FreeCAD running and the bridge started, you can verify connectivity:

```bash
# With pip installation
freecad-mcp --check --mode xmlrpc

# From the source checkout
uv run freecad-mcp --check --mode xmlrpc
```

A successful response indicates the bridge is working correctly.

---

## Next Steps

- [Configuration](configuration.md) - Set up environment variables and MCP client settings
- [Quick Start](quickstart.md) - Create your first model with AI assistance
