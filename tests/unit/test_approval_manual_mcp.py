"""Verify the manual approval fixture never executes arbitrary input."""

import json
import sys
from pathlib import Path
from typing import Literal

import pytest
from mcp import StdioServerParameters
from mcp.client import Client
from mcp.types import ElicitResult, TextContent

SERVER = Path(__file__).resolve().parents[1] / "research" / "approval_manual_mcp.py"


@pytest.mark.asyncio
async def test_manual_fixture_rejects_other_code_and_elicitation_does_not_execute(
    tmp_path: Path,
) -> None:
    """The temporary client server accepts only its fixed reviewed example."""
    connection = tmp_path / "connection.json"
    connection.write_text(json.dumps({"port": 1, "secret": "78" * 32}))
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(SERVER), str(connection)]
    )
    questions = []

    async def callback(_context, params):
        questions.append(params.message)
        assert set(params.requested_schema) <= {"type", "properties", "required"}
        return ElicitResult(action="accept", content={"approved": True})

    async with Client(
        parameters, mode="legacy", elicitation_callback=callback
    ) as client:
        rejected = await client.call_tool("execute_python", {"code": "not_allowed()"})
        assert not rejected.is_error
        assert isinstance(rejected.content[0], TextContent)
        assert "TestInputRejected" in rejected.content[0].text
        accepted = await client.call_tool("elicitation_probe", {"code": "test text"})
        assert not accepted.is_error
        assert isinstance(accepted.content[0], TextContent)
        assert "PROBE_APPROVED" in accepted.content[0].text
        direct = await client.call_tool("elicitation_direct_probe", {"code": "direct"})
        assert not direct.is_error
        assert isinstance(direct.content[0], TextContent)
        assert "PROBE_APPROVED" in direct.content[0].text
        protocol = await client.call_tool("elicitation_protocol_probe", {})
        assert not protocol.is_error
    assert questions == [
        "Review this test text (it will not execute):\ntest text",
        "Review this test text (it will not execute):\ndirect",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, expected", [("decline", "PROBE_DENIED"), ("cancel", "PROBE_CANCELLED")]
)
async def test_direct_elicitation_decline_never_reports_approval(
    tmp_path: Path,
    action: Literal["decline", "cancel"],
    expected: str,
) -> None:
    """A declined direct probe cannot be mistaken for an affirmative answer."""
    connection = tmp_path / "connection.json"
    connection.write_text(json.dumps({"port": 1, "secret": "78" * 32}))
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(SERVER), str(connection)]
    )

    async def decline(_context, _params):
        return ElicitResult(action=action)

    async with Client(
        parameters, mode="legacy", elicitation_callback=decline
    ) as client:
        result = await client.call_tool("elicitation_direct_probe", {"code": "text"})
        assert not result.is_error
        assert isinstance(result.content[0], TextContent)
        assert expected in result.content[0].text


@pytest.mark.asyncio
async def test_direct_elicitation_without_back_channel_reports_unavailable(
    tmp_path: Path,
) -> None:
    """Modern SDK sessions cannot approve a direct request without a channel."""
    connection = tmp_path / "connection.json"
    connection.write_text(json.dumps({"port": 1, "secret": "78" * 32}))
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(SERVER), str(connection)]
    )
    async with Client(parameters, mode="auto") as client:
        result = await client.call_tool("elicitation_direct_probe", {"code": "text"})
        assert not result.is_error
        assert isinstance(result.content[0], TextContent)
        assert "PROBE_UNAVAILABLE" in result.content[0].text
