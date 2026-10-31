"""Read-only reviewed texts. No database and no writes during requests."""

import hashlib
import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, HttpUrl

from korean_lit_mcp.contracts import Copyright, Digest, Identifier, Input, Source, Text


class SourceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Manifest(Input):
    work_id: Identifier
    edition_id: Identifier
    title: Annotated[Text, Field(max_length=200)]
    author: Annotated[Text, Field(max_length=100)]
    year: int = Field(ge=0, le=9999)
    edition: Text
    source: Source
    copyright: Copyright
    rights_url: HttpUrl
    rights_note: Text
    reviewed_at: AwareDatetime
    filename: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]+\.txt$")]
    sha256: Digest
    segmentation: Literal["blank_lines", "source_lines"] = "blank_lines"
    note: str = ""


@dataclass(frozen=True)
class Paragraph:
    number: int
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Edition:
    manifest: Manifest
    text: str
    paragraphs: tuple[Paragraph, ...]


def split_paragraphs(text: str, *, source_lines: bool = False) -> tuple[Paragraph, ...]:
    boundaries = [0]
    pattern = r"\r\n|\r|\n" if source_lines else r"\r?\n(?:[ \t]*\r?\n)+"
    boundaries.extend(match.end() for match in re.finditer(pattern, text))
    if boundaries[-1] != len(text):
        boundaries.append(len(text))
    return tuple(
        Paragraph(number, start, end, text[start:end])
        for number, (start, end) in enumerate(pairwise(boundaries), start=1)
        if end > start
    )


def read_limited(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise SourceError("file_too_large", "검수 자료의 파일 크기가 제한을 넘습니다.")
    return raw


def load_editions(directory: Path) -> tuple[Edition, ...]:
    if not directory.exists():
        raise SourceError("corpus_missing", "검수 원문 디렉터리가 없습니다.")
    editions: list[Edition] = []
    seen: set[tuple[str, str]] = set()
    filenames: set[str] = set()
    root = directory.resolve()
    for path in sorted(directory.glob("*.json")):
        if path.resolve().parent != root:
            raise SourceError(
                "invalid_manifest", "원문 메타데이터 경로 또는 크기가 잘못되었습니다."
            )
        manifest = Manifest.model_validate_json(read_limited(path, 65536))
        if manifest.copyright != "public_domain":
            raise SourceError(
                "copyright_restricted", "보호 또는 권리 불명 자료의 본문은 제공하지 않습니다."
            )
        text_path = directory / manifest.filename
        if text_path.resolve().parent != root:
            raise SourceError("invalid_text", "원문 파일 경로 또는 크기가 잘못되었습니다.")
        raw = read_limited(text_path, 250000)
        if hashlib.sha256(raw).hexdigest() != manifest.sha256:
            raise SourceError("hash_mismatch", "검수한 원문 파일의 해시와 다릅니다.")
        key = (manifest.work_id, manifest.edition_id)
        if key in seen:
            raise SourceError("duplicate_edition", "동일 작품·판본 식별자가 중복되었습니다.")
        if manifest.filename in filenames:
            raise SourceError(
                "duplicate_file", "하나의 원문 파일을 여러 판본에 연결할 수 없습니다."
            )
        seen.add(key)
        filenames.add(manifest.filename)
        text = raw.decode("utf-8")
        if not text.strip() or len(text) > 50000:
            raise SourceError("invalid_text", "원문이 비어 있거나 문자 수 상한을 넘습니다.")
        editions.append(
            Edition(
                manifest,
                text,
                split_paragraphs(text, source_lines=manifest.segmentation == "source_lines"),
            )
        )
    return tuple(editions)


def select_edition(
    editions: tuple[Edition, ...],
    *,
    work_id: str | None = None,
    title: str | None = None,
    author: str | None = None,
    edition_id: str | None = None,
) -> Edition:
    matches = [
        edition
        for edition in editions
        if (
            edition.manifest.work_id == work_id
            if work_id is not None
            else edition.manifest.title == title and edition.manifest.author == author
        )
        and (edition_id is None or edition.manifest.edition_id == edition_id)
    ]
    if not matches:
        raise SourceError(
            "not_found", "일치하는 검수 작품·판본이 없습니다. search_works로 확인하세요."
        )
    if len(matches) != 1:
        raise SourceError("ambiguous_edition", "여러 판본이 있습니다. edition_id를 지정하세요.")
    selected = matches[0]
    if selected.manifest.copyright != "public_domain":
        raise SourceError(
            "copyright_restricted", "보호 또는 권리 불명 자료의 본문은 제공하지 않습니다."
        )
    return selected
