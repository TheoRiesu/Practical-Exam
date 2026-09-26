"""Membership Lookup and Registry package."""
from .models import Member, MembershipType, MemberStatus
from .validators import ValidationError, validate_member_data
from .db import get_connection, init_db, resolve_db_path
from .fuzzy_utils import fuzzy_rank, row_score, similarity
from .phone_utils import digits_of, format_phone_display
from .repository import MemberRepository
from .service import MemberService

__all__ = [
    "Member", "MembershipType", "MemberStatus",
    "ValidationError", "validate_member_data",
    "get_connection", "init_db", "resolve_db_path",
    "digits_of", "format_phone_display",
    "fuzzy_rank", "row_score", "similarity",
    "MemberRepository", "MemberService",
]

__version__ = "1.0.0"
