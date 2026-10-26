"""Tag identity and surgical, explicitly planned HTML metadata cleanup."""
from dataclasses import dataclass
from html.parser import HTMLParser
from html import unescape
import re

TAG_RE = re.compile(r"[a-z0-9_-]+", re.IGNORECASE)
TOPIC_RE = re.compile(r"r-[a-z0-9]+(?:-[a-z0-9]+)*")
TOPIC_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
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
        self.head_end = None
        self.canonical_sources = []
        self.source_candidate = None
        self.feed(content)
        self.close()

    def source_offset(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if self.source_candidate:
            self.source_candidate["nested"] = True
            if tag == self.source_candidate["tag"]:
                self.source_candidate["depth"] += 1
        elif ((tag == "template" and {"data-lamanotes-work-markdown", "data-lamanotes-text-markdown"} & attributes.keys())
              or "data-lamanotes-work-source" in attributes):
            self.source_candidate = {"tag": tag, "start": self.source_offset() + len(self.get_starttag_text()), "depth": 1, "nested": False}
        if tag in {"script", "style", "template"}:
            self.skip_depth += 1
        if tag == "meta":
            self.metadata.append((str(attributes.get("name", "")).lower(), attributes.get("content", ""), self.source_offset(), self.get_starttag_text()))
        if not self.skip_depth and tag in {"div", "p", "footer"}:
            self.candidates.append({"tag": tag, "parts": []})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in {"script", "style", "template", "div", "p", "footer"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "head":
            self.head_end = self.source_offset()
        if self.source_candidate and tag == self.source_candidate["tag"]:
            self.source_candidate["depth"] -= 1
            if not self.source_candidate["depth"]:
                self.canonical_sources.append((self.source_candidate["start"], self.source_offset(), self.source_candidate["nested"]))
                self.source_candidate = None
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


def replace_tag_metadata(content, tags, *, expected_tags, research_topic=None, expected_primary_topic=None):
    """Replace an audited tag set and explicit topic without reserializing HTML."""
    def valid_tags(values):
        if not isinstance(values, (list, tuple, set, frozenset)):
            raise ValueError("Use an explicit tag list.")
        normalized = {normalize_tag_name(value) for value in values}
        if "" in normalized:
            raise ValueError("The tag plan contains an invalid tag.")
        return normalized

    before = _TagDocument(content)
    if before.tags != valid_tags(expected_tags):
        raise ValueError("The tag set changed after the audit.")
    if len(before.primary_topics) > 1:
        raise ValueError("Conflicting primary Research topic metadata needs review.")
    target = valid_tags(tags)
    if "pinned" in target and "pinned" not in before.tags:
        raise ValueError("A tag cleanup must preserve existing pinning.")
    target.update(before.tags & {"pinned"})
    if research_topic is not None and not TOPIC_ID_RE.fullmatch(research_topic):
        raise ValueError("The Research topic ID is invalid.")
    if before.source_candidate:
        raise ValueError("The canonical Markdown source is not closed.")

    from .file_system.file_system import FileSystemNotes
    from .models import Note
    previous_context = FileSystemNotes._context_from_note(Note(title="", content=content, last_modified=1))
    if previous_context.primary_research_topic != expected_primary_topic:
        raise ValueError("The primary Research topic changed after the audit.")
    if previous_context.research_topics and research_topic is None:
        raise ValueError("Keep the Research topic explicitly when removing topic tags.")
    patches = {}
    inserted = []
    found_tags = found_topic = False
    for name, value, start, raw in before.metadata:
        if name not in TAG_META_NAMES | TOPIC_META_NAMES:
            continue
        attribute = re.search(r"(?<![\w:-])content\s*=\s*(['\"])(.*?)\1", raw, re.IGNORECASE | re.DOTALL)
        if not attribute:
            raise ValueError("Quoted tag metadata is required for a surgical edit.")
        original = attribute.group(2)
        if name in TAG_META_NAMES:
            found_tags = True
            if not re.fullmatch(r"[\s,#a-zA-Z0-9_-]*", original):
                raise ValueError("Tag metadata with other syntax needs manual review.")
            replacement = ",".join(sorted(target))
        else:
            found_topic = True
            replacement = research_topic or ""
        if replacement != original:
            patches[(start + attribute.start(2), start + attribute.end(2))] = replacement
    if not found_tags and (target or before.tag_text_spans) and (before.head_end is not None or not before.tag_text_spans):
        inserted.append('<meta name="lamanotes-tags" content="' + ",".join(sorted(target)) + '">')
    if research_topic and not found_topic:
        inserted.append('<meta name="lamanotes-research-topic" content="' + research_topic + '">')
    if inserted:
        if before.head_end is None:
            raise ValueError("An HTML head is required to add guarded metadata.")
        patches[(before.head_end, before.head_end)] = "".join(inserted)

    visible = " ".join("#" + tag for tag in sorted(target - {"pinned"}))
    first = True
    for start, end in sorted(before.tag_text_spans):
        original = content[start:end]
        if not original.strip():
            continue
        replacement = re.sub(r"\S(?:[\s\S]*\S)?", visible if first else "", original, count=1)
        first = False
        if replacement != original:
            patches[(start, end)] = replacement
    for start, end, nested in before.canonical_sources:
        if nested:
            raise ValueError("Canonical Markdown with nested HTML needs manual review.")
        patches.update(_canonical_tag_patches(content[start:end], start, visible))

    ordered = sorted(patches)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Overlapping tag markup needs manual review.")
    updated = content
    for start, end in reversed(ordered):
        updated = updated[:start] + patches[(start, end)] + updated[end:]
    after = _TagDocument(updated)
    if FileSystemNotes._extract_tags(content)[1] != before.tags or FileSystemNotes._extract_tags(updated)[1] != target:
        raise ValueError("The tag markup needs review with the normal note parser.")
    protected = {name for name, _, _, _ in before.metadata} - TAG_META_NAMES - TOPIC_META_NAMES
    if before.identities(protected) != after.identities(protected):
        raise ValueError("A tag cleanup must preserve identity and provenance metadata.")
    context = FileSystemNotes._context_from_note(Note(title="", content=updated, last_modified=1))
    if context.primary_research_topic != research_topic:
        raise ValueError("The explicit Research topic could not be preserved.")
    return TagRewrite(updated, tuple(sorted(before.tags)), tuple(sorted(target)), tuple((start, end, patches[(start, end)]) for start, end in ordered))


def _canonical_tag_patches(source, start, visible):
    patches = {}
    fence = None
    first = True
    offset = start
    for line in source.splitlines(keepends=True):
        text = unescape(line.rstrip("\r\n"))
        delimiter = re.match(r"^\s{0,3}(`{3,}|~{3,})", text)
        if delimiter:
            marker = delimiter.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
        elif fence is None and re.fullmatch(r"\s*(?:#[a-zA-Z0-9_-]+\s*)+", text):
            original = line.rstrip("\r\n")
            replacement = re.sub(r"\S(?:[\s\S]*\S)?", visible if first else "", original, count=1)
            first = False
            if replacement != original:
                patches[(offset, offset + len(original))] = replacement
        offset += len(line)
    if first and visible:
        newline = "\r\n" if "\r\n" in source else "\n"
        patches[(start + len(source), start + len(source))] = newline + newline + visible
    return patches
