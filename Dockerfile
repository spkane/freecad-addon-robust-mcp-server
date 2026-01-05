# syntax=docker/dockerfile:1.7

# FreeCAD MCP Server Dockerfile
# Multi-stage build with BuildKit optimizations for multi-arch support
#
# Build:
#   docker build -t freecad-mcp .
#
# Build multi-arch:
#   docker buildx build --platform linux/amd64,linux/arm64 -t freecad-mcp .
#
# Run:
#   docker run --rm -i freecad-mcp

# =============================================================================
# Stage 1: Builder - Install dependencies and build the package
# =============================================================================
FROM python:3.11-slim AS builder

# Install build dependencies
# hadolint ignore=DL3008
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Install uv for fast dependency management
# Using pip cache mount for faster rebuilds
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile uv

# Copy only dependency files first for better layer caching
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Version for setuptools-scm when building without git (e.g., in Docker)
# This can be overridden at build time with --build-arg VERSION=x.y.z
ARG VERSION=0.0.0.dev0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

# Create virtual environment and install dependencies
# Using uv cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-compile .

# =============================================================================
# Stage 2: Runtime - Minimal image for running the server
# =============================================================================
FROM python:3.11-slim AS runtime

# Labels for container metadata (OCI Image Spec)
# Note: version, revision, and created are set dynamically in CI/CD workflows
LABEL org.opencontainers.image.title="FreeCAD MCP Server" \
      org.opencontainers.image.description="MCP (Model Context Protocol) server for FreeCAD integration with AI assistants" \
      org.opencontainers.image.url="https://github.com/spkane/freecad-robust-mcp-and-more" \
      org.opencontainers.image.source="https://github.com/spkane/freecad-robust-mcp-and-more" \
      org.opencontainers.image.documentation="https://github.com/spkane/freecad-robust-mcp-and-more#readme" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="Sean P. Kane" \
      org.opencontainers.image.authors="Sean P. Kane <spkane@gmail.com>" \
      org.opencontainers.image.base.name="python:3.11-slim"

# Create non-root user for security
RUN groupadd --gid 1000 mcpuser && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home mcpuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Default to xmlrpc mode (requires FreeCAD running externally)
    FREECAD_MODE="xmlrpc" \
    FREECAD_SOCKET_HOST="host.docker.internal" \
    FREECAD_SOCKET_PORT="9876" \
    FREECAD_XMLRPC_PORT="9875" \
    FREECAD_TIMEOUT_MS="30000"

# Switch to non-root user
USER mcpuser
WORKDIR /home/mcpuser

# Health check - verify the server can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import freecad_mcp; print('ok')" || exit 1

# Default command - run the MCP server in stdio mode
ENTRYPOINT ["freecad-mcp"]
