# Use the official uv image for the fastest builds
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# 1. Install a modern Node.js (Standard apt-get node is often too old)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python dependencies first (for layer caching)
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev

# 3. Copy the whole project (including backend, frontend, opgg-mcp)
COPY backend ./backend
COPY frontend ./frontend
COPY opgg-mcp ./opgg-mcp

# 4. CRITICAL: Build the OPGG MCP Server
WORKDIR /app/opgg-mcp
RUN npm install && npm run build

# 5. Build the React Frontend
WORKDIR /app/frontend
RUN npm install && npm run build

# 6. Move to backend and expose your API port
WORKDIR /app/backend
EXPOSE 8000

# 7. Run the FastAPI server
CMD ["uv", "run", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]