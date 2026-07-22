from __future__ import annotations

import base64
import hashlib
import html
import ipaddress
import json
import re
import socket
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx
import tinycss2
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .errors import PublicationError

MAX_ASSET_BYTES = 4_000_000
MAX_ASSET_COUNT = 24
MAX_TOTAL_ASSET_BYTES = 32 * 1024 * 1024
MAX_PUBLIC_HTML = 850_000
MAX_PUBLIC_CSS = 200_000
RESERVED_TAG = re.compile(
    r"^(?:private|work|infra|pinned|project-.+|task-.+)$", re.IGNORECASE
)
TAG_ONLY_TEXT = re.compile(r"^#[a-zA-Z0-9_-]+(?:\s+#[a-zA-Z0-9_-]+)*$")
SLUG_TOKEN = re.compile(r"[^a-z0-9]+")
PUBLIC_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$", re.IGNORECASE)
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
LOCAL_PATH = re.compile(
    r"(?:^|[\s\"'(])(?:[a-z]:[\\/]|\\\\[a-z0-9._-]+\\)", re.IGNORECASE
)
PRIVATE_IPV4 = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"169\.254\.\d{1,3}\.\d{1,3}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3})\b"
)
CREDENTIAL_PATTERNS = (
    re.compile(
        r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:github_pat_[a-zA-Z0-9_]{20,}|gh[pousr]_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})\b"
    ),
    re.compile(
        r"\b(?:sk-(?:proj-|ant-)?[a-zA-Z0-9_-]{20,}|"
        r"glpat-[a-zA-Z0-9_-]{20,}|npm_[a-zA-Z0-9]{20,}|"
        r"xox[baprs]-[a-zA-Z0-9-]{20,}|AIza[0-9A-Za-z_-]{35}|"
        r"(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{16,})\b"
    ),
    re.compile(
        r"\b(?:authorization\s*:\s*bearer|"
        r"(?:api[_-]?key|access[_-]?token|password)\s*[:=])"
        r"\s*[\"']?[^\s\"']{12,}",
        re.IGNORECASE,
    ),
)
FORBIDDEN_REMOVE = {
    "base",
    "button",
    "embed",
    "form",
    "link",
    "meta",
    "noscript",
    "object",
    "script",
    "select",
    "source",
    "style",
    "template",
    "textarea",
    "track",
}
RUNTIME_TAGS = {"audio", "canvas", "iframe", "video"}
RUNTIME_SVG_TAGS = {
    "animate",
    "animatemotion",
    "animatetransform",
    "discard",
    "mpath",
    "set",
}
FORBIDDEN_SVG_TAGS = {
    "script",
    "foreignobject",
    "iframe",
    "object",
    "embed",
    "style",
}
INTERNAL_ATTRIBUTE = re.compile(
    r"^(?:data-lamanotes-|lamanotes-|data-nirvnotes-|nirvnotes-|"
    r"data-work-source|data-work-markdown|"
    r"data-editor-source|data-draft)",
    re.IGNORECASE,
)
MIME_EXTENSION = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "application/pdf": "pdf",
}
DEFAULT_PUBLIC_CSS = (
    ".lamanote-source>h1,.nirvnote-source>h1{font-size:clamp(2rem,5vw,3.4rem);"
    "line-height:1.06;letter-spacing:0}"
)
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


