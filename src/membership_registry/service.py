"""Service layer: validation + business rules on top of repository."""
from __future__ import annotations

import sqlite3

from .repository import MemberRepository
from .validators import validate_member_data

DB_COLS = ("member_code", "first_name", "last_name", "email", "phone",
           "date_of_birth", "membership_type", "status", "join_date",
           "address", "notes")


class MemberService:
    def __init__(self, repo: MemberRepository):
        self.repo = repo

    def register(self, data: dict) -> sqlite3.Row:
        cleaned = validate_member_data(data)
        row = {k: cleaned.get(k) or None for k in DB_COLS}
        # keep empty code as "" so repo auto-assigns
        if not cleaned.get("member_code"):
            row["member_code"] = ""
        return self.repo.create(row)

    def edit(self, member_id: int, data: dict) -> sqlite3.Row | None:
        cleaned = validate_member_data(data, is_update=True)
        patch = {k: (cleaned[k] if cleaned[k] != "" else None)
                 for k in DB_COLS if k in cleaned}
        return self.repo.update(member_id, patch)

    def lookup(self, query: str, **kw) -> list[sqlite3.Row]:
        return self.repo.search(query, **kw)

    def set_status(self, member_id: int, status: str) -> sqlite3.Row | None:
        cleaned = validate_member_data({"status": status}, is_update=True)
        return self.repo.update(member_id, {"status": cleaned["status"]})
