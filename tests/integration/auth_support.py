"""Authentication helpers for integration tests using a configured pairing."""

import xmlrpc.client
from typing import Any

from freecad_mcp.bridge.authentication import credentials_from_config
from freecad_mcp.bridge.xmlrpc import AuthenticatedXmlRpcTransport
from freecad_mcp.config import get_config


def integration_proxy(
    host: str = "localhost", port: int = 9875
) -> xmlrpc.client.ServerProxy:
    """Return an authenticated XML-RPC proxy for the configured bridge."""
    client_id, signer = credentials_from_config(get_config())
    transport = AuthenticatedXmlRpcTransport(client_id, signer, 10.0)
    return xmlrpc.client.ServerProxy(
        f"http://{host}:{port}", allow_none=True, transport=transport
    )


def integration_credentials() -> dict[str, Any]:
    """Return configured credentials for an authenticated bridge client."""
    client_id, signer = credentials_from_config(get_config())
    return {"client_id": client_id, "signer": signer}
