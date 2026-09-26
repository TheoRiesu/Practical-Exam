"""Repository: raw CRUD + search queries against SQLite."""
from __future__ import annotations

import sqlite3
from typing import Any

from .phone_utils import digits_of, sqlite_digits_only
from .fuzzy_utils import (
    CANDIDATE_POOL,
    DEFAULT_CUTOFF,
    MIN_FUZZY_LEN,
    fuzzy_rank,
)


class MemberRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._ensure_digits_func()

    def _ensure_digits_func(self) -> None:
        """Register digits_only() on this connection (no-op if unsupported).

        get_connection() already registers it, but a repo can be handed any
        sqlite3 connection (e.g. in tests), so ensure it here too.
        """
        try:
            self.conn.create_function(
                "digits_only", 1, sqlite_digits_only, deterministic=True)
        except Exception:  # noqa: BLE001
            try:
                self.conn.create_function("digits_only", 1, sqlite_digits_only)
            except Exception:  # noqa: BLE001
                pass

    # ---------- helpers ----------
    def _next_code(self) -> str:
        cur = self.conn.execute(
            "SELECT member_code FROM members WHERE member_code GLOB 'M-[0-9]*'"
        )
        best = 0
        for (code,) in cur.fetchall():
            try:
                best = max(best, int(code.split("-", 1)[1]))
            except ValueError:
                continue
        return f"M-{best + 1:04d}"

    # ---------- CRUD ----------
    def create(self, row: dict[str, Any]) -> sqlite3.Row:
        row = dict(row)
        if not row.get("member_code"):
            row["member_code"] = self._next_code()
        try:
            cur = self.conn.execute(
                """INSERT INTO members
                (member_code, first_name, last_name, email, phone, date_of_birth,
                 membership_type, status, join_date, address, notes)
                VALUES (:member_code, :first_name, :last_name, :email, :phone,
                 :date_of_birth, :membership_type, :status, :join_date, :address, :notes)""",
                row,
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if "member_code" in msg:
                raise ValueError(f"member_code {row.get('member_code')} already exists")
            if "email" in msg:
                raise ValueError(f"email {row.get('email')} already exists")
            raise ValueError(f"database integrity error: {e}")
        return self.get_by_id(cur.lastrowid)

    def get_by_id(self, member_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM members WHERE id = ?", (member_id,)
        ).fetchone()

    def get_by_code(self, code: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM members WHERE member_code = ? COLLATE NOCASE",
            (code.strip(),),
        ).fetchone()

    def list_all(self, *, status: str | None = None, limit: int = 200) -> list[sqlite3.Row]:
        if status:
            return self.conn.execute(
                "SELECT * FROM members WHERE status = ? ORDER BY last_name, first_name LIMIT ?",
                (status.upper(), limit),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM members ORDER BY last_name, first_name LIMIT ?", (limit,)
        ).fetchall()

    def search(self, query: str, *, status: str | None = None, limit: int = 100,
               fuzzy: bool = True, cutoff: float = DEFAULT_CUTOFF) -> list[sqlite3.Row]:
        """Search function (minimum feature): code, name, email, phone — case-insensitive partial.

        Numbers are digit-normalized: a stored phone "123-456" matches queries
        "123-456", "123456", or substring "34". Display keeps dashes
        (see phone_utils.format_phone_display); search ignores them.

        With fuzzy=True (default), typo-tolerant matches (e.g. "Sntos" ->
        "Santos") are appended after exact hits. Pass fuzzy=False for
        strict LIKE-only matching.
        """
        raw = query.strip()
        q = f"%{raw.lower()}%"
        # dash/space-insensitive code match: "M0001" finds "M-0001"
        q_nodash = f"%{raw.lower().replace('-', '').replace(' ', '')}%"
        q_digits = digits_of(raw)
        sql = """SELECT * FROM members
                 WHERE (lower(member_code) LIKE :q
                    OR REPLACE(REPLACE(lower(member_code), '-', ''), ' ', '') LIKE :qn
                    OR lower(first_name) LIKE :q
                    OR lower(last_name) LIKE :q OR lower(first_name || ' ' || last_name) LIKE :q
                    OR lower(email) LIKE :q OR lower(COALESCE(phone,'')) LIKE :q"""
        params: dict[str, Any] = {"q": q, "qn": q_nodash}
        if q_digits:
            sql += (" OR digits_only(COALESCE(phone,'')) LIKE :qd"
                    " OR digits_only(member_code) LIKE :qd")
            params["qd"] = f"%{q_digits}%"
        sql += ")"
        if status:
            sql += " AND status = :status"
            params["status"] = status.upper()
        sql += " ORDER BY last_name, first_name LIMIT :limit"
        params["limit"] = limit
        exact = self.conn.execute(sql, params).fetchall()
        if not fuzzy or len(raw) < MIN_FUZZY_LEN or len(exact) >= limit:
            return exact
        seen = {r["id"] for r in exact}
        pool = [r for r in self.list_all(status=status, limit=CANDIDATE_POOL)
                if r["id"] not in seen]
        extra = [r for _, r in fuzzy_rank(raw, pool, cutoff=cutoff,
                                          limit=limit - len(exact))]
        return [*exact, *extra]

    def update(self, member_id: int, patch: dict[str, Any]) -> sqlite3.Row | None:
        allowed = {"first_name", "last_name", "email", "phone", "date_of_birth",
                   "membership_type", "status", "join_date", "address", "notes", "member_code"}
        cols = {k: v for k, v in patch.items() if k in allowed}
        if not cols:
            return self.get_by_id(member_id)
        cols["updated_at"] = "datetime('now')"
        set_clause = ", ".join(
            f"{k} = :{k}" if k != "updated_at" else "updated_at = datetime('now')" for k in cols if k != "updated_at"
        )
        try:
            self.conn.execute(
                f"UPDATE members SET {set_clause}, updated_at = datetime('now') WHERE id = :id",
                {**cols, "id": member_id},
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"update violates uniqueness: {e}")
        return self.get_by_id(member_id)

    def delete(self, member_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def count_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) c FROM members GROUP BY status"
        ).fetchall()
        return {r["status"]: r["c"] for r in rows}

    def count_total(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
