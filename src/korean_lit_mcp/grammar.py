"""Reviewed grammar concepts; lookup only, with no inference or request storage."""

import unicodedata
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, TypeAdapter, ValidationError, model_validator

from korean_lit_mcp.contracts import Envelope, Identifier, Input, Source, Text
from korean_lit_mcp.sources import SourceError, read_limited

Period = Literal["modern", "middle", "early_modern"]
Term = Annotated[Text, Field(max_length=100)]
Description = Annotated[Text, Field(max_length=2000)]


class GrammarRequest(Input):
    term: Term
    period: Period
    limit: int = Field(default=5, ge=1, le=10)


class GrammarSource(Input):
    title: Description
    author: Term
    url: HttpUrl
    location: Description
    version: Description
    checked_at: date
    license: Literal["CC-BY-SA-2.0-KR"]
    license_url: Literal["https://creativecommons.org/licenses/by-sa/2.0/kr/"]
    changes: Description


class GrammarExample(Input):
    text: Description
    kind: Literal["constructed", "source_example"]
    source_url: HttpUrl | None
    location: Description


class GrammarEntry(Input):
    entry_id: Identifier
    term: Term
    period: Period
    aliases: Annotated[list[Term], Field(max_length=20)]
    explanation: Description
    sources: Annotated[list[GrammarSource], Field(min_length=1, max_length=10)]
    examples: Annotated[list[GrammarExample], Field(min_length=1, max_length=10)]
    limitations: Annotated[list[Description], Field(min_length=1, max_length=10)]
    entry_version: Identifier

    @model_validator(mode="after")
    def validate_examples(self) -> Self:
        source_urls = {source.url for source in self.sources}
        for example in self.examples:
            if example.kind == "constructed":
                if example.source_url is not None:
                    raise ValueError("Constructed examples must not claim a source quotation.")
            elif example.source_url not in source_urls:
                raise ValueError("Source examples must reference an entry source.")
        return self


def load_grammar(directory: Path) -> tuple[GrammarEntry, ...]:
    path = directory / "entries.json"
    if path.resolve().parent != directory.resolve():
        raise SourceError("invalid_grammar_data", "문법 자료 경로가 검수 디렉터리를 벗어납니다.")
    try:
        raw = read_limited(path, 1_000_000)
        entries = TypeAdapter(tuple[GrammarEntry, ...]).validate_json(raw)
    except (OSError, ValidationError) as error:
        raise SourceError(
            "invalid_grammar_data", "문법 검수 자료를 읽을 수 없거나 형식·출처가 잘못되었습니다."
        ) from error
    if not entries or len({entry.entry_id for entry in entries}) != len(entries):
        raise SourceError("invalid_grammar_data", "문법 자료가 비어 있거나 식별자가 중복됩니다.")
    return entries


def term_key(value: str) -> str:
    # The literature search key removes araea; grammar must preserve that distinction.
    return "".join(unicodedata.normalize("NFC", value).split())


def lookup_grammar(
    request: GrammarRequest, entries: tuple[GrammarEntry, ...]
) -> Envelope[dict[str, object]]:
    query = term_key(request.term)
    matches = []
    for entry in entries:
        if entry.period != request.period:
            continue
        keys = [term_key(value) for value in (entry.term, *entry.aliases)]
        if any(query in key for key in keys):
            matches.append((query not in keys, entry.entry_id, entry))
    matches.sort(key=lambda match: (match[0], match[1]))
    items = [entry.model_dump(mode="json") for _, _, entry in matches[: request.limit]]
    note = (
        f"요청 시대 {request.period}의 검수 용어·별칭에서 개념 조회만 수행했습니다. "
        "임의 문장 분석·문헌 원문 대조·시험 정답 검증은 수행하지 않았습니다. "
    )
    note += (
        "저작권 보호 자료이며 항목별 CC BY-SA 2.0 KR 출처·이용조건을 따르세요."
        if items
        else "해당 시대의 검수 항목을 찾지 못했습니다. 용어나 현상 자체가 없다는 뜻은 아닙니다."
    )
    return Envelope(
        items=items,
        source=Source(name="검수 문법 자료(국립국어원 우리말샘·온용어)"),
        copyright="protected" if items else "unknown",
        note=note,
    )
