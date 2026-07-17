NOTES_READ = "notes:read"
NOTES_WRITE = "notes:write"
ATTACHMENTS_WRITE = "attachments:write"
PUBLICATIONS_WRITE = "publications:write"

ALL_SCOPES = frozenset(
    {
        NOTES_READ,
        NOTES_WRITE,
        ATTACHMENTS_WRITE,
        PUBLICATIONS_WRITE,
    }
)
