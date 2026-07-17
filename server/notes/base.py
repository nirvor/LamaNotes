from abc import ABC, abstractmethod
from typing import Literal

from .models import (
    Note,
    NoteContext,
    NoteCreate,
    NoteIndexEntry,
    NoteUpdate,
    SearchResult,
)


class BaseNotes(ABC):
    @abstractmethod
    def create(self, data: NoteCreate) -> Note:
        """Create a new note."""
        pass

    @abstractmethod
    def get(self, title: str) -> Note:
        """Get a specific note."""
        pass

    @abstractmethod
    def update(self, title: str, new_data: NoteUpdate) -> Note:
        """Update a specific note."""
        pass

    @abstractmethod
    def delete(self, title: str) -> None:
        """Delete a specific note.""" ""
        pass

    @abstractmethod
    def search(
        self,
        term: str,
        sort: Literal["score", "title", "last_modified"] = "score",
        order: Literal["asc", "desc"] = "desc",
        limit: int = None,
    ) -> list[SearchResult]:
        """Search for notes."""
        pass

    @abstractmethod
    def get_tags(self) -> list[str]:
        """Get a list of all indexed tags."""
        pass

    @abstractmethod
    def get_context(self, title: str) -> NoteContext:
        """Get structured context for a specific note."""
        pass

    @abstractmethod
    def get_semantic_index(self) -> list[NoteIndexEntry]:
        """Get a structured index of all notes."""
        pass
