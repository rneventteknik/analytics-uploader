# Multi-stage Dockerfile for analytics-uploader
# Stage 1: Builder - installs dependencies and builds the application
# Stage 2: Runtime - minimal image with only runtime requirements

# First stage: Build the application with all dependencies
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Optimize uv behavior for production builds
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Disable Python downloads to use the system interpreter
# This ensures consistency between builder and runtime stages
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (better layer caching)
# Mount cache for faster rebuilds and bind lock/config files
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy application source code and SQL files
COPY . /app

# Install the project package (creates analytics-uploader CLI command)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


# Second stage: Runtime image without build tools
FROM python:3.13-slim-bookworm

# Important: Use the same Python version as the builder stage
# The path to the Python executable must match between stages

# Setup a non-root user for security
RUN groupadd --system --gid 999 appuser \
 && useradd --system --gid 999 --uid 999 --create-home appuser

# Copy the application from the builder stage
COPY --from=builder --chown=appuser:appuser /app /app

# Place executables in the environment at the front of the path
# This makes the analytics-uploader command available
ENV PATH="/app/.venv/bin:$PATH"

# Ensure Python output is sent straight to terminal without buffering
ENV PYTHONUNBUFFERED=1

# Use the non-root user to run the application
USER appuser

# Use /app as the working directory
WORKDIR /app

# Set the entry point to the analytics-uploader CLI command
# Default arguments point to the SQL directory in the container
ENTRYPOINT ["analytics-uploader"]
CMD ["-s", "/app/sql"]
