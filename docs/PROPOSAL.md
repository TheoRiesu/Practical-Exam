# Membership Lookup and Registry — System Proposal

## A. Scenario / Real-world problem
A local community organization (barangay association / alumni / cooperative) keeps
its membership list in a spreadsheet + paper logbook. Lookups ("Is member M-0042
active? What is their contact?") take minutes, duplicates happen (same email twice),
and there is no validation (mistyped emails, future join dates, inconsistent status
labels like "active" vs "Active" vs "ACTV").

## Proposed solution
**Membership Lookup and Registry**: a Python-based, CLI/TUI, highly modular app
with a persistent SQLite database (same file format as Prisma + better-sqlite3 —
see `prisma/schema.prisma`, so the Node/Prisma toolchain can read the same
`data/membership.db`).

## B. Requirements gathering
- Stakeholders: membership coordinator, secretary, treasurer (read-only lookup).
- Current pain: slow manual search, no validation, no audit of status changes.
- Constraints: must run offline on a shared office PC, no server, single file DB.

### Functional requirements
1. Register / edit / delete members with validated fields.
2. **Search function**: partial, case-insensitive, across code / name / email / phone,
   with optional status filter.
3. **Data validation**: code format M-XXXX, email regex, phone digit count,
   ISO dates, past birthdate, non-future join date, enum type/status, length caps,
   unique code + email (case-insensitive).
4. Status lifecycle: ACTIVE / INACTIVE / SUSPENDED / EXPIRED.
5. List + statistics (counts by status).
6. Seed script for demo/sample data.

### Non-functional requirements
1. Offline-first, stdlib-only (zero-install `python3` run).
2. **User-friendly interface**: menu-driven TUI, tabulated output, confirmations.
3. Modularity: `config / db / models / validators / repository / service / ui / app`
   — each independently testable.
4. Persistence: SQLite file with indexes; WAL mode.
5. Testability: external `tests/test_edgecases.py` uses a **temporary DB**
   (`tempfile.TemporaryDirectory`) and never touches `data/membership.db`.
6. Interop: `prisma/schema.prisma` documents the same model for better-sqlite3.

## C. Minimum features traceability
| Requirement       | Implementation                          |
|-------------------|-----------------------------------------|
| Search Function   | `MemberRepository.search()` (exact + digit-normalized + fuzzy) + TUI opt 1 / `app.py search` / `make search q=...` |
| Fuzzy search      | `fuzzy_utils.py` (difflib ranking, cutoff 0.6) appended after exact hits; `--no-fuzzy` for strict |
| Data Validation   | `validators.py` + `service.py` guards   |
| User-Friendly UI  | `ui.py` menu + tables + `app.py` CLI; `app_textual.py` live table/mouse/sidebar/buttons |
| Persistent DB     | `db.py` SQLite + `prisma/schema.prisma` |
| Sample data       | `seed.py` (`make seed`)                 |
| Edge-case testing | `tests/test_edgecases.py` (temp DB) (`make test`) |
