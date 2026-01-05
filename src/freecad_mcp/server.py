"""FreeCAD MCP Server - Main entry point.

This module provides the main MCP server implementation for FreeCAD
integration with AI assistants (Claude, GPT, and other MCP-compatible tools).
It exposes tools, resources, and prompts for interacting with FreeCAD.

Features:
    - Full Python console access (GUI and headless modes)
    - Document and object management
    - PartDesign workflow (sketches, pads, pockets, fillets)
    - Import/export (STEP, STL, OBJ, IGES)
    - Macro management
    - Screenshot capture
    - Multiple connection modes (embedded, XML-RPC, socket)

Example:
    Run as a module::

        $ python -m freecad_mcp.server

    Or use the installed command::

        $ freecad-mcp

    With environment variables::

        $ FREECAD_MODE=socket FREECAD_SOCKET_HOST=localhost freecad-mcp
"""

import logging
import sys
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP

from freecad_mcp.config import FreecadMode, TransportType, get_config

if TYPE_CHECKING:
    from freecad_mcp.bridge.base import FreecadBridge

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate unique instance ID at module load time
# This ID is stable for the lifetime of this server process
INSTANCE_ID: str = str(uuid.uuid4())

# Global bridge instance (initialized on startup via lifespan)
_bridge: Any = None


def get_instance_id() -> str:
    """Get the unique instance ID for this MCP server process.

    Returns:
        The UUID string that uniquely identifies this server instance.
    """
    return INSTANCE_ID


async def get_bridge() -> "FreecadBridge":
    """Get the active FreeCAD bridge.

    Returns:
        The active FreecadBridge instance.

    Raises:
        RuntimeError: If bridge is not initialized.
    """
    if _bridge is None:
        msg = "FreeCAD bridge not initialized"
        raise RuntimeError(msg)
    return _bridge


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Manage FreeCAD bridge lifecycle.

    This async context manager initializes the FreeCAD bridge on startup
    and disconnects it on shutdown.

    Args:
        _server: The FastMCP server instance (unused).

    Yields:
        None - the bridge is stored in the global _bridge variable.
    """
    global _bridge
    config = get_config()

    logger.info("Initializing FreeCAD bridge...")

    if config.mode == FreecadMode.EMBEDDED:
        from freecad_mcp.bridge.embedded import EmbeddedBridge

        _bridge = EmbeddedBridge(
            freecad_path=str(config.freecad_path) if config.freecad_path else None,
        )
        logger.info("Using embedded bridge (headless mode)")

    elif config.mode == FreecadMode.XMLRPC:
        from freecad_mcp.bridge.xmlrpc import XmlRpcBridge

        _bridge = XmlRpcBridge(
            host=config.socket_host,
            port=config.xmlrpc_port,
        )
        logger.info(
            "Using XML-RPC bridge: %s:%d", config.socket_host, config.xmlrpc_port
        )

    else:  # SOCKET mode
        from freecad_mcp.bridge.socket import SocketBridge

        _bridge = SocketBridge(
            host=config.socket_host,
            port=config.socket_port,
        )
        logger.info(
            "Using socket bridge: %s:%d", config.socket_host, config.socket_port
        )

    await _bridge.connect()
    logger.info("FreeCAD bridge connected")

    # Log FreeCAD version
    try:
        version = await _bridge.get_freecad_version()
        logger.info(
            "FreeCAD %s (GUI: %s)",
            version.get("version", "unknown"),
            "available" if version.get("gui_available") else "headless",
        )
    except Exception as e:
        logger.warning("Could not get FreeCAD version: %s", e)

    try:
        yield
    finally:
        # Shutdown
        if _bridge:
            logger.info("Disconnecting FreeCAD bridge...")
            await _bridge.disconnect()
            _bridge = None


# Create the MCP server instance with lifespan
mcp = FastMCP(
    name="freecad-mcp",
    lifespan=lifespan,
)


def register_all_components() -> None:
    """Register all MCP components (tools, resources, prompts)."""
    # Register tools
    from freecad_mcp.tools import register_all_tools

    register_all_tools(mcp, get_bridge)

    # Register resources
    from freecad_mcp.resources import register_resources

    register_resources(mcp, get_bridge)

    # Register prompts
    from freecad_mcp.prompts import register_prompts

    register_prompts(mcp, get_bridge)


# Register all components
register_all_components()


def main() -> None:
    """Run the FreeCAD MCP server."""
    config = get_config()

    # Set up logging
    logging.getLogger().setLevel(config.log_level)

    # Print instance ID to stdout for test automation to capture
    # This is printed before logging to ensure it's easily parseable
    print(f"FREECAD_MCP_INSTANCE_ID={INSTANCE_ID}", file=sys.stdout, flush=True)

    logger.info("Starting FreeCAD MCP server")
    logger.info("Instance ID: %s", INSTANCE_ID)
    logger.info("Mode: %s", config.mode.value)
    logger.info("Transport: %s", config.transport.value)

    # Run the server
    if config.transport == TransportType.HTTP:
        logger.info("Starting HTTP transport on port %d", config.http_port)
        mcp.run(  # type: ignore[call-arg]
            transport="streamable-http",
            host="0.0.0.0",  # noqa: S104
            port=config.http_port,
        )
    else:
        logger.info("Starting stdio transport")
        mcp.run()


if __name__ == "__main__":
    main()
