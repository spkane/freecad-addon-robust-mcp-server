"""FreeCAD Robust MCP Server - Main entry point.

This module provides the main Robust MCP Server implementation for FreeCAD
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

    Show help::

        $ freecad-mcp --help
"""

import argparse
import ipaddress
import logging
import os
import sys
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from freecad_mcp.config import FreecadMode, TransportType, get_config

if TYPE_CHECKING:
    from freecad_mcp.bridge.base import FreecadBridge
    from freecad_mcp.config import ServerConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate unique instance ID at module load time
# This ID is stable for the lifetime of this server process
INSTANCE_ID: str = str(uuid.uuid4())

# Global bridge instance (initialized on startup via lifespan)
_bridge: Any = None


def get_instance_id() -> str:
    """Get the unique instance ID for this Robust MCP Server process.

    Returns:
        The UUID string that uniquely identifies this server instance.
    """
    return INSTANCE_ID


def is_loopback_host(host: str) -> bool:
    """Check whether a host binds only to loopback interfaces.

    Args:
        host: The bind address to check.

    Returns:
        True for the ``localhost`` hostname and for any address in the
        IPv4 (``127.0.0.0/8``) or IPv6 (``::1/128``) loopback ranges,
        False for any other address or hostname.
    """
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _format_host(host: str) -> str:
    """Bracket an IPv6 address for use in HTTP authority strings.

    IPv6 addresses in HTTP headers and URLs must be enclosed in square brackets
    (e.g. ``[::1]``) to avoid ambiguity with the colon-separated port syntax.
    IPv4 addresses, hostnames, and explicit ``host:port`` values are returned
    unchanged.

    Args:
        host: A hostname, IPv4 address, bare IPv6 address, or host:port string.

    Returns:
        The formatted host string with brackets around IPv6 addresses.
    """
    if _is_ipv6(host) and not host.startswith("["):
        return f"[{host}]"
    return host


def _is_ipv6(host: str) -> bool:
    """Detect whether a host string is a bare IPv6 address.

    Detection uses :mod:`ipaddress` validation instead of checking for a
    colon, so explicit ``host:port`` values (e.g. ``mcp.example.com:443``)
    are not misclassified as IPv6 and wrapped in brackets. Already-bracketed
    addresses (e.g. ``[::1]``) are **not** detected as IPv6 by this helper;
    use :func:`_format_host` to apply brackets when needed.

    Args:
        host: A hostname, IP address, or ``host:port`` string.

    Returns:
        ``True`` if *host* is an unbracketed IPv6 address, ``False``
        otherwise (including hostnames, IPv4 addresses, ``host:port``
        values, and anything that does not parse as an IP address).
    """
    try:
        return ipaddress.ip_address(host).version == 6
    except ValueError:
        return False


def _build_transport_security(config: "ServerConfig") -> TransportSecuritySettings:
    """Build transport security settings from configuration.

    Args:
        config: The server configuration.

    Returns:
        TransportSecuritySettings with explicit allowlist for both
        loopback and non-loopback binds.

    Raises:
        ValueError: If http_host is non-loopback and http_allowed_hosts is empty.
    """
    if is_loopback_host(config.http_host):
        host = _format_host(config.http_host)
        # Both the bare value and the port-wildcard form are required: MCP
        # matches allowlist entries exactly, and clients omit the port for
        # the default ports (80/443), so "host:*" alone rejects those
        # requests with HTTP 421.
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[host, f"{host}:*"],
            allowed_origins=[f"http://{host}", f"http://{host}:*"],
        )

    # Non-loopback: require explicit allowlist
    if not config.http_allowed_hosts:
        raise ValueError(
            f"http_allowed_hosts is required when binding to non-loopback "
            f"host '{config.http_host}'. Set FREECAD_HTTP_ALLOWED_HOSTS to a "
            f"comma-separated list of allowed hosts."
        )

    raw_hosts = [h.strip() for h in config.http_allowed_hosts.split(",") if h.strip()]
    if not raw_hosts:
        raise ValueError(
            "http_allowed_hosts is empty after parsing. Provide at least one "
            "host in FREECAD_HTTP_ALLOWED_HOSTS."
        )

    # Emit both the bare authority and the port-wildcard form for each host:
    # MCP matches allowlist entries exactly, and "host:*" only matches Host
    # headers that carry a port (see mcp.server.transport_security).
    allowed_hosts: list[str] = []
    allowed_origins: list[str] = []
    for raw_host in raw_hosts:
        formatted = _format_host(raw_host)
        allowed_hosts.extend([formatted, f"{formatted}:*"])
        allowed_origins.extend([f"http://{formatted}", f"http://{formatted}:*"])

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


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


