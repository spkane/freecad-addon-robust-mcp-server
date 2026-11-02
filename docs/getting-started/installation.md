# Installation

This guide covers installing the FreeCAD Robust MCP Server and connecting it to your AI assistant.

For the everyday stable-release workflow, start with the [Quick Start](quickstart.md).
This page also covers source installations and other configuration options.

---

## Requirements

- **FreeCAD 1.0.2 or newer** is required. FreeCAD 1.1.4 or newer is recommended
  for security; earlier releases have known vulnerabilities when opening untrusted
  documents.
- **Python 3.11 or newer** for the separate MCP server. Embedded mode requires
  a Python minor version matching the FreeCAD build and is supported on Linux.
- An **MCP-compatible AI assistant** (Claude Code, Cursor, etc.)

FreeCAD 1.1.4 fixes file-writing vulnerabilities affecting earlier releases.
See the [FreeCAD release notes](https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4)
and [security advisories](https://github.com/FreeCAD/FreeCAD/security/advisories).
The Qt5 test lane checks compatibility with older FreeCAD, not its security support.

---

## Installation Methods

### Method 1: pip

The currently published package predates bridge pairing. To use the paired
bridge described below, install a matching server and workbench from a
pairing-capable release candidate using Method 2, or use matching builds from
the same source checkout using Method 3. After a pairing-capable stable release
is published, the package can be installed with:

```bash
pip install freecad-robust-mcp
```

### Method 2: GitHub release assets

Install **both components**: the MCP server runs as a separate process, and the
Robust MCP Bridge workbench runs inside FreeCAD. Use a compatible server and
workbench pair. For RC testing, choose the same RC version of each component;
pre-release assets are not installed by the ordinary stable PyPI command.

1. Open [server releases](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-server)
   and select the desired release. Under **Assets**, download the server wheel
   named `freecad_robust_mcp-<version>-py3-none-any.whl`. Choose a release
   marked **Pre-release** only if you intend to test it.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), open
   a terminal, and install the downloaded wheel. Replace the example path with
   the actual file in your Downloads folder; keep the quotes around paths with
   spaces. `--force` replaces an existing uv-managed installation as well.

   On macOS or Linux:

   ```bash
   uv tool install --force "/absolute/path/to/freecad_robust_mcp-<version>-py3-none-any.whl"
   uv tool update-shell
   ```

   On Windows PowerShell:

   ```powershell
   uv tool install --force "$env:USERPROFILE\Downloads\freecad_robust_mcp-<version>-py3-none-any.whl"
   uv tool update-shell
   ```

   Open a new terminal and run `freecad-mcp --version`. If the command is not
   found, see [uv's executable directory instructions](https://docs.astral.sh/uv/reference/storage/#executable-directory).
   Alternatively, install the downloaded wheel with `python -m pip install
   --upgrade "/absolute/path/to/the/downloaded.whl"` in your chosen Python
   environment; configure your assistant to use that environment's executable.
   If an older server was installed by another method, update or remove that
   installation and confirm your assistant points to the new executable.
3. Open [workbench releases](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-workbench)
   and select the corresponding compatible release. Download either its
   `freecad-mcp-workbench-<version>.zip` or `.tar.gz` archive; both contain the
   same workbench. Install it using the [manual workbench steps](#manual-installation-from-a-release-archive).

The `cam-gate-v1.json` file is a CI compatibility receipt. It is not needed for
installation. GitHub's **Source code** archives are repository snapshots, not
substitutes for the wheel or packaged workbench archive.

To update, quit FreeCAD and stop the assistant's MCP server, then install the
new server wheel and replace the workbench in each FreeCAD profile you use.
Restart FreeCAD and reconnect your assistant. Keep the existing pairing unless
you intend to replace it; check the new release's compatibility notes before
mixing versions. Merely downloading a wheel or archive does not install it.

### Method 3: From Source (development builds)

Install [Git](https://git-scm.com/install/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/) first. In a new
Terminal (macOS/Linux) or PowerShell (Windows), run:

```bash
git clone https://github.com/spkane/freecad-addon-robust-mcp-server.git
cd freecad-addon-robust-mcp-server
uv sync --all-extras
```

Use `uv run freecad-mcp` from this checkout for the server. Install the
workbench from the same checkout using the source installation steps below.
This workflow does not require `mise` or `just`; the development setup is
documented separately in the contributor guide.

### Method 4: Docker

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
checkout used for the server, run the following command, then restart FreeCAD:

```bash
uv run python scripts/install_workbench.py
```

This also works in Windows PowerShell. If you use `just`, the equivalent is
`just install::mcp-bridge-workbench`.

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
the unversioned profile. The selected profile may differ from the version of
FreeCAD you launch. Verify the printed path and supply the correct `Mod`
directory explicitly if needed. The installer removes recognized older
workbench layouts after the new package is installed. Do not copy the
repository itself into `Mod`.

If you selected a profile explicitly, pass the same `Mod` directory to
`just install::status` or `just install::uninstall-mcp-bridge-workbench`. These
status and uninstall recipes require Bash, including on Windows.

### Manual installation from a release archive

Pairing-capable release candidates are available. Use a workbench archive
compatible with the MCP server you installed, and choose the matching RC
versions when testing a candidate.

1. Quit FreeCAD. Download the `freecad-mcp-workbench-<version>.zip` or `.tar.gz`
   asset from the desired [workbench release](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-workbench&expanded=true).
1. Move older Robust MCP Bridge installations out of the selected profile’s
   `Mod` directory, including prior `freecad-mcp-workbench-*` archive folders
   and the source-installed `RobustMCPBridge` folder.
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

These instructions require pairing-capable server and workbench builds. The
stable 0.6.2 releases predate pairing; use matching pairing-capable candidates
or matching source builds until a newer stable release is available.

After installation, verify everything is working:

### Step 1: Pair the bridge

If this user account is already paired, keep the existing credential and skip
this step. Otherwise, run the pairing command on the same computer and user
account as FreeCAD:

```bash
# With pip installation
freecad-mcp --pair-bridge

# From the source checkout
uv run freecad-mcp --pair-bridge
```

A server running in a container or under a different account needs access to the
same pairing credential; pairing the host account alone does not provision it
there. For credential storage and alternative setups, see [Configuration](configuration.md).

If FreeCAD reports that the bridge is not paired, run the pairing command in a
terminal as the same user who runs FreeCAD. If `freecad-mcp` is not on your
`PATH`, use the full path to the installed executable. Then select **Start MCP
Bridge** in FreeCAD. If you restart FreeCAD instead, the bridge starts
automatically only when auto-start is enabled; otherwise, select **Start MCP
Bridge** after FreeCAD reopens. One pairing is shared by compatible workbench
installations under that user account.

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
