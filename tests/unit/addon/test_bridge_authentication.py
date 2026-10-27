"""Tests for the bridge request authentication primitives."""

import base64
import hmac
import importlib
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

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