# Will be created in main() with full configuration.
# None until main() runs.
mcp: FastMCP | None = None


def get_mcp() -> FastMCP:
    """Return the live FastMCP instance created by :func:`main`.

    The package-level ``mcp`` name is ``None`` until ``main()`` creates the
    server, and back to ``None`` once the transport stops. A
    ``from freecad_mcp import mcp`` performed before startup captures that
    ``None`` binding and keeps it even after ``main()`` assigns the real
    instance, so importing the name directly can leave callers with a stale
    value. This accessor resolves the module-level binding at call time
    instead, so it returns the running instance whenever the server is up.

    Returns:
        The FastMCP server instance.

    Raises:
        RuntimeError: If ``main()`` has not created the instance yet.

    Example:
        >>> from freecad_mcp import get_mcp
        >>> mcp = get_mcp()  # only after main() starts; RuntimeError before
    """
    if mcp is None:
        raise RuntimeError(
            "MCP server not initialized yet: freecad_mcp.server.mcp is None "
            "until main() creates the FastMCP instance."
        )
    return mcp


def register_all_components(fastmcp: FastMCP) -> None:
    """Register all MCP components (tools, resources, prompts).

    Args:
        fastmcp: The FastMCP instance to register components on.
    """
    # Register tools
    from freecad_mcp.tools import register_all_tools

    register_all_tools(fastmcp, get_bridge)

    # Register resources
    from freecad_mcp.resources import register_resources

    register_resources(fastmcp, get_bridge)

    # Register prompts
    from freecad_mcp.prompts import register_prompts

    register_prompts(fastmcp, get_bridge)


