"""ASGI entrypoint loaded by Vercel's Python runtime."""

from korean_lit_mcp.runtime import create_app_from_env

app = create_app_from_env()