@dataclass(frozen=True)
class PublicAsset:
    asset_id: str
    file_name: str
    content_type: str
    sha256: str
    content: bytes

    @property
    def byte_length(self) -> int:
        return len(self.content)

    def manifest_entry(self) -> dict:
        return {
            "assetId": self.asset_id,
            "fileName": self.file_name,
            "contentType": self.content_type,
            "byteLength": self.byte_length,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class PublicProjection:
    title: str
    description: str
    language: str
    tags: tuple[str, ...]
    note_kind: str
    public_html: str
    public_css: str
    assets: tuple[PublicAsset, ...]
    content_hash: str

    def manifest(self, source_id: str, requested_slug: str | None) -> dict:
        page = {
            "title": self.title,
            "description": self.description,
            "language": self.language,
            "tags": list(self.tags),
            "noteKind": self.note_kind,
        }
        if requested_slug is not None:
            page["requestedSlug"] = requested_slug
        return {
            "schemaVersion": 1,
            "source": {"id": source_id, "system": "lamanotes"},
            "page": page,
            "content": {
                "publicHtml": self.public_html,
                "publicCss": self.public_css,
                "contentHash": self.content_hash,
            },
            "assets": [asset.manifest_entry() for asset in self.assets],
        }


class PublicProjectionBuilder:
    def __init__(self, storage_path: str, timeout_seconds: int = 20) -> None:
        self.storage_path = Path(storage_path).resolve()
        self.attachments_path = (self.storage_path / "attachments").resolve()
        self.timeout_seconds = max(2, min(int(timeout_seconds), 60))
        self._assets_by_hash: dict[str, PublicAsset] = {}

    def build(self, title: str, content: str) -> PublicProjection:
        self._assets_by_hash = {}
        normalized_source = (
            str(content or "").replace("\r\n", "\n").replace("\r", "\n")
        )
        soup = BeautifulSoup(normalized_source, "html.parser")
        note_kind = self._note_kind(soup)
        language = self._language(soup)
        tags = self._tags(soup)
        description = self._description(soup, title)
        style_blocks = [
            style.get_text("\n") for style in soup.find_all("style")
        ]

        self._remove_internal_content(soup)
        root = self._public_root(soup, note_kind)
        self._sanitize_tree(root, title)
        public_html = self._serialize_root(root, title)
        public_css = self._public_css(style_blocks)

        assets = tuple(
            PublicAsset(
                asset_id=f"asset_{index}",
                file_name=asset.file_name,
                content_type=asset.content_type,
                sha256=asset.sha256,
                content=asset.content,
            )
            for index, asset in enumerate(
                sorted(
                    self._assets_by_hash.values(),
                    key=lambda item: item.file_name,
                ),
                start=1,
            )
        )
        if len(assets) > MAX_ASSET_COUNT:
            raise PublicationError(
                413,
                "publication_too_large",
                f"This note contains more than {MAX_ASSET_COUNT} public assets.",
            )
        if sum(asset.byte_length for asset in assets) > MAX_TOTAL_ASSET_BYTES:
            raise PublicationError(
                413,
                "publication_too_large",
                "The public assets exceed the 32 MiB total limit.",
            )

        canonical_assets = [
            {
                "fileName": asset.file_name,
                "contentType": asset.content_type,
                "byteLength": asset.byte_length,
                "sha256": asset.sha256,
            }
            for asset in assets
        ]
        canonical = {
            "schemaVersion": 1,
            "title": title.strip(),
            "description": description,
            "language": language,
            "tags": list(tags),
            "noteKind": note_kind,
            "publicHtml": public_html,
            "publicCss": public_css,
            "assets": canonical_assets,
        }
        canonical_json = json.dumps(
            canonical, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        content_hash = f"sha256:{hashlib.sha256(canonical_json).hexdigest()}"
        return PublicProjection(
            title=title.strip(),
            description=description,
            language=language,
            tags=tags,
            note_kind=note_kind,
            public_html=public_html,
            public_css=public_css,
            assets=assets,
            content_hash=content_hash,
        )

    @staticmethod
    def suggested_slug(title: str) -> str:
        normalized = unicodedata.normalize("NFKD", title or "")
        ascii_value = (
            normalized.encode("ascii", "ignore").decode("ascii").lower()
        )
        slug = SLUG_TOKEN.sub("-", ascii_value).strip("-")[:80].strip("-")
        return slug or "note"

    @staticmethod
    def _note_kind(soup: BeautifulSoup) -> str:
        marker = soup.find(
            "meta",
            attrs={"name": {"lamanotes-note-kind", "flatnotes-note-kind"}},
        )
        if str(marker.get("content") if marker else "").lower() == "work":
            return "work"
        if soup.select_one(
            "[data-lamanotes-note-kind='work'],"
            "[data-flatnotes-note-kind='work']"
        ):
            return "work"
        return "research"

    @staticmethod
    def _language(soup: BeautifulSoup) -> str:
        html_tag = soup.find("html")
        language = str(html_tag.get("lang") if html_tag else "").strip()
        return language if PUBLIC_LANGUAGE.fullmatch(language) else "de"

    @staticmethod
    def _split_tags(value: str) -> set[str]:
        return {
            token.lower()
            for token in re.split(r"[\s,#]+", value or "")
            if token and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", token)
        }

    def _tags(self, soup: BeautifulSoup) -> tuple[str, ...]:
        tags: set[str] = set()
        for meta in soup.find_all(
            "meta",
            attrs={"name": {"lamanotes-tags", "flatnotes-tags"}},
        ):
            tags.update(self._split_tags(str(meta.get("content") or "")))
        for element in soup.find_all(["p", "div", "footer"]):
            text = " ".join(element.stripped_strings).strip()
            if TAG_ONLY_TEXT.fullmatch(text):
                tags.update(self._split_tags(text))
        return tuple(
            sorted(tag for tag in tags if not RESERVED_TAG.fullmatch(tag))
        )

    def _description(self, soup: BeautifulSoup, title: str) -> str:
        candidates = []
        for name in ("description", "lamanotes-summary", "flatnotes-summary"):
            meta = soup.find("meta", attrs={"name": name})
            if meta:
                candidates.append(str(meta.get("content") or ""))
        summary = soup.select_one(".lamanote-summary, .flatnote-summary")
        if summary:
            candidates.append(summary.get_text(" ", strip=True))
        paragraph = soup.find("p")
        if paragraph:
            candidates.append(paragraph.get_text(" ", strip=True))
        candidates.append(title)
        for candidate in candidates:
            text = re.sub(r"\s+", " ", candidate or "").strip()
            if text:
                self._assert_safe_material(text, "Description")
                return text[:240].rstrip()
        return ""

    def _remove_internal_content(self, soup: BeautifulSoup) -> None:
        for comment in soup.find_all(
            string=lambda value: isinstance(value, Comment)
        ):
            comment.extract()
        for tag in list(soup.find_all(True)):
            # Decomposing a parent also clears attrs/name on descendants that
            # are still present in the snapshot returned by find_all().
            if tag.name is None or tag.attrs is None:
                continue
            name = tag.name.lower()
            if (
                name == "input"
                and str(tag.get("type") or "").lower() == "checkbox"
            ):
                tag.replace_with(
                    NavigableString(
                        "[x]" if tag.has_attr("checked") else "[ ]"
                    )
                )
                continue
            if name in RUNTIME_TAGS:
                raise PublicationError(
                    422,
                    "runtime_component",
                    f"The note contains a runtime <{name}> component. Use a static image or SVG.",
                )
            if name in FORBIDDEN_REMOVE or name == "input":
                tag.decompose()
                continue
            if tag.has_attr("hidden"):
                tag.decompose()
                continue
            if name in {"p", "div", "footer"} and TAG_ONLY_TEXT.fullmatch(
                " ".join(tag.stripped_strings).strip()
            ):
                tag.decompose()
                continue
            classes = {str(value).lower() for value in tag.get("class", [])}
            if classes.intersection(
                {
                    "lamanotes-editor-controls",
                    "lamanotes-copy-control",
                    "lamanotes-tag-controls",
                    "flatnotes-editor-controls",
                    "flatnotes-copy-control",
                    "flatnotes-tag-controls",
                    "toastui-editor-toolbar",
                }
            ):
                tag.decompose()

    def _public_root(self, soup: BeautifulSoup, note_kind: str) -> Tag:
        if note_kind == "work":
            source = soup.select_one(
                "article[data-lamanotes-note-kind='work'],"
                "article[data-flatnotes-note-kind='work']"
            )
            if source is None:
                source = soup.select_one(
                    ".lamanote-work-rendered, .flatnote-work-rendered"
                )
        else:
            source = soup.find("body") or soup.select_one("article")
        if source is None:
            source = soup

        output_soup = BeautifulSoup("", "html.parser")
        article = output_soup.new_tag("article")
        article["class"] = [
            "lamanote",
            (
                "lamanote-work-public"
                if note_kind == "work"
                else "lamanote-research-public"
            ),
        ]
        article["data-lamanotes-component"] = (
            "work-note" if note_kind == "work" else "research-note"
        )
        if isinstance(source, Tag) and source.name == "article":
            safe_classes = [
                value
                for value in source.get("class", [])
                if not str(value).lower().startswith(("toastui-", "editor-"))
            ]
            article["class"] = list(
                dict.fromkeys(article["class"] + safe_classes)
            )
        children = list(source.contents) if hasattr(source, "contents") else []
        for child in children:
            article.append(child.extract())
        self._normalize_lamanotes_contract(article)
        return article

    @staticmethod
    def _normalize_lamanotes_contract(root: Tag) -> None:
        for tag in [root, *root.find_all(True)]:
            if tag.has_attr("data-flatnotes-component"):
                tag["data-lamanotes-component"] = tag.get(
                    "data-lamanotes-component",
                    tag.get("data-flatnotes-component"),
                )
                del tag.attrs["data-flatnotes-component"]
            classes = []
            for value in tag.get("class", []):
                normalized = str(value)
                lower = normalized.lower()
                if lower == "flatnotes":
                    normalized = "lamanotes"
                elif lower.startswith("flatnotes-"):
                    normalized = f"lamanotes-{normalized[len('flatnotes-'):]}"
                elif lower == "flatnote":
                    normalized = "lamanote"
                elif lower.startswith("flatnote-"):
                    normalized = f"lamanote-{normalized[len('flatnote-'):]}"
                classes.append(normalized)
            if classes:
                tag["class"] = list(dict.fromkeys(classes))

    def _sanitize_tree(self, root: Tag, title: str) -> None:
        first_h1 = root.find("h1")
        if (
            first_h1
            and first_h1.get_text(" ", strip=True).casefold()
            == title.strip().casefold()
        ):
            first_h1.decompose()

        for tag in list(root.find_all(True)):
            if not tag.parent:
                continue
            name = tag.name.lower()
            if name == "svg":
                self._validate_inline_svg(tag)
            for attribute in list(tag.attrs):
                lower = attribute.lower()
                if lower.startswith("on") or lower in {
                    "action",
                    "formaction",
                    "ping",
                    "srcdoc",
                    "contenteditable",
                    "draggable",
                }:
                    del tag.attrs[attribute]
                    continue
                if (
                    lower.startswith(("data-lamanotes-", "data-flatnotes-"))
                    and lower != "data-lamanotes-component"
                ):
                    del tag.attrs[attribute]
                    continue
                if (
                    lower != "data-lamanotes-component"
                    and INTERNAL_ATTRIBUTE.match(lower)
                ):
                    del tag.attrs[attribute]
                    continue
                value = tag.attrs.get(attribute)
                if isinstance(value, list):
                    value = " ".join(str(item) for item in value)
                self._assert_safe_material(
                    str(value or ""), f"Attribute {lower}"
                )

            if tag.has_attr("style"):
                sanitized = self._sanitize_declarations(
                    str(tag.get("style") or "")
                )
                if sanitized:
                    tag["style"] = sanitized
                else:
                    del tag.attrs["style"]

            if name == "img":
                source = str(tag.get("src") or "").strip()
                if not source:
                    raise PublicationError(
                        422, "asset_missing", "An image has no source."
                    )
                asset = self._resolve_asset(source)
                tag["src"] = f"assets/{asset.file_name}"
                tag.attrs.pop("srcset", None)
                if not tag.has_attr("alt"):
                    tag["alt"] = Path(asset.file_name).stem
                tag["loading"] = "lazy"
                tag["decoding"] = "async"
            elif name == "a" and tag.has_attr("href"):
                href = str(tag.get("href") or "").strip()
                if self._is_asset_source(href):
                    asset = self._resolve_asset(href)
                    tag["href"] = f"assets/{asset.file_name}"
                elif href.startswith("#"):
                    pass
                elif self._is_public_link(href):
                    if tag.get("target") == "_blank":
                        rel = set(tag.get("rel") or [])
                        rel.update({"noopener", "noreferrer"})
                        tag["rel"] = sorted(rel)
                elif self._unsafe_category(href):
                    self._assert_safe_material(href, "Link")
                else:
                    tag.unwrap()
            elif name not in {"svg", "use", "image"}:
                for attribute in ("src", "poster"):
                    if tag.has_attr(attribute):
                        del tag.attrs[attribute]

        for text_node in root.find_all(string=True):
            self._assert_safe_material(str(text_node), "Public text")

    def _serialize_root(self, root: Tag, title: str) -> str:
        if not root.get_text(" ", strip=True) and not root.find(
            ["img", "svg", "table", "figure"]
        ):
            raise PublicationError(
                400, "invalid_request", "The note has no public content."
            )
        markup = str(root).replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(markup) > MAX_PUBLIC_HTML:
            raise PublicationError(
                413, "publication_too_large", "The public HTML exceeds 850 KB."
            )
        self._assert_safe_material(title, "Title")
        return markup

    def _public_css(self, style_blocks: list[str]) -> str:
        output = [DEFAULT_PUBLIC_CSS]
        for css in style_blocks:
            sanitized = self._sanitize_stylesheet(css)
            if sanitized:
                output.append(sanitized)
        result = "".join(output).replace("\r\n", "\n").replace("\r", "\n")
        if len(result) > MAX_PUBLIC_CSS:
            raise PublicationError(
                413, "publication_too_large", "The public CSS exceeds 200 KB."
            )
        self._assert_safe_material(result, "Note CSS")
        return result

    def _sanitize_stylesheet(self, value: str) -> str:
        rules = tinycss2.parse_stylesheet(
            value or "", skip_comments=True, skip_whitespace=True
        )
        return self._serialize_css_rules(rules)

    def _serialize_css_rules(self, rules) -> str:
        output = []
        for rule in rules:
            if rule.type == "error":
                raise PublicationError(
                    422, "unsafe_public_content", "The note CSS is invalid."
                )
            if rule.type == "qualified-rule":
                selector = tinycss2.serialize(rule.prelude).strip()
                scoped = self._scope_selector(selector)
                declarations = self._sanitize_declarations(
                    tinycss2.serialize(rule.content)
                )
                if scoped and declarations:
                    output.append(f"{scoped}{{{declarations}}}")
                continue
            if rule.type != "at-rule":
                continue
            name = str(rule.lower_at_keyword or "").lower()
            if name in {
                "import",
                "namespace",
                "font-face",
                "keyframes",
                "-webkit-keyframes",
            }:
                continue
            if (
                name not in {"media", "supports", "container"}
                or rule.content is None
            ):
                continue
            nested = tinycss2.parse_rule_list(
                rule.content, skip_comments=True, skip_whitespace=True
            )
            serialized = self._serialize_css_rules(nested)
            if serialized:
                prelude = self._compact_css_fragment(
                    tinycss2.serialize(rule.prelude).strip()
                )
                output.append(f"@{name} {prelude}{{{serialized}}}")
        return "".join(output)

    def _scope_selector(self, selector: str) -> str:
        scoped = []
        for item in self._split_selector_list(selector):
            item = re.sub(
                r"(?<![a-z0-9_-])(?::root|html|body)(?![a-z0-9_-])",
                "",
                item,
                flags=re.IGNORECASE,
            )
            item = re.sub(r"\s+", " ", item).strip()
            item = self._compact_css_fragment(item, compact_combinators=True)
            if not item:
                item = ".nirvnote-source"
            elif not item.startswith(".nirvnote-source"):
                item = f".nirvnote-source {item}"
            scoped.append(item)
        return ",".join(scoped)

    @staticmethod
    def _split_selector_list(selector: str) -> list[str]:
        output = []
        current = []
        depth = 0
        for character in selector:
            if character in "([":
                depth += 1
            elif character in ")]" and depth:
                depth -= 1
            if character == "," and depth == 0:
                output.append("".join(current).strip())
                current = []
            else:
                current.append(character)
        if current:
            output.append("".join(current).strip())
        return [item for item in output if item]

    def _sanitize_declarations(self, value: str) -> str:
        declarations = tinycss2.parse_declaration_list(
            value or "", skip_comments=True, skip_whitespace=True
        )
        output = []
        for declaration in declarations:
            if declaration.type == "error":
                raise PublicationError(
                    422, "unsafe_public_content", "The note CSS is invalid."
                )
            if declaration.type != "declaration":
                continue
            property_name = declaration.lower_name
            serialized = self._compact_css_fragment(
                tinycss2.serialize(declaration.value).strip()
            )
            if property_name in {"behavior", "-moz-binding"}:
                continue
            if property_name == "position" and re.search(
                r"\bfixed\b", serialized, re.IGNORECASE
            ):
                continue
            if re.search(r"\bexpression\s*\(", serialized, re.IGNORECASE):
                continue
            rewritten = self._rewrite_css_urls(serialized)
            important = "!important" if declaration.important else ""
            output.append(f"{property_name}:{rewritten}{important}")
        return ";".join(output)

    @staticmethod
    def _compact_css_fragment(
        value: str, *, compact_combinators: bool = False
    ) -> str:
        """Remove only CSS whitespace that is never semantically required."""
        output: list[str] = []
        pending_space = False
        quote = ""
        escaped = False
        punctuation = set("(){}[],:;")
        if compact_combinators:
            punctuation.update(">+~")

        for character in value:
            if quote:
                output.append(character)
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = ""
                continue

            if character in {'"', "'"}:
                if pending_space and output and output[-1] not in punctuation:
                    output.append(" ")
                pending_space = False
                quote = character
                output.append(character)
                continue

            if character.isspace():
                pending_space = True
                continue

            if pending_space and output:
                previous = output[-1]
                if (
                    previous not in punctuation
                    and character not in punctuation
                ):
                    output.append(" ")
            pending_space = False
            if character in punctuation and output and output[-1] == " ":
                output.pop()
            output.append(character)

        return "".join(output).strip()

    def _rewrite_css_urls(self, value: str) -> str:
        def replace(match: re.Match) -> str:
            target = html.unescape(match.group(2).strip())
            if target.startswith("#"):
                return f'url("{target}")'
            asset = self._resolve_asset(target)
            return f'url("assets/{asset.file_name}")'

        return CSS_URL.sub(replace, value)

    def _resolve_asset(self, source: str) -> PublicAsset:
        decoded = urllib.parse.unquote(html.unescape(source.strip()))
        if decoded.startswith("data:"):
            original_name, content = self._decode_data_uri(decoded)
        elif decoded.lower().startswith("https://"):
            original_name, content = self._fetch_remote(decoded)
        else:
            original_name, content = self._read_local_asset(decoded)

        content_type, content = self._sniff_asset(content)
        digest_hex = hashlib.sha256(content).hexdigest()
        digest = f"sha256:{digest_hex}"
        existing = self._assets_by_hash.get(digest)
        if existing:
            return existing
        extension = MIME_EXTENSION[content_type]
        safe_stem = self._safe_stem(Path(original_name).stem)
        file_name = f"{safe_stem}-{digest_hex[:12]}.{extension}"
        asset = PublicAsset(
            asset_id="asset_pending",
            file_name=file_name,
            content_type=content_type,
            sha256=digest,
            content=content,
        )
        self._assets_by_hash[digest] = asset
        return asset

    def _read_local_asset(self, source: str) -> tuple[str, bytes]:
        path_text = source.split("?", 1)[0].split("#", 1)[0]
        normalized = path_text.replace("\\", "/")
        if normalized.startswith("/attachments/"):
            relative = normalized[len("/attachments/") :]
            root = self.attachments_path
        elif normalized.startswith("attachments/"):
            relative = normalized[len("attachments/") :]
            root = self.attachments_path
        elif normalized.startswith("/note-assets/"):
            relative = normalized[len("/note-assets/") :]
            root = self.storage_path
        elif "/" not in normalized.strip("/"):
            relative = normalized.strip("/")
            root = self.storage_path
        else:
            raise PublicationError(
                422,
                "asset_missing",
                "A public image uses an unsupported source path.",
            )
        if not relative or "\x00" in relative:
            raise PublicationError(
                422, "asset_missing", "A public asset path is invalid."
            )
        try:
            candidate = (root / relative).resolve(strict=True)
        except (OSError, RuntimeError):
            raise PublicationError(
                422,
                "asset_missing",
                f"The public asset '{Path(relative).name}' could not be found.",
            )
        if candidate.parent != root and root not in candidate.parents:
            raise PublicationError(
                422, "asset_missing", "A public asset path is invalid."
            )
        if not candidate.is_file():
            raise PublicationError(
                422, "asset_missing", "A public asset is missing."
            )
        if candidate.stat().st_size > MAX_ASSET_BYTES:
            raise PublicationError(
                413,
                "asset_too_large",
                f"The asset '{candidate.name}' exceeds the 4 MB publication limit.",
            )
        return candidate.name, candidate.read_bytes()

    def _decode_data_uri(self, source: str) -> tuple[str, bytes]:
        match = re.fullmatch(
            r"data:([a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+)(;base64)?,(.*)",
            source,
            re.DOTALL,
        )
        if not match:
            raise PublicationError(
                422, "asset_mismatch", "An embedded asset is invalid."
            )
        content_type = match.group(1).lower()
        try:
            content = (
                base64.b64decode(match.group(3), validate=True)
                if match.group(2)
                else urllib.parse.unquote_to_bytes(match.group(3))
            )
        except (ValueError, TypeError):
            raise PublicationError(
                422, "asset_mismatch", "An embedded asset is invalid."
            )
        extension = MIME_EXTENSION.get(content_type, "bin")
        return f"embedded.{extension}", content

    def _fetch_remote(self, source: str) -> tuple[str, bytes]:
        current = source
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": "LamaNotes-Publisher/1.0",
                "Accept": "image/*,application/pdf",
            },
        ) as client:
            for _ in range(4):
                self._validate_remote_url(current)
                try:
                    with client.stream("GET", current) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise PublicationError(
                                    422,
                                    "asset_missing",
                                    "A remote asset redirect is invalid.",
                                )
                            current = urllib.parse.urljoin(current, location)
                            continue
                        if response.status_code != 200:
                            raise PublicationError(
                                422,
                                "asset_missing",
                                "A remote public asset could not be fetched.",
                            )
                        length = response.headers.get("content-length")
                        if length and int(length) > MAX_ASSET_BYTES:
                            raise PublicationError(
                                413,
                                "asset_too_large",
                                "A remote asset exceeds the 4 MB publication limit.",
                            )
                        chunks = []
                        total = 0
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > MAX_ASSET_BYTES:
                                raise PublicationError(
                                    413,
                                    "asset_too_large",
                                    "A remote asset exceeds the 4 MB publication limit.",
                                )
                            chunks.append(chunk)
                        name = (
                            Path(urllib.parse.urlparse(current).path).name
                            or "remote-asset"
                        )
                        return name, b"".join(chunks)
                except PublicationError:
                    raise
                except (httpx.HTTPError, ValueError):
                    raise PublicationError(
                        502,
                        "consumer_unavailable",
                        "A remote public asset could not be fetched safely.",
                        retryable=True,
                    )
        raise PublicationError(
            422, "asset_missing", "A remote asset has too many redirects."
        )

    def _validate_remote_url(self, value: str) -> None:
        parsed = urllib.parse.urlparse(value)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise PublicationError(
                422,
                "unsafe_public_content",
                "A remote asset must use a public HTTPS URL.",
            )
        hostname = parsed.hostname.lower()
        if (
            hostname.endswith((".local", ".internal", ".ts.net"))
            or hostname == "localhost"
        ):
            raise PublicationError(
                422,
                "unsafe_public_content",
                "A remote asset points to a private destination.",
            )
        try:
            addresses = socket.getaddrinfo(
                hostname, parsed.port or 443, type=socket.SOCK_STREAM
            )
        except socket.gaierror:
            raise PublicationError(
                422,
                "asset_missing",
                "A remote asset host could not be resolved.",
            )
        for address in {item[4][0] for item in addresses}:
            try:
                if not ipaddress.ip_address(address).is_global:
                    raise PublicationError(
                        422,
                        "unsafe_public_content",
                        "A remote asset points to a private destination.",
                    )
            except ValueError:
                raise PublicationError(
                    422,
                    "unsafe_public_content",
                    "A remote asset address is invalid.",
                )

    def _sniff_asset(self, content: bytes) -> tuple[str, bytes]:
        if not content or len(content) > MAX_ASSET_BYTES:
            raise PublicationError(
                413, "asset_too_large", "A public asset is empty or too large."
            )
        if (
            content.startswith(b"\x89PNG\r\n\x1a\n")
            and b"IEND" in content[-32:]
        ):
            return "image/png", content
        if content.startswith(b"\xff\xd8") and content.rstrip().endswith(
            b"\xff\xd9"
        ):
            return "image/jpeg", content
        if content[:6] in {b"GIF87a", b"GIF89a"} and content.rstrip().endswith(
            b";"
        ):
            return "image/gif", content
        if (
            len(content) >= 12
            and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP"
            and int.from_bytes(content[4:8], "little") + 8 <= len(content)
        ):
            return "image/webp", content
        if content.startswith(b"%PDF-") and b"%%EOF" in content[-1024:]:
            return "application/pdf", content
        decoded = content.decode("utf-8-sig", errors="ignore").lstrip()
        if decoded.startswith("<svg") or decoded.startswith("<?xml"):
            return "image/svg+xml", self._sanitize_svg_asset(content)
        raise PublicationError(
            422,
            "asset_mismatch",
            "A public asset has an unsupported or incomplete file structure.",
        )

    def _sanitize_svg_asset(self, content: bytes) -> bytes:
        text = content.decode("utf-8-sig")
        if re.search(r"<!doctype|<!entity", text, re.IGNORECASE):
            raise PublicationError(
                422,
                "unsafe_public_content",
                "SVG declarations are not publishable.",
            )
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            raise PublicationError(
                422, "asset_mismatch", "An SVG asset is not well-formed."
            )
        if self._local_name(root.tag) != "svg":
            raise PublicationError(
                422, "asset_mismatch", "An SVG asset has no SVG root."
            )
        for element in root.iter():
            name = self._local_name(element.tag)
            if name in RUNTIME_SVG_TAGS:
                raise PublicationError(
                    422,
                    "runtime_component",
                    "An SVG asset contains animation.",
                )
            if name in FORBIDDEN_SVG_TAGS:
                raise PublicationError(
                    422,
                    "unsafe_public_content",
                    "An SVG asset contains executable content.",
                )
            for attribute, value in element.attrib.items():
                lower = self._local_name(attribute)
                if lower.startswith("on"):
                    raise PublicationError(
                        422,
                        "unsafe_public_content",
                        "An SVG asset contains an event handler.",
                    )
                if lower in {"href", "src"} and not str(value).startswith("#"):
                    raise PublicationError(
                        422,
                        "unsafe_public_content",
                        "An SVG asset contains an external reference.",
                    )
                if lower == "style":
                    element.set(
                        attribute, self._sanitize_declarations(str(value))
                    )
                self._assert_safe_material(str(value), "SVG asset")
            if element.text:
                self._assert_safe_material(element.text, "SVG asset")
        ET.register_namespace("", SVG_NAMESPACE)
        return ET.tostring(root, encoding="utf-8", method="xml")

    def _validate_inline_svg(self, svg: Tag) -> None:
        for tag in svg.find_all(True):
            name = tag.name.lower()
            if name in RUNTIME_SVG_TAGS:
                raise PublicationError(
                    422,
                    "runtime_component",
                    "Inline SVG animation is not publishable.",
                )
            if name in FORBIDDEN_SVG_TAGS:
                raise PublicationError(
                    422,
                    "unsafe_public_content",
                    "Inline SVG contains executable content.",
                )
            for attribute, value in list(tag.attrs.items()):
                lower = attribute.lower()
                if lower.startswith("on"):
                    del tag.attrs[attribute]
                elif lower in {"href", "xlink:href", "src"} and not str(
                    value
                ).startswith("#"):
                    raise PublicationError(
                        422,
                        "unsafe_public_content",
                        "Inline SVG contains an external reference.",
                    )

    @staticmethod
    def _local_name(value: str) -> str:
        return str(value).split("}", 1)[-1].split(":", 1)[-1].lower()

    @staticmethod
    def _safe_stem(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "asset")
        ascii_value = (
            normalized.encode("ascii", "ignore").decode("ascii").lower()
        )
        stem = SLUG_TOKEN.sub("-", ascii_value).strip("-")
        return (stem or "asset")[:100].rstrip("-")

    @staticmethod
    def _is_asset_source(value: str) -> bool:
        decoded = urllib.parse.unquote(html.unescape(value or ""))
        return (
            decoded.startswith(
                ("/attachments/", "attachments/", "/note-assets/", "data:")
            )
            or decoded.lower().startswith("https://")
            and bool(
                re.search(
                    r"\.(?:png|jpe?g|webp|gif|svg|pdf)(?:[?#]|$)",
                    decoded,
                    re.IGNORECASE,
                )
            )
        )

    @staticmethod
    def _is_public_link(value: str) -> bool:
        try:
            parsed = urllib.parse.urlparse(value)
        except ValueError:
            return False
        if parsed.scheme in {"mailto", "tel"}:
            return True
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        try:
            address = ipaddress.ip_address(parsed.hostname.strip("[]"))
            return address.is_global
        except ValueError:
            return (
                not parsed.hostname.lower().endswith(
                    (".local", ".internal", ".ts.net")
                )
                and parsed.hostname.lower() != "localhost"
            )

    @staticmethod
    def _unsafe_category(value: str) -> str | None:
        inspected = urllib.parse.unquote(str(value or ""))
        if LOCAL_PATH.search(inspected):
            return "local path"
        if re.search(
            r"\b(?:file|vscode|vscode-insiders|pywebview):",
            inspected,
            re.IGNORECASE,
        ):
            return "local application URL"
        if re.search(
            r"\b(?:localhost|0\.0\.0\.0|127\.0\.0\.1|\[?::1\]?)\b",
            inspected,
            re.IGNORECASE,
        ):
            return "loopback address"
        if PRIVATE_IPV4.search(inspected):
            return "private network address"
        if re.search(r"\b[a-z0-9.-]+\.ts\.net\b", inspected, re.IGNORECASE):
            return "Tailnet address"
        for pattern in CREDENTIAL_PATTERNS:
            if pattern.search(inspected):
                return "credential-like value"
        return None

    def _assert_safe_material(self, value: str, location: str) -> None:
        category = self._unsafe_category(value)
        if category:
            raise PublicationError(
                422,
                "unsafe_public_content",
                f"{location} contains a {category}.",
            )