async def check_freecad_connection(
    mode: str | None = None, host: str | None = None, port: int | None = None
) -> bool:
    """Test FreeCAD bridge connection.

    Args:
        mode: Connection mode override (xmlrpc, socket, embedded).
        host: Host override for connection.
        port: Port override for connection.

    Returns:
        True if connection successful, False otherwise.
    """
    import os

    # Apply overrides to env
    if mode:
        os.environ["FREECAD_MODE"] = mode
    if host:
        os.environ["FREECAD_SOCKET_HOST"] = host
    if port:
        mode_val = mode or os.environ.get("FREECAD_MODE", "xmlrpc")
        if mode_val == "xmlrpc":
            os.environ["FREECAD_XMLRPC_PORT"] = str(port)
        else:
            os.environ["FREECAD_SOCKET_PORT"] = str(port)

    config = get_config()
    print(f"Testing connection to FreeCAD ({config.mode.value} mode)...")

    try:
        bridge: FreecadBridge
        if config.mode == FreecadMode.EMBEDDED:
            from freecad_mcp.bridge.embedded import EmbeddedBridge

            bridge = EmbeddedBridge(
                freecad_path=(
                    str(config.freecad_path) if config.freecad_path else None
                ),
            )
        elif config.mode == FreecadMode.XMLRPC:
            from freecad_mcp.bridge.xmlrpc import XmlRpcBridge

            bridge = XmlRpcBridge(
                host=config.socket_host,
                port=config.xmlrpc_port,
            )
            print(f"  Host: {config.socket_host}:{config.xmlrpc_port}")
        else:
            from freecad_mcp.bridge.socket import SocketBridge

            bridge = SocketBridge(
                host=config.socket_host,
                port=config.socket_port,
            )
            print(f"  Host: {config.socket_host}:{config.socket_port}")

        await bridge.connect()
        version_info = await bridge.get_freecad_version()
        await bridge.disconnect()

        print("✓ Connection successful!")
        print(f"  FreeCAD version: {version_info.get('version', 'unknown')}")
        print(f"  GUI available: {version_info.get('gui_available', 'unknown')}")
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def apply_cli_args_to_env(args: argparse.Namespace) -> None:
    """Apply CLI arguments as environment variables.

    CLI arguments override existing environment variables.

    Args:
        args: Parsed command-line arguments.
    """
    import os

    if args.mode:
        os.environ["FREECAD_MODE"] = args.mode
    if args.transport:
        os.environ["FREECAD_TRANSPORT"] = args.transport
    if args.host:
        os.environ["FREECAD_SOCKET_HOST"] = args.host
    if args.port:
        # Set appropriate port based on mode
        mode = os.environ.get("FREECAD_MODE", "xmlrpc")
        if mode == "xmlrpc":
            os.environ["FREECAD_XMLRPC_PORT"] = str(args.port)
        else:
            os.environ["FREECAD_SOCKET_PORT"] = str(args.port)
    if args.http_host:
        os.environ["FREECAD_HTTP_HOST"] = args.http_host
    if args.http_port:
        os.environ["FREECAD_HTTP_PORT"] = str(args.http_port)
    if args.log_level:
        os.environ["FREECAD_LOG_LEVEL"] = args.log_level


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="freecad-mcp",
        description="FreeCAD Robust MCP Server - Connect AI assistants to FreeCAD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  FREECAD_MODE           Connection mode: xmlrpc, socket, or embedded
                         (default: xmlrpc)
  FREECAD_SOCKET_HOST    Host for socket/XML-RPC connection (default: localhost)
  FREECAD_SOCKET_PORT    Port for socket connection (default: 9876)
  FREECAD_XMLRPC_PORT    Port for XML-RPC connection (default: 9875)
  FREECAD_TRANSPORT      Transport type: stdio or http (default: stdio)
  FREECAD_HTTP_HOST      Host to bind for HTTP transport (default: 127.0.0.1)
                         Binding to a non-loopback address exposes the MCP
                         server remotely: put it behind authentication, TLS
                         or a trusted reverse proxy.
  FREECAD_HTTP_PORT      Port for HTTP transport (default: 8000)
  FREECAD_HTTP_ALLOWED_HOSTS
                         Comma-separated allowlist of Host/Origin values,
                         required when FREECAD_HTTP_HOST is non-loopback
  FREECAD_LOG_LEVEL      Logging level: DEBUG, INFO, WARNING, ERROR
                         (default: INFO)

Examples:
  # Start with default settings (XML-RPC mode, stdio transport)
  freecad-mcp

  # Use socket mode
  FREECAD_MODE=socket freecad-mcp

  # Use HTTP transport for local access (binds 127.0.0.1 only)
  FREECAD_TRANSPORT=http FREECAD_HTTP_PORT=8080 freecad-mcp

  # Use HTTP transport for remote access (non-loopback bind needs an
  # explicit host allowlist; see the security note on FREECAD_HTTP_HOST)
  FREECAD_TRANSPORT=http FREECAD_HTTP_HOST=0.0.0.0 FREECAD_HTTP_PORT=8080 \\
    FREECAD_HTTP_ALLOWED_HOSTS=mcp.example.com freecad-mcp

  # Connect to remote FreeCAD instance
  FREECAD_SOCKET_HOST=192.168.1.100 freecad-mcp

Prerequisites:
  The FreeCAD Robust MCP Bridge must be running before starting this server.
  Start it via:
    - FreeCAD GUI: Install Robust MCP Bridge workbench, enable auto-start
    - Headless: just freecad::run-headless
    - Development: just freecad::run-gui
