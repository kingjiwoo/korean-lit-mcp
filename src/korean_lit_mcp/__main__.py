import os
from pathlib import Path

from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions

if __name__ == "__main__":
    editions = load_editions(Path(os.environ.get("WORKS_DIR", "data/works")))
    create_server(editions=editions).run(transport="http", host="127.0.0.1", port=8000)
