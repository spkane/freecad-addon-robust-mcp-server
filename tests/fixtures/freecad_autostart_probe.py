"""Exercise the actual workbench initializer inside a disposable FreeCAD process."""

import json
import os
import runpy
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "freecad" / "RobustMCPBridge"
sys.path.insert(0, str(root))
# Ensure a previously installed workbench cannot satisfy this regression.
for name in list(sys.modules):
    if name in {"preferences", "commands", "freecad_mcp_bridge"} or name.startswith(
        "freecad_mcp_bridge."
    ):
        del sys.modules[name]

import preferences  # noqa: E402

preferences.set_auto_start(False)
preferences.set_auto_start_headless(os.environ["MCP_TEST_HEADLESS"] == "1")
preferences.set_auto_start_headless_batch(os.environ["MCP_TEST_BATCH"] == "1")
preferences.set_xmlrpc_port(int(os.environ["MCP_TEST_XMLRPC_PORT"]))
preferences.set_socket_port(int(os.environ["MCP_TEST_SOCKET_PORT"]))
runpy.run_path(str(root / "__init__.py"), run_name="mcp_autostart_probe")
import commands  # noqa: E402

plugin = commands._mcp_plugin
started = plugin is not None and plugin.is_running
listening = False
if started:
    for _ in range(200):
        if plugin._xmlrpc_server is not None and plugin._socket_server is not None:
            listening = True
            break
        time.sleep(0.05)
    plugin.stop()
Path(os.environ["MCP_TEST_RESULT"]).write_text(
    json.dumps({"started": started, "listening": listening}), encoding="utf-8"
)
