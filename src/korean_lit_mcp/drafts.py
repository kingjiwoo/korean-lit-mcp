"""Extract only explicit quotation markers; unmarked prose is never certified."""

import re
from dataclasses import dataclass

PATTERN = re.compile(
    r"<quote>(?P<tag>.*?)</quote>|<passage>(?P<passage>.*?)</passage>"
    r"|“(?P<curly>[^“”]+)”|「(?P<corner>[^「」]+)」|『(?P<double>[^『』]+)』"
    r'|"(?P<ascii>[^"\n]+)"|‘(?P<single>[^‘’\n]+)’',
    re.DOTALL,
)


@dataclass(frozen=True)
class ExtractedQuote:
    text: str
    start: int
    end: int


def extract_quotes(draft: str) -> tuple[list[ExtractedQuote], list[str]]:
    quotes: list[ExtractedQuote] = []
    notes: list[str] = []
    for match in PATTERN.finditer(draft):
        group = match.lastgroup
        assert group is not None
        start, end = match.span(group)
        text = draft[start:end]
        if not text.strip():
            notes.append("비어 있는 인용 표시가 있습니다.")
            continue
        if any(
            marker in text
            for marker in ('"', "“", "”", "「", "」", "『", "』", "<quote>", "<passage>")
        ):
            notes.append("중첩된 인용 표시는 범위를 확정하지 못합니다.")
            continue
        quotes.append(ExtractedQuote(text, start, end))
    if not quotes:
        notes.append("지원하는 표시에서 인용을 추출하지 못했습니다.")
    notes.append("표시 없는 인용·빈칸·밑줄·서식 및 지원하지 않는 표시는 미검증입니다.")
    return quotes, notes
