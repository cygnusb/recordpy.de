FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Install dependencies separately from the project code (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    WETTERREKORD_DATA_DIR=/data

VOLUME /data
EXPOSE 8000

CMD ["uvicorn", "wetterrekord.app:app", "--host", "0.0.0.0", "--port", "8000"]
