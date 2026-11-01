"""Tool boundaries. Text is never trimmed or rewritten by input validation."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Copyright = Literal["public_domain", "protected", "unknown"]
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[\w.-]+$")]
Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Quote = Annotated[Text, Field(max_length=2000)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Source(BaseModel):
    name: str
    url: HttpUrl | None = None


class ErrorInfo(BaseModel):
    code: str
    message: str


class SearchContext(BaseModel):
    request: dict[str, object]
    scope: Literal["reviewed_catalogue", "reviewed_catalogue_and_nl", "itkc"]
    outcome: Literal[
        "matches",
        "no_matches",
        "empty_catalogue",
        "related_records",
        "upstream_error",
        "partial_results",
    ]
    reviewed_work_count: int | None = None
    reviewed_edition_count: int | None = None
    upstream_error: ErrorInfo | None = None


class Envelope[T](BaseModel):
    items: list[T] = Field(default_factory=list)
    source: Source
    copyright: Copyright = "unknown"
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    note: str = ""
    error: ErrorInfo | None = None
    search_context: SearchContext | None = None

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        if self.error is not None and self.items:
            raise ValueError("Error responses must not contain successful items.")
        return self


class PassageRequest(Input):
    """Paragraph indices are 1-based and inclusive."""

    work_id: Identifier | None = None
    title: Annotated[Text, Field(max_length=200)] | None = None
    author: Annotated[Text, Field(max_length=100)] | None = None
    edition_id: Identifier | None = None
    start: int = Field(default=1, ge=1, le=50000)
    end: int | None = Field(default=None, ge=1, le=50000)

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.work_id is not None:
            if self.title is not None or self.author is not None:
                raise ValueError("Choose work_id or title and author, not both.")
        elif self.title is None or self.author is None:
            raise ValueError("Provide work_id or both title and author.")
        if self.end is not None and self.end < self.start:
            raise ValueError("end must not precede start.")
        return self


class VerifyRequest(Input):
    quotes: Annotated[list[Quote], Field(min_length=1, max_length=20)] | None = None
    draft: Annotated[Text, Field(max_length=30000)] | None = None
    work_id: Identifier | None = None
    edition_id: Identifier | None = None
    source_hash: Digest | None = None
    source_text: Annotated[Text, Field(max_length=50000)] | None = None

    @model_validator(mode="after")
    def validate_modes(self) -> Self:
        if (self.quotes is None) == (self.draft is None):
            raise ValueError("Provide exactly one of quotes or draft.")
        if (self.work_id is None) == (self.source_text is None):
            raise ValueError("Provide exactly one of work_id or source_text.")
        if self.work_id is not None:
            if self.edition_id is None or self.source_hash is None:
                raise ValueError("work_id requires edition_id and source_hash from get_passage.")
        elif self.edition_id is not None or self.source_hash is not None:
            raise ValueError("User-provided text does not accept a stored edition or hash.")
        return self


class SearchRequest(Input):
    query: Annotated[Text, Field(max_length=200)]
    author: Annotated[Text, Field(max_length=100)] | None = None
    year_from: int | None = Field(default=None, ge=0, le=9999)
    year_to: int | None = Field(default=None, ge=0, le=9999)
    limit: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_years(self) -> Self:
        if (
            self.year_from is not None
            and self.year_to is not None
            and self.year_to < self.year_from
        ):
            raise ValueError("year_to must not precede year_from.")
        return self
