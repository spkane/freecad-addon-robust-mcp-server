"""Client-side request proof construction for paired FreeCAD bridges."""

import hashlib
import re

_CLIENT_ID = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
_CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_DOMAIN = b"freecad-robust-mcp-bridge-request-v1\x00"


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
