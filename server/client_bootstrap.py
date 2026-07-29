from typing import List

from global_config import GlobalConfigResponseModel
from helpers import CustomBaseModel
from notes.models import NoteIndexEntry


class ClientBootstrapResponse(CustomBaseModel):
    """Safe first-load data for an already authenticated LamaNotes client."""

    config: GlobalConfigResponseModel
    index: List[NoteIndexEntry]


def client_config_response(config) -> GlobalConfigResponseModel:
    return GlobalConfigResponseModel(
        auth_type=config.auth_type,
        google_auth_enabled=config.google_auth_enabled,
        password_login_enabled=config.password_login_enabled,
        quick_access_hide=config.quick_access_hide,
        quick_access_title=config.quick_access_title,
        quick_access_term=config.quick_access_term,
        quick_access_sort=config.quick_access_sort,
        quick_access_limit=config.quick_access_limit,
    )
