# Hermes TUI Dockerfile
FROM python:3.12-slim AS base

LABEL maintainer="Hermes TUI Contributors"
LABEL description="Hermes TUI — Terminal AI agent interface"
LABEL org.opencontainers.image.source="https://github.com/hermes-tui/hermes-tui"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for Textual
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Create config directory
RUN mkdir -p /root/.hermes-tui

# Set environment defaults
ENV HERMES_TUI_CONFIG_DIR=/root/.hermes-tui \
    TERM=xterm-256color

ENTRYPOINT ["hermes-tui"]
CMD ["chat"]
