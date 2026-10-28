"""Start a test-only authenticated bridge inside a standalone FreeCAD process.

The launching test supplies a temporary user home and credential store. It
must never be used as a production startup script.
"""

import json
import os
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2]
workbench = Path(
    os.environ.get(
        "FREECAD_AUTH_TEST_WORKBENCH_PATH", str(root / "freecad" / "RobustMCPBridge")
    )
)
sys.path.insert(0, str(workbench))
for module_name in list(sys.modules):
    if module_name == "freecad_mcp_bridge" or module_name.startswith(
        "freecad_mcp_bridge."
    ):
        del sys.modules[module_name]

from freecad_mcp_bridge.server import FreecadMCPPlugin  # noqa: E402

plugin = FreecadMCPPlugin(
    host="127.0.0.1",
    port=int(os.environ.get("FREECAD_AUTH_TEST_SOCKET_PORT", "0")),
    xmlrpc_port=int(os.environ.get("FREECAD_AUTH_TEST_XMLRPC_PORT", "0")),
)
plugin.start()
deadline = time.monotonic() + 10
while (
    plugin._socket_server is None or plugin._xmlrpc_server is None
) and time.monotonic() < deadline:
    time.sleep(0.02)
assert plugin._socket_server is not None and plugin._xmlrpc_server is not None
ready = {
    "socket": plugin._socket_server.sockets[0].getsockname()[1],
    "xmlrpc": plugin._xmlrpc_server.server_address[1],
}
ready_path = Path(os.environ["FREECAD_AUTH_TEST_READY"])
temporary_path = ready_path.with_suffix(".tmp")
temporary_path.write_text(json.dumps(ready), encoding="utf-8")
temporary_path.replace(ready_path)
plugin.run_forever()
