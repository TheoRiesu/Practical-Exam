"""Seed script: generates sample entries in the (persistent) DB.

Usage:
    python -m membership_registry.seed [--db PATH] [--count N] [--reset]
    python src/membership_registry/seed.py --count 12

--reset drops existing rows first. Idempotent-ish without --reset (skips
duplicate emails/codes).
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from membership_registry.db import get_connection, init_db  # noqa: E402
from membership_registry.repository import MemberRepository  # noqa: E402
from membership_registry.service import MemberService  # noqa: E402
from membership_registry.validators import ValidationError  # noqa: E402

FIRST = ["Maria", "Jose", "Ana", "Ramon", "Liza", "Mark", "Jenny", "Paolo",
         "Rosa", "Daniel", "Grace", "Kevin", "Sofia", "Miguel", "Aya"]
LAST = ["Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza",
        "Torres", "Tomas", "Andrada", "Castillo", "Flores", "Villanueva", "Ramos"]
TYPES = ["REGULAR", "STUDENT", "SENIOR", "HONORARY", "ASSOCIATE"]
STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE", "SUSPENDED", "EXPIRED"]
STREETS = ["Mabini St", "Rizal Ave", "Bonifacio Rd", "Luna St", "Kalayaan Ave"]


def sample(i: int, rng: random.Random) -> dict:
    fn, ln = rng.choice(FIRST), rng.choice(LAST)
    return {
        "first_name": fn,
        "last_name": ln,
        "email": f"{fn.lower()}.{ln.lower()}{i}@example.org",
        "phone": f"+63-9{rng.randint(10, 99)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
        "date_of_birth": f"{rng.randint(1960, 2005)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        "membership_type": rng.choice(TYPES),
        "status": rng.choice(STATUSES),
        "join_date": f"{rng.randint(2018, 2026)}-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}",
        "address": f"{rng.randint(1, 999)} {rng.choice(STREETS)}, Manila",
        "notes": "seeded sample",
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=None)
    p.add_argument("--count", type=int, default=12)
    p.add_argument("--reset", action="store_true", help="delete existing rows first")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    path = init_db(args.db)
    conn = get_connection(path)
    if args.reset:
        conn.execute("DELETE FROM members")
        conn.commit()
    svc = MemberService(MemberRepository(conn))
    rng = random.Random(args.seed)
    ok, skipped = 0, 0
    for i in range(1, args.count + 1):
        try:
            svc.register(sample(i, rng))
            ok += 1
        except (ValidationError, ValueError) as e:
            skipped += 1
            print(f"  skip #{i}: {e}")
    print(f"Seeded {ok} member(s) into {path} (skipped {skipped})")


if __name__ == "__main__":
    main()
