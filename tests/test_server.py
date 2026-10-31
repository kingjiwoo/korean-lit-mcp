import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from korean_lit_mcp.contracts import Envelope, PassageRequest, Source
from korean_lit_mcp.server import create_server


async def test_mcp_round_trip() -> None:
    server = create_server()

    @server.tool
    def sample(request: PassageRequest) -> Envelope[str]:
        return Envelope(items=[request.work_id or request.title or ""], source=Source(name="test"))

    @server.tool
    def failure() -> str:
        raise RuntimeError("private_marker_not_for_client")

    async with Client(server) as client:
        tools = await client.list_tools()
        assert "sample" in [tool.name for tool in tools]
        result = await client.call_tool("sample", {"request": {"work_id": "test"}})
        assert result.structured_content is not None
        assert result.structured_content["items"] == ["test"]
        with pytest.raises(ToolError):
            await client.call_tool("sample", {"request": {}})
        with pytest.raises(ToolError) as error:
            await client.call_tool("failure", {})
        assert "private_marker" not in str(error.value)
