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
        assert config.http_port == 8000
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

    def test_http_transport_from_env(self):
        """Configuration should read transport from environment."""
        with mock.patch.dict(os.environ, {"FREECAD_TRANSPORT": "http"}):
            config = ServerConfig()

        assert config.transport == TransportType.HTTP

    def test_invalid_port_raises_error(self):
        """Invalid port should raise validation error."""
        with mock.patch.dict(os.environ, {"FREECAD_SOCKET_PORT": "99999"}):
            with pytest.raises(Exception):  # Pydantic validation error
                ServerConfig()

    def test_get_config_returns_instance(self):
        """get_config should return a ServerConfig instance."""
        config = get_config()

        assert isinstance(config, ServerConfig)


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
