import os

import uvicorn

from korean_lit_mcp.runtime import create_app_from_env

if __name__ == "__main__":
    try:
        app = create_app_from_env()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    uvicorn.run(
        app,
        host=os.environ.get("MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        access_log=False,
        log_level="warning",
    )
