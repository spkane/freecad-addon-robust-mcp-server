"""Tests for the bridge request authentication primitives."""

import base64
import builtins
import hashlib
import hmac
import importlib
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from freecad_mcp.bridge.authentication import request_proof_message

ADDON_DIR = Path(__file__).parents[3] / "freecad" / "RobustMCPBridge"
TEST_KEY = b"a test key used only to verify the callback interface"


@pytest.fixture
def auth_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import the standalone bridge package without launching FreeCAD."""
    monkeypatch.syspath_prepend(str(ADDON_DIR))
    return importlib.import_module("freecad_mcp_bridge.authentication")


def _verifier(client_id: str, message: bytes, proof: bytes) -> bool:
    """Simulate one paired client with a constant-time test verifier."""
    expected = hmac.digest(TEST_KEY, message, "sha256")
    return client_id == "paired" and hmac.compare_digest(expected, proof)


def _proof(module: Any, client_id: str, challenge: str, body: bytes) -> str:
    """Build a test-only proof for an XML-RPC request."""
    message = module.request_proof_message(client_id, challenge, "xmlrpc", body)
    return base64.b64encode(hmac.digest(TEST_KEY, message, "sha256")).decode()


def test_authorized_request_cannot_be_replayed(auth_module: Any) -> None:
    """A valid proof succeeds exactly once for its issued challenge."""
    auth = auth_module.BridgeAuthenticator(_verifier)
    challenge = auth.issue_challenge()
    body = b"<methodCall/>"
    proof = _proof(auth_module, "paired", challenge, body)
    assert auth.verify("paired", challenge, "xmlrpc", body, proof) is True
    assert auth.verify("paired", challenge, "xmlrpc", body, proof) is False


@pytest.mark.parametrize("transport", ["xmlrpc", "socket"])
def test_client_and_addon_construct_identical_proof_messages(
    auth_module: Any, transport: str
) -> None:
    """The separately installed client and addon must use the same wire format."""
    challenge = auth_module.BridgeAuthenticator(_verifier).issue_challenge()
    body = b"request bytes\x00\xff"
    assert request_proof_message("paired", challenge, transport, body) == (
        auth_module.request_proof_message("paired", challenge, transport, body)
    )


def test_paired_client_verifier_checks_fingerprint_and_revocation(
    auth_module: Any,
) -> None:
    """Revocation takes effect for subsequent proofs and key substitution fails."""
    public_key = b"canonical public key test fixture"
    client_id = hashlib.sha256(public_key).hexdigest()
    approved = {client_id: public_key}

    def verify_signature(key: bytes, message: bytes, proof: bytes) -> bool:
        return key == public_key and message == b"message" and proof == b"signature"

    verifier = auth_module.PairedClientVerifier(approved.get, verify_signature)
    assert verifier(client_id, b"message", b"signature")
    assert not verifier(client_id, b"message", b"incorrect")
    approved[client_id] = b"substituted key"
    assert not verifier(client_id, b"message", b"signature")
    del approved[client_id]
    assert not verifier(client_id, b"message", b"signature")
    assert not verifier("unpaired", b"message", b"signature")


def test_paired_client_verifier_fails_closed_on_provider_error(
    auth_module: Any,
) -> None:
    """An unavailable trust store cannot authorize a client."""

    def unavailable(_client_id: str) -> bytes | None:
        raise RuntimeError("unavailable")

    verifier = auth_module.PairedClientVerifier(unavailable, lambda *_args: True)
    assert not verifier("a" * 64, b"message", b"signature")


def test_ed25519_provider_missing_fails_closed(
    auth_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unavailable FreeCAD crypto dependency must not allow a downgrade."""
    original_import = builtins.__import__

    def import_without_crypto(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("cryptography"):
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_crypto)
    with pytest.raises(RuntimeError, match="compatible Ed25519 crypto provider"):
        auth_module.create_ed25519_verifier(lambda _client_id: None)


@pytest.mark.parametrize("transport", ["socket", "xmlrpc"])
def test_real_signature_authentication_and_revocation(
    auth_module: Any, transport: str
) -> None:
    """Validate real asymmetric signatures and reject a revoked client."""
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    client_id = hashlib.sha256(public_bytes).hexdigest()
    approved = {client_id: public_bytes}

    verifier = auth_module.create_ed25519_verifier(approved.get)
    auth = auth_module.BridgeAuthenticator(verifier)
    challenge = auth.issue_challenge()
    body = b"request body"
    message = request_proof_message(client_id, challenge, transport, body)
    proof = base64.b64encode(private_key.sign(message)).decode("ascii")
    assert auth.verify(client_id, challenge, transport, body, proof)
    assert not auth.verify(client_id, challenge, transport, body, proof)

    challenge = auth.issue_challenge()
    message = request_proof_message(client_id, challenge, transport, body)
    proof = base64.b64encode(private_key.sign(message)).decode("ascii")
    del approved[client_id]
    assert not auth.verify(client_id, challenge, transport, body, proof)


