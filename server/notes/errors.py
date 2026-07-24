class ResearchNoteContractError(ValueError):
    """The selected note does not satisfy the Research Note contract."""


class ResearchNoteConflictError(RuntimeError):
    """The selected note is ambiguous or changed since it was loaded."""
