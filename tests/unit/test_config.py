"""Tests for configuration module."""

import os
from unittest import mock

import pytest

from freecad_mcp.config import FreecadMode, ServerConfig, TransportType, get_config


class TestServerConfig:
    """Tests for ServerConfig class."""

    def test_default_values(self):
        """Default configuration should use sensible defaults."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = ServerConfig()

        assert config.mode == FreecadMode.EMBEDDED
        assert config.socket_host == "localhost"
        assert config.socket_port == 9876
        assert config.timeout_ms == 30000
        assert config.max_output_size == 1_000_000
        assert config.transport == TransportType.STDIO
        assert config.http_host == "127.0.0.1"
        assert config.http_port == 8000
        assert config.http_allowed_hosts == [
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ]
        assert config.http_allowed_origins == [
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ]
        assert config.log_level == "INFO"
        assert config.enable_sandbox is True

    def test_socket_mode_from_env(self):
        """Configuration should read mode from environment."""
        with mock.patch.dict(os.environ, {"FREECAD_MODE": "socket"}):
            config = ServerConfig()

        assert config.mode == FreecadMode.SOCKET

    def test_custom_port_from_env(self):
        """Configuration should read port from environment."""
        with mock.patch.dict(os.environ, {"FREECAD_SOCKET_PORT": "12345"}):
            config = ServerConfig()

        assert config.socket_port == 12345

    def test_execution_timeout_from_env(self) -> None:
        """Configuration should read the default execution timeout."""
        with mock.patch.dict(
            os.environ,
            {"FREECAD_TIMEOUT_MS": "45000"},
            clear=True,
        ):
            config = ServerConfig()

        assert config.timeout_ms == 45000

    @pytest.mark.parametrize("timeout_ms", ["999", "600001"])
    def test_invalid_execution_timeout_raises_error(self, timeout_ms: str) -> None:
        """Configured execution timeouts must remain inside supported bounds."""
        with (
            mock.patch.dict(
                os.environ,
                {"FREECAD_TIMEOUT_MS": timeout_ms},
                clear=True,
            ),
            pytest.raises(Exception),
        ):
            ServerConfig()

    def test_http_transport_from_env(self):
        """Configuration should read transport from environment."""
        with mock.patch.dict(os.environ, {"FREECAD_TRANSPORT": "http"}):
            config = ServerConfig()

        assert config.transport == TransportType.HTTP

    def test_http_security_allowlists_from_env(self) -> None:
        """HTTP Host and Origin allowlists should be configurable as JSON."""
        environment = {
            "FREECAD_HTTP_HOST": "192.0.2.10",
            "FREECAD_HTTP_ALLOWED_HOSTS": '["mcp.example.com", "mcp.example.com:*"]',
            "FREECAD_HTTP_ALLOWED_ORIGINS": '["https://app.example.com"]',
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            config = ServerConfig()

        assert config.http_host == "192.0.2.10"
        assert config.http_allowed_hosts == [
            "mcp.example.com",
            "mcp.example.com:*",
        ]
        assert config.http_allowed_origins == ["https://app.example.com"]

    def test_invalid_port_raises_error(self):
        """Invalid port should raise validation error."""
        with mock.patch.dict(os.environ, {"FREECAD_SOCKET_PORT": "99999"}):
            with pytest.raises(Exception):  # Pydantic validation error
                ServerConfig()

    def test_get_config_returns_instance(self):
        """get_config should return a ServerConfig instance."""
        config = get_config()

        assert isinstance(config, ServerConfig)

    def test_working_directory_dotenv_is_not_loaded(self, tmp_path, monkeypatch):
        """A caller's .env cannot change configuration or prevent startup."""
        (tmp_path / ".env").write_text(
            "FREECAD_MODE=socket\nFREECAD_ALLOW_UNSAFE_CODE=true\nUNRELATED=x\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.dict(os.environ, {}, clear=True):
            config = ServerConfig()
        assert config.mode == FreecadMode.EMBEDDED
        assert config.allow_unsafe_code is False

    def test_environment_overrides_ignored_working_directory_dotenv(
        self, tmp_path, monkeypatch
    ):
        """Explicit environment settings remain supported."""
        (tmp_path / ".env").write_text("FREECAD_MODE=embedded\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        with mock.patch.dict(os.environ, {"FREECAD_MODE": "socket"}, clear=True):
            assert ServerConfig().mode == FreecadMode.SOCKET


class TestFreecadMode:
    """Tests for FreecadMode enum."""

    def test_embedded_value(self):
        """EMBEDDED should have correct string value."""
        assert FreecadMode.EMBEDDED.value == "embedded"

    def test_socket_value(self):
        """SOCKET should have correct string value."""
        assert FreecadMode.SOCKET.value == "socket"


class TestTransportType:
    """Tests for TransportType enum."""

    def test_stdio_value(self):
        """STDIO should have correct string value."""
        assert TransportType.STDIO.value == "stdio"

    def test_http_value(self):
        """HTTP should have correct string value."""
        assert TransportType.HTTP.value == "http"