""",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information and exit",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Test FreeCAD connection and exit (doesn't start MCP server)",
    )

    parser.add_argument(
        "--mode",
        choices=["xmlrpc", "socket", "embedded"],
        help="Connection mode (overrides FREECAD_MODE env var)",
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        help="Transport type (overrides FREECAD_TRANSPORT env var)",
    )

    parser.add_argument(
        "--host",
        help="Host for FreeCAD connection (overrides FREECAD_SOCKET_HOST)",
    )

    parser.add_argument(
        "--port",
        type=int,
        help="Port for FreeCAD connection (mode-dependent)",
    )

    parser.add_argument(
        "--http-host",
        help="Host/address for HTTP transport to bind to "
        "(overrides FREECAD_HTTP_HOST; default: 127.0.0.1)",
    )

    parser.add_argument(
        "--http-port",
        type=int,
        help="Port for HTTP transport (overrides FREECAD_HTTP_PORT)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (overrides FREECAD_LOG_LEVEL)",
    )

    return parser.parse_args()


def main() -> None:
    """Run the FreeCAD Robust MCP Server."""
    global mcp

    # Parse arguments first - this handles --help without connecting to FreeCAD
    args = parse_args()

    # Handle --version
    if args.version:
        try:
            from importlib.metadata import version

            ver = version("freecad-mcp")
        except Exception:
            ver = "unknown"
        print(f"freecad-mcp {ver}")
        print(f"Instance ID: {INSTANCE_ID}")
        sys.exit(0)

    # Handle --check (test connection without starting MCP server)
    if args.check:
        import asyncio

        success = asyncio.run(
            check_freecad_connection(mode=args.mode, host=args.host, port=args.port)
        )
        sys.exit(0 if success else 1)

    # Apply CLI arguments as environment variables (they override existing ones)
    apply_cli_args_to_env(args)

    # Now get config (which reads from environment)
    config = get_config()

    # Set up logging
    logging.getLogger().setLevel(config.log_level)

    # Print instance ID to stderr only for test automation (when env var is set).
    # This avoids unwanted output during normal use.
    # Must use stderr because stdout is reserved for JSON-RPC in stdio mode.
    if os.environ.get("FREECAD_MCP_TESTING"):
        print(f"FREECAD_MCP_INSTANCE_ID={INSTANCE_ID}", file=sys.stderr, flush=True)

    logger.info("Starting FreeCAD Robust MCP Server")
    logger.info("Instance ID: %s", INSTANCE_ID)
    logger.info("Mode: %s", config.mode.value)
    logger.info("Transport: %s", config.transport.value)

    # Build transport security ONLY for HTTP transport
    transport_security = None
    if config.transport == TransportType.HTTP:
        transport_security = _build_transport_security(config)
        if not is_loopback_host(config.http_host):
            logger.warning(
                "HTTP transport bound to '%s' - remote MCP access is exposed "
                "without authentication. Secure it with auth, TLS or a trusted "
                "reverse proxy.",
                config.http_host,
            )

    # Create FastMCP with full configuration (including security).
    # Keep it local until components are registered so that a registration
    # failure never publishes a partially initialized instance.
    server = FastMCP(
        name="freecad-mcp",
        lifespan=lifespan,
        host=config.http_host,
        port=config.http_port,
        log_level=config.log_level,  # type: ignore[arg-type]
        transport_security=transport_security,
    )

    register_all_components(server)

    # Publish the package-level export only after registration succeeded so
    # that ``import freecad_mcp; freecad_mcp.mcp`` returns the live instance.
    # Callers that imported ``mcp`` before startup still hold the None
    # binding; they should use get_mcp() to resolve it at call time.
    import freecad_mcp

    mcp = server
    freecad_mcp.mcp = server

    # Run the server; clear both bindings when the transport ends (normal
    # shutdown or failure) so get_mcp() never returns a stopped instance.
    try:
        if config.transport == TransportType.HTTP:
            logger.info(
                "Starting HTTP transport on %s:%d", config.http_host, config.http_port
            )
            server.run(transport="streamable-http")
        else:
            logger.info("Starting stdio transport")
            logger.info(
                "Waiting for MCP client connection (FreeCAD connection tested "
                "on first request)..."
            )
            logger.info(
                "Tip: Use 'freecad-mcp --check' to test FreeCAD connection directly"
            )
            server.run()
    finally:
        mcp = None
        freecad_mcp.mcp = None


if __name__ == "__main__":
    main()
