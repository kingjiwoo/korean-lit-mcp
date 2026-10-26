from fastmcp import FastMCP


def create_server() -> FastMCP:
    return FastMCP(
        "korean-lit-mcp",
        instructions=(
            "인용 전 get_passage로 판본과 원문을 확보하고 작성 후 verify_quote로 검증하세요. "
            "교사 제공 본문은 검증에만 사용하세요. 미검증 범위를 검증 완료라고 표시하지 마세요. "
            "출처와 판본을 결과물에 표시하세요."
        ),
        mask_error_details=True,
    )
