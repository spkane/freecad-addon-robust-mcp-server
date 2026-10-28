"""Static bearer authentication for the optional MCP HTTP endpoint."""

import hmac

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ApiKeyMiddleware:
    """Require one bearer credential for every HTTP request to the wrapped app.

    This is a static API key, not an OAuth authorization server. Key generation
    and secure storage are the caller's responsibility.
    """

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        """Initialize the middleware with a nonempty ASCII credential."""
        try:
            key = api_key.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("HTTP API key must be ASCII") from exc
        if len(key) < 32 or any(c <= 32 or c >= 127 for c in key):
            raise ValueError("HTTP API key must contain at least 32 visible characters")
        self._app = app
        self._key = key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate HTTP requests before forwarding them to the MCP app."""
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        values = [
            value
            for name, value in scope["headers"]
            if name.lower() == b"authorization"
        ]
        authorized = False
        if len(values) == 1:
            scheme, separator, token = values[0].partition(b" ")
            authorized = (
                scheme.lower() == b"bearer"
                and separator == b" "
                and hmac.compare_digest(token, self._key)
            )
        if not authorized:
            response = PlainTextResponse(
                "Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"}
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)
