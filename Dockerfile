# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Install uv (pinned version for reproducible builds)
COPY --from=ghcr.io/astral-sh/uv:0.9.6 /uv /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml ./

# Install dependencies using uv with cache mount
# The cache mount persists between builds for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -e .

# Copy SQL files and source code
COPY sql/ ./sql/
COPY src/ ./src/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run as non-root user for security
RUN useradd appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default command runs analytics-uploader with SQL directory
# Mount credentials.json file and pass path via -c flag
# Example: docker run -v ./credentials.json:/app/credentials.json:ro analytics-uploader -c /app/credentials.json
ENTRYPOINT ["analytics-uploader"]
CMD ["-s", "/app/sql"]
