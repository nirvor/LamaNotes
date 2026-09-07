import hashlib
import re
from typing import List, Literal, Optional

from pydantic import Field, model_validator
from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

from helpers import CustomBaseModel, is_valid_filename, strip_whitespace

NoteFormat = Literal["html", "markdown"]
NoteKind = Literal["research", "work", "legacy-markdown"]
ResearchType = Literal[
    "research",
    "travel",
    "shopping",
    "invest",
    "practical",
    "aluhut",
]
ResearchFreshness = Literal[
    "timeless",
    "3-years",
    "1-year",
    "1-month",
    "1-week",
    "24-hours",
]


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


def note_version(content: str, note_format: str) -> str:
    return hashlib.sha256(f"{note_format}\0{content or ''}".encode("utf-8")).hexdigest()


class Note(CustomBaseModel):
    title: str
    content: Optional[str] = Field(None)
    last_modified: float
    format: NoteFormat = "html"
    version: str = ""

    @model_validator(mode="after")
    def set_version(self):
        self.version = note_version(self.content, self.format)
        return self


class NoteUpdate(CustomBaseModel):
    new_title: Annotated[
        Optional[str],
        AfterValidator(strip_whitespace),
        AfterValidator(is_valid_filename),
    ] = Field(None)
    new_content: Optional[str] = Field(None)
    new_format: Optional[NoteFormat] = Field(None)
    expected_version: Optional[str] = Field(None, pattern=r"^[a-f0-9]{64}$")


def normalize_research_topic(value: str) -> str:
    topic = str(value or "").strip().casefold().lstrip("#")
    if not re.fullmatch(r"r-[a-z0-9]+(?:-[a-z0-9]+)*", topic):
        raise ValueError("primary research topic must be a valid r-* tag")
    return topic


class ResearchNoteUpdate(CustomBaseModel):
    current_title: Annotated[
        str,
        AfterValidator(strip_whitespace),
        AfterValidator(is_valid_filename),
    ] = Field(min_length=1, max_length=180)
    new_title: Annotated[
        str,
        AfterValidator(strip_whitespace),
        AfterValidator(is_valid_filename),
    ] = Field(min_length=1, max_length=180)
    primary_research_topic: Annotated[
        str,
        AfterValidator(normalize_research_topic),
    ] = Field(min_length=3, max_length=48)
    expected_last_modified: float = Field(gt=0)
    research_id: Optional[str] = Field(None, max_length=35)

    @model_validator(mode="after")
    def validate_research_id(self):
        if self.research_id is None:
            return self
        research_id = self.research_id.strip().casefold()
        if not re.fullmatch(r"lr-[a-f0-9]{32}", research_id):
            raise ValueError("research ID is invalid")
        self.research_id = research_id
        return self


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
    primary_research_topic: Optional[str] = Field(None)
    research_id: Optional[str] = Field(None)
    research_origin: Optional[Literal["lamastart", "codex"]] = Field(None)
    research_type: Optional[ResearchType] = Field(None)
    research_freshness: Optional[ResearchFreshness] = Field(None)
    parent_research_id: Optional[str] = Field(None)
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
    primary_research_topic: Optional[str] = Field(None)
    research_id: Optional[str] = Field(None)
    research_origin: Optional[Literal["lamastart", "codex"]] = Field(None)
    research_type: Optional[ResearchType] = Field(None)
    research_freshness: Optional[ResearchFreshness] = Field(None)
    parent_research_id: Optional[str] = Field(None)
    summary: Optional[str] = Field(None)
    heading_count: int = 0
    link_count: int = 0
    media_count: int = 0
    source_count: int = 0
    component_count: int = 0
    word_count: int = 0
