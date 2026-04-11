FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# 1. Install Node.js and npm (required to run the OP.GG MCP server)
RUN apt-get update && \
    apt-get install -y nodejs npm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy lockfiles and install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 3. Copy the rest of the project
COPY . .

EXPOSE 8000

# 4. Use uv to run the server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]