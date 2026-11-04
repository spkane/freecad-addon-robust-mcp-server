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
   it appears exactly once in the workbench selector, its commands are present,
   and there are no unexpected errors in Report view. Inspect the profile's `Mod` directory
   for duplicate copies from older installation methods.
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
   the next release, restart, and verify version, metadata, behavior, and that
   the workbench appears only once with no duplicate installation directories.

Record the OS, FreeCAD and Addon Manager versions, source ref, installation
method, observed results, and sanitized Report view messages for each run.
Repeat on macOS, Windows, and Linux. A custom repository exercises the Addon
Manager without testing the public Index's review or cache; repeat a final
smoke test through the public listing after acceptance.

## Automated lifecycle test

The Linux GUI CI matrix runs `tests/addon_manager/test_lifecycle.py` on FreeCAD
1.0.2 and the latest stable FreeCAD, with a non-blocking weekly canary. In an
isolated container and profile, it uses FreeCAD's actual Addon Manager installer
and addon operations to install an earlier release from a Git fixture, disable,
enable, update to the current checkout, uninstall, and reinstall. It restarts
FreeCAD, checks the manifest and workbench discovery, verifies default listener
state, and pairs and connects to the bridge. It also checks that an unrelated
addon and the pairing directory survive uninstall.

The test opts in with `FREECAD_ADDON_LIFECYCLE_DISPOSABLE=1` and refuses to
operate when FreeCAD's user data directory is outside its disposable profile.
Run it only in a disposable Linux container with a graphical display. It does
not manipulate the Addon Manager's graphical controls, test the public Index,
or cover native macOS and Windows profile and credential behavior. Those remain
manual checks and automation work before Index submission.
