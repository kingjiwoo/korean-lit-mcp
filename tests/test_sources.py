import hashlib
import json
from pathlib import Path

import pytest

from korean_lit_mcp.sources import SourceError, load_editions, select_edition, split_paragraphs


def write_edition(directory: Path, **changes: object) -> None:
    raw = "합성 원문입니다.\r\n\r\n두 번째 문단.\r\n".encode()
    payload = {
        "work_id": "test",
        "edition_id": "first",
        "title": "합성 작품",
        "author": "테스트",
        "year": 1900,
        "edition": "합성 fixture",
        "source": {"name": "합성", "url": "https://example.org/source"},
        "copyright": "public_domain",
        "rights_url": "https://example.org/rights",
        "rights_note": "합성 테스트 데이터",
        "reviewed_at": "2026-10-26T00:00:00Z",
        "filename": "text.txt",
        "sha256": hashlib.sha256(raw).hexdigest(),
        **changes,
    }
    (directory / "test.json").write_text(json.dumps(payload), encoding="utf-8")
    (directory / "text.txt").write_bytes(raw)


def test_original_bytes_and_addresses(tmp_path: Path) -> None:
    write_edition(tmp_path)
    edition = load_editions(tmp_path)[0]
    assert "\r\n" in edition.text
    assert "".join(p.text for p in edition.paragraphs) == edition.text
    for paragraph in edition.paragraphs:
        assert edition.text[paragraph.start : paragraph.end] == paragraph.text


def test_bundled_sources_are_intact() -> None:
    editions = load_editions(Path("data/works"))
    assert {e.manifest.work_id for e in editions} == {"gongu-9000397", "gongu-9000404"}


def test_corruption_is_rejected(tmp_path: Path) -> None:
    write_edition(tmp_path, sha256="0" * 64)
    with pytest.raises(SourceError, match="해시"):
        load_editions(tmp_path)


@pytest.mark.parametrize("rights", ["protected", "unknown"])
def test_rights_guard(tmp_path: Path, rights: str) -> None:
    write_edition(tmp_path, copyright=rights)
    with pytest.raises(SourceError, match="제공하지"):
        select_edition(load_editions(tmp_path), work_id="test")


def test_line_addresses_preserve_crlf() -> None:
    text = "한 행\r\n다음 행\r\n"
    paragraphs = split_paragraphs(text, source_lines=True)
    assert [p.text for p in paragraphs] == ["한 행\r\n", "다음 행\r\n"]


def test_blank_line_runs_preserve_original() -> None:
    text = "첫 문단\n\n\n  \n둘째 문단"
    paragraphs = split_paragraphs(text)
    assert len(paragraphs) == 2
    assert paragraphs[1].text == "둘째 문단"
    assert "".join(p.text for p in paragraphs) == text


def test_duplicate_manifest_rejected(tmp_path: Path) -> None:
    write_edition(tmp_path)
    (tmp_path / "copy.json").write_bytes((tmp_path / "test.json").read_bytes())
    with pytest.raises(SourceError, match="중복"):
        load_editions(tmp_path)


def test_text_symlink_outside_directory_rejected(tmp_path: Path) -> None:
    corpus = tmp_path / "works"
    corpus.mkdir()
    write_edition(corpus, filename="outside.txt")
    outside = tmp_path / "outside.txt"
    outside.write_text("외부 파일", encoding="utf-8")
    (corpus / "outside.txt").symlink_to(outside)
    with pytest.raises(SourceError, match="경로"):
        load_editions(corpus)


def test_file_size_bound(tmp_path: Path) -> None:
    write_edition(tmp_path)
    (tmp_path / "text.txt").write_bytes(b"x" * 250001)
    with pytest.raises(SourceError, match="크기"):
        load_editions(tmp_path)
