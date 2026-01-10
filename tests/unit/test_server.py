"""Tests for the main server module."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from freecad_mcp.config import FreecadMode

# Default argv for main() tests to avoid argparse errors
DEFAULT_ARGV: list[str] = ["freecad-mcp"]


class TestGetInstanceId:
    """Tests for get_instance_id function."""

    def test_returns_string(self):
        """Instance ID should be a string."""
        from freecad_mcp.server import get_instance_id

        instance_id = get_instance_id()
        assert isinstance(instance_id, str)

    def test_returns_uuid_format(self):
        """Instance ID should be a valid UUID format."""
        from freecad_mcp.server import get_instance_id

        instance_id = get_instance_id()
        # UUID format: 8-4-4-4-12 hex characters
        parts = instance_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_consistent_across_calls(self):
        """Instance ID should be consistent within a process."""
        from freecad_mcp.server import get_instance_id

        id1 = get_instance_id()
        id2 = get_instance_id()
        assert id1 == id2


class TestGetBridge:
    """Tests for get_bridge function."""

    @pytest.mark.asyncio
    async def test_raises_when_not_initialized(self):
        """Should raise RuntimeError when bridge is not initialized."""
        import freecad_mcp.server as server_module

        # Save original bridge
        original_bridge = server_module._bridge

        try:
            # Set bridge to None
            server_module._bridge = None

            with pytest.raises(RuntimeError, match="not initialized"):
                await server_module.get_bridge()
        finally:
            # Restore original bridge
            server_module._bridge = original_bridge

    @pytest.mark.asyncio
    async def test_returns_bridge_when_initialized(self):
        """Should return bridge when it's initialized."""
        import freecad_mcp.server as server_module

        # Save original bridge
        original_bridge = server_module._bridge

        try:
            # Set up mock bridge
            mock_bridge = MagicMock()
            server_module._bridge = mock_bridge

            bridge = await server_module.get_bridge()
            assert bridge is mock_bridge
        finally:
            # Restore original bridge
            server_module._bridge = original_bridge


class TestLifespan:
    """Tests for the lifespan context manager."""

    @pytest.mark.asyncio
    async def test_embedded_mode_initialization(self):
        """Should initialize embedded bridge in embedded mode."""
        import freecad_mcp.server as server_module

        mock_config = MagicMock()
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.freecad_path = None

        mock_embedded_bridge = AsyncMock()
        mock_embedded_bridge.get_freecad_version = AsyncMock(
            return_value={"version": "1.0.0", "gui_available": False}
        )

        with (
            patch.object(server_module, "get_config", return_value=mock_config),
            patch(
                "freecad_mcp.bridge.embedded.EmbeddedBridge",
                return_value=mock_embedded_bridge,
            ) as mock_embedded_class,
        ):
            mock_server = MagicMock()

            async with server_module.lifespan(mock_server):
                # Bridge should be initialized
                mock_embedded_class.assert_called_once_with(freecad_path=None)
                mock_embedded_bridge.connect.assert_called_once()

            # After exiting, disconnect should be called
            mock_embedded_bridge.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_xmlrpc_mode_initialization(self):
        """Should initialize XML-RPC bridge in xmlrpc mode."""
        import freecad_mcp.server as server_module

        mock_config = MagicMock()
        mock_config.mode = FreecadMode.XMLRPC
        mock_config.socket_host = "localhost"
        mock_config.xmlrpc_port = 9875

        mock_xmlrpc_bridge = AsyncMock()
        mock_xmlrpc_bridge.get_freecad_version = AsyncMock(
            return_value={"version": "1.0.0", "gui_available": True}
        )

        with (
            patch.object(server_module, "get_config", return_value=mock_config),
            patch(
                "freecad_mcp.bridge.xmlrpc.XmlRpcBridge",
                return_value=mock_xmlrpc_bridge,
            ) as mock_xmlrpc_class,
        ):
            mock_server = MagicMock()

            async with server_module.lifespan(mock_server):
                mock_xmlrpc_class.assert_called_once_with(host="localhost", port=9875)
                mock_xmlrpc_bridge.connect.assert_called_once()

            mock_xmlrpc_bridge.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_socket_mode_initialization(self):
        """Should initialize socket bridge in socket mode."""
        import freecad_mcp.server as server_module

        mock_config = MagicMock()
        mock_config.mode = FreecadMode.SOCKET
        mock_config.socket_host = "localhost"
        mock_config.socket_port = 9876

        mock_socket_bridge = AsyncMock()
        mock_socket_bridge.get_freecad_version = AsyncMock(
            return_value={"version": "1.0.0", "gui_available": True}
        )

        with (
            patch.object(server_module, "get_config", return_value=mock_config),
            patch(
                "freecad_mcp.bridge.socket.SocketBridge",
                return_value=mock_socket_bridge,
            ) as mock_socket_class,
        ):
            mock_server = MagicMock()

            async with server_module.lifespan(mock_server):
                mock_socket_class.assert_called_once_with(host="localhost", port=9876)
                mock_socket_bridge.connect.assert_called_once()

            mock_socket_bridge.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_version_fetch_failure_logs_warning(self):
        """Should log warning if version fetch fails."""
        import freecad_mcp.server as server_module

        mock_config = MagicMock()
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.freecad_path = None

        mock_bridge = AsyncMock()
        mock_bridge.get_freecad_version = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        with (
            patch.object(server_module, "get_config", return_value=mock_config),
            patch(
                "freecad_mcp.bridge.embedded.EmbeddedBridge",
                return_value=mock_bridge,
            ),
            patch.object(server_module.logger, "warning") as mock_warning,
        ):
            mock_server = MagicMock()

            async with server_module.lifespan(mock_server):
                # Warning should be logged
                mock_warning.assert_called_once()
                assert "Could not get FreeCAD version" in str(mock_warning.call_args)


class TestRegisterAllComponents:
    """Tests for register_all_components function."""

    def test_registers_tools(self):
        """Should register all tool categories."""
        from freecad_mcp.server import mcp

        # The function is called at module load, but we can verify
        # that the mcp instance exists and has tools registered
        assert mcp is not None
        assert mcp.name == "freecad-mcp"


class TestMain:
    """Tests for main function."""

    def test_main_prints_instance_id(self):
        """Main should print instance ID on startup."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(server_module.mcp, "run") as mock_run,
            patch("builtins.print") as mock_print,
        ):
            # Mock run to exit immediately
            mock_run.return_value = None

            server_module.main()

            # Check that instance ID was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("FREECAD_MCP_INSTANCE_ID=" in call for call in print_calls)

    def test_main_http_transport(self):
        """Main should start HTTP transport when configured."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_port = 8080

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(server_module.mcp, "run") as mock_run,
            patch("builtins.print"),
        ):
            server_module.main()

            # Should call run with HTTP transport settings
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs.get("transport") == "streamable-http"
            assert call_kwargs.get("port") == 8080

    def test_main_stdio_transport(self):
        """Main should start stdio transport by default."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(server_module.mcp, "run") as mock_run,
            patch("builtins.print"),
        ):
            server_module.main()

            # Should call run without transport arguments (stdio is default)
            mock_run.assert_called_once_with()
