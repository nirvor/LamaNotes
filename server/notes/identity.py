import re
import secrets
from html.parser import HTMLParser

NOTE_ID_RE = re.compile(r"^ln-[a-f0-9]{32}$")


class IdentityParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (
            tag == "meta"
            and attrs.get("name", "").lower() == "lamanotes-note-id"
        ):
            self.values.append(attrs.get("content", ""))


def read_note_id(content):
    parser = IdentityParser()
    parser.feed(content or "")
    if not parser.values:
        return None
    if len(parser.values) != 1 or not NOTE_ID_RE.fullmatch(parser.values[0]):
        raise ValueError("Invalid or duplicate note identity.")
    return parser.values[0]


def with_note_id(content, note_id=None):
    content = content or ""
    existing = read_note_id(content)
    if existing:
        if note_id and existing != note_id:
            raise ValueError("A note identity cannot be replaced.")
        return content
    note_id = note_id or "ln-" + secrets.token_hex(16)
    if not NOTE_ID_RE.fullmatch(note_id):
        raise ValueError("Invalid note identity.")
    metadata = f'<meta name="lamanotes-note-id" content="{note_id}">'
    head = re.search(r"<head\b[^>]*>", content, re.I)
    if head:
        position = head.end()
        return content[:position] + metadata + content[position:]
    return metadata + "\n" + content


def preserve_note_id(previous, replacement):
    note_id = read_note_id(previous)
    proposed = read_note_id(replacement)
    if proposed and proposed != note_id:
        raise ValueError("A note identity cannot be supplied or replaced.")
    return with_note_id(replacement, note_id) if note_id else replacement
