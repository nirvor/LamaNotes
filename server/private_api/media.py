import re


def normalized_mime(value):
    media = (value or "").split(";", 1)[0].strip().lower()
    return media if re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", media) else "application/octet-stream"


def image_preview(asset):
    width, height = asset.get("width"), asset.get("height")
    return (asset.get("mediaType") in {"image/png", "image/jpeg", "image/webp", "image/gif"}
            and bool(width and height and width > 0 and height > 0 and width * height <= 40_000_000))


def editable_text(data, max_bytes):
    if len(data) > max_bytes:
        return None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        return None
    if any((ord(char) < 32 and char not in "\t\r\n") or ord(char) == 127 for char in text):
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n")
