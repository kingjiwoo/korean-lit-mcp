FROM ghcr.io/astral-sh/uv:0.8.8 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy \
    MCP_HOST=0.0.0.0 PORT=8080 OTEL_SDK_DISABLED=true DO_NOT_TRACK=1
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev && useradd --system --uid 10001 app
USER 10001
EXPOSE 8080
CMD ["/app/.venv/bin/python", "-m", "korean_lit_mcp"]
