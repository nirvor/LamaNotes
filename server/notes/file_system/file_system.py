import glob
import os
import re
import shutil
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from typing import Iterable, List, Literal, Set, Tuple

import whoosh
from whoosh import writing
from whoosh.analysis import CharsetFilter, StemmingAnalyzer
from whoosh.fields import DATETIME, ID, KEYWORD, TEXT, SchemaClass
from whoosh.highlight import ContextFragmenter, WholeFragmenter
from whoosh.index import Index, LockError
from whoosh.qparser import MultifieldParser
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.query import Every
from whoosh.searching import Hit
from whoosh.support.charset import accent_map

from helpers import get_env, is_valid_filename
from logger import logger
from publications.metadata import (
    PUBLICATION_FILE_LOCK,
    preserve_publication_metadata,
    strip_publication_metadata,
)

from ..base import BaseNotes
from ..models import (
    Note,
    NoteComponent,
    NoteContext,
    NoteCreate,
    NoteFormat,
    NoteHeading,
    NoteIndexEntry,
    NoteKind,
    NoteLink,
    NoteMedia,
    NoteUpdate,
    SearchResult,
)

HTML_EXT = ".html"
LEGACY_MARKDOWN_EXT = ".md"
NOTE_EXTENSIONS = (HTML_EXT, LEGACY_MARKDOWN_EXT)
INDEX_SCHEMA_VERSION = "8"
HTML_METADATA_ONLY_TAGS = {"pinned"}
TAG_META_NAMES = {"lamanotes-tags", "flatnotes-tags"}
NOTE_KIND_META_NAMES = {"lamanotes-note-kind", "flatnotes-note-kind"}
SUMMARY_META_NAMES = {"description", "lamanotes-summary", "flatnotes-summary"}
RESEARCH_TOPIC_TAG_RE = re.compile(r"r-[a-z0-9]+(?:-[a-z0-9]+)*")

StemmingFoldingAnalyzer = StemmingAnalyzer() | CharsetFilter(accent_map)


class IndexSchema(SchemaClass):
    filename = ID(unique=True, stored=True)
    last_modified = DATETIME(stored=True, sortable=True)
    title = TEXT(
        field_boost=2.0, analyzer=StemmingFoldingAnalyzer, sortable=True
    )
    content = TEXT(analyzer=StemmingFoldingAnalyzer)
    tags = KEYWORD(lowercase=True, field_boost=2.0)


class NoteHtmlParser(HTMLParser):
    """Extract searchable text and legacy-compatible note metadata."""

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
    SKIP_TAGS = {"script", "style", "template"}
    TAG_CONTAINER_TAGS = {"div", "footer", "p"}
    TAG_ONLY_RE = re.compile(r"^#[a-zA-Z0-9_-]+(?:\s+#[a-zA-Z0-9_-]+)*$")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.meta_tags: Set[str] = set()
        self.visible_tags: Set[str] = set()
        self.tag_candidates: List[dict] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if (
            tag == "meta"
            and attrs_dict.get("name", "").lower() in TAG_META_NAMES
        ):
            self.meta_tags.update(
                FileSystemNotes._split_tag_list(attrs_dict.get("content", ""))
            )

        if tag == "img":
            alt_text = attrs_dict.get("alt", "").strip()
            if alt_text:
                self.parts.append(f" {alt_text} ")

        if tag in self.TAG_CONTAINER_TAGS:
            self.tag_candidates.append({"tag": tag, "parts": []})

        if tag in self.BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return

        if tag in self.TAG_CONTAINER_TAGS:
            for index in range(len(self.tag_candidates) - 1, -1, -1):
                candidate = self.tag_candidates[index]
                if candidate["tag"] != tag:
                    continue
                self.tag_candidates.pop(index)
                text = re.sub(
                    r"\s+", " ", " ".join(candidate["parts"])
                ).strip()
                if self.TAG_ONLY_RE.fullmatch(text):
                    self.visible_tags.update(
                        FileSystemNotes._split_tag_list(text)
                    )
                break

        if tag in self.BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data):
        if self.skip_depth:
            return

        if data.strip():
            self.parts.append(data)
            for candidate in self.tag_candidates:
                candidate["parts"].append(data)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


