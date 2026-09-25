"""Tests for the main server module."""

import os
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


class TestIsLoopbackHost:
    """Tests for is_loopback_host helper."""

    @pytest.mark.parametrize(
        "host,expected",
        [
            ("127.0.0.1", True),
            ("127.0.0.2", True),
            ("localhost", True),
            ("::1", True),
            ("0.0.0.0", False),  # noqa: S104
            ("192.168.1.100", False),
            ("mcp.example.com", False),
        ],
    )
    def test_loopback_classification(self, host: str, expected: bool) -> None:
        from freecad_mcp.server import is_loopback_host

        assert is_loopback_host(host) is expected


class TestFormatHost:
    """Tests for _format_host / _is_ipv6 helpers."""

    @pytest.mark.parametrize(
        "host,expected_ipv6",
        [
            ("::1", True),
            ("::2", True),
            ("2001:db8::1", True),
            ("mcp.example.com", False),
            ("mcp.example.com:443", False),
            ("192.168.1.100", False),
            ("192.168.1.100:8080", False),
            ("[::1]", False),
        ],
    )
    def test_is_ipv6_detection(self, host: str, expected_ipv6: bool) -> None:
        """IPv6 detection must validate the address, not look for a colon."""
        from freecad_mcp.server import _is_ipv6

        assert _is_ipv6(host) is expected_ipv6

    @pytest.mark.parametrize(
        "host,expected",
        [
            ("::1", "[::1]"),
            ("::2", "[::2]"),
            ("mcp.example.com", "mcp.example.com"),
            # Explicit port values must not be wrapped in brackets:
            # wrapping breaks the exact Host match in the MCP allowlist.
            ("mcp.example.com:443", "mcp.example.com:443"),
            ("192.168.1.100:8080", "192.168.1.100:8080"),
            ("192.168.1.100", "192.168.1.100"),
            # Already bracketed input is returned unchanged.
            ("[::1]", "[::1]"),
        ],
    )
    def test_format_host(self, host: str, expected: str) -> None:
        """Only bare IPv6 addresses get brackets; host:port stays as-is."""
        from freecad_mcp.server import _format_host

        assert _format_host(host) == expected


class TestGetMcp:
    """Tests for the get_mcp accessor."""

    def test_raises_before_initialization(self) -> None:
        """Should raise RuntimeError while server.mcp is None."""
        import freecad_mcp.server as server_module

        original = server_module.mcp
        try:
            server_module.mcp = None
            with pytest.raises(RuntimeError, match="not initialized yet"):
                server_module.get_mcp()
        finally:
            server_module.mcp = original

    def test_returns_live_instance_after_initialization(self) -> None:
        """Should resolve the module binding at call time, not import time."""
        import freecad_mcp.server as server_module

        original = server_module.mcp
        try:
            server_module.mcp = None
            # Resolve before initialization -> RuntimeError
            with pytest.raises(RuntimeError):
                server_module.get_mcp()
            # Simulate main() creating the instance
            sentinel = MagicMock()
            server_module.mcp = sentinel
            # Same caller, called again, now gets the live instance
            assert server_module.get_mcp() is sentinel
        finally:
            server_module.mcp = original

    def test_package_reexports_get_mcp(self) -> None:
        """freecad_mcp.get_mcp must be the server accessor."""
        import freecad_mcp
        from freecad_mcp.server import get_mcp

        assert freecad_mcp.get_mcp is get_mcp

    def test_main_publishes_binding_only_after_registration(self) -> None:
        """A registration failure must leave the mcp binding unpublished."""
        import freecad_mcp
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO
        mock_config.http_host = "127.0.0.1"

        # Start from a clean slate and restore afterwards, so the assertions
        # do not depend on what other tests left behind.
        original_server_mcp = server_module.mcp
        original_package_mcp = freecad_mcp.mcp
        server_module.mcp = None
        freecad_mcp.mcp = None
        try:
            with (
                patch.object(sys, "argv", DEFAULT_ARGV),
                patch.object(server_module, "get_config", return_value=mock_config),
                patch.object(server_module, "FastMCP", return_value=MagicMock()),
                patch.object(
                    server_module,
                    "register_all_components",
                    side_effect=RuntimeError("registration failed"),
                ),
                patch("builtins.print"),
            ):
                with pytest.raises(RuntimeError, match="registration failed"):
                    server_module.main()

            assert server_module.mcp is None
            assert freecad_mcp.mcp is None
        finally:
            server_module.mcp = original_server_mcp
            freecad_mcp.mcp = original_package_mcp

    def test_main_clears_bindings_after_shutdown(self) -> None:
        """Both bindings must be None once the transport run() returns."""
        import freecad_mcp
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO
        mock_config.http_host = "127.0.0.1"

        mock_mcp_instance = MagicMock()

        # Capture the binding while run() is executing (before the finally
        # block clears it).
        captured: list[object] = []

        def _capture_binding(*_args: object, **_kwargs: object) -> None:
            captured.append(server_module.mcp)

        mock_mcp_instance.run.side_effect = _capture_binding

        # Restore whatever the bindings held before the test, including when an
        # assertion below fails, so later tests do not depend on execution order.
        original_server_mcp = server_module.mcp
        original_package_mcp = freecad_mcp.mcp
        try:
            with (
                patch.object(sys, "argv", DEFAULT_ARGV),
                patch.object(server_module, "get_config", return_value=mock_config),
                patch.object(server_module, "FastMCP", return_value=mock_mcp_instance),
                patch("builtins.print"),
            ):
                server_module.main()

            # Published while the transport ran, cleared after shutdown
            assert captured and captured[0] is mock_mcp_instance
            assert server_module.mcp is None
            assert freecad_mcp.mcp is None
        finally:
            server_module.mcp = original_server_mcp
            freecad_mcp.mcp = original_package_mcp


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

    def test_registers_tools(self) -> None:
        """Should register tools, resources and prompts on the instance."""
        from freecad_mcp.server import register_all_components

        mock_mcp = MagicMock()
        register_all_components(mock_mcp)
        assert mock_mcp.tool.called
        assert mock_mcp.resource.called
        assert mock_mcp.prompt.called


