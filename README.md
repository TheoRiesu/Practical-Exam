# Membership Lookup and Registry

Python-based CLI/TUI, highly modular, persistent SQLite DB (file-compatible with
Prisma + better-sqlite3 — see `prisma/schema.prisma`).

Two interfaces share the same service/repository/validators:
- **Classic CLI/TUI** (`app.py`) — stdlib only, menu loop, zero-install.
- **Interactive TUI** (`app_textual.py`) — live table, mouse clicks, sidebar stats, buttons, auto-refresh (requires venv + Textual).

```
Practical-Exam/
├── .venv/                        # local virtual env (created by you, gitignored)
├── Makefile                      # short commands: make setup|seed|app|tui|search|list|test
├── prisma/schema.prisma          # Prisma model (better-sqlite3, file:./data/membership.db)
├── src/membership_registry/
│   ├── config.py                 # DB path resolution ($MEMBERSHIP_DB override)
│   ├── db.py                     # SQLite persistence + schema/indexes (WAL) + digits_only()
│   ├── models.py                 # Member dataclass + enums (mirrors Prisma)
│   ├── validators.py             # Data Validation (min. feature)
│   ├── repository.py             # CRUD + Search Function (min. feature: exact+digit+fuzzy)
│   ├── fuzzy_utils.py            # typo-tolerant ranking (difflib, stdlib-only)
│   ├── phone_utils.py            # digit-normalized search + dash-formatted display
│   ├── service.py                # business rules (validation → repo)
│   ├── ui.py                     # classic menu UI (User-Friendly Interface)
│   ├── app.py                    # entrypoint: classic interactive TUI + subcommands
│   ├── app_textual.py            # entrypoint: interactive Textual TUI (live table/mouse/sidebar)
│   └── seed.py                   # sample-entry generator into the DB
├── tests/test_edgecases.py       # external edge-case tests on a TEMPORARY db
├── requirements.txt              # textual (only needed for app_textual.py)
└── docs/PROPOSAL.md              # scenario, functional/non-functional reqs
```

## 1b. Short commands (npm-run style, no venv activation needed)

```bash
make help                 # list all commands
make setup                # create .venv + install requirements
make seed                 # seed 12 samples (N=20 for 20, RESET=1 to wipe first)
make app                  # classic menu CLI/TUI
make tui                  # interactive Textual TUI
make list                 # list members (STATUS=ACTIVE to filter)
make search q=Sntos       # fuzzy search (EXACT=1 for strict, STATUS=ACTIVE to filter)
make test                 # edge-case tests (temp DB only)
```

All `make` targets call `.venv/bin/python` directly. Windows PowerShell
equivalent: replace `make X` with `.venv\Scripts\python.exe <same args>`
(see commands in sections 2–5).

## 1. Setup — create and use venv (required for interactive TUI, recommended for all)

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

> Keep the venv activated for every command below (prompt shows `(.venv)`).
> The classic CLI (`app.py`), seed script, and tests also run fine on system
> Python without a venv, but **use the venv so everyone runs the same deps**.
> Never commit `.venv/` — it is already in `.gitignore`.

Verify install:
```bash
python -c "import textual; print(textual.__version__)"
```

## 2. Seed sample entries (persistent DB)

```bash
# venv activated
python src/membership_registry/seed.py --count 12          # first run
python src/membership_registry/seed.py --count 5           # add more (skips dup emails)
python src/membership_registry/seed.py --count 12 --reset  # wipe + reseed
```

## 3. Run — classic CLI (stdlib, no Textual needed)

```bash
python src/membership_registry/app.py
python src/membership_registry/app.py list --limit 5
python src/membership_registry/app.py search Sntos            # fuzzy: finds "Santos"
python src/membership_registry/app.py search Sntos --no-fuzzy # strict: no match
python src/membership_registry/app.py search 9418629830       # digits find "+63-941-862-9830"
python src/membership_registry/app.py add --first-name Ana --last-name Cruz \
  --email ana.cruz@example.org --join-date 2024-05-01
```

## 4. Run — interactive Textual TUI (needs venv)

```bash
# venv activated
python src/membership_registry/app_textual.py
python src/membership_registry/app_textual.py --db /tmp/x.db
```

What you get:
- **Table auto-loads** on launch; narrows **live as you type** in search (+ status dropdown).
- **Single-click** a row → detail pane in sidebar updates.
- **Double-click** a row → detail modal (with Edit shortcut).
- **Right-click** a row (or press `m`) → quick-action menu: View / Edit / Cycle status / Delete.
- **Sidebar** → live statistics (total + counts by status) and selected-member details.
- **Buttons** → `+ Add`, `Edit selected`, `Cycle status`, `Delete selected`, `Refresh`; keys `n/r/m/q` work too.
- **Everything updates**: every add/edit/status/delete ends in `refresh_all()` (table + stats + detail).

Mouse note: right-click needs a terminal with mouse-reporting enabled
(Terminal.app, iTerm2, Windows Terminal, VS Code terminal all work; over plain
SSH it depends on the client — `m` key is the fallback).

## 5. Tests (temporary DB only — main DB untouched)

```bash
# venv activated (or system python — tests are stdlib-only)
python -m unittest discover -s tests -v
python tests/test_edgecases.py
```

Custom DB location: `python src/membership_registry/app.py --db /tmp/x.db`
or `MEMBERSHIP_DB=/tmp/x.db python src/membership_registry/app.py`
(same `--db` flag exists on `app_textual.py` and `seed.py`).

## Prisma / better-sqlite3 note
`prisma/schema.prisma` declares `datasource db { provider = "sqlite" }`, which is
what `better-sqlite3` uses. The Python app writes plain SQLite to the same path
(`data/membership.db`), so `npx prisma studio` / any better-sqlite3 script can
open the seeded file directly — persistent database shared across stacks.
