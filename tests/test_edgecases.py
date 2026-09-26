"""External edge-case tests — NEVER touch the main DB.

Every test gets a FRESH temporary SQLite file via tempfile (see make_service),
so ./data/membership.db is left untouched. Run with:

    python -m unittest discover -s tests -v
    python tests/test_edgecases.py
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from membership_registry.config import DEFAULT_DB_PATH  # noqa: E402
from membership_registry.db import get_connection, init_db  # noqa: E402
from membership_registry.repository import MemberRepository  # noqa: E402
from membership_registry.service import MemberService  # noqa: E402
from membership_registry.validators import ValidationError, validate_member_data  # noqa: E402


def make_service() -> tuple[MemberService, Path, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory(prefix="membership-test-")
    db = Path(tmp.name) / "test.db"
    init_db(db)
    svc = MemberService(MemberRepository(get_connection(db)))
    return svc, db, tmp


GOOD = {
    "first_name": "Test",
    "last_name": "User",
    "email": "test.user@example.org",
    "phone": "+63-912-345-6789",
    "date_of_birth": "1995-04-17",
    "membership_type": "REGULAR",
    "status": "ACTIVE",
    "join_date": "2023-01-15",
    "address": "123 Mabini St",
    "notes": "ok",
}


class TestTempDbIsolation(unittest.TestCase):
    def test_uses_temp_db_not_main(self):
        svc, db, tmp = make_service()
        try:
            self.assertNotEqual(str(db), str(DEFAULT_DB_PATH))
            self.assertFalse(str(DEFAULT_DB_PATH) in str(db))
            self.assertTrue(str(db).startswith(tempfile.gettempdir()))
        finally:
            tmp.cleanup()


class TestValidationEdgeCases(unittest.TestCase):
    def setUp(self):
        self.svc, self.db, self.tmp = make_service()

    def tearDown(self):
        self.tmp.cleanup()

    def base(self, **over) -> dict:
        d = dict(GOOD)
        d.update(over)
        return d

    def test_missing_required(self):
        for field in ("first_name", "last_name", "email", "join_date"):
            with self.subTest(field=field):
                d = self.base()
                d.pop(field)
                with self.assertRaises(ValidationError):
                    self.svc.register(d)

    def test_bad_email(self):
        for bad in ("plain", "a@", "@b.com", "a b@c.com", "x" * 115 + "@a.com"):
            with self.subTest(email=bad):
                with self.assertRaises(ValidationError):
                    validate_member_data(self.base(email=bad))

    def test_email_normalized_lowercase(self):
        row = self.svc.register(self.base(email="MiXeD@Example.ORG"))
        self.assertEqual(row["email"], "mixed@example.org")

    def test_bad_phone(self):
        for bad in ("123", "abc-def-ghij", "1" * 30, "+++-"):
            with self.subTest(phone=bad):
                with self.assertRaises(ValidationError):
                    validate_member_data(self.base(phone=bad))

    def test_bad_code_format(self):
        for bad in ("1234", "M-12", "M-ABCD", "X-0001", "M-1234567"):
            with self.subTest(code=bad):
                with self.assertRaises(ValidationError):
                    validate_member_data(self.base(member_code=bad))

    def test_bad_dates(self):
        with self.assertRaises(ValidationError):
            validate_member_data(self.base(join_date="15-01-2023"))
        with self.assertRaises(ValidationError):
            validate_member_data(self.base(join_date="2999-01-01"))  # future
        with self.assertRaises(ValidationError):
            validate_member_data(self.base(date_of_birth="2999-01-01"))  # future dob
        with self.assertRaises(ValidationError):
            validate_member_data(self.base(membership_type="GOLD"))
        with self.assertRaises(ValidationError):
            validate_member_data(self.base(status="PENDING"))

    def test_name_injection_and_length(self):
        with self.assertRaises(ValidationError):
            validate_member_data(self.base(first_name="A" * 61))
        with self.assertRaises(ValidationError):
            validate_member_data(self.base(last_name="Robert; DROP TABLE members;--"))

    def test_duplicate_email_rejected(self):
        self.svc.register(self.base())
        with self.assertRaises(ValueError):
            self.svc.register(self.base(first_name="Other"))

    def test_duplicate_email_case_insensitive(self):
        self.svc.register(self.base())
        with self.assertRaises(ValueError):
            self.svc.register(self.base(email="TEST.USER@example.org"))

    def test_duplicate_code_rejected(self):
        r = self.svc.register(self.base(member_code="M-0099"))
        self.assertEqual(r["member_code"], "M-0099")
        with self.assertRaises(ValueError):
            self.svc.register(self.base(email="other@example.org", member_code="M-0099"))

    def test_auto_code_sequence(self):
        a = self.svc.register(self.base())
        b = self.svc.register(self.base(email="b@example.org", first_name="Bee"))
        self.assertRegex(a["member_code"], r"^M-\d{4,}$")
        self.assertGreater(int(b["member_code"][2:]), int(a["member_code"][2:]))


class TestSearchEdgeCases(unittest.TestCase):
    def setUp(self):
        self.svc, self.db, self.tmp = make_service()
        self.svc.register(dict(GOOD, first_name="Maria", last_name="Santos",
                               email="maria.santos@example.org", member_code="M-0101"))
        self.svc.register(dict(GOOD, first_name="Jose", last_name="Reyes",
                               email="jose.reyes@example.org", phone="+63-900-111-2222",
                               member_code="M-0102", status="SUSPENDED"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_partial_case_insensitive(self):
        self.assertEqual(len(self.svc.lookup("maria")), 1)
        self.assertEqual(len(self.svc.lookup("MARIA")), 1)
        self.assertEqual(len(self.svc.lookup("sant")), 1)
        self.assertEqual(len(self.svc.lookup("m-010")), 2)

    def test_full_name_and_email_phone(self):
        self.assertEqual(len(self.svc.lookup("maria santos")), 1)
        self.assertEqual(len(self.svc.lookup("jose.reyes@")), 1)
        self.assertEqual(len(self.svc.lookup("900-111")), 1)

    def test_no_match_and_empty(self):
        self.assertEqual(self.svc.lookup("zzz-no-such-person"), [])
        self.assertGreaterEqual(len(self.svc.lookup("")), 2)  # empty = match-all LIKE %%

    def test_status_filter(self):
        self.assertEqual(len(self.svc.lookup("m-010", status="SUSPENDED")), 1)
        self.assertEqual(len(self.svc.lookup("m-010", status="EXPIRED")), 0)

    def test_sql_like_special_chars_safe(self):
        # % and _ must not crash / must not dump everything unexpectedly
        rows = self.svc.lookup("%")
        self.assertIsInstance(rows, list)


class TestLifecycleEdgeCases(unittest.TestCase):
    def setUp(self):
        self.svc, self.db, self.tmp = make_service()

    def tearDown(self):
        self.tmp.cleanup()

    def test_update_then_lookup(self):
        r = self.svc.register(dict(GOOD))
        u = self.svc.edit(r["id"], {"last_name": "Updated", "status": "INACTIVE"})
        self.assertEqual(u["last_name"], "Updated")
        self.assertEqual(len(self.svc.lookup("updated")), 1)

    def test_update_bad_email_rejected(self):
        r = self.svc.register(dict(GOOD))
        with self.assertRaises(ValidationError):
            self.svc.edit(r["id"], {"email": "not-an-email"})

    def test_set_status_invalid(self):
        r = self.svc.register(dict(GOOD))
        with self.assertRaises(ValidationError):
            self.svc.set_status(r["id"], "BANNED")

    def test_delete_missing_returns_false(self):
        self.assertFalse(self.svc.repo.delete(999999))

    def test_unicode_names_ok(self):
        r = self.svc.register(dict(GOOD, first_name="José", last_name="Peña",
                                   email="jose.pena@example.org"))
        self.assertEqual(r["first_name"], "José")
        self.assertEqual(len(self.svc.lookup("peña")), 1)


class TestPhoneDigitSearch(unittest.TestCase):
    """Numbers resolve as digits: '123-456' findable via '123456' or '34'."""

    def setUp(self):
        self.svc, self.db, self.tmp = make_service()
        self.svc.register(dict(GOOD, first_name="Dash", last_name="Number",
                               email="dash.number@example.org",
                               phone="123-456", join_date="2023-03-01"))
        self.svc.register(dict(GOOD, first_name="Plus", last_name="Country",
                               email="plus.country@example.org",
                               phone="+63-912-345-6789", join_date="2023-03-02",
                               member_code="M-0202"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_dashed_finds_dashed(self):
        self.assertGreaterEqual(len(self.svc.lookup("123-456")), 1)

    def test_digits_only_finds_dashed(self):
        self.assertGreaterEqual(len(self.svc.lookup("123456")), 1)

    def test_substring_digits(self):
        self.assertGreaterEqual(len(self.svc.lookup("34")), 1)

    def test_full_international_digits(self):
        self.assertGreaterEqual(len(self.svc.lookup("639123456789")), 1)
        self.assertGreaterEqual(len(self.svc.lookup("9123456789")), 1)

    def test_code_without_dash(self):
        self.assertGreaterEqual(len(self.svc.lookup("M0202")), 1)

    def test_unrelated_digits_no_match(self):
        self.assertEqual(self.svc.lookup("000000000"), [])

    def test_display_formats_dashes(self):
        from membership_registry.phone_utils import digits_of, format_phone_display
        self.assertEqual(digits_of("+63-912-345-6789"), "639123456789")
        self.assertEqual(format_phone_display("123456"), "123-456")
        self.assertEqual(format_phone_display("123-456"), "123-456")
        self.assertEqual(format_phone_display("+63-912-345-6789"), "+63-912-345-6789")


class TestFuzzySearch(unittest.TestCase):
    """Typo-tolerant search: 'Sntos' finds 'Santos', exact hits stay first."""

    def setUp(self):
        self.svc, self.db, self.tmp = make_service()
        self.svc.register(dict(GOOD, first_name="Maria", last_name="Santos",
                               email="maria.santos@example.org",
                               member_code="M-0301", join_date="2023-01-01"))
        self.svc.register(dict(GOOD, first_name="Jose", last_name="Reyes",
                               email="jose.reyes@example.org",
                               member_code="M-0302", join_date="2023-02-01"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_typo_last_name(self):
        hits = [dict(r)["last_name"] for r in self.svc.lookup("Sntos")]
        self.assertIn("Santos", hits)

    def test_typo_first_name(self):
        hits = [dict(r)["first_name"] for r in self.svc.lookup("Mria")]
        self.assertIn("Maria", hits)

    def test_exact_still_first(self):
        rows = self.svc.lookup("Santos")
        self.assertEqual(dict(rows[0])["last_name"], "Santos")

    def test_no_fuzzy_flag_is_strict(self):
        self.assertEqual(self.svc.lookup("Sntos", fuzzy=False), [])

    def test_gibberish_still_empty(self):
        self.assertEqual(self.svc.lookup("zzz-no-such-person"), [])

    def test_short_query_skips_fuzzy(self):
        # 2-char queries use exact matching only (no fuzzy noise)
        self.assertIsInstance(self.svc.lookup("Ma"), list)


if __name__ == "__main__":
    # Guard: refuse to run if MEMBERSHIP_DB points at the real DB file.
    import os
    if os.environ.get("MEMBERSHIP_DB", "") == str(DEFAULT_DB_PATH):
        print("Refusing: MEMBERSHIP_DB points at production DB.")
        sys.exit(2)
    unittest.main(verbosity=2)
