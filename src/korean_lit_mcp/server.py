from fastmcp import FastMCP

from korean_lit_mcp.contracts import Envelope, PassageRequest, SearchRequest
from korean_lit_mcp.passages import get_passage, search_works
from korean_lit_mcp.sources import Edition


def create_server(*, editions: tuple[Edition, ...] = ()) -> FastMCP:
    server = FastMCP(
        "korean-lit-mcp",
        instructions=(
            "인용 전 get_passage로 판본과 원문을 확보하세요. "
            "미검증 범위를 검증 완료라고 표시하지 마세요. "
            "출처와 판본을 결과물에 표시하세요."
        ),
        mask_error_details=True,
    )

    @server.tool(name="search_works", annotations={"readOnlyHint": True})
    def search(request: SearchRequest) -> Envelope[dict[str, object]]:
        """작품 제목·작가로 검수된 원문을 찾을 때 사용합니다.

        판본별 ID와 본문 제공 여부를 반환합니다.
        """
        return search_works(request, editions)

    @server.tool(name="get_passage", annotations={"readOnlyHint": True})
    def passage(request: PassageRequest) -> Envelope[dict[str, object]]:
        """인용 작성 전에 만료 판본의 원문을 확보할 때 사용합니다.

        원문을 변형 없이 반환합니다. 문단·행 주소는 1부터 시작하고 끝을 포함합니다.
        """
        return get_passage(request, editions)

    return server
