"""Text-based TUI: menus, tables, prompts. No third-party deps."""
from __future__ import annotations

import sqlite3

from .phone_utils import format_phone_display
from .validators import ValidationError

MENU = """
╔══════════════════════════════════════════╗
║   MEMBERSHIP LOOKUP & REGISTRY           ║
╠══════════════════════════════════════════╣
║ 1. Search members                        ║
║ 2. List all members                      ║
║ 3. View member details                   ║
║ 4. Register new member                   ║
║ 5. Edit member                           ║
║ 6. Change status (activate/suspend/...)  ║
║ 7. Delete member                         ║
║ 8. Statistics                            ║
║ 0. Exit                                  ║
╚══════════════════════════════════════════╝
"""

COLS = ["id", "member_code", "first_name", "last_name", "email",
        "phone", "membership_type", "status", "join_date"]


def _cell(v) -> str:
    return "" if v is None else str(v)


def _display_cell(col: str, v) -> str:
    """Display formatting: phones render with dashes, everything else raw."""
    if col == "phone":
        return format_phone_display("" if v is None else str(v))
    return _cell(v)


def print_table(rows: list[sqlite3.Row], cols: list[str] | None = None) -> None:
    cols = cols or COLS
    if not rows:
        print("  (no records found)")
        return
    widths = {c: max(len(c), max(len(_display_cell(c, r[c])) for r in rows)) for c in cols}
    header = " | ".join(c.upper().ljust(widths[c]) for c in cols)
    print("  " + header)
    print("  " + "-+-".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  " + " | ".join(_display_cell(c, r[c]).ljust(widths[c]) for c in cols))
    print(f"  ({len(rows)} record(s))")


def print_detail(row: sqlite3.Row) -> None:
    print("\n── Member details ──────────────────────")
    for k in row.keys():
        print(f"  {k:16}: {_display_cell(k, row[k])}")
    print("────────────────────────────────────────")


def prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    v = input(f"{msg}{suffix}: ").strip()
    return v if v != "" else default


def prompt_member_form(existing: dict | None = None) -> dict:
    e = existing or {}
    print("\nEnter member data (leave blank to keep existing on edit):")
    return {
        "first_name": prompt("First name", str(e.get("first_name", ""))),
        "last_name": prompt("Last name", str(e.get("last_name", ""))),
        "email": prompt("Email", str(e.get("email", "") or "")),
        "phone": prompt("Phone", str(e.get("phone", "") or "")),
        "date_of_birth": prompt("Birthdate YYYY-MM-DD", str(e.get("date_of_birth", "") or "")),
        "membership_type": prompt("Type REGULAR/STUDENT/SENIOR/HONORARY/ASSOCIATE",
                                  str(e.get("membership_type", "REGULAR"))),
        "status": prompt("Status ACTIVE/INACTIVE/SUSPENDED/EXPIRED",
                         str(e.get("status", "ACTIVE"))),
        "join_date": prompt("Join date YYYY-MM-DD", str(e.get("join_date", "") or "")),
        "address": prompt("Address", str(e.get("address", "") or "")),
        "notes": prompt("Notes", str(e.get("notes", "") or "")),
    }


def show_error(e: Exception) -> None:
    if isinstance(e, ValidationError):
        print("✖ Validation failed:")
        for m in e.errors:
            print(f"   - {m}")
    else:
        print(f"✖ Error: {e}")
