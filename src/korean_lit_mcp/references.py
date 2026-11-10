"""Resolve a request-scoped reference; never store supplied text."""

from dataclasses import dataclass

from korean_lit_mcp.contracts import Copyright, Source, TextReference
from korean_lit_mcp.sources import Edition, Paragraph, select_edition, split_paragraphs


@dataclass(frozen=True)
class ReferenceText:
    text: str
    paragraphs: tuple[Paragraph, ...]
    source: Source
    copyright: Copyright
    source_hash: str | None


def resolve_reference(request: TextReference, editions: tuple[Edition, ...]) -> ReferenceText:
    if request.source_text is not None:
        return ReferenceText(
            request.source_text,
            split_paragraphs(request.source_text),
            Source(name="교사 제공 텍스트"),
            "unknown",
            None,
        )
    edition = select_edition(editions, work_id=request.work_id, edition_id=request.edition_id)
    m = edition.manifest
    return ReferenceText(edition.text, edition.paragraphs, m.source, m.copyright, m.sha256)