@pytest.mark.parametrize("altered", ["body", "transport", "identity", "proof"])
def test_proof_is_bound_to_exact_request(auth_module: Any, altered: str) -> None:
    """A modified request or client identity is rejected and consumes its nonce."""
    auth = auth_module.BridgeAuthenticator(_verifier)
    challenge = auth.issue_challenge()
    body = b"<methodCall/>"
    proof = _proof(auth_module, "paired", challenge, body)
    client = "other" if altered == "identity" else "paired"
    received_body = b"<other/>" if altered == "body" else body
    transport = "socket" if altered == "transport" else "xmlrpc"
    received_proof = (
        base64.b64encode(b"wrong").decode() if altered == "proof" else proof
    )
    assert not auth.verify(client, challenge, transport, received_body, received_proof)
    assert not auth.verify("paired", challenge, "xmlrpc", body, proof)


@pytest.mark.parametrize("proof", [None, "!", "", "A" * 12000])
def test_malformed_proof_consumes_challenge(auth_module: Any, proof: object) -> None:
    """Malformed or oversized proofs fail closed and cannot be retried."""
    auth = auth_module.BridgeAuthenticator(_verifier)
    challenge = auth.issue_challenge()
    assert not auth.verify("paired", challenge, "xmlrpc", b"test", proof)
    assert not auth.verify("paired", challenge, "xmlrpc", b"test", proof)


def test_key_provider_errors_fail_closed(auth_module: Any) -> None:
    """A failed key provider never authenticates a request."""

    def unavailable(_client_id: str, _message: bytes, _proof: bytes) -> bool:
        raise RuntimeError("provider unavailable")

    auth = auth_module.BridgeAuthenticator(unavailable)
    challenge = auth.issue_challenge()
    assert not auth.verify("paired", challenge, "socket", b"request", "eA==")


def test_xmlrpc_headers_bind_body_and_reject_replay(auth_module: Any) -> None:
    """HTTP authentication uses the original XML bytes and a one-use nonce."""
    auth = auth_module.BridgeAuthenticator(_verifier)
    challenge = auth.issue_challenge()
    body = b"<methodCall/>"
    headers = Message()
    headers["X-FreeCAD-Client"] = "paired"
    headers["X-FreeCAD-Challenge"] = challenge
    headers["X-FreeCAD-Proof"] = _proof(auth_module, "paired", challenge, body)
    assert auth.verify_xmlrpc_headers(headers, body)
    assert not auth.verify_xmlrpc_headers(headers, body)


def test_xmlrpc_headers_reject_altered_body(auth_module: Any) -> None:
    """A valid proof for one XML body must not authorize modified XML."""
    auth = auth_module.BridgeAuthenticator(_verifier)
    challenge = auth.issue_challenge()
    headers = Message()
    headers["X-FreeCAD-Client"] = "paired"
    headers["X-FreeCAD-Challenge"] = challenge
    headers["X-FreeCAD-Proof"] = _proof(auth_module, "paired", challenge, b"first")
    assert not auth.verify_xmlrpc_headers(headers, b"modified")
    assert not auth.verify_xmlrpc_headers(headers, b"first")


@pytest.mark.parametrize(
    "header", ["X-FreeCAD-Client", "X-FreeCAD-Challenge", "X-FreeCAD-Proof"]
)
def test_xmlrpc_rejects_duplicate_auth_headers(auth_module: Any, header: str) -> None:
    """Ambiguous headers must never select one of multiple proofs or identities."""
    auth = auth_module.BridgeAuthenticator(_verifier)
    challenge = auth.issue_challenge()
    body = b"<methodCall/>"
    headers = Message()
    headers["X-FreeCAD-Client"] = "paired"
    headers["X-FreeCAD-Challenge"] = challenge
    headers["X-FreeCAD-Proof"] = _proof(auth_module, "paired", challenge, body)
    headers[header] = headers[header]
    assert not auth.verify_xmlrpc_headers(headers, body)
