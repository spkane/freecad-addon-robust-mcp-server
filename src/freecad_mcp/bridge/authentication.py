"""Client-side request proof construction for paired FreeCAD bridges."""

import hashlib
import hmac
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_mcp.config import ServerConfig

_CLIENT_ID = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
_CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_DOMAIN = b"freecad-robust-mcp-bridge-request-v1\x00"


def credentials_from_config(
    config: "ServerConfig",
) -> tuple[str, Callable[[bytes], bytes]]:
    """Load the explicitly configured bridge identity and shared-secret signer.

    Raises:
        ValueError: If either credential is missing or malformed.
    """
    client_id = config.bridge_client_id
    configured_secret = config.bridge_secret
    if client_id is None and configured_secret is None:
        from freecad_mcp.bridge.credential_store import read_credential

        client_id, raw = read_credential()
    elif configured_secret is not None:
        raw = configured_secret.get_secret_value()
    else:
        raw = ""
    if not isinstance(client_id, str) or _CLIENT_ID.fullmatch(client_id) is None:
        raise ValueError("A valid bridge client ID and secret are required")
    if re.fullmatch(r"[0-9a-fA-F]{64}", raw) is None:
        raise ValueError("Bridge secret must be 64 hexadecimal characters")
    return client_id, create_hmac_signer(bytes.fromhex(raw))


def create_hmac_signer(secret: bytes) -> Callable[[bytes], bytes]:
    """Create a request signer for a paired 32-byte shared secret.

    Raises:
        ValueError: If the credential is not exactly 32 bytes.
    """
    if not isinstance(secret, bytes) or len(secret) != 32:
        raise ValueError("Bridge credential must be exactly 32 bytes")

    def sign(message: bytes) -> bytes:
        return hmac.digest(secret, message, "sha256")

    return sign


def request_proof_message(
    client_id: str, challenge: str, transport: str, body: bytes
) -> bytes:
    """Bind a paired identity, transport, one-use challenge, and request bytes.

    Raises:
        ValueError: If the request proof inputs are invalid.
    """
    if (
        not isinstance(client_id, str)
        or _CLIENT_ID.fullmatch(client_id) is None
        or not isinstance(challenge, str)
        or _CHALLENGE.fullmatch(challenge) is None
        or transport not in ("xmlrpc", "socket")
        or not isinstance(body, bytes)
    ):
        raise ValueError("Invalid bridge request proof input")
    return (
        _DOMAIN
        + client_id.encode("ascii")
        + b"\x00"
        + transport.encode("ascii")
        + b"\x00"
        + challenge.encode("ascii")
        + b"\x00"
        + hashlib.sha256(body).digest()
    )
