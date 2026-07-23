from typing import List, Literal, Optional

from pydantic import Field
from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

from helpers import CustomBaseModel, is_valid_filename, strip_whitespace

NoteFormat = Literal["html", "markdown"]
NoteKind = Literal["research", "work", "legacy-markdown"]


class NoteBase(CustomBaseModel):
    title: str


class NoteCreate(CustomBaseModel):
    title: Annotated[
        str,
        AfterValidator(strip_whitespace),
        AfterValidator(is_valid_filename),
    ]
    content: Optional[str] = Field(None)
    format: NoteFormat = "html"


class Note(CustomBaseModel):
    title: str
    content: Optional[str] = Field(None)
    last_modified: float
    format: NoteFormat = "html"


class NoteUpdate(CustomBaseModel):
    new_title: Annotated[
        Optional[str],
        AfterValidator(strip_whitespace),
        AfterValidator(is_valid_filename),
    ] = Field(None)
    new_content: Optional[str] = Field(None)
    new_format: Optional[NoteFormat] = Field(None)


class SearchResult(CustomBaseModel):
    title: str
    last_modified: float

    score: Optional[float] = Field(None)
    title_highlights: Optional[str] = Field(None)
    content_highlights: Optional[str] = Field(None)
    tag_matches: Optional[List[str]] = Field(None)


class NoteHeading(CustomBaseModel):
    level: int
    text: str


class NoteLink(CustomBaseModel):
    href: str
    text: str
    is_source: bool = False


class NoteMedia(CustomBaseModel):
    src: str
    alt: Optional[str] = Field(None)
    caption: Optional[str] = Field(None)
    width: Optional[int] = Field(None)
    height: Optional[int] = Field(None)


class NoteComponent(CustomBaseModel):
    name: str
    count: int


class NoteContext(CustomBaseModel):
    title: str
    last_modified: float
    format: NoteFormat = "html"
    note_kind: NoteKind = "research"
    tags: List[str] = Field(default_factory=list)
    research_topics: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(None)
    headings: List[NoteHeading] = Field(default_factory=list)
    links: List[NoteLink] = Field(default_factory=list)
    media: List[NoteMedia] = Field(default_factory=list)
    sources: List[NoteLink] = Field(default_factory=list)
    components: List[NoteComponent] = Field(default_factory=list)
    text: str = ""
    word_count: int = 0
    llm_text: str = ""


class NoteIndexEntry(CustomBaseModel):
    title: str
    last_modified: float
    format: NoteFormat = "html"
    note_kind: NoteKind = "research"
    tags: List[str] = Field(default_factory=list)
    research_topics: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(None)
    heading_count: int = 0
    link_count: int = 0
    media_count: int = 0
    source_count: int = 0
    component_count: int = 0
    word_count: int = 0
