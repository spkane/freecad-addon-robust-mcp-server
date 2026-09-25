# Installation

This guide covers installing the FreeCAD Robust MCP Server and connecting it to your AI assistant.

---

## Requirements

- **FreeCAD** 0.21+ or 1.0+ (with Python 3.11)
- **Python 3.11** (must match FreeCAD's bundled Python version)
- An **MCP-compatible AI assistant** (Claude Code, Cursor, etc.)

---

## Installation Methods

### Method 1: pip (Recommended)

The simplest way to install the Robust MCP Server:

```bash
pip install freecad-robust-mcp
```

### Method 2: From Source (for Development)

```bash
git clone https://github.com/spkane/freecad-robust-mcp-and-more.git
cd freecad-robust-mcp-and-more

# Install mise (if not already installed)
curl https://mise.run | sh

mise trust
mise install
just setup
```

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

> **Not in the Addon Manager.** The workbench is not in the FreeCAD Addon
> Manager catalog yet. Searching for "Robust MCP" there returns nothing. Use
> one of the methods below.

### With `just` (recommended)

From a clone of this repository:

```bash
just install::mcp-bridge-workbench
```

This copies the workbench into the correct `Mod/RobustMCPBridge/` location and
generates its `package.xml`. Restart FreeCAD, then pick **Robust MCP Bridge**
from the workbench dropdown.

### Manual installation

1. Download the latest release archive from
   [GitHub Releases](https://github.com/spkane/freecad-robust-mcp-and-more/releases).
1. Extract the release archive so the workbench lands at the new-style namespace layout `Mod/RobustMCPBridge/freecad/RobustMCPBridge/`. The archive ships the package as `freecad/RobustMCPBridge`, so place that folder under `Mod/RobustMCPBridge/`, not directly in `Mod`:
   - **Linux:** `~/.local/share/FreeCAD/Mod/RobustMCPBridge/`
   - **macOS:** `~/Library/Application Support/FreeCAD/Mod/RobustMCPBridge/`
   - **Windows:** `%APPDATA%\FreeCAD\<version>\Mod\RobustMCPBridge\` (where `<version>` is your FreeCAD version directory: `v1-1`, `v1-2`, `v2-0`, ...)
1. Restart FreeCAD.

> Do **not** copy the whole repository into `Mod`. The installer builds the
> correct namespace layout and a standalone `package.xml`; a raw copy does not
> produce a working workbench.

### Windows notes

- **Install the Rust `just`, not the Python one.** `uv tool install just`
  installs an unrelated Python package that fails with
  `ModuleNotFoundError: No module named 'dateutil'`. Install the real `just`
  (the Rust task runner) with a package manager, for example:

  ```bash
  choco install just      # Chocolatey
  ```

- **Use Git Bash, not PowerShell.** The install recipes need a Unix-like
  shell. In PowerShell you may see `could not find cygpath executable`. Run
  the `just install::...` commands inside Git Bash (or MSYS2).

- **`python3` may be missing.** The installer calls `python3`. On Windows you
  often have only `python`. Add a `python3` wrapper on your `PATH`, or run
  the install from a shell where `python3` resolves.

---

## Verifying Installation

After installation, verify everything is working:

### Step 1: Start FreeCAD with the Robust MCP Bridge

1. **Start FreeCAD** and select the **Robust MCP Bridge** workbench from the workbench selector dropdown
1. **Click "Start MCP Bridge"** in the toolbar (or use the MCP Bridge menu)
1. Check the FreeCAD console for confirmation messages:

```text
MCP Bridge started!
  - XML-RPC: localhost:9875
  - Socket:  localhost:9876
```

### Step 2: Verify the Robust MCP Server

Test that the Robust MCP Server command is available:

```bash
# With pip installation
freecad-mcp --help

# With source installation
uv run freecad-mcp --help
```

### Step 3: Test the Connection

With FreeCAD running and the bridge started, you can verify connectivity:

```bash
# Quick connectivity test using curl (XML-RPC)
curl -X POST http://localhost:9875 \
  -H "Content-Type: text/xml" \
  -d '<?xml version="1.0"?><methodCall><methodName>ping</methodName></methodCall>'
```

A successful response indicates the bridge is working correctly.

---

## Next Steps

- [Configuration](configuration.md) - Set up environment variables and MCP client settings
- [Quick Start](quickstart.md) - Create your first model with AI assistance