class TestApplyCliArgsToEnv:
    """Tests for CLI argument to environment mapping."""

    def test_http_host_maps_to_env(self) -> None:
        """--http-host should set FREECAD_HTTP_HOST."""
        from argparse import Namespace

        import freecad_mcp.server as server_module

        args = Namespace(
            mode=None,
            transport=None,
            host=None,
            port=None,
            http_host="0.0.0.0",  # noqa: S104
            http_port=None,
            log_level=None,
        )

        with patch.dict(os.environ, {}, clear=True):
            server_module.apply_cli_args_to_env(args)
            assert os.environ["FREECAD_HTTP_HOST"] == "0.0.0.0"  # noqa: S104


class TestMain:
    """Tests for main function."""

    def test_main_prints_instance_id(self) -> None:
        """Main should print instance ID on startup when FREECAD_MCP_TESTING is set."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO
        mock_config.http_host = "127.0.0.1"

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(server_module, "FastMCP", return_value=mock_mcp_instance),
            patch("builtins.print") as mock_print,
            patch.dict(os.environ, {"FREECAD_MCP_TESTING": "1"}),
        ):
            server_module.main()

            # Check that instance ID was printed to stderr (not stdout, to avoid
            # corrupting JSON-RPC in stdio mode)
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("FREECAD_MCP_INSTANCE_ID=" in call for call in print_calls)
            # Verify it was printed to stderr
            instance_id_call = next(
                call
                for call in mock_print.call_args_list
                if "FREECAD_MCP_INSTANCE_ID=" in str(call)
            )
            assert instance_id_call.kwargs.get("file") == sys.stderr

    def test_main_no_instance_id_without_testing_env(self) -> None:
        """Main should NOT print instance ID when FREECAD_MCP_TESTING is unset."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO
        mock_config.http_host = "127.0.0.1"

        # Ensure FREECAD_MCP_TESTING is not set
        env_without_testing = {
            k: v for k, v in os.environ.items() if k != "FREECAD_MCP_TESTING"
        }

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(server_module, "FastMCP", return_value=mock_mcp_instance),
            patch("builtins.print") as mock_print,
            patch.dict(os.environ, env_without_testing, clear=True),
        ):
            server_module.main()

            # Check that instance ID was NOT printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert not any("FREECAD_MCP_INSTANCE_ID=" in call for call in print_calls)

    def test_main_http_transport(self) -> None:
        """Main should start HTTP transport when configured."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_host = "127.0.0.1"
        mock_config.http_port = 8080

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(
                server_module, "FastMCP", return_value=mock_mcp_instance
            ) as mock_fastmcp,
            patch("builtins.print"),
        ):
            server_module.main()

            # Verify FastMCP was constructed with correct params
            mock_fastmcp.assert_called_once()
            call_kwargs = mock_fastmcp.call_args.kwargs
            assert call_kwargs["host"] == "127.0.0.1"
            assert call_kwargs["port"] == 8080
            assert call_kwargs["log_level"] == "INFO"

            # Verify transport_security for loopback
            ts = call_kwargs["transport_security"]
            assert ts is not None
            assert ts.enable_dns_rebinding_protection is True
            assert "127.0.0.1:*" in ts.allowed_hosts
            assert "127.0.0.1" in ts.allowed_hosts
            assert "http://127.0.0.1:*" in ts.allowed_origins
            assert "http://127.0.0.1" in ts.allowed_origins

            # Verify run() was called with HTTP transport
            mock_mcp_instance.run.assert_called_once_with(transport="streamable-http")

    def test_main_http_transport_remote_host_widens_security(self) -> None:
        """A non-loopback bind with explicit allowlist must use allowlist entries."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_host = "0.0.0.0"  # noqa: S104
        mock_config.http_port = 8080
        mock_config.http_allowed_hosts = "192.168.1.100,10.0.0.1"

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(
                server_module, "FastMCP", return_value=mock_mcp_instance
            ) as mock_fastmcp,
            patch.object(server_module.logger, "warning") as mock_warning,
            patch("builtins.print"),
        ):
            server_module.main()

            call_kwargs = mock_fastmcp.call_args.kwargs
            ts = call_kwargs["transport_security"]
            assert ts is not None
            assert ts.enable_dns_rebinding_protection is True
            assert "192.168.1.100:*" in ts.allowed_hosts
            assert "192.168.1.100" in ts.allowed_hosts
            assert "10.0.0.1:*" in ts.allowed_hosts
            assert "10.0.0.1" in ts.allowed_hosts
            assert "http://192.168.1.100:*" in ts.allowed_origins
            assert "http://192.168.1.100" in ts.allowed_origins
            assert "http://10.0.0.1:*" in ts.allowed_origins
            assert "http://10.0.0.1" in ts.allowed_origins

            mock_warning.assert_called_once()
            mock_mcp_instance.run.assert_called_once_with(transport="streamable-http")

    def test_main_http_transport_ipv6_allowed_hosts(self) -> None:
        """IPv6 loopback bind must bracket the host in allowlists."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_host = "::1"
        mock_config.http_port = 8080

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(
                server_module, "FastMCP", return_value=mock_mcp_instance
            ) as mock_fastmcp,
            patch("builtins.print"),
        ):
            server_module.main()

            call_kwargs = mock_fastmcp.call_args.kwargs
            ts = call_kwargs["transport_security"]
            assert ts is not None
            assert ts.enable_dns_rebinding_protection is True
            # Loopback bind: IPv6 must be bracketed
            assert "[::1]:*" in ts.allowed_hosts
            assert "[::1]" in ts.allowed_hosts
            assert "http://[::1]:*" in ts.allowed_origins
            assert "http://[::1]" in ts.allowed_origins

            mock_mcp_instance.run.assert_called_once_with(transport="streamable-http")

    def test_main_http_transport_non_loopback_ipv6_hosts(self) -> None:
        """Non-loopback bind with IPv6 in http_allowed_hosts must bracket them."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_host = "0.0.0.0"  # noqa: S104
        mock_config.http_port = 8080
        mock_config.http_allowed_hosts = "192.168.1.100,::2"

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(
                server_module, "FastMCP", return_value=mock_mcp_instance
            ) as mock_fastmcp,
            patch("builtins.print"),
        ):
            server_module.main()

            call_kwargs = mock_fastmcp.call_args.kwargs
            ts = call_kwargs["transport_security"]
            assert ts is not None
            # IPv4 host
            assert "192.168.1.100:*" in ts.allowed_hosts
            assert "192.168.1.100" in ts.allowed_hosts
            assert "http://192.168.1.100:*" in ts.allowed_origins
            assert "http://192.168.1.100" in ts.allowed_origins
            # IPv6 host must be bracketed
            assert "[::2]:*" in ts.allowed_hosts
            assert "[::2]" in ts.allowed_hosts
            assert "http://[::2]:*" in ts.allowed_origins
            assert "http://[::2]" in ts.allowed_origins

            mock_mcp_instance.run.assert_called_once_with(transport="streamable-http")

    def test_main_http_transport_explicit_port_allowed_hosts(self) -> None:
        """Explicit host:port allowlist values must not be bracketed as IPv6."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_host = "0.0.0.0"  # noqa: S104
        mock_config.http_port = 8080
        mock_config.http_allowed_hosts = "mcp.example.com:443"

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(
                server_module, "FastMCP", return_value=mock_mcp_instance
            ) as mock_fastmcp,
            patch("builtins.print"),
        ):
            server_module.main()

            call_kwargs = mock_fastmcp.call_args.kwargs
            ts = call_kwargs["transport_security"]
            assert ts is not None
            # Exact value preserved: brackets would never match the Host header
            assert "mcp.example.com:443" in ts.allowed_hosts
            assert "http://mcp.example.com:443" in ts.allowed_origins
            assert "[mcp.example.com:443]" not in ts.allowed_hosts

            mock_mcp_instance.run.assert_called_once_with(transport="streamable-http")

    def test_main_http_transport_non_loopback_requires_allowed_hosts(self) -> None:
        """A non-loopback bind without http_allowed_hosts must raise ValueError."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_host = "0.0.0.0"  # noqa: S104
        mock_config.http_port = 8080
        mock_config.http_allowed_hosts = None

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch("builtins.print"),
        ):
            with pytest.raises(ValueError, match="http_allowed_hosts is required"):
                server_module.main()

    def test_main_http_transport_non_loopback_empty_after_parse(self) -> None:
        """Whitespace-only http_allowed_hosts must raise ValueError."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.HTTP
        mock_config.http_host = "0.0.0.0"  # noqa: S104
        mock_config.http_port = 8080
        mock_config.http_allowed_hosts = " , "  # whitespace-only

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch("builtins.print"),
        ):
            with pytest.raises(
                ValueError, match="http_allowed_hosts is empty after parsing"
            ):
                server_module.main()

    def test_main_stdio_transport(self) -> None:
        """Main should start stdio transport by default."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO
        mock_config.http_host = "127.0.0.1"

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(server_module, "FastMCP", return_value=mock_mcp_instance),
            patch("builtins.print"),
        ):
            server_module.main()

            # Should call run without transport arguments (stdio is default)
            mock_mcp_instance.run.assert_called_once_with()

    def test_main_stdio_transport_non_loopback_no_validation(self) -> None:
        """Stdio transport should not validate http_allowed_hosts."""
        import freecad_mcp.server as server_module
        from freecad_mcp.config import TransportType

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.mode = FreecadMode.EMBEDDED
        mock_config.transport = TransportType.STDIO
        mock_config.http_host = "0.0.0.0"  # noqa: S104
        mock_config.http_allowed_hosts = None

        mock_mcp_instance = MagicMock()

        with (
            patch.object(sys, "argv", DEFAULT_ARGV),
            patch.object(server_module, "get_config", return_value=mock_config),
            patch.object(server_module, "FastMCP", return_value=mock_mcp_instance),
            patch("builtins.print"),
        ):
            server_module.main()

            mock_mcp_instance.run.assert_called_once_with()


