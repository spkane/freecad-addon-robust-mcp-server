"""Tests for the bridge request authentication primitives."""

import base64
import builtins
import hashlib
import hmac
import importlib
import os
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import SecretStr

from freecad_mcp.bridge.authentication import (
    create_hmac_signer,
    credentials_from_config,
    request_proof_message,
)
from freecad_mcp.config import ServerConfig

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


@pytest.mark.parametrize("transport", ["socket", "xmlrpc"])
def test_shared_secret_proofs_bind_requests_and_allow_revocation(
    auth_module: Any, transport: str
) -> None:
    """Shared-secret proofs require the right request and an active pairing."""
    secret = bytes(range(32))
    paired = {"client-1": secret}
    auth = auth_module.BridgeAuthenticator(auth_module.create_hmac_verifier(paired.get))
    sign = create_hmac_signer(secret)
    challenge = auth.issue_challenge()
    message = request_proof_message("client-1", challenge, transport, b"original")
    proof = base64.b64encode(sign(message)).decode("ascii")
    assert not auth.verify("client-1", challenge, transport, b"modified", proof)
    assert not auth.verify("client-1", challenge, transport, b"original", proof)

    challenge = auth.issue_challenge()
    message = request_proof_message("client-1", challenge, transport, b"original")
    proof = base64.b64encode(sign(message)).decode("ascii")
    assert auth.verify("client-1", challenge, transport, b"original", proof)
    challenge = auth.issue_challenge()
    message = request_proof_message("client-1", challenge, transport, b"original")
    proof = base64.b64encode(sign(message)).decode("ascii")
    del paired["client-1"]
    assert not auth.verify("client-1", challenge, transport, b"original", proof)


def test_shared_secret_provider_rejects_invalid_credentials(auth_module: Any) -> None:
    """Malformed secrets and unavailable credential stores fail closed."""
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        create_hmac_signer(b"short")
    verifier = auth_module.create_hmac_verifier(lambda _client: b"short")
    assert not verifier("client-1", b"message", b"proof")

    def unavailable(_client: str) -> bytes | None:
        raise OSError("unavailable")

    assert not auth_module.create_hmac_verifier(unavailable)(
        "client-1", b"message", b"proof"
    )


def test_configured_bridge_credentials_sign_requests() -> None:
    """Configured credentials produce the same proof as the underlying signer."""
    config = ServerConfig(
        bridge_client_id="client-1", bridge_secret=SecretStr("01" * 32)
    )
    client_id, sign = credentials_from_config(config)
    assert client_id == "client-1"
    assert sign(b"message") == hmac.digest(b"\x01" * 32, b"message", "sha256")
    assert "010101" not in repr(config)


def test_workbench_environment_credentials_authenticate_requests(
    auth_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The workbench accepts only the matching configured identity and secret."""
    monkeypatch.setenv("FREECAD_BRIDGE_CLIENT_ID", "client-1")
    monkeypatch.setenv("FREECAD_BRIDGE_SECRET", "01" * 32)
    auth = auth_module.authenticator_from_environment()
    challenge = auth.issue_challenge()
    message = request_proof_message("client-1", challenge, "xmlrpc", b"request")
    proof = base64.b64encode(create_hmac_signer(b"\x01" * 32)(message)).decode()
    assert auth.verify("client-1", challenge, "xmlrpc", b"request", proof)


def test_missing_pairing_explains_how_to_start_bridge(
    auth_module: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing credential gives setup instructions without starting a bridge."""
    monkeypatch.delenv("FREECAD_BRIDGE_CLIENT_ID", raising=False)
    monkeypatch.delenv("FREECAD_BRIDGE_SECRET", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    if os.name == "nt":
        pytest.skip("Windows uses Credential Manager rather than a file")
    with pytest.raises(auth_module.PairingRequiredError) as error:
        auth_module.authenticator_from_environment()
    assert "freecad-mcp --pair-bridge" in str(error.value)
    assert "Start MCP Bridge" in str(error.value)


@pytest.mark.parametrize(
    "client_id,secret", [("", "01" * 32), ("client", "01"), ("client", "zz" * 32)]
)
def test_workbench_rejects_missing_or_invalid_credentials(
    auth_module: Any, monkeypatch: pytest.MonkeyPatch, client_id: str, secret: str
) -> None:
    """Invalid environment configuration cannot start an authenticated bridge."""
    monkeypatch.setenv("FREECAD_BRIDGE_CLIENT_ID", client_id)
    monkeypatch.setenv("FREECAD_BRIDGE_SECRET", secret)
    with pytest.raises(RuntimeError, match="authentication provider is required"):
        auth_module.authenticator_from_environment()


@pytest.mark.parametrize(
    "client_id,secret",
    [(None, "01" * 32), ("bad id", "01" * 32), ("client", "zz" * 32), ("client", "01")],
)
def test_invalid_configured_bridge_credentials_fail_closed(
    client_id: str | None, secret: str
) -> None:
    """Invalid IDs and secrets cannot create a bridge signer."""
    config = ServerConfig(bridge_client_id=client_id, bridge_secret=SecretStr(secret))
    with pytest.raises(ValueError):
        credentials_from_config(config)


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


def test_p256_verifier_rejects_bad_signatures_and_noncanonical_keys(
    auth_module: Any,
) -> None:
    """Only an approved SEC1 uncompressed key and valid signature are accepted."""
    key = ec.generate_private_key(ec.SECP256R1())
    public_key = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    client_id = hashlib.sha256(public_key).hexdigest()
    approved = {client_id: public_key}
    verifier = auth_module.create_p256_verifier(approved.get)
    signature = key.sign(b"message", ec.ECDSA(hashes.SHA256()))
    assert verifier(client_id, b"message", signature)
    assert not verifier(client_id, b"changed", signature)
    assert not verifier(client_id, b"message", b"invalid")
    compressed = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
    )
    compressed_id = hashlib.sha256(compressed).hexdigest()
    approved[compressed_id] = compressed
    assert not verifier(compressed_id, b"message", signature)


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