class NoteSemanticParser(HTMLParser):
    """Extract structured context from a rendered HTML note."""

    BLOCK_TAGS = NoteHtmlParser.BLOCK_TAGS
    SKIP_TAGS = {"script", "style", "template"}
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    COMPONENT_CLASSES = {
        **{
            f"lamanote-{name}": component
            for name, component in {
                "summary": "summary",
                "hero": "hero",
                "banner": "banner",
                "metrics": "metrics",
                "media-row": "media-row",
                "media-grid": "media-grid",
                "card-grid": "card-grid",
                "callout": "callout",
                "panel": "panel",
                "plot": "plot",
                "diagram": "diagram",
                "map": "map",
                "schematic": "schematic",
                "timeline": "timeline",
                "source-list": "sources",
            }.items()
        },
        **{
            f"flatnote-{name}": component
            for name, component in {
                "summary": "summary",
                "hero": "hero",
                "banner": "banner",
                "metrics": "metrics",
                "media-row": "media-row",
                "media-grid": "media-grid",
                "card-grid": "card-grid",
                "callout": "callout",
                "panel": "panel",
                "plot": "plot",
                "diagram": "diagram",
                "map": "map",
                "schematic": "schematic",
                "timeline": "timeline",
                "source-list": "sources",
            }.items()
        },
        "lamanotes-media-figure": "media",
        "flatnotes-media-figure": "media",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts: List[str] = []
        self.summary_parts: List[str] = []
        self.heading: dict | None = None
        self.headings: List[NoteHeading] = []
        self.link_stack: List[dict] = []
        self.links: List[NoteLink] = []
        self.media: List[NoteMedia] = []
        self.figure_stack: List[dict] = []
        self.element_stack: List[dict] = []
        self.components = Counter()
        self.meta_tags: Set[str] = set()
        self.meta_description: str | None = None
        self.note_kind: NoteKind = "research"
        self.skip_depth = 0
        self.summary_depth = 0
        self.source_depth = 0
        self.figcaption_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        classes = set(attrs_dict.get("class", "").split())
        is_summary = bool(
            {
                "lamanote-summary",
                "lamanotes-note-lead-abstract",
                "flatnote-summary",
                "flatnotes-note-lead-abstract",
            }
            & classes
        )
        is_source = bool(
            {"lamanote-source-list", "flatnote-source-list"} & classes
        )

        self._add_components(tag, attrs_dict, classes)
        self._read_meta(tag, attrs_dict)
        if (
            (
                attrs_dict.get("data-lamanotes-note-kind")
                or attrs_dict.get("data-flatnotes-note-kind", "")
            )
            .strip()
            .lower()
            == "work"
        ):
            self.note_kind = "work"

        if tag not in self.VOID_TAGS:
            self.element_stack.append(
                {
                    "tag": tag,
                    "is_summary": is_summary,
                    "is_source": is_source,
                }
            )

        if is_summary:
            self.summary_depth += 1
        if is_source:
            self.source_depth += 1

        if re.fullmatch(r"h[1-6]", tag):
            self.heading = {"level": int(tag[1]), "parts": []}

        if tag == "a" and attrs_dict.get("href"):
            self.link_stack.append(
                {
                    "href": attrs_dict["href"].strip(),
                    "parts": [],
                    "is_source": self.source_depth > 0,
                }
            )

        if tag == "figure":
            self.figure_stack.append(
                {"media_indices": [], "caption_parts": []}
            )

        if tag == "figcaption":
            self.figcaption_depth += 1

        if tag == "img":
            self._add_media(attrs_dict)

        if tag in self.BLOCK_TAGS:
            self.text_parts.append(" ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return

        if re.fullmatch(r"h[1-6]", tag) and self.heading:
            heading_text = self._normalize(" ".join(self.heading["parts"]))
            if heading_text:
                self.headings.append(
                    NoteHeading(level=self.heading["level"], text=heading_text)
                )
            self.heading = None

        if tag == "a" and self.link_stack:
            link = self.link_stack.pop()
            text = self._normalize(" ".join(link["parts"])) or link["href"]
            self.links.append(
                NoteLink(
                    href=link["href"],
                    text=text,
                    is_source=bool(link["is_source"]),
                )
            )

        if tag == "figcaption" and self.figcaption_depth:
            self.figcaption_depth -= 1

        if tag == "figure" and self.figure_stack:
            figure = self.figure_stack.pop()
            caption = self._normalize(" ".join(figure["caption_parts"]))
            if caption:
                for media_index in figure["media_indices"]:
                    media_item = self.media[media_index]
                    self.media[media_index] = media_item.model_copy(
                        update={"caption": caption}
                    )

        if tag in self.BLOCK_TAGS:
            self.text_parts.append(" ")

        self._pop_element(tag)

    def handle_data(self, data):
        if self.skip_depth:
            return

        if not data.strip():
            return

        self.text_parts.append(data)
        if self.summary_depth:
            self.summary_parts.append(data)
        if self.heading:
            self.heading["parts"].append(data)
        if self.link_stack:
            self.link_stack[-1]["parts"].append(data)
        if self.figcaption_depth and self.figure_stack:
            self.figure_stack[-1]["caption_parts"].append(data)

    @property
    def text(self) -> str:
        return self._normalize(" ".join(self.text_parts))

    @property
    def summary(self) -> str | None:
        if self.meta_description:
            return self.meta_description
        summary_text = self._normalize(" ".join(self.summary_parts))
        return summary_text or None

    @property
    def sources(self) -> List[NoteLink]:
        return [link for link in self.links if link.is_source]

    def _add_media(self, attrs_dict: dict):
        src = attrs_dict.get("src", "").strip()
        if not src:
            return

        width = self._optional_int(attrs_dict.get("width"))
        height = self._optional_int(attrs_dict.get("height"))
        media_item = NoteMedia(
            src=src,
            alt=attrs_dict.get("alt", "").strip() or None,
            width=width,
            height=height,
        )
        self.media.append(media_item)
        if self.figure_stack:
            self.figure_stack[-1]["media_indices"].append(len(self.media) - 1)

    def _add_components(self, tag: str, attrs_dict: dict, classes: Set[str]):
        explicit_components = FileSystemNotes._split_tag_list(
            attrs_dict.get("data-lamanotes-component")
            or attrs_dict.get("data-flatnotes-component", "")
        )
        for component in explicit_components:
            self.components[component] += 1

        for class_name in classes:
            component = self.COMPONENT_CLASSES.get(class_name)
            if component:
                self.components[component] += 1

    def _read_meta(self, tag: str, attrs_dict: dict):
        if tag != "meta":
            return

        name = attrs_dict.get("name", "").lower()
        if name in TAG_META_NAMES:
            self.meta_tags.update(
                FileSystemNotes._split_tag_list(attrs_dict.get("content", ""))
            )
        elif name in NOTE_KIND_META_NAMES:
            note_kind = attrs_dict.get("content", "").strip().lower()
            if note_kind == "work":
                self.note_kind = "work"
        elif name in SUMMARY_META_NAMES:
            description = self._normalize(attrs_dict.get("content", ""))
            if description:
                self.meta_description = description

    def _pop_element(self, tag: str):
        if tag in self.VOID_TAGS:
            return

        for index in range(len(self.element_stack) - 1, -1, -1):
            item = self.element_stack[index]
            if item["tag"] != tag:
                continue

            self.element_stack.pop(index)
            if item["is_summary"] and self.summary_depth:
                self.summary_depth -= 1
            if item["is_source"] and self.source_depth:
                self.source_depth -= 1
            return

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _optional_int(value: str | None) -> int | None:
        try:
            return int(value) if value else None
        except ValueError:
            return None


class FileSystemNotes(BaseNotes):
    TAGS_RE = re.compile(r"(?:(?<=^#)|(?<=\s#))[a-zA-Z0-9_-]+(?=\s|$)")
    CODEBLOCK_RE = re.compile(r"`{1,3}.*?`{1,3}", re.DOTALL)
    TAGS_WITH_HASH_RE = re.compile(
        r"(?:(?<=^)|(?<=\s))#[a-zA-Z0-9_-]+(?=\s|$)"
    )

    def __init__(self):
        self.storage_path = get_env(
            "LAMANOTES_PATH",
            mandatory=True,
            legacy_keys=("FLATNOTES_PATH",),
        )
        if not os.path.exists(self.storage_path):
            raise NotADirectoryError(
                f"'{self.storage_path}' is not a valid directory."
            )
        self.index = self._load_index()
        self._semantic_index_cache_lock = threading.Lock()
        self._semantic_index_cache_signature = None
        self._semantic_index_cache = None
        self._sync_index_with_retry(optimize=True)

    def create(self, data: NoteCreate) -> Note:
        """Create a new note."""
        self._raise_if_title_exists(data.title)
        note_format = data.format or "html"
        filepath = self._path_from_title(data.title, note_format)
        content = data.content or ""
        if note_format == "html":
            content = strip_publication_metadata(content)
        self._write_file(filepath, content)
        self._invalidate_semantic_index_cache()
        return Note(
            title=data.title,
            content=content,
            last_modified=os.path.getmtime(filepath),
            format=note_format,
        )

    def get(self, title: str) -> Note:
        """Get a specific note."""
        is_valid_filename(title)
        filepath = self._existing_path_from_title(title)
        content = self._read_file(filepath)
        return Note(
            title=title,
            content=content,
            last_modified=os.path.getmtime(filepath),
            format=self._format_from_path(filepath),
        )

    def update(self, title: str, data: NoteUpdate) -> Note:
        """Update a specific note."""
        with PUBLICATION_FILE_LOCK:
            is_valid_filename(title)
            filepath = self._existing_path_from_title(title)
            existing_content = self._read_file(filepath)
            existing_format = self._format_from_path(filepath)

            next_title = (
                data.new_title if data.new_title is not None else title
            )
            next_format = (
                data.new_format
                if data.new_format is not None
                else self._format_from_path(filepath)
            )
            new_filepath = self._path_from_title(next_title, next_format)
            if filepath != new_filepath:
                self._raise_if_title_exists(next_title, ignore_path=filepath)
                os.rename(filepath, new_filepath)
                title = next_title
                filepath = new_filepath
            else:
                title = next_title

            if data.new_content is not None:
                content = data.new_content
                if next_format == "html":
                    content = (
                        preserve_publication_metadata(
                            existing_content, content
                        )
                        if existing_format == "html"
                        else strip_publication_metadata(content)
                    )
                self._write_file(filepath, content, overwrite=True)
            else:
                content = self._read_file(filepath)
            self._invalidate_semantic_index_cache()
            return Note(
                title=title,
                content=content,
                last_modified=os.path.getmtime(filepath),
                format=self._format_from_path(filepath),
            )

    def delete(self, title: str) -> None:
        """Delete a specific note."""
        is_valid_filename(title)
        filepath = self._existing_path_from_title(title)
        os.remove(filepath)
        self._invalidate_semantic_index_cache()
        self._sync_index_with_retry(optimize=True)

    def search(
        self,
        term: str,
        sort: Literal["score", "title", "last_modified"] = "score",
        order: Literal["asc", "desc"] = "desc",
        limit: int = None,
    ) -> Tuple[SearchResult, ...]:
        """Search the index for the given term."""
        self._sync_index_with_retry()
        term = self._pre_process_search_term(term)
        with self.index.searcher() as searcher:
            # Parse Query
            if term == "*":
                query = Every()
            else:
                parser = MultifieldParser(
                    self._fieldnames_for_term(term), self.index.schema
                )
                parser.add_plugin(DateParserPlugin())
                query = parser.parse(term)

            # Determine Sort By
            # Note: For the 'sort' option, "score" is converted to None as
            # that is the default for searches anyway and it's quicker for
            # Whoosh if you specify None.
            sort = sort if sort in ["title", "last_modified"] else None

            # Determine Sort Direction
            # Note: Confusingly, when sorting by 'score', reverse = True means
            # asc so we have to flip the logic for that case!
            reverse = order == "desc"
            if sort is None:
                reverse = not reverse

            # Run Search
            results = searcher.search(
                query,
                sortedby=sort,
                reverse=reverse,
                limit=limit,
                terms=True,
            )
            return tuple(self._search_result_from_hit(hit) for hit in results)

    def get_tags(self) -> list[str]:
        """Return tags that are present in the current note files."""
        return sorted(
            {
                tag
                for note in self.get_semantic_index()
                for tag in note.tags
            }
        )

    def get_context(self, title: str) -> NoteContext:
        """Return structured, LLM-friendly context for one note."""
        return self._context_from_note(self.get(title))

    def get_semantic_index(self) -> List[NoteIndexEntry]:
        """Return a compact structured index for all notes."""
        lock = self._get_semantic_index_cache_lock()
        with lock:
            signature = self._semantic_index_signature()
            if (
                self._semantic_index_cache is not None
                and signature == self._semantic_index_cache_signature
            ):
                return list(self._semantic_index_cache)

            contexts = [
                self._context_from_note(self._get_by_filename(filename))
                for filename, _, _ in signature
            ]
            contexts.sort(key=lambda item: item.last_modified, reverse=True)
            index = [
                NoteIndexEntry(
                    title=context.title,
                    last_modified=context.last_modified,
                    format=context.format,
                    note_kind=context.note_kind,
                    tags=context.tags,
                    research_topics=context.research_topics,
                    summary=context.summary,
                    heading_count=len(context.headings),
                    link_count=len(context.links),
                    media_count=len(context.media),
                    source_count=len(context.sources),
                    component_count=sum(
                        component.count for component in context.components
                    ),
                    word_count=context.word_count,
                )
                for context in contexts
            ]
            self._semantic_index_cache_signature = signature
            self._semantic_index_cache = index
            return list(index)

    def _get_semantic_index_cache_lock(self):
        lock = getattr(self, "_semantic_index_cache_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._semantic_index_cache_lock = lock
            self._semantic_index_cache_signature = None
            self._semantic_index_cache = None
        return lock

    def _semantic_index_signature(self) -> tuple[tuple[str, int, int], ...]:
        signature = []
        for filename in sorted(self._list_all_note_filenames()):
            filepath = os.path.join(self.storage_path, filename)
            try:
                stat = os.stat(filepath)
            except FileNotFoundError:
                continue
            signature.append((filename, stat.st_mtime_ns, stat.st_size))
        return tuple(signature)

    def _invalidate_semantic_index_cache(self) -> None:
        lock = self._get_semantic_index_cache_lock()
        with lock:
            self._semantic_index_cache_signature = None
            self._semantic_index_cache = None

    @property
    def _index_path(self):
        return os.path.join(self.storage_path, ".lamanotes")

    def _path_from_title(
        self, title: str, note_format: NoteFormat = "html"
    ) -> str:
        return os.path.join(
            self.storage_path, title + self._extension_from_format(note_format)
        )

    def _path_candidates_from_title(self, title: str) -> Tuple[str, ...]:
        return tuple(
            os.path.join(self.storage_path, title + extension)
            for extension in NOTE_EXTENSIONS
        )

    def _existing_path_from_title(self, title: str) -> str:
        is_valid_filename(title)
        for filepath in self._path_candidates_from_title(title):
            if os.path.isfile(filepath):
                return filepath
        raise FileNotFoundError(f"'{title}' does not exist.")

    def _raise_if_title_exists(
        self, title: str, ignore_path: str | None = None
    ) -> None:
        normalized_ignore_path = (
            os.path.abspath(ignore_path) if ignore_path else None
        )
        for filepath in self._path_candidates_from_title(title):
            if not os.path.isfile(filepath):
                continue
            if normalized_ignore_path == os.path.abspath(filepath):
                continue
            raise FileExistsError(f"'{title}' already exists.")

    def _get_by_filename(self, filename: str) -> Note:
        """Get a note by its filename."""
        filepath = os.path.join(self.storage_path, filename)
        title = self._strip_ext(filename)
        content = self._read_file(filepath)
        return Note(
            title=title,
            content=content,
            last_modified=os.path.getmtime(filepath),
            format=self._format_from_path(filepath),
        )

    def _load_index(self) -> Index:
        """Load the note index or create new if not exists."""
        index_dir_exists = os.path.exists(self._index_path)
        if index_dir_exists and whoosh.index.exists_in(
            self._index_path, indexname=INDEX_SCHEMA_VERSION
        ):
            logger.info("Loading existing index")
            return whoosh.index.open_dir(
                self._index_path, indexname=INDEX_SCHEMA_VERSION
            )
        else:
            if index_dir_exists:
                logger.info("Deleting outdated index")
                self._clear_dir(self._index_path)
            else:
                os.mkdir(self._index_path)
            logger.info("Creating new index")
            return whoosh.index.create_in(
                self._index_path, IndexSchema, indexname=INDEX_SCHEMA_VERSION
            )

    @classmethod
    def _looks_like_html(cls, content: str) -> bool:
        return bool(
            re.search(
                r"<(?:!doctype|html|head|body|article|section|div|p|h[1-6]|"
                r"figure|img|meta|style|script)\b",
                content or "",
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _split_tag_list(value: str) -> Set[str]:
        return {
            tag.lower().lstrip("#")
            for tag in re.findall(r"#?[a-zA-Z0-9_-]+", value or "")
        }

    @staticmethod
    def _research_topics(tags: Iterable[str]) -> List[str]:
        tag_set = set(tags)
        if "research" not in tag_set:
            return []
        return sorted(tag for tag in tag_set if RESEARCH_TOPIC_TAG_RE.fullmatch(tag))

    @classmethod
    def _html_to_text_and_meta_tags(
        cls, content: str
    ) -> Tuple[str, Set[str], Set[str]]:
        parser = NoteHtmlParser()
        parser.feed(content or "")
        parser.close()
        return (parser.text, parser.meta_tags, parser.visible_tags)

    @classmethod
    def _extract_tags(cls, content: str) -> Tuple[str, Set[str]]:
        """Return searchable text and lowercase tags for Markdown or HTML."""
        meta_tags: Set[str] = set()
        searchable_content = content or ""
        if cls._looks_like_html(searchable_content):
            (
                searchable_content,
                meta_tags,
                visible_tags,
            ) = cls._html_to_text_and_meta_tags(searchable_content)
            content_ex_tags, _ = cls._re_extract(
                cls.TAGS_RE, searchable_content
            )
            if visible_tags:
                metadata_only_tags = meta_tags.intersection(
                    HTML_METADATA_ONLY_TAGS
                )
                return (
                    content_ex_tags,
                    visible_tags.union(metadata_only_tags),
                )
            return (content_ex_tags, meta_tags)

        content_ex_codeblock = re.sub(cls.CODEBLOCK_RE, "", searchable_content)
        _, tags = cls._re_extract(cls.TAGS_RE, content_ex_codeblock)
        content_ex_tags, _ = cls._re_extract(cls.TAGS_RE, searchable_content)
        try:
            tags = [tag.lower() for tag in tags]
            return (content_ex_tags, set(tags).union(meta_tags))
        except IndexError:
            return (searchable_content, meta_tags)

    @classmethod
    def _context_from_note(cls, note: Note) -> NoteContext:
        if note.format == "html" or cls._looks_like_html(note.content or ""):
            parser = NoteSemanticParser()
            parser.feed(note.content or "")
            parser.close()
            content_ex_tags, tags = cls._extract_tags(note.content or "")
            text = content_ex_tags or parser.text
            summary = parser.summary or cls._truncate_text(text, 320)
            components = [
                NoteComponent(name=name, count=count)
                for name, count in sorted(parser.components.items())
            ]
            context = NoteContext(
                title=note.title,
                last_modified=note.last_modified,
                format=note.format,
                note_kind=parser.note_kind,
                tags=sorted(tags.union(parser.meta_tags)),
                summary=summary,
                headings=parser.headings,
                links=parser.links,
                media=parser.media,
                sources=parser.sources,
                components=components,
                text=text,
                word_count=cls._word_count(text),
            )
        else:
            context = cls._markdown_context_from_note(note)

        context = context.model_copy(
            update={"research_topics": cls._research_topics(context.tags)}
        )
        return context.model_copy(
            update={"llm_text": cls._build_llm_text(context)}
        )

    @classmethod
    def _markdown_context_from_note(cls, note: Note) -> NoteContext:
        content = note.content or ""
        content_ex_tags, tags = cls._extract_tags(content)
        headings = [
            NoteHeading(level=len(match.group(1)), text=match.group(2).strip())
            for match in re.finditer(
                r"^(#{1,6})\s+(.+)$", content, re.MULTILINE
            )
        ]
        media = [
            NoteMedia(src=match.group(2), alt=match.group(1) or None)
            for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", content)
        ]
        links = [
            NoteLink(
                href=match.group(2), text=match.group(1) or match.group(2)
            )
            for match in re.finditer(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)", content)
        ]
        sources = [
            link
            for link in links
            if "source" in link.text.lower() or "quelle" in link.text.lower()
        ]
        summary = cls._truncate_text(content_ex_tags, 320)
        return NoteContext(
            title=note.title,
            last_modified=note.last_modified,
            format=note.format,
            note_kind="legacy-markdown",
            tags=sorted(tags),
            summary=summary,
            headings=headings,
            links=links,
            media=media,
            sources=sources,
            components=[],
            text=content_ex_tags,
            word_count=cls._word_count(content_ex_tags),
        )

    @classmethod
    def _build_llm_text(cls, context: NoteContext) -> str:
        lines = [f"# {context.title}", ""]
        lines.append(f"Note kind: {context.note_kind}")
        if context.tags:
            lines.append(
                "Tags: " + " ".join(f"#{tag}" for tag in context.tags)
            )
        if context.summary:
            lines.extend(["", "Summary:", context.summary])
        if context.headings:
            lines.extend(["", "Headings:"])
            lines.extend(
                f"- H{heading.level} {heading.text}"
                for heading in context.headings[:40]
            )
        if context.media:
            lines.extend(["", "Media:"])
            lines.extend(
                cls._format_media_for_context(media)
                for media in context.media[:30]
            )
        if context.links:
            lines.extend(["", "Links:"])
            lines.extend(
                f"- {link.text}: {link.href}" for link in context.links[:40]
            )
        if context.sources:
            lines.extend(["", "Sources:"])
            lines.extend(
                f"- {source.text}: {source.href}"
                for source in context.sources[:40]
            )
        if context.components:
            lines.extend(["", "Components:"])
            lines.extend(
                f"- {component.name}: {component.count}"
                for component in context.components
            )
        if context.text:
            lines.extend(
                ["", "Text:", cls._truncate_text(context.text, 12000)]
            )
        return "\n".join(lines).strip()

    @staticmethod
    def _format_media_for_context(media: NoteMedia) -> str:
        label = media.alt or media.caption or "Media"
        dimensions = (
            f" ({media.width}x{media.height})"
            if media.width and media.height
            else ""
        )
        caption = f" - {media.caption}" if media.caption else ""
        return f"- {label}{dimensions}: {media.src}{caption}"

    @staticmethod
    def _truncate_text(value: str, max_length: int) -> str:
        text = re.sub(r"\s+", " ", value or "").strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 1].rstrip() + "..."

    @staticmethod
    def _word_count(value: str) -> int:
        return len(re.findall(r"\w+", value or ""))

    def _add_note_to_index(
        self, writer: writing.IndexWriter, note: Note
    ) -> None:
        """Add a Note object to the index using the given writer. If the
        filename already exists in the index an update will be performed
        instead."""
        content_ex_tags, tag_set = self._extract_tags(note.content)
        tag_string = " ".join(tag_set)
        writer.update_document(
            filename=note.title + self._extension_from_format(note.format),
            last_modified=datetime.fromtimestamp(note.last_modified),
            title=note.title,
            content=content_ex_tags,
            tags=tag_string,
        )

    def _list_all_note_filenames(self) -> List[str]:
        """Return a list of all note filenames."""
        filenames_by_title = {}
        for extension in NOTE_EXTENSIONS:
            for filepath in glob.glob(
                os.path.join(self.storage_path, "*" + extension)
            ):
                filename = os.path.split(filepath)[1]
                title = self._strip_ext(filename)
                if title not in filenames_by_title or extension == HTML_EXT:
                    filenames_by_title[title] = filename
        return list(filenames_by_title.values())

    def _sync_index(self, optimize: bool = False, clean: bool = False) -> None:
        """Synchronize the index with the notes directory.
        Specify clean=True to completely rebuild the index"""
        all_filenames = set(self._list_all_note_filenames())
        indexed = set()
        writer = self.index.writer()
        if clean:
            writer.mergetype = writing.CLEAR  # Clear the index
        with self.index.searcher() as searcher:
            for idx_note in searcher.all_stored_fields():
                idx_filename = idx_note["filename"]
                idx_filepath = os.path.join(self.storage_path, idx_filename)
                # Delete missing
                if (
                    not os.path.exists(idx_filepath)
                    or idx_filename not in all_filenames
                ):
                    writer.delete_by_term("filename", idx_filename)
                    logger.info(f"'{idx_filename}' removed from index")
                # Update modified
                elif (
                    datetime.fromtimestamp(os.path.getmtime(idx_filepath))
                    != idx_note["last_modified"]
                ):
                    logger.info(f"'{idx_filename}' updated")
                    self._add_note_to_index(
                        writer, self._get_by_filename(idx_filename)
                    )
                    indexed.add(idx_filename)
                # Ignore already indexed
                else:
                    indexed.add(idx_filename)
        # Add new
        for filename in all_filenames:
            if filename not in indexed:
                self._add_note_to_index(
                    writer, self._get_by_filename(filename)
                )
                logger.info(f"'{filename}' added to index")
        writer.commit(optimize=optimize)
        logger.info("Index synchronized")

    def _sync_index_with_retry(
        self,
        optimize: bool = False,
        clean: bool = False,
        max_retries: int = 8,
        retry_delay: float = 0.25,
    ) -> None:
        for _ in range(max_retries):
            try:
                self._sync_index(optimize=optimize, clean=clean)
                return
            except LockError:
                logger.warning(f"Index locked, retrying in {retry_delay}s")
                time.sleep(retry_delay)
        logger.error(f"Failed to sync index after {max_retries} retries")

    @classmethod
    def _pre_process_search_term(cls, term):
        term = term.strip()
        # Replace "#tagname" with "tags:tagname"
        term = re.sub(
            cls.TAGS_WITH_HASH_RE,
            lambda tag: "tags:" + tag.group(0)[1:],
            term,
        )
        return term

    @staticmethod
    def _re_extract(pattern, string) -> Tuple[str, List[str]]:
        """Similar to re.sub but returns a tuple of:

        - `string` with matches removed
        - list of matches"""
        matches = []
        text = re.sub(pattern, lambda tag: matches.append(tag.group()), string)
        return (text, matches)

    @staticmethod
    def _strip_ext(filename):
        """Return the given filename without the extension."""
        return os.path.splitext(filename)[0]

    @staticmethod
    def _extension_from_format(note_format: NoteFormat) -> str:
        return HTML_EXT if note_format == "html" else LEGACY_MARKDOWN_EXT

    @staticmethod
    def _format_from_path(filepath: str) -> NoteFormat:
        if os.path.splitext(filepath)[1].lower() == LEGACY_MARKDOWN_EXT:
            return "markdown"
        return "html"

    @staticmethod
    def _clear_dir(path):
        """Delete all contents of the given directory."""
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

    def _search_result_from_hit(self, hit: Hit):
        matched_fields = self._get_matched_fields(hit.matched_terms())

        title = self._strip_ext(hit["filename"])
        last_modified = hit["last_modified"].timestamp()

        # If the search was ordered using a text field then hit.score is the
        # value of that field. This isn't useful so only set self._score if it
        # is a float.
        score = hit.score if type(hit.score) is float else None

        if "title" in matched_fields:
            hit.results.fragmenter = WholeFragmenter()
            title_highlights = hit.highlights("title", text=title)
        else:
            title_highlights = None

        if "content" in matched_fields:
            hit.results.fragmenter = ContextFragmenter()
            content = self._read_file(
                os.path.join(self.storage_path, hit["filename"])
            )
            content_ex_tags, _ = FileSystemNotes._extract_tags(content)
            content_highlights = hit.highlights(
                "content",
                text=content_ex_tags,
            )
        else:
            content_highlights = None

        tag_matches = (
            [field[1] for field in hit.matched_terms() if field[0] == "tags"]
            if "tags" in matched_fields
            else None
        )

        return SearchResult(
            title=title,
            last_modified=last_modified,
            score=score,
            title_highlights=title_highlights,
            content_highlights=content_highlights,
            tag_matches=tag_matches,
        )

    def _fieldnames_for_term(self, term: str) -> List[str]:
        """Return a list of field names to search based on the given term. If
        the term includes a phrase then only search title and content. If the
        term does not include a phrase then also search tags."""
        fields = ["title", "content"]
        if '"' not in term:
            # If the term does not include a phrase then also search tags
            fields.append("tags")
        return fields

    @staticmethod
    def _get_matched_fields(matched_terms):
        """Return a set of matched fields from a set of ('field', 'term') "
        "tuples generated by whoosh.searching.Hit.matched_terms()."""
        return set([matched_term[0] for matched_term in matched_terms])

    @staticmethod
    def _read_file(filepath: str):
        logger.debug(f"Reading from '{filepath}'")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return content

    @staticmethod
    def _write_file(filepath: str, content: str, overwrite: bool = False):
        logger.debug(f"Writing to '{filepath}'")
        if not overwrite and os.path.exists(filepath):
            raise FileExistsError(filepath)
        directory = os.path.dirname(os.path.abspath(filepath))
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{os.path.basename(filepath)}.",
            suffix=".tmp",
            dir=directory,
        )
        try:
            with os.fdopen(
                descriptor, "w", encoding="utf-8", newline=""
            ) as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            if not overwrite and os.path.exists(filepath):
                raise FileExistsError(filepath)
            os.replace(temporary_name, filepath)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
