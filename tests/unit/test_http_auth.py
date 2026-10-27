"""Tests for HTTP bearer authentication."""

from typing import Any

import pytest
from starlette.responses import PlainTextResponse
from starlette.types import Message, Receive, Scope, Send

from freecad_mcp.http_auth import ApiKeyMiddleware

KEY = "test-only-key-0123456789abcdef0123456789"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ([], 401),
        ([(b"authorization", b"Bearer wrong")], 401),
        ([(b"authorization", b"Basic " + KEY.encode())], 401),
        ([(b"authorization", b"Bearer " + KEY.encode())], 200),
        ([(b"authorization", b"bearer " + KEY.encode())], 200),
        (
            [(b"authorization", b"Bearer " + KEY.encode())] * 2,
            401,
        ),
    ],
)
async def test_http_requests_require_one_correct_bearer(
    headers: list[tuple[bytes, bytes]], status: int
) -> None:
    """Only one correct bearer token permits a request to reach the app."""
    calls: list[bool] = []
    messages: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        calls.append(True)
        await PlainTextResponse("ok")(scope, receive, send)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": headers,
    }
    await ApiKeyMiddleware(app, KEY)(scope, receive, send)
    assert messages[0]["status"] == status
    assert bool(calls) == (status == 200)


@pytest.mark.parametrize("key", ["", "short", " " * 32, "é" * 32])
def test_invalid_api_keys_fail_closed(key: str) -> None:
    """Missing or malformed keys cannot configure HTTP authentication."""

    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise AssertionError("not called")

    with pytest.raises(ValueError):
        ApiKeyMiddleware(app, key)
