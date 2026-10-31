from korean_lit_mcp.server import create_server

if __name__ == "__main__":
    create_server().run(transport="http", host="127.0.0.1", port=8000)
