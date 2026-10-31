import logging
import os
from pathlib import Path

import uvicorn

from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.sources import load_editions

if __name__ == "__main__":
    editions = load_editions(Path(os.environ.get("WORKS_DIR", "data/works")))
    try:
        app = create_http_app(
            editions=editions,
            allowed_hosts=os.environ.get("MCP_ALLOWED_HOSTS", "localhost,127.0.0.1").split(","),
            allowed_origins=[x for x in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if x],
            nl_api_key=os.environ.get("NL_API_KEY"),
        )
    except ValueError as error:
        raise SystemExit(str(error)) from None
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    uvicorn.run(
        app,
        host=os.environ.get("MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        access_log=False,
        log_level="warning",
    )
