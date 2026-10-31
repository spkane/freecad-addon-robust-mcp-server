"""Request-bound authentication primitives for the FreeCAD bridge.

This module does not configure a key store or authenticate listener requests by
itself. The listener must obtain a trusted client verifier and call this logic
before parsing or dispatching a privileged request.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
from typing import TYPE_CHECKING

if __package__:
    from .challenges import ChallengeStore
else:
    from challenges import ChallengeStore  # type: ignore[import-not-found,no-redef]

if TYPE_CHECKING:
    from collections.abc import Callable
    from email.message import Message

_CLIENT_ID = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
_CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_DOMAIN = b"freecad-robust-mcp-bridge-request-v1\x00"
_MAX_PROOF_BYTES = 8192
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")


def create_hmac_verifier(
    lookup: Callable[[str], bytes | None],
) -> Callable[[str, bytes, bytes], bool]:
    """Verify request proofs using individually paired 32-byte shared secrets.

    The lookup is responsible for credential protection and revocation. A
    shared secret permits anyone who can read it to impersonate that client.
    """

    def verify(client_id: str, message: bytes, proof: bytes) -> bool:
        if not isinstance(client_id, str) or _CLIENT_ID.fullmatch(client_id) is None:
            return False
        try:
            secret = lookup(client_id)
            if not isinstance(secret, bytes) or len(secret) != 32:
                return False
            return hmac.compare_digest(hmac.digest(secret, message, "sha256"), proof)
        except Exception:
            return False

    return verify


class PairingRequiredError(RuntimeError):
    """The shared per-user bridge pairing has not been created yet."""


def authenticator_from_environment() -> BridgeAuthenticator:
    """Load an explicitly configured shared credential for this bridge.

    Raises:
        RuntimeError: If the client ID or shared secret is missing or invalid.
    """
    import os

    client_id = os.environ.get("FREECAD_BRIDGE_CLIENT_ID", "")
    secret_hex = os.environ.get("FREECAD_BRIDGE_SECRET", "")
    if not client_id and not secret_hex:
        if __package__:
            from .credential_store import read_credential
        else:
            from credential_store import read_credential  # type: ignore[import-not-found,no-redef]
        try:
            client_id, secret_hex = read_credential()
        except FileNotFoundError as exc:
            raise PairingRequiredError(
                "MCP Bridge is not paired yet. On this computer, open a terminal "
                "and run `freecad-mcp --pair-bridge` using the installed MCP "
                "server. Then select Start MCP Bridge in FreeCAD, or restart "
                "FreeCAD if running headless. "
                "If the command is not on your PATH, use the full path to your "
                "installed freecad-mcp executable. Installation and pairing: "
                "https://spkane.github.io/freecad-addon-robust-mcp-server/"
                "latest/getting-started/installation/"
            ) from exc
        except (OSError, ValueError, RuntimeError) as exc:
            raise RuntimeError(
                "Cannot start the FreeCAD bridge: a trusted client authentication "
                "provider is required; create a secure bridge pairing first"
            ) from exc
    if (
        _CLIENT_ID.fullmatch(client_id) is None
        or re.fullmatch(r"[0-9a-fA-F]{64}", secret_hex) is None
    ):
        raise RuntimeError(
            "Cannot start the FreeCAD bridge: a trusted client authentication "
            "provider is required (configure a valid client ID and secret)"
        )
    secret = bytes.fromhex(secret_hex)
    return BridgeAuthenticator(
        create_hmac_verifier(
            lambda candidate: secret if candidate == client_id else None
        )
    )


class PairedClientVerifier:
    """Resolve approved public keys for every request and verify their proofs.

    The lookup must use an externally protected trust store. This class does not
    create a trust store or provide an operating-system isolation boundary.
    """

    def __init__(
        self,
        lookup: Callable[[str], bytes | None],
        verify_signature: Callable[[bytes, bytes, bytes], bool],
    ) -> None:
        """Use an authoritative key lookup and a signature verification provider.

        Args:
            lookup: Resolve an approved fingerprint to canonical public key bytes.
            verify_signature: Verify a signature with the resolved public key.
        """
        self._lookup = lookup
        self._verify_signature = verify_signature

    def __call__(self, client_id: str, message: bytes, proof: bytes) -> bool:
        """Reject unknown, revoked, malformed, or incorrectly identified keys."""
        if not isinstance(client_id, str) or _FINGERPRINT.fullmatch(client_id) is None:
            return False
        try:
            key = self._lookup(client_id)
            if not isinstance(key, bytes) or not key or len(key) > 8192:
                return False
            fingerprint = hashlib.sha256(key).hexdigest()
            if not hmac.compare_digest(fingerprint, client_id):
                return False
            return self._verify_signature(key, message, proof) is True
        except Exception:
            return False


def create_ed25519_verifier(
    lookup: Callable[[str], bytes | None],
) -> PairedClientVerifier:
    """Create a verifier for raw 32-byte Ed25519 public keys.

    The supplied lookup must be backed by an independently protected trust
    store. This function does not establish that operating-system boundary.

    Args:
        lookup: Resolve an approved key fingerprint to its raw public key.

    Returns:
        A verifier accepting only valid Ed25519 signatures from approved keys.

    Raises:
        RuntimeError: If the FreeCAD runtime cannot load the crypto provider.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except (ImportError, OSError) as e:
        raise RuntimeError(
            "The FreeCAD bridge requires a compatible Ed25519 crypto provider"
        ) from e

    def verify_signature(key: bytes, message: bytes, signature: bytes) -> bool:
        if len(key) != 32 or len(signature) != 64:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(signature, message)
        except (InvalidSignature, ValueError):
            return False
        return True

    return PairedClientVerifier(lookup, verify_signature)


