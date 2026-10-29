"""Verify the container smoke check rejects incomplete MCP responses."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from scripts import smoke_container


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_version", [True, False])
async def test_bridge_smoke_requires_a_real_version(
    monkeypatch: pytest.MonkeyPatch, valid_version: bool
) -> None:
    """A successful protocol response alone must not hide a failed tool call."""
    session = SimpleNamespace(
        initialize=AsyncMock(
            return_value=SimpleNamespace(
                server_info=SimpleNamespace(name="freecad-mcp")
            )
        ),
        list_tools=AsyncMock(
            return_value=SimpleNamespace(
                tools=[SimpleNamespace(name="get_freecad_version")]
            )
        ),
        call_tool=AsyncMock(
            return_value=SimpleNamespace(
                is_error=False,
                structured_content={"version": "1.1.4"} if valid_version else {},
            )
        ),
    )

    @asynccontextmanager
    async def streams(_parameters):
        yield (None, None)

    @asynccontextmanager
    async def client(*_streams):
        yield session

    monkeypatch.setattr(smoke_container, "stdio_client", streams)
    monkeypatch.setattr(smoke_container, "ClientSession", client)
    if valid_version:
        await smoke_container.check_image("test-image", bridge=True)
        session.call_tool.assert_awaited_once_with("get_freecad_version")
    else:
        with pytest.raises(RuntimeError, match="did not return a version"):
            await smoke_container.check_image("test-image", bridge=True)
