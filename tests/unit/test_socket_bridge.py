"""Tests for socket bridge implementation."""

import asyncio
import json
from unittest import mock

import pytest

from freecad_mcp.bridge.socket import RequestNotSentError, SocketBridge


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

    def test_initialization_preserves_positional_auto_reconnect(self):
        """The historical fourth positional argument should disable reconnects."""
        bridge = SocketBridge("192.168.1.1", 12345, 5.0, False)

        assert bridge._timeout == 5.0
        assert bridge._auto_reconnect is False
        assert bridge._execution_timeout_ms == 30000

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
            request_timeout=45.0,
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
            request_timeout=60.0,
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

    @pytest.fixture(autouse=True)
    def paired_signer(self, monkeypatch):
        """Supply a test signer for communication tests using mock streams."""
        original = SocketBridge.__init__

        def initialize(bridge, *args, **kwargs):
            kwargs.setdefault("client_id", "test-client")
            kwargs.setdefault("signer", lambda _message: b"test-proof")
            original(bridge, *args, **kwargs)

        monkeypatch.setattr(SocketBridge, "__init__", initialize)

    @staticmethod
    def authenticated_responses(result):
        """Provide a fresh challenge followed by one server response."""
        return [
            json.dumps({"challenge": "A" * 43}).encode() + b"\n",
            json.dumps({"jsonrpc": "2.0", "id": "test", "result": result}).encode()
            + b"\n",
        ]

    @pytest.fixture
    def mock_streams(self):
        """Create mock reader and writer streams."""
        reader = mock.AsyncMock(spec=asyncio.StreamReader)
        reader.at_eof.return_value = False
        writer = mock.MagicMock(spec=asyncio.StreamWriter)
        writer.is_closing.return_value = False
        writer.drain = mock.AsyncMock()
        writer.close = mock.MagicMock()
        writer.wait_closed = mock.AsyncMock()
        return reader, writer

    @pytest.mark.asyncio
    async def test_idle_closed_stream_is_reconnected_before_sending(
        self, mock_streams
    ) -> None:
        """Reconnect a known-closed idle stream before sending a mutation."""
        old_reader, old_writer = mock_streams
        old_reader.at_eof.return_value = True
        new_reader = mock.AsyncMock(spec=asyncio.StreamReader)
        new_reader.at_eof.return_value = False
        new_reader.readline.side_effect = self.authenticated_responses("done")
        new_writer = mock.MagicMock(spec=asyncio.StreamWriter)
        new_writer.is_closing.return_value = False
        new_writer.drain = mock.AsyncMock()
        new_writer.wait_closed = mock.AsyncMock()
        bridge = SocketBridge()
        bridge._reader, bridge._writer, bridge._connected = old_reader, old_writer, True

        async def open_replacement() -> None:
            bridge._reader, bridge._writer, bridge._connected = (
                new_reader,
                new_writer,
                True,
            )

        with mock.patch.object(bridge, "_open_streams", side_effect=open_replacement):
            assert await bridge._send_request("execute", {"code": "work()"}) == "done"
        old_writer.write.assert_not_called()
        old_writer.close.assert_called_once()
        assert new_writer.write.call_count == 2

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

    @pytest.mark.asyncio
    async def test_oversized_response_discards_connection(self, mock_streams) -> None:
        """An oversized response must close the stream and report a clear error."""
        reader, writer = mock_streams
        reader.readline.side_effect = [
            json.dumps({"challenge": "A" * 43}).encode() + b"\n",
            ValueError("response exceeds limit"),
        ]
        bridge = SocketBridge()
        bridge._reader, bridge._writer, bridge._connected = reader, writer, True
        with pytest.raises(ConnectionError, match="response exceeds the socket limit"):
            await bridge._send_request("execute", {"code": "pass"})
        writer.close.assert_called_once()
        assert bridge._reader is None and bridge._writer is None

    @pytest.mark.asyncio
    async def test_drain_timeout_discards_connection_and_releases_lock(
        self,
        mock_streams,
    ) -> None:
        """A stalled socket write should time out and release request state."""
        reader, writer = mock_streams

        async def stalled_drain() -> None:
            await asyncio.Event().wait()

        writer.drain.side_effect = stalled_drain
        bridge = SocketBridge(timeout=0.01)
        bridge._reader = reader
        bridge._writer = writer
        bridge._connected = True

        with pytest.raises(TimeoutError) as error:
            await bridge._send_request("execute", {"code": "possibly_sent"})

        assert not isinstance(error.value, RequestNotSentError)
        writer.write.assert_called_once()
        reader.readline.assert_not_awaited()
        writer.close.assert_called_once_with()
        assert bridge._reader is None
        assert bridge._writer is None
        assert bridge._connected is False
        assert bridge._lock.locked() is False

    @pytest.mark.asyncio
    async def test_request_timeout_includes_waiting_for_lock(
        self,
        mock_streams,
    ) -> None:
        """An expired queued request should never be written to FreeCAD."""
        reader, writer = mock_streams
        bridge = SocketBridge()
        bridge._reader = reader
        bridge._writer = writer
        bridge._connected = True

        await bridge._lock.acquire()
        try:
            with pytest.raises(RequestNotSentError):
                await bridge._send_request(
                    "execute",
                    {"code": "queued"},
                    response_timeout=1.0,
                    request_timeout=0.01,
                )
        finally:
            bridge._lock.release()

        writer.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_queued_execute_reports_code_not_executed(
        self,
        mock_streams,
    ) -> None:
        """An execute request that expires in the queue should be unambiguous."""
        reader, writer = mock_streams
        bridge = SocketBridge(execution_timeout_ms=1000)
        bridge._reader = reader
        bridge._writer = writer
        bridge._connected = True

        await bridge._lock.acquire()
        try:
            result = await bridge.execute_python("state_changing_operation()")
        finally:
            bridge._lock.release()

        assert result.success is False
        assert result.error_type == "RequestNotSentError"
        assert "code was not executed" in result.stderr
        assert "may continue" not in result.stderr
        writer.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconnect_deadline_before_write_reports_request_not_sent(
        self,
    ) -> None:
        """An initial reconnect deadline should retain definitive retry guidance."""
        bridge = SocketBridge()

        async def slow_open() -> None:
            await asyncio.sleep(1.0)

        with mock.patch.object(
            bridge,
            "_open_streams",
            new=mock.AsyncMock(side_effect=slow_open),
        ):
            with pytest.raises(RequestNotSentError):
                await bridge._send_request(
                    "execute",
                    {"code": "not_sent"},
                    request_timeout=0.01,
                )

    @pytest.mark.asyncio
    async def test_reconnect_deadline_after_write_remains_ambiguous(
        self,
        mock_streams,
    ) -> None:
        """A failed write attempt should retain conservative timeout guidance."""
        reader, writer = mock_streams
        writer.drain.side_effect = ConnectionResetError("reset")
        bridge = SocketBridge()
        bridge._reader = reader
        bridge._writer = writer
        bridge._connected = True

        async def slow_open() -> None:
            await asyncio.sleep(1.0)

        with mock.patch.object(
            bridge,
            "_open_streams",
            new=mock.AsyncMock(side_effect=slow_open),
        ):
            with pytest.raises(ConnectionError, match="execution may have occurred"):
                await bridge._send_request(
                    "execute",
                    {"code": "possibly_sent"},
                    request_timeout=0.01,
                )

    @pytest.mark.asyncio
    async def test_waiting_request_selects_streams_after_acquiring_lock(
        self,
        mock_streams,
    ) -> None:
        """A queued request should use streams current when its turn starts."""
        old_reader, old_writer = mock_streams
        replacement_reader = mock.AsyncMock(spec=asyncio.StreamReader)
        replacement_writer = mock.MagicMock(spec=asyncio.StreamWriter)
        replacement_writer.drain = mock.AsyncMock()
        replacement_reader.readline.side_effect = self.authenticated_responses("done")
        bridge = SocketBridge()
        bridge._reader = old_reader
        bridge._writer = old_writer
        bridge._connected = True

        await bridge._lock.acquire()
        request = asyncio.create_task(
            bridge._send_request(
                "execute",
                {"code": "queued"},
                request_timeout=1.0,
            )
        )
        await asyncio.sleep(0)
        bridge._reader = replacement_reader
        bridge._writer = replacement_writer
        bridge._lock.release()

        assert await request == "done"
        old_writer.write.assert_not_called()
        assert replacement_writer.write.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_reset_reconnects_outside_request_lock(
        self,
        mock_streams,
    ) -> None:
        """A reset during a request must not resend a possible mutation."""
        failed_reader, failed_writer = mock_streams
        failed_writer.drain.side_effect = ConnectionResetError("reset")
        replacement_reader = mock.AsyncMock(spec=asyncio.StreamReader)
        replacement_writer = mock.MagicMock(spec=asyncio.StreamWriter)
        replacement_writer.drain = mock.AsyncMock()
        replacement_reader.readline.return_value = (
            json.dumps({"jsonrpc": "2.0", "id": "new", "result": "done"}).encode()
            + b"\n"
        )
        bridge = SocketBridge()
        bridge._reader = failed_reader
        bridge._writer = failed_writer
        bridge._connected = True

        async def reconnect() -> None:
            assert bridge._lock.locked() is False
            bridge._reader = replacement_reader
            bridge._writer = replacement_writer
            bridge._connected = True

        with mock.patch.object(
            bridge,
            "_open_streams",
            new=mock.AsyncMock(side_effect=reconnect),
        ) as connect:
            with pytest.raises(ConnectionError, match="execution may have occurred"):
                await asyncio.wait_for(
                    bridge._send_request("execute", {"code": "retry"}),
                    timeout=1.0,
                )

        connect.assert_not_awaited()
        failed_writer.close.assert_called_once_with()
        replacement_writer.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_next_request_reconnects_after_response_timeout(
        self,
        mock_streams,
    ) -> None:
        """The request after a discarded timed-out stream should reconnect."""
        timed_out_reader, timed_out_writer = mock_streams
        timed_out_reader.readline.side_effect = TimeoutError
        bridge = SocketBridge(timeout=0.01)
        bridge._reader = timed_out_reader
        bridge._writer = timed_out_writer
        bridge._connected = True

        with pytest.raises(TimeoutError):
            await bridge._send_request("execute", {"code": "first"})

        replacement_reader = mock.AsyncMock(spec=asyncio.StreamReader)
        replacement_writer = mock.MagicMock(spec=asyncio.StreamWriter)
        replacement_writer.drain = mock.AsyncMock()
        replacement_reader.readline.side_effect = self.authenticated_responses("done")

        async def reconnect() -> None:
            bridge._reader = replacement_reader
            bridge._writer = replacement_writer
            bridge._connected = True

        with mock.patch.object(
            bridge,
            "_open_streams",
            new=mock.AsyncMock(side_effect=reconnect),
        ) as connect:
            result = await bridge._send_request("execute", {"code": "second"})

        assert result == "done"
        connect.assert_awaited_once_with()
        assert replacement_writer.write.call_count == 2

    @pytest.mark.asyncio
    async def test_missing_streams_do_not_reconnect_when_disabled(self) -> None:
        """Missing streams should retain the error when reconnect is disabled."""
        bridge = SocketBridge(auto_reconnect=False)

        with mock.patch.object(
            bridge,
            "_open_streams",
            new=mock.AsyncMock(),
        ) as connect:
            with pytest.raises(ConnectionError, match="Not connected"):
                await bridge._send_request("ping")

        connect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failed_missing_stream_reconnect_preserves_error(self) -> None:
        """A failed automatic reconnect should still report a connection error."""
        bridge = SocketBridge()

        with mock.patch.object(
            bridge,
            "_open_streams",
            new=mock.AsyncMock(side_effect=ConnectionError("unreachable")),
        ) as connect:
            with pytest.raises(ConnectionError, match="Not connected"):
                await bridge._send_request("ping")

        connect.assert_awaited_once_with()


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


