"""Data validation (one of the minimum required features)."""
from __future__ import annotations

import re
from datetime import date, datetime

from .models import MembershipType, MemberStatus

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[+\d][\d\s\-().]{5,20}$")
CODE_RE = re.compile(r"^M-\d{4,6}$")
ALLOWED_NAME_EXTRA = set(" '’-.-")


def _valid_name(v: str) -> bool:
    if not (1 <= len(v) <= 60):
        return False
    return all(c.isalpha() or c in ALLOWED_NAME_EXTRA for c in v)


class ValidationError(ValueError):
    """Raised when any field fails validation. Holds a list of messages."""

    def __init__(self, errors: list[str] | str):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("; ".join(self.errors))


def _parse_iso(d: str, field: str, errors: list[str]) -> date | None:
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        errors.append(f"{field} must be YYYY-MM-DD (got {d!r})")
        return None


def validate_member_data(data: dict, *, is_update: bool = False) -> dict:
    """Validate + normalize a member payload. Returns cleaned dict or raises."""
    errors: list[str] = []
    cleaned: dict = {}

    def get(k: str) -> str:
        v = data.get(k, "")
        return "" if v is None else str(v).strip()

    code = get("member_code")
    if code:
        if not CODE_RE.match(code):
            errors.append("member_code must look like M-0001 (M- + 4-6 digits)")
        cleaned["member_code"] = code.upper()
    elif not is_update:
        cleaned["member_code"] = ""  # auto-assign later

    for f in ("first_name", "last_name"):
        v = get(f)
        if not v and not is_update:
            errors.append(f"{f} is required")
        elif v:
            if len(v) > 60:
                errors.append(f"{f} max 60 chars")
            elif not _valid_name(v):
                errors.append(f"{f} contains invalid characters")
            cleaned[f] = v

    email = get("email")
    if not email and not is_update:
        errors.append("email is required")
    elif email:
        if len(email) > 120:
            errors.append("email max 120 chars")
        elif not EMAIL_RE.match(email):
            errors.append(f"email {email!r} is not valid")
        cleaned["email"] = email.lower()

    phone = get("phone")
    if phone:
        digits = re.sub(r"\D", "", phone)
        if not PHONE_RE.match(phone) or not (6 <= len(digits) <= 15):
            errors.append("phone must have 6-15 digits, e.g. 123-456 or +63-912-345-6789")
        cleaned["phone"] = phone
    elif "phone" in data:
        cleaned["phone"] = ""

    dob = get("date_of_birth")
    if dob:
        d = _parse_iso(dob, "date_of_birth", errors)
        if d and d >= date.today():
            errors.append("date_of_birth must be in the past")
        cleaned["date_of_birth"] = dob
    elif "date_of_birth" in data:
        cleaned["date_of_birth"] = ""

    mtype = get("membership_type").upper() or MembershipType.REGULAR.value
    if mtype not in {m.value for m in MembershipType}:
        errors.append(f"membership_type must be one of {[m.value for m in MembershipType]}")
    cleaned["membership_type"] = mtype

    status = get("status").upper() or MemberStatus.ACTIVE.value
    if status not in {m.value for m in MemberStatus}:
        errors.append(f"status must be one of {[m.value for m in MemberStatus]}")
    cleaned["status"] = status

    join = get("join_date")
    if not join and not is_update:
        errors.append("join_date is required (YYYY-MM-DD)")
    elif join:
        d = _parse_iso(join, "join_date", errors)
        if d and d > date.today():
            errors.append("join_date cannot be in the future")
        cleaned["join_date"] = join

    for f in ("address", "notes"):
        if f in data:
            v = get(f)
            if len(v) > 500:
                errors.append(f"{f} max 500 chars")
            cleaned[f] = v

    if errors:
        raise ValidationError(errors)
    return cleaned
