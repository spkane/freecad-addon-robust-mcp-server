"""Configuration management for FreeCAD MCP Server.

This module handles all configuration settings for the MCP server,
including FreeCAD connection settings, execution limits, and logging.
"""

from enum import Enum
from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FreecadMode(str, Enum):
    """FreeCAD connection mode."""

    EMBEDDED = "embedded"
    SOCKET = "socket"
    XMLRPC = "xmlrpc"


class TransportType(str, Enum):
    """MCP transport type."""

    STDIO = "stdio"
    HTTP = "http"


class ServerConfig(BaseSettings):
    """Configuration for the FreeCAD MCP server.

    Settings are loaded from environment variables with the FREECAD_ prefix.
    For example, FREECAD_MODE sets the mode field.

    Attributes:
        mode: Connection mode - 'embedded', 'socket', or 'xmlrpc'.
        freecad_path: Path to FreeCAD's lib directory (for embedded mode).
        socket_host: Hostname for socket/xmlrpc connection.
        socket_port: Port for JSON-RPC socket connection (default 9876).
        xmlrpc_port: Port for XML-RPC connection (default 9875, neka-nat compatible).
        timeout_ms: Default execution timeout in milliseconds.
        max_output_size: Maximum output size in bytes.
        transport: MCP transport type.
        http_port: Port for HTTP transport.
        log_level: Logging level.
    """

    model_config = SettingsConfigDict(
        env_prefix="FREECAD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # FreeCAD connection settings
    mode: FreecadMode = FreecadMode.EMBEDDED
    freecad_path: Annotated[
        Path | None,
        Field(
            description="Path to FreeCAD's lib directory",
            alias="FREECAD_PATH",
        ),
    ] = None

    # Socket settings (for socket mode)
    socket_host: Annotated[
        str,
        Field(description="Socket/XML-RPC server hostname"),
    ] = "localhost"
    socket_port: Annotated[
        int,
        Field(ge=1, le=65535, description="Socket server port (JSON-RPC)"),
    ] = 9876
    xmlrpc_port: Annotated[
        int,
        Field(ge=1, le=65535, description="XML-RPC server port (neka-nat compatible)"),
    ] = 9875

    # Execution limits
    timeout_ms: Annotated[
        int,
        Field(ge=1000, le=600000, description="Execution timeout in ms"),
    ] = 30000
    max_output_size: Annotated[
        int,
        Field(ge=1000, description="Maximum output size in bytes"),
    ] = 1_000_000

    # MCP transport settings
    transport: TransportType = TransportType.STDIO
    http_port: Annotated[
        int,
        Field(ge=1, le=65535, description="HTTP server port"),
    ] = 8000

    # Logging
    log_level: str = "INFO"

    # Security settings
    enable_sandbox: bool = True
    allow_file_access: bool = True
    allow_network_access: bool = False


def get_config() -> ServerConfig:
    """Get the server configuration.

    Returns:
        ServerConfig instance populated from environment variables.
    """
    return ServerConfig()
