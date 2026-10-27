"""Test-only credentials for integration tests against a disposable bridge.

The deterministic key is public test data and must never be used in production.
"""

import hashlib
import xmlrpc.client
from collections.abc import Callable
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from freecad_mcp.bridge.xmlrpc import AuthenticatedXmlRpcTransport

_TEST_KEY = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
_PUBLIC = _TEST_KEY.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
)
TEST_CLIENT_ID = hashlib.sha256(_PUBLIC).hexdigest()
TEST_SIGNER: Callable[[bytes], bytes] = _TEST_KEY.sign


def integration_proxy(
    host: str = "localhost", port: int = 9875
) -> xmlrpc.client.ServerProxy:
    """Return an authenticated XML-RPC proxy for the disposable test bridge."""
    transport = AuthenticatedXmlRpcTransport(TEST_CLIENT_ID, TEST_SIGNER, 10.0)
    return xmlrpc.client.ServerProxy(
        f"http://{host}:{port}", allow_none=True, transport=transport
    )


def integration_credentials() -> dict[str, Any]:
    """Return test-only constructor arguments for an authenticated client."""
    return {"client_id": TEST_CLIENT_ID, "signer": TEST_SIGNER}
