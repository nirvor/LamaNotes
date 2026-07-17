from helpers import CustomBaseModel


class AttachmentCreateResponse(CustomBaseModel):
    filename: str
    url: str
    original_filename: str | None = None
    content_type: str | None = None
    size: int | None = None
    sha256: str | None = None
    reused: bool = False
    width: int | None = None
    height: int | None = None