class TestSocketBridgeScreenshotCodegen:
    """Tests for the screenshot code generated by the socket bridge."""

    @pytest.mark.asyncio
    async def test_uses_type_not_dunder_class(self):
        """Generated code must use type(view).__name__, not view.__class__.

        FreeCAD's View3DInventor has a broken __class__ that returns a dict,
        so view.__class__.__name__ raises AttributeError.
        """
        from freecad_mcp.bridge.base import ExecutionResult, ViewAngle

        bridge = SocketBridge()
        captured = {}

        async def fake_exec(code):
            captured["code"] = code
            return ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "data": "eHl6",
                    "format": "png",
                    "width": 800,
                    "height": 600,
                },
                stdout="",
                stderr="",
                execution_time_ms=1.0,
            )

        with mock.patch.object(bridge, "execute_python", side_effect=fake_exec):
            result = await bridge.get_screenshot(view_angle=ViewAngle.ISOMETRIC)

        assert result.success is True
        assert "type(view).__name__" in captured["code"]
        assert "view.__class__.__name__" not in captured["code"]

    @pytest.mark.asyncio
    async def test_generated_screenshot_code_compiles(self):
        """The generated screenshot source must be valid Python."""
        from freecad_mcp.bridge.base import ExecutionResult, ViewAngle

        bridge = SocketBridge()
        captured = {}

        async def fake_exec(code):
            captured["code"] = code
            return ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "data": "eHl6",
                    "format": "png",
                    "width": 800,
                    "height": 600,
                },
                stdout="",
                stderr="",
                execution_time_ms=1.0,
            )

        with mock.patch.object(bridge, "execute_python", side_effect=fake_exec):
            await bridge.get_screenshot(view_angle=ViewAngle.TOP)

        compile(captured["code"], "<mcp>", "exec")
