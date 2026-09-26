"""CLI entrypoint: interactive TUI + non-interactive subcommands."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from membership_registry.config import resolve_db_path  # noqa: E402
from membership_registry.db import get_connection, init_db  # noqa: E402
from membership_registry.repository import MemberRepository  # noqa: E402
from membership_registry.service import MemberService  # noqa: E402
from membership_registry.ui import (  # noqa: E402
    MENU, print_detail, print_table, prompt, prompt_member_form, show_error,
)


def build_service(db: str | None) -> tuple[MemberService, Path]:
    path = init_db(db)
    conn = get_connection(path)
    return MemberService(MemberRepository(conn)), path


def cmd_search(svc: MemberService, args: argparse.Namespace) -> None:
    rows = svc.lookup(args.query, status=args.status, limit=args.limit,
                      fuzzy=not args.no_fuzzy)
    print_table(rows)


def cmd_list(svc: MemberService, args: argparse.Namespace) -> None:
    print_table(svc.repo.list_all(status=args.status, limit=args.limit))


def cmd_add(svc: MemberService, args: argparse.Namespace) -> None:
    data = {k: v for k, v in vars(args).items()
            if k in ("first_name", "last_name", "email", "phone", "date_of_birth",
                     "membership_type", "status", "join_date", "address", "notes") and v}
    try:
        print_detail(svc.register(data))
    except Exception as e:  # noqa: BLE001
        show_error(e)
        raise SystemExit(1)


def run_interactive(svc: MemberService) -> None:
    print("Membership Lookup & Registry — offline-first, SQLite-backed.")
    while True:
        print(MENU)
        choice = prompt("Choose").strip()
        try:
            if choice == "1":
                q = prompt("Search (code/name/email/phone)")
                if q:
                    print_table(svc.lookup(q))
            elif choice == "2":
                f = prompt("Filter status (blank=all)")
                print_table(svc.repo.list_all(status=f or None))
            elif choice == "3":
                key = prompt("Member code or numeric id")
                row = (svc.repo.get_by_id(int(key)) if key.isdigit()
                       else svc.repo.get_by_code(key))
                print_detail(row) if row else print("  Not found.")
            elif choice == "4":
                print_detail(svc.register(prompt_member_form()))
                print("✔ Member registered.")
            elif choice == "5":
                key = prompt("Member code or id to edit")
                row = (svc.repo.get_by_id(int(key)) if key.isdigit()
                       else svc.repo.get_by_code(key))
                if not row:
                    print("  Not found.")
                    continue
                updated = svc.edit(row["id"], prompt_member_form(dict(row)))
                print_detail(updated)
                print("✔ Member updated.")
            elif choice == "6":
                key = prompt("Member code or id")
                row = (svc.repo.get_by_id(int(key)) if key.isdigit()
                       else svc.repo.get_by_code(key))
                if not row:
                    print("  Not found.")
                    continue
                st = prompt("New status", str(row["status"]))
                print_detail(svc.set_status(row["id"], st))
                print("✔ Status updated.")
            elif choice == "7":
                key = prompt("Member code or id to DELETE")
                row = (svc.repo.get_by_id(int(key)) if key.isdigit()
                       else svc.repo.get_by_code(key))
                if not row:
                    print("  Not found.")
                    continue
                print_detail(row)
                if prompt("Type DELETE to confirm").strip() == "DELETE":
                    print("✔ Deleted." if svc.repo.delete(row["id"]) else "  Not deleted.")
            elif choice == "8":
                print(f"  Total: {svc.repo.count_total()}")
                for s, c in svc.repo.count_by_status().items():
                    print(f"  {s:10}: {c}")
            elif choice == "0":
                print("Goodbye.")
                break
            else:
                print("  Invalid choice, try 0-8.")
        except Exception as e:  # noqa: BLE001
            show_error(e)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Membership Lookup and Registry (CLI/TUI)")
    p.add_argument("--db", default=None, help="SQLite file (default ./data/membership.db or $MEMBERSHIP_DB)")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("search", help="Search members (exact + typo-tolerant fuzzy)")
    s.add_argument("query")
    s.add_argument("--status", default=None)
    s.add_argument("--limit", type=int, default=100)
    s.add_argument("--no-fuzzy", action="store_true", help="strict LIKE-only matching")

    li = sub.add_parser("list", help="List members")
    li.add_argument("--status", default=None)
    li.add_argument("--limit", type=int, default=200)

    a = sub.add_parser("add", help="Register member non-interactively")
    for f in ("first_name", "last_name", "email", "phone", "date_of_birth",
              "membership_type", "status", "join_date", "address", "notes"):
        a.add_argument(f"--{f.replace('_', '-')}", dest=f, default=None)

    args = p.parse_args(argv)
    svc, path = build_service(args.db)
    print(f"[db] {path}")
    if args.cmd == "search":
        cmd_search(svc, args)
    elif args.cmd == "list":
        cmd_list(svc, args)
    elif args.cmd == "add":
        cmd_add(svc, args)
    else:
        run_interactive(svc)


if __name__ == "__main__":
    main()
