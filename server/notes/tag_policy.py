"""Tag identity and surgical, explicitly planned HTML metadata cleanup."""
from dataclasses import dataclass
from html.parser import HTMLParser
from html import unescape
import re

TAG_RE = re.compile(r"[a-z0-9_-]+", re.IGNORECASE)
TOPIC_RE = re.compile(r"r-[a-z0-9]+(?:-[a-z0-9]+)*")
TAG_META_NAMES = {"lamanotes-tags", "flatnotes-tags"}
TOPIC_META_NAMES = {"lamanotes-research-topic", "flatnotes-research-topic"}
TECHNICAL_SUGGESTION_TAGS = frozenset({"r-acceptance", "r-fixture", "design-reference", "publisher-demo"})


def normalize_tag_name(value):
    tag = str(value or "").strip().lstrip("#").strip().lower()
    return tag if TAG_RE.fullmatch(tag) else ""


def split_tag_list(value):
    # Existing HTML metadata also accepts comma- and whitespace-separated lists.
    return {tag.lower() for tag in re.findall(r"#?([a-zA-Z0-9_-]+)", value or "")}


@dataclass(frozen=True)
class TagRewrite:
    content: str
    previous_tags: tuple
    tags: tuple
    changed_spans: tuple


class _TagDocument(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=False)
        self.content = content
        self.line_offsets = [0]
        self.line_offsets.extend(match.end() for match in re.finditer("\n", content))
        self.metadata = []
        self.visible = set()
        self.tag_text_spans = set()
        self.candidates = []
        self.skip_depth = 0
        self.feed(content)
        self.close()

    def source_offset(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.skip_depth += 1
        attributes = dict(attrs)
        if tag == "meta":
            self.metadata.append((str(attributes.get("name", "")).lower(), attributes.get("content", ""), self.source_offset(), self.get_starttag_text()))
        if not self.skip_depth and tag in {"div", "p", "footer"}:
            self.candidates.append({"tag": tag, "parts": []})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in {"script", "style", "template", "div", "p", "footer"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag in {"div", "p", "footer"}:
            for index in range(len(self.candidates) - 1, -1, -1):
                candidate = self.candidates[index]
                if candidate["tag"] != tag:
                    continue
                self.candidates.pop(index)
                text = re.sub(r"\s+", " ", " ".join(part[2] for part in candidate["parts"])).strip()
                if re.fullmatch(r"#[a-zA-Z0-9_-]+(?:\s+#[a-zA-Z0-9_-]+)*", text):
                    self.visible.update(split_tag_list(text))
                    self.tag_text_spans.update((start, end) for start, end, _ in candidate["parts"])
                break

    def handle_data(self, data):
        if self.skip_depth:
            return
        span = (self.source_offset(), self.source_offset() + len(data), data)
        for candidate in self.candidates:
            candidate["parts"].append(span)

    def handle_entityref(self, name):
        for candidate in self.candidates:
            candidate["parts"].append((self.source_offset(), self.source_offset() + len(name) + 2, unescape("&" + name + ";")))

    def handle_charref(self, name):
        self.handle_entityref("#" + name)

    @property
    def meta_tags(self):
        return set().union(*(split_tag_list(value) for name, value, _, _ in self.metadata if name in TAG_META_NAMES))

    @property
    def tags(self):
        return self.visible | (self.meta_tags & {"pinned"}) if self.visible else self.meta_tags

    @property
    def primary_topics(self):
        return {normalize_tag_name(value) for name, value, _, _ in self.metadata if name in TOPIC_META_NAMES}

    def identities(self, names):
        return tuple((name, value) for name, value, _, _ in self.metadata if name in names)


def rewrite_tag_metadata(content, replacements, *, expected_primary_topic=None):
    """Change approved tag tokens only. Every unselected source span stays exact."""
    mapping = {}
    for old, new in replacements.items():
        source, target = normalize_tag_name(old), normalize_tag_name(new)
        if not source or not target or {source, target} & {"pinned", "research", "shared"}:
            raise ValueError("Use topic tags; pinning and workflow tags need their own operation.")
        if source != target:
            mapping[source] = target
    if any(target in mapping for target in mapping.values()):
        raise ValueError("Chained tag aliases need a separate explicit plan.")
    before = _TagDocument(content)
    if expected_primary_topic:
        expected = normalize_tag_name(expected_primary_topic)
        if not TOPIC_RE.fullmatch(expected) or expected not in mapping:
            raise ValueError("The expected primary topic needs an explicit replacement.")
        if not TOPIC_RE.fullmatch(mapping[expected]):
            raise ValueError("A primary Research topic needs a valid replacement r-* topic.")
        topic_sets = [{tag for tag in tags if TOPIC_RE.fullmatch(tag)} for tags in (before.meta_tags, before.visible)]
        if "research" not in before.tags or any(topics and topics != {expected} for topics in topic_sets) or expected not in before.tags:
            raise ValueError("The Research topic state is ambiguous or changed.")
        if before.primary_topics and before.primary_topics != {expected}:
            raise ValueError("The explicit primary Research topic disagrees with the tag rows.")

    patches = {}
    for name, value, start, raw in before.metadata:
        if name not in TAG_META_NAMES | TOPIC_META_NAMES:
            continue
        attribute = re.search(r"(?<![\w:-])content\s*=\s*(['\"])(.*?)\1", raw, re.IGNORECASE | re.DOTALL)
        if not attribute:
            raise ValueError("Quoted tag metadata is required for a surgical edit.")
        original = attribute.group(2)
        if name in TOPIC_META_NAMES:
            replacement = mapping.get(normalize_tag_name(value), original)
        else:
            if not re.fullmatch(r"[\s,#a-zA-Z0-9_-]*", original):
                raise ValueError("Tag metadata with other syntax needs manual review.")
            replacement = _replace_tokens(original, mapping, allow_bare=True)
        if replacement != original:
            patches[(start + attribute.start(2), start + attribute.end(2))] = replacement
    for start, end in before.tag_text_spans:
        original = content[start:end]
        replacement = _replace_tokens(original, mapping)
        if replacement != original:
            patches[(start, end)] = replacement
    ordered = sorted(patches)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Overlapping tag markup needs manual review.")
    updated = content
    for start, end in reversed(ordered):
        updated = updated[:start] + patches[(start, end)] + updated[end:]
    after = _TagDocument(updated)
    expected_tags = {mapping.get(tag, tag) for tag in before.tags}
    if after.tags != expected_tags:
        raise ValueError("The tag rows could not be changed without ambiguity.")
    identity_names = {"lamanotes-note-id", "flatnotes-note-id", "lamanotes-research-id", "flatnotes-research-id"}
    if before.identities(identity_names) != after.identities(identity_names):
        raise ValueError("A tag cleanup must preserve note identity and Research provenance.")
    from .file_system.file_system import FileSystemNotes
    if FileSystemNotes._extract_tags(content)[1] != before.tags or FileSystemNotes._extract_tags(updated)[1] != expected_tags:
        raise ValueError("This tag markup needs manual review with the normal note parser.")
    return TagRewrite(updated, tuple(sorted(before.tags)), tuple(sorted(after.tags)), tuple((start, end, patches[(start, end)]) for start, end in ordered))


def _replace_tokens(value, mapping, *, allow_bare=False):
    if not mapping:
        return value
    prefix = "#?" if allow_bare else "#"
    pattern = re.compile(r"(?<![a-zA-Z0-9_-])(" + prefix + r")(" + "|".join(re.escape(key) for key in sorted(mapping, key=len, reverse=True)) + r")(?![a-zA-Z0-9_-])", re.IGNORECASE)
    return pattern.sub(lambda match: match.group(1) + mapping[match.group(2).lower()], value)
