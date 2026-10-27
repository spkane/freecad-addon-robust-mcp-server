"""Launch the MCP server with a deterministic test-only bridge signer.

This fixture is used only by protocol subprocess tests; it is not an identity
provider or a production entry point.
"""

import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import freecad_mcp.bridge.xmlrpc as xmlrpc_bridge
from freecad_mcp.server import main

test_key = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
public_key = test_key.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
)
client_id = hashlib.sha256(public_key).hexdigest()
original_bridge = xmlrpc_bridge.XmlRpcBridge


class TestXmlRpcBridge(original_bridge):
    """Inject a public, deterministic test credential into the real client."""

    def __init__(self, **kwargs):
        """Use the test credential with all normal client arguments."""
        super().__init__(**kwargs, client_id=client_id, signer=test_key.sign)


if __name__ == "__main__":
    xmlrpc_bridge.XmlRpcBridge = TestXmlRpcBridge  # type: ignore[misc,assignment]
    main()
