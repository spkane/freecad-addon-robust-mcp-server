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

### Method 1: Public releases with pip

> **Current stable release:** PyPI and the stable workbench are at 0.6.2 and
> predate pairing. For the pairing workflow below, use matching RC4 assets via
> [Method 2](#method-2-github-release-assets) until a pairing-capable stable
> release is published.

#### MCP server

In the Python environment your assistant will use, install or update the stable
server package:

```bash
python -m pip install --upgrade freecad-robust-mcp
freecad-mcp --version
```

On Windows, `py -m pip` can be used in place of `python -m pip`. If the
executable is not on your PATH, configure the assistant with its full path in
that Python environment. The [Quick Start](quickstart.md#1-install-the-mcp-server)
provides an alternative using `uv`.

#### FreeCAD workbench bridge

1. Quit FreeCAD. Download the compatible stable workbench ZIP or `.tar.gz`
   from [workbench releases](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-workbench).
2. Extract its package folder into the active FreeCAD profile's `Mod` folder.
   The folder must directly contain `package.xml` and `freecad`. Move any older
   Robust MCP Bridge package out of that profile's `Mod` first.
3. Repeat for each FreeCAD profile you use. See the
   [profile and archive instructions](#manual-installation-from-a-release-archive)
   to find the active path.

#### Pair and configure

For a pairing-capable server and workbench, run this once as the same user who
runs FreeCAD; retain your existing credential if already paired:

```bash
freecad-mcp --pair-bridge
```

Start FreeCAD, select **Robust MCP Bridge**, and click **Start MCP Bridge**.
Configure your assistant to launch the installed `freecad-mcp` executable over
stdio, using the [Codex and Claude setup examples](quickstart.md#4-connect-your-assistant).
Restart or reconnect the assistant, then ask it to check the FreeCAD connection.
For troubleshooting, see [pairing and verification](#verifying-installation).

### Method 2: GitHub release assets

Install **both components**. Choose compatible releases; for RC testing, use
matching RC versions of the server and workbench. Ordinary PyPI installation
selects stable releases, not these pre-release assets.

#### MCP server

1. Open [server releases](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-server)
   and select the desired release. Under **Assets**, download
   `freecad_robust_mcp-<version>-py3-none-any.whl`. Choose a **Pre-release**
   only when you intend to test it.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
   open a new Terminal (macOS/Linux) or PowerShell (Windows). The following
   commands install the downloaded **0.7.0-rc.4** wheel from Downloads. For a
   different release or download location, substitute the actual filename and
   path. The wheel uses `0.7.0rc4` without a hyphen; the workbench archive uses
   `0.7.0-rc.4`.

   On macOS or Linux:

   ```bash
   uv tool install --force "$HOME/Downloads/freecad_robust_mcp-0.7.0rc4-py3-none-any.whl"
   uv tool update-shell
   ```

   On Windows PowerShell:

   ```powershell
   uv tool install --force "$env:USERPROFILE\Downloads\freecad_robust_mcp-0.7.0rc4-py3-none-any.whl"
   uv tool update-shell
   ```

   `--force` replaces an existing uv-managed installation. Open a new terminal
   and run `freecad-mcp --version`. If the command is not found, see [uv's
   executable directory instructions](https://docs.astral.sh/uv/reference/storage/#executable-directory).
   Alternatively, use `python -m pip install --upgrade` with the downloaded
   wheel path inside your chosen Python environment. If an older server was
   installed by another method, update or remove it and confirm the assistant
   points to the intended executable.

#### FreeCAD workbench bridge

1. Quit FreeCAD. Open [workbench releases](https://github.com/spkane/freecad-addon-robust-mcp-server/releases?q=robust-mcp-workbench)
   and select the matching compatible release. For RC4, download
   `freecad-mcp-workbench-0.7.0-rc.4.zip`. Its `.tar.gz` alternative contains
   the same workbench.
2. Extract the package folder into the active FreeCAD profile's `Mod` folder.
   It must directly contain `package.xml` and `freecad`. Move any older Robust
   MCP Bridge package out of that profile's `Mod` first, and repeat for each
   profile you use. The [profile and archive instructions](#manual-installation-from-a-release-archive)
   show how to find the active path.

The `cam-gate-v1.json` asset is a CI receipt and is not needed for installation.
GitHub's **Source code** archives are repository snapshots, not substitutes for
the server wheel or packaged workbench archive.

#### Pair and configure

If this user account is already paired, keep its credential. Otherwise run:

```bash
freecad-mcp --pair-bridge
```

Start FreeCAD, select **Robust MCP Bridge**, and click **Start MCP Bridge**.
Configure the assistant to launch the installed `freecad-mcp` executable over
stdio using the [Codex and Claude setup examples](quickstart.md#4-connect-your-assistant).
Restart or reconnect the assistant, then ask it to check the FreeCAD connection.
For troubleshooting, see [pairing and verification](#verifying-installation).

**To update:** Quit FreeCAD and stop the assistant's MCP server, then install
both the new server wheel and the compatible workbench in every FreeCAD profile
you use. Restart FreeCAD and reconnect the assistant. Keep the existing pairing
unless you intend to replace it. Check release notes before mixing versions.

### Method 3: From Source (development builds)

#### MCP server

Install [Git](https://git-scm.com/install/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/) first. In a new
Terminal (macOS/Linux) or PowerShell (Windows), run:

```bash
git clone https://github.com/spkane/freecad-addon-robust-mcp-server.git
cd freecad-addon-robust-mcp-server
uv sync --all-extras
```

Use `uv run freecad-mcp` from this checkout for the server. This workflow does
not require `mise` or `just`; the development setup is documented separately
in the contributor guide.

#### FreeCAD workbench bridge

Quit FreeCAD and run `uv run python scripts/install_workbench.py` from the
checkout. Verify the printed installation path is the profile you use; the
installer can select a different versioned profile. Use the
[source installation instructions](#from-the-same-source-checkout) to select a
specific `Mod` directory and repeat for other profiles.

#### Pair and configure

If this user account is not already paired, run
`uv run freecad-mcp --pair-bridge` from the checkout. Start FreeCAD, select
**Robust MCP Bridge**, and click **Start MCP Bridge**. Configure your assistant
to launch `uv` with arguments `run`, `--project`, the absolute checkout path,
and `freecad-mcp`; see [client configuration](configuration.md#mcp-client-configuration).
Restart or reconnect the assistant, then ask it to check the FreeCAD connection.

### Method 4: Docker

#### MCP server

Run the Robust MCP Server in a container:

```bash
# Pull from Docker Hub
docker pull spkane/freecad-robust-mcp

# Or build locally
docker build -t freecad-robust-mcp .
```

#### FreeCAD workbench bridge

Install a compatible workbench in the FreeCAD profile you use, following the
[release archive instructions](#manual-installation-from-a-release-archive).

#### Pair and configure

Pair the host user, start the bridge in FreeCAD, and give the container access
to that pairing credential. Configure the container and your assistant using
the [container configuration guide](configuration.md#docker-desktop-configuration).

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
   - **Linux:** `~/.local/share/FreeCAD/v1-1/Mod/`
   - **macOS:** `~/Library/Application Support/FreeCAD/v1-1/Mod/`
   - **Windows:** `%APPDATA%\FreeCAD\v1-1\Mod\`
1. Restart FreeCAD

These paths are examples for FreeCAD 1.1. Select the profile for the FreeCAD
version you actually use: for example, a development build may use `v27-1/Mod`.
Custom and older profiles may use a different or unversioned location. In the
running FreeCAD version, open **View > Panels > Python console** and run:

```python
import os
print(os.path.join(App.getUserAppDataDir(), "Mod"))
```

Use the printed directory, creating it if needed. The extracted package folder
must directly contain `package.xml` and the nested `freecad/RobustMCPBridge/`
workbench. Repeat the installation for each profile you use.

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