def create_p256_verifier(
    lookup: Callable[[str], bytes | None],
) -> PairedClientVerifier:
    """Create a verifier for uncompressed SEC1 P-256 keys and DER signatures.

    Args:
        lookup: Resolve an approved fingerprint to a 65-byte public key.

    Returns:
        A verifier using ECDSA with SHA-256.

    Raises:
        RuntimeError: If the FreeCAD runtime cannot load the crypto provider.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
    except (ImportError, OSError) as e:
        raise RuntimeError(
            "The FreeCAD bridge requires a compatible P-256 crypto provider"
        ) from e

    def verify_signature(key: bytes, message: bytes, signature: bytes) -> bool:
        if len(key) != 65 or key[0] != 4 or not 8 <= len(signature) <= 72:
            return False
        try:
            public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), key
            )
            public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        except (InvalidSignature, ValueError):
            return False
        return True

    return PairedClientVerifier(lookup, verify_signature)


def request_proof_message(
    client_id: str,
    challenge: str,
    transport: str,
    request_body: bytes,
) -> bytes:
    """Build the domain-separated message a paired client must authenticate.

    Args:
        client_id: Identifier of the paired client.
        challenge: Single-use server nonce.
        transport: Either ``xmlrpc`` or ``socket``.
        request_body: Exact wire request body to be dispatched.

    Returns:
        A deterministic byte string binding identity, transport, nonce and body.

    Raises:
        ValueError: If any identifier or body is malformed.
    """
    if (
        not isinstance(client_id, str)
        or _CLIENT_ID.fullmatch(client_id) is None
        or not isinstance(challenge, str)
        or _CHALLENGE.fullmatch(challenge) is None
        or transport not in ("xmlrpc", "socket")
        or not isinstance(request_body, bytes)
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
        + hashlib.sha256(request_body).digest()
    )


class BridgeAuthenticator:
    """Consume one-use challenges and delegate proof validation to a key provider."""

    def __init__(
        self,
        verifier: Callable[[str, bytes, bytes], bool],
        challenges: ChallengeStore | None = None,
    ) -> None:
        """Initialize with a paired-client verifier and challenge store.

        Args:
            verifier: Validates a client's proof for the given message.
            challenges: Optional challenge store, primarily for tests.
        """
        self._verifier = verifier
        self._challenges = challenges if challenges is not None else ChallengeStore()

    def issue_challenge(self) -> str:
        """Issue a random, short-lived request challenge."""
        return self._challenges.issue()

    def verify_xmlrpc_headers(self, headers: Message, body: bytes) -> bool:
        """Verify one unambiguous set of authentication headers and raw XML.

        This must be called after a bounded body read and before XML parsing.
        Header duplication is rejected even when duplicate values match.

        Args:
            headers: Parsed HTTP headers from the XML-RPC request.
            body: Exact bounded request bytes, before XML parsing.

        Returns:
            True only when all headers and the request proof are valid.
        """
        values = [
            headers.get_all(name, [])
            for name in (
                "X-FreeCAD-Client",
                "X-FreeCAD-Challenge",
                "X-FreeCAD-Proof",
            )
        ]
        if any(len(value) != 1 for value in values):
            return False
        return self.verify(values[0][0], values[1][0], "xmlrpc", body, values[2][0])

    def verify(
        self,
        client_id: object,
        challenge: object,
        transport: object,
        request_body: object,
        encoded_proof: object,
    ) -> bool:
        """Consume a challenge and verify the proof against the exact request.

        Malformed input, a replay, an unpaired client or a verifier error must
        fail closed. A challenge is consumed even when proof validation fails.

        Args:
            client_id: Claimed paired-client identifier.
            challenge: Server-issued nonce.
            transport: Request protocol identifier.
            request_body: Raw request bytes before deserialization.
            encoded_proof: Base64-encoded signature or authentication proof.

        Returns:
            True only when a fresh challenge and proof both validate.
        """
        if not self._challenges.consume(challenge):
            return False
        if (
            not isinstance(client_id, str)
            or not isinstance(challenge, str)
            or not isinstance(transport, str)
            or not isinstance(request_body, bytes)
            or not isinstance(encoded_proof, str)
            or len(encoded_proof) > (_MAX_PROOF_BYTES * 4 // 3 + 4)
        ):
            return False
        try:
            proof = base64.b64decode(encoded_proof, validate=True)
            if not proof or len(proof) > _MAX_PROOF_BYTES:
                return False
            message = request_proof_message(
                client_id, challenge, transport, request_body
            )
            return self._verifier(client_id, message, proof) is True
        except (ValueError, binascii.Error, UnicodeError):
            return False
        except Exception:
            # Key-provider errors are not authorization and must not expose keys.
            return False
