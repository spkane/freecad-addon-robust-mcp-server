# Testing Addon Manager before Index listing

FreeCAD's Addon Manager supports custom repositories, so the workbench can be
exercised through its actual install controls before it is in the public Index.
Use a disposable operating-system account, virtual machine, or FreeCAD profile
whose data and credentials may be removed. Do not run lifecycle tests in a
profile containing your normal workbench or pairing credential.

## Manual test setup

1. Install the FreeCAD version under test and Git. Use FreeCAD 1.0.2 for the
   compatibility boundary and the latest stable FreeCAD for the primary
   supported path. FreeCAD 1.1.4 or newer is recommended for security; do not
   use untrusted documents with older releases.
2. In FreeCAD, open **Edit → Preferences → Addon Manager** (on macOS, use the
   application menu for Preferences). Under **Custom repositories**, add
   `https://github.com/spkane/freecad-addon-robust-mcp-server` and the branch
   or release ref you intend to test. Test an immutable release tag before
   submission; branch and tag support can differ by Addon Manager version.
3. Open **Tools → Addon manager**, find **FreeCAD Robust MCP Bridge**, and
   install it. Restart FreeCAD when prompted. Confirm that the workbench loads,
   its commands appear, and there are no unexpected errors in Report view.
4. Install a matching MCP server, create a pairing for the disposable account,
   and test starting and stopping the bridge and a basic MCP operation. Confirm
   that neither the bridge nor its listeners starts before the user enables
   auto-start or explicitly starts it.
5. Using the Addon Manager, disable the workbench and restart; verify that it
   does not load. Re-enable it, restart, then uninstall and restart. Verify that
   the workbench is gone, its listeners are stopped, and unrelated addons and
   the user's other data remain intact. Pairing credentials are separately
   managed; do not assume uninstall removes them.
6. Reinstall and repeat the startup and pairing checks. For upgrade coverage,
   install a prior release first, use the Addon Manager update flow to install
   the next release, restart, and verify version, metadata, and behavior.

Record the OS, FreeCAD and Addon Manager versions, source ref, installation
method, observed results, and sanitized Report view messages for each run.
Repeat on macOS, Windows, and Linux. A custom repository exercises the Addon
Manager without testing the public Index's review or cache; repeat a final
smoke test through the public listing after acceptance.

## Automation gap

Current CI exercises the workbench and its archive builder, but does **not**
execute Addon Manager's full install, update, disable, and uninstall lifecycle.
Add an isolated-profile GUI integration job that exercises those operations
through the real Addon Manager, checks metadata and version changes, restarts
FreeCAD to verify loading and disabling, and checks listener and cleanup state.
Run it on all three operating systems; require that each job proves isolation
before it changes any profile or credentials. Avoid replacing this coverage
with a test that only copies the package files or mocks the Addon Manager.
