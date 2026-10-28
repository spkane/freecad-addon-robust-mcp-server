"""Exercise the actual workbench initializer inside a disposable FreeCAD process."""

import importlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import FreeCAD

root = Path(__file__).resolve().parents[2] / "freecad" / "RobustMCPBridge"
sys.path.insert(0, str(root.parents[1]))
params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/RobustMCPBridge")
params.SetBool("AutoStart", False)
params.SetBool("AutoStartHeadless", os.environ["MCP_TEST_HEADLESS"] == "1")
params.SetBool("AutoStartHeadlessBatch", os.environ["MCP_TEST_BATCH"] == "1")
params.SetInt("XMLRPCPort", int(os.environ["MCP_TEST_XMLRPC_PORT"]))
params.SetInt("SocketPort", int(os.environ["MCP_TEST_SOCKET_PORT"]))
package_name = "freecad.MCPActualProbe"


def load_workbench():
    """Load this checkout as a FreeCAD namespace workbench."""
    spec = importlib.util.spec_from_file_location(
        package_name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)


load_workbench()
commands = importlib.import_module(package_name + ".commands")

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
