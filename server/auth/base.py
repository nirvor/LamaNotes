from abc import ABC, abstractmethod
from collections.abc import Callable

from fastapi import Depends, HTTPException

from .models import AuthPrincipal, Login, Token


class BaseAuth(ABC):
    @abstractmethod
    def login(self, data: Login) -> Token:
        """Login a user."""
        pass

    @abstractmethod
    def authenticate(self, token: str) -> AuthPrincipal:
        """Authenticate a user."""
        pass

    @abstractmethod
    def issue_session(self, remember_me: bool = True) -> Token:
        """Issue a session after a trusted external identity check."""
        pass

    def require(self, scope: str) -> Callable:
        def require_scope(
            principal: AuthPrincipal = Depends(self.authenticate),
        ) -> AuthPrincipal:
            if scope not in principal.scopes:
                raise HTTPException(
                    status_code=403,
                    detail="The credential does not have the required scope.",
                )
            return principal

        return require_scope
