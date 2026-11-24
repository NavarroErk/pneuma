FROM python:3.12-slim

# grab the uv binary from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# install dependencies first (cached unless pyproject/lock change)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# app code + frontend
COPY backend/ .
COPY frontend/ ./static

RUN chmod +x start.sh
EXPOSE 6650
CMD ["./start.sh"]