"""FreeCAD MCP Bridge Plugin.

This package is installed into FreeCAD's Mod directory to provide
socket and XML-RPC servers for MCP communication.

Based on learnings from competitive analysis:
- Queue-based GUI communication for thread safety (from neka-nat)
- JSON-RPC 2.0 protocol for modern integration (port 9876)
- XML-RPC compatibility mode for neka-nat addons (port 9875)

To install, copy this directory to:
- macOS: ~/Library/Application Support/FreeCAD/Mod/MCPBridge/
- Linux: ~/.local/share/FreeCAD/Mod/MCPBridge/
- Windows: %APPDATA%/FreeCAD/Mod/MCPBridge/

Or use the justfile command:
    just install-freecad-plugin
"""

from freecad_mcp.freecad_plugin.server import (
    DEFAULT_SOCKET_PORT,
    DEFAULT_XMLRPC_PORT,
    FreecadMCPPlugin,
)

__all__ = [
    "DEFAULT_SOCKET_PORT",
    "DEFAULT_XMLRPC_PORT",
    "FreecadMCPPlugin",
    "start",
]


def start(
    host: str = "localhost",
    port: int = DEFAULT_SOCKET_PORT,
    xmlrpc_port: int = DEFAULT_XMLRPC_PORT,
    enable_xmlrpc: bool = True,
) -> FreecadMCPPlugin:
    """Start the MCP bridge servers.

    Args:
        host: Hostname to bind to.
        port: Port for JSON-RPC socket server.
        xmlrpc_port: Port for XML-RPC server.
        enable_xmlrpc: Whether to enable XML-RPC server.

    Returns:
        The running plugin instance.
    """
    plugin = FreecadMCPPlugin(
        host=host,
        port=port,
        xmlrpc_port=xmlrpc_port,
        enable_xmlrpc=enable_xmlrpc,
    )
    plugin.start()
    return plugin