class TestStdioProtocolCleanliness:
    """Tests to ensure stdio mode produces clean JSON-RPC output.

    These tests verify that stdout contains ONLY valid JSON-RPC messages,
    with no debug output, print statements, or other text that would corrupt
    the MCP protocol. This is critical for compatibility with MCP clients
    like Claude Desktop.

    The bug this catches: Any print() to stdout (instead of stderr) will
    cause MCP clients to fail with JSON parse errors like:
        "Unexpected token 'F', "FREECAD_MC"... is not valid JSON"
    """

    def test_no_stdout_before_jsonrpc(self):
        """Verify no stray output appears on stdout before JSON-RPC messages.

        This test spawns the MCP server as a subprocess and validates that
        ALL stdout output is valid JSON-RPC. Any non-JSON output on stdout
        will corrupt the MCP protocol.
        """
        import json
        import os
        import subprocess
        import time

        # Start the MCP server process
        # Use a non-existent FreeCAD host so it won't actually connect
        proc = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "freecad_mcp.server",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **dict(os.environ),
                "FREECAD_MODE": "xmlrpc",
                "FREECAD_XMLRPC_PORT": "59999",  # Non-existent port
                "FREECAD_SOCKET_HOST": "localhost",
            },
        )

        try:
            # Ensure pipes are available
            assert proc.stdin is not None
            assert proc.stdout is not None

            # Send a minimal MCP initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"},
                },
            }
            request_bytes = json.dumps(init_request).encode() + b"\n"
            proc.stdin.write(request_bytes)
            proc.stdin.flush()

            # Give the server a moment to respond
            time.sleep(0.5)

            # Set stdout to non-blocking mode
            os.set_blocking(proc.stdout.fileno(), False)

            # Read any available stdout
            stdout_data = b""
            try:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    stdout_data += chunk
            except (BlockingIOError, TypeError):
                pass  # No more data available

            # Validate that ALL stdout is valid JSON-RPC
            # Each line should be a valid JSON object
            stdout_text = stdout_data.decode("utf-8", errors="replace")
            lines = [line.strip() for line in stdout_text.split("\n") if line.strip()]

            for line in lines:
                try:
                    parsed = json.loads(line)
                    # Should be a JSON-RPC message (has jsonrpc field)
                    assert "jsonrpc" in parsed, (
                        f"stdout contains JSON but not JSON-RPC: {line[:100]}"
                    )
                except json.JSONDecodeError as e:
                    pytest.fail(
                        f"stdout contains non-JSON output which corrupts MCP protocol!\n"
                        f"Invalid line: {line[:200]!r}\n"
                        f"JSON error: {e}\n\n"
                        f"All stdout lines:\n{stdout_text[:1000]}"
                    )

        finally:
            # Clean up the process
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_instance_id_on_stderr_not_stdout(self) -> None:
        """Verify FREECAD_MCP_INSTANCE_ID is printed to stderr, not stdout.

        The instance ID must go to stderr because stdout is reserved for
        JSON-RPC messages in stdio mode.
        """
        import os
        import subprocess
        import time

        proc = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "freecad_mcp.server",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **dict(os.environ),
                "FREECAD_MODE": "xmlrpc",
                "FREECAD_XMLRPC_PORT": "59999",
                "FREECAD_SOCKET_HOST": "localhost",
                "FREECAD_MCP_TESTING": "1",  # Enable stderr instance ID output
            },
        )

        try:
            # Ensure pipes are available
            assert proc.stdout is not None
            assert proc.stderr is not None

            # Set pipes to non-blocking mode
            os.set_blocking(proc.stdout.fileno(), False)
            os.set_blocking(proc.stderr.fileno(), False)

            # Poll for stderr content with timeout (CI systems can be slower)
            stderr_data = b""
            max_wait = 5.0  # 5 second timeout
            poll_interval = 0.1
            elapsed = 0.0

            while elapsed < max_wait:
                try:
                    chunk = proc.stderr.read(4096)
                    if chunk:
                        stderr_data += chunk
                        # Check if we got the instance ID
                        if b"FREECAD_MCP_INSTANCE_ID=" in stderr_data:
                            break
                except (BlockingIOError, TypeError):
                    pass  # No data available yet

                time.sleep(poll_interval)
                elapsed += poll_interval

            stderr_text = stderr_data.decode("utf-8", errors="replace")

            # Instance ID should be in stderr
            assert "FREECAD_MCP_INSTANCE_ID=" in stderr_text, (
                f"Instance ID not found in stderr after {max_wait}s.\n"
                f"stderr: {stderr_text[:500]}"
            )

            # Read stdout (should NOT contain instance ID)
            stdout_data = b""
            try:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    stdout_data += chunk
            except (BlockingIOError, TypeError):
                pass  # No more data available

            stdout_text = stdout_data.decode("utf-8", errors="replace")

            # Instance ID should NOT be in stdout
            assert "FREECAD_MCP_INSTANCE_ID=" not in stdout_text, (
                f"Instance ID incorrectly appears in stdout, corrupting MCP protocol!\n"
                f"stdout: {stdout_text[:500]}"
            )

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
