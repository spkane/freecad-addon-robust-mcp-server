"""Authentication helpers for integration tests using a configured pairing."""

import xmlrpc.client
from typing import Any

from freecad_mcp.bridge.authentication import credentials_from_config
from freecad_mcp.bridge.xmlrpc import AuthenticatedXmlRpcTransport
from freecad_mcp.config import get_config


def integration_proxy(
    host: str | None = None, port: int | None = None
) -> xmlrpc.client.ServerProxy:
    """Return an authenticated XML-RPC proxy for the configured bridge."""
    config = get_config()
    host = host or config.socket_host
    port = port if port is not None else config.xmlrpc_port
    client_id, signer = credentials_from_config(config)
    transport = AuthenticatedXmlRpcTransport(client_id, signer, 10.0)
    return xmlrpc.client.ServerProxy(
        f"http://{host}:{port}", allow_none=True, transport=transport
    )


def integration_credentials() -> dict[str, Any]:
    """Return configured credentials for an authenticated bridge client."""
    client_id, signer = credentials_from_config(get_config())
    return {"client_id": client_id, "signer": signer}
