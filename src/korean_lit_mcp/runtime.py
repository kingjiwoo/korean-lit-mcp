"""Authenticated single-process HTTP serving with bounded request resources."""

import asyncio
import logging
import secrets
import time
import uuid
from collections import deque

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from korean_lit_mcp.metrics import request_id
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import Edition


class Guard:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.authorization = ("Bearer " + token).encode("ascii")
        self.events: deque[float] = deque()
        self.active = 0
        self.clock = time.monotonic

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] == "/health":
            status = 200 if scope["method"] == "GET" else 405
            await JSONResponse(
                {"status": "ok"} if status == 200 else {"error": "method_not_allowed"},
                status_code=status,
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        headers = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
        if len(headers) > 1:
            await JSONResponse(
                {"error": "duplicate_authorization"},
                status_code=400,
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        authorized = (
            bool(headers)
            and headers[0][:7].lower() == b"bearer "
            and secrets.compare_digest(headers[0][7:], self.authorization[7:])
        )
        if not authorized:
            await JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        now = self.clock()
        while self.events and self.events[0] <= now - 60:
            self.events.popleft()
        if len(self.events) >= 30:
            await JSONResponse(
                {"error": "rate_limit"}, status_code=429, headers={"Retry-After": "60"}
            )(scope, receive, send)
            return
        if self.active >= 8:
            await JSONResponse({"error": "busy"}, status_code=503)(scope, receive, send)
            return
        self.events.append(now)
        self.active += 1
        correlation = uuid.uuid4().hex
        context_token = request_id.set(correlation)
        status = 500
        started = False

        async def send_safe(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                status = message["status"]
                started = True
                message["headers"] = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                ] + [(b"cache-control", b"no-store")]
            await send(message)

        try:
            body = bytearray()
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > 1024 * 1024:
                        await JSONResponse({"error": "body_too_large"}, status_code=413)(
                            scope, receive, send_safe
                        )
                        return
                    if not message.get("more_body", False):
                        break
            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, send_safe)
        except TimeoutError:
            if not started:
                await JSONResponse({"error": "request_timeout"}, status_code=408)(
                    scope, receive, send_safe
                )
        except Exception:
            if not started:
                await JSONResponse({"error": "internal_error"}, status_code=500)(
                    scope, receive, send_safe
                )
        finally:
            self.active -= 1
            request_id.reset(context_token)
            logging.getLogger("korean_lit_mcp.requests").info(
                "request id=%s status=%d elapsed_ms=%d",
                correlation,
                status,
                int((self.clock() - now) * 1000),
            )


def create_http_app(
    *,
    token: str,
    editions: tuple[Edition, ...],
    allowed_hosts: list[str],
    allowed_origins: list[str] | None = None,
    nl_api_key: str | None = None,
) -> Guard:
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError("MCP_AUTH_TOKEN must be an ASCII token of at least 32 characters.")
    if not allowed_hosts or "*" in allowed_hosts:
        raise ValueError("Explicit MCP_ALLOWED_HOSTS are required.")
    server = create_server(editions=editions, token=token, nl_api_key=nl_api_key)
    app = server.http_app(
        json_response=True,
        stateless_http=True,
        host_origin_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins or [],
    )
    # Library exception logs may contain validated teacher inputs or API query keys.
    for name in ["fastmcp", "mcp", "httpx", "httpcore", *logging.Logger.manager.loggerDict]:
        if name.split(".")[0] in {"fastmcp", "mcp", "httpx", "httpcore"}:
            logging.getLogger(name).setLevel(logging.CRITICAL)
    return Guard(app, token)
