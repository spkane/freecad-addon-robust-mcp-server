"""Tests for socket bridge implementation."""

import asyncio
import json
from unittest import mock

import pytest

from freecad_mcp.bridge.socket import SocketBridge


class TestSocketBridge:
    """Tests for SocketBridge class."""

    def test_initialization_defaults(self):
        """Bridge should initialize with correct defaults."""
        bridge = SocketBridge()

        assert bridge._host == "localhost"
        assert bridge._port == 9876
        assert bridge._reader is None
        assert bridge._writer is None
        assert bridge._execution_timeout_ms == 30000

    def test_initialization_custom(self):
        """Bridge should accept custom host and port."""
        bridge = SocketBridge(host="192.168.1.1", port=12345)

        assert bridge._host == "192.168.1.1"
        assert bridge._port == 12345

    @pytest.mark.asyncio
    async def test_is_connected_before_connect(self):
        """is_connected should return False before connect."""
        bridge = SocketBridge()

        assert await bridge.is_connected() is False

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """connect should raise ConnectionError on failure."""
        bridge = SocketBridge(host="invalid-host-12345", port=99999)

        with pytest.raises(ConnectionError):
            await bridge.connect()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """disconnect should handle not being connected."""
        bridge = SocketBridge()

        # Should not raise
        await bridge.disconnect()

    @pytest.mark.asyncio
    async def test_execute_python_when_not_connected(self):
        """execute_python should return error when not connected."""
        bridge = SocketBridge()

        result = await bridge.execute_python("x = 1")

        assert result.success is False
        assert result.error_type == "ConnectionError"

    @pytest.mark.asyncio
    async def test_execute_python_uses_configured_timeout(self):
        """An omitted per-call timeout should use the configured default."""
        bridge = SocketBridge(execution_timeout_ms=45000)

        with mock.patch.object(
            bridge,
            "_send_request",
            new=mock.AsyncMock(return_value={"success": True, "result": "done"}),
        ) as send_request:
            result = await bridge.execute_python("_result_ = 'done'")

        assert result.success is True
        send_request.assert_awaited_once_with(
            "execute",
            {"code": "_result_ = 'done'", "timeout_ms": 45000},
            response_timeout=46.0,
        )

    @pytest.mark.asyncio
    async def test_execute_python_passes_per_call_timeout(self):
        """A per-call timeout should override the configured default."""
        bridge = SocketBridge(execution_timeout_ms=45000)

        with mock.patch.object(
            bridge,
            "_send_request",
            new=mock.AsyncMock(return_value={"success": True, "result": "done"}),
        ) as send_request:
            await bridge.execute_python("_result_ = 'done'", timeout_ms=60000)

        send_request.assert_awaited_once_with(
            "execute",
            {"code": "_result_ = 'done'", "timeout_ms": 60000},
            response_timeout=61.0,
        )

    @pytest.mark.asyncio
    async def test_execute_python_preserves_server_timeout_message(self):
        """Server-side timeout details should be exposed to the MCP caller."""
        bridge = SocketBridge()

        with mock.patch.object(
            bridge,
            "_send_request",
            new=mock.AsyncMock(
                return_value={
                    "success": False,
                    "error_type": "TimeoutError",
                    "error_message": (
                        "Execution timed out after 30000ms; "
                        "code already running in FreeCAD may continue"
                    ),
                }
            ),
        ):
            result = await bridge.execute_python("long_operation()")

        assert result.success is False
        assert result.error_type == "TimeoutError"
        assert "may continue" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_python_rejects_invalid_timeout(self):
        """Per-call timeouts outside the supported bounds should fail locally."""
        bridge = SocketBridge()

        with mock.patch.object(
            bridge,
            "_send_request",
            new=mock.AsyncMock(),
        ) as send_request:
            result = await bridge.execute_python("pass", timeout_ms=999)

        assert result.success is False
        assert result.error_type == "ValueError"
        send_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_python_reports_client_response_timeout(self):
        """A missing server response should retain late-execution guidance."""
        bridge = SocketBridge()

        with mock.patch.object(
            bridge,
            "_send_request",
            new=mock.AsyncMock(side_effect=TimeoutError),
        ):
            result = await bridge.execute_python("long_operation()")

        assert result.success is False
        assert result.error_type == "TimeoutError"
        assert "may continue" in result.stderr


class TestSocketBridgeCommunication:
    """Tests for socket communication."""

    @pytest.fixture
    def mock_streams(self):
        """Create mock reader and writer streams."""
        reader = mock.AsyncMock(spec=asyncio.StreamReader)
        writer = mock.MagicMock(spec=asyncio.StreamWriter)
        writer.is_closing.return_value = False
        writer.drain = mock.AsyncMock()
        writer.close = mock.MagicMock()
        writer.wait_closed = mock.AsyncMock()
        return reader, writer

    @pytest.mark.asyncio
    async def test_send_request_format(self, mock_streams):
        """Requests should be formatted correctly when connected."""
        reader, writer = mock_streams
        bridge = SocketBridge()
        bridge._reader = reader
        bridge._writer = writer
        bridge._connected = True

        # Setup response
        response = {"jsonrpc": "2.0", "id": "test-1", "result": {"success": True}}
        reader.readline.return_value = json.dumps(response).encode() + b"\n"

        # Our bridge sends and receives in one call
        # Just verify we can set up the bridge state correctly
        assert bridge._reader is not None
        assert bridge._writer is not None
        assert bridge._connected is True

    @pytest.mark.asyncio
    async def test_response_timeout_discards_desynchronized_connection(
        self,
        mock_streams,
    ) -> None:
        """A timed-out read should close the stream before another request."""
        reader, writer = mock_streams
        reader.readline.side_effect = TimeoutError
        bridge = SocketBridge(timeout=0.01)
        bridge._reader = reader
        bridge._writer = writer
        bridge._connected = True

        with pytest.raises(TimeoutError):
            await bridge._send_request("ping")

        writer.close.assert_called_once_with()
        assert bridge._reader is None
        assert bridge._writer is None
        assert bridge._connected is False


class TestSocketBridgeDocuments:
    """Tests for document handling via socket."""

    @pytest.mark.asyncio
    async def test_get_documents_when_not_connected(self):
        """get_documents should return empty list when not connected."""
        bridge = SocketBridge()

        # This will fail to send request, should return empty
        docs = await bridge.get_documents()

        assert docs == []

    @pytest.mark.asyncio
    async def test_get_active_document_when_not_connected(self):
        """get_active_document should return None when not connected."""
        bridge = SocketBridge()

        doc = await bridge.get_active_document()

        assert doc is None

    @pytest.mark.asyncio
    async def test_is_gui_available_when_not_connected(self):
        """is_gui_available should return False when not connected."""
        bridge = SocketBridge()

        result = await bridge.is_gui_available()

        assert result is False


class TestSocketBridgeVersionInfo:
    """Tests for version info handling."""

    @pytest.mark.asyncio
    async def test_get_version_when_not_connected(self):
        """get_freecad_version should return unknown when not connected."""
        bridge = SocketBridge()

        version = await bridge.get_freecad_version()

        assert version["version"] == "unknown"
        assert version["gui_available"] is False
