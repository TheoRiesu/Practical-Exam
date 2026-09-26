"""Interactive Textual TUI — live table, mouse, sidebar, buttons, auto-refresh.

Keeps the SAME service/repository/validators as the stdlib CLI, so all
validation + search + persistence rules are shared. Only this UI layer is new.

Features (vs stdlib app.py menu loop):
  - table auto-loads on mount + live-refreshes as you type in search
  - single-click row  -> detail pane updates in sidebar
  - double-click row  -> opens detail/edit modal
  - right-click row   -> opens quick-action menu (view/edit/status/delete)
  - sidebar           -> live statistics + selected-member detail
  - buttons           -> Add / Edit / Status / Delete / Refresh (no typing menus)
  - everything re-renders after any mutation via refresh_all()

Run (inside venv, see README):
    python src/membership_registry/app_textual.py
    python src/membership_registry/app_textual.py --db /tmp/x.db
    python -m membership_registry.app_textual   (with src on PYTHONPATH)

Requires: pip install -r requirements.txt  (textual)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.events import Click
    from textual.screen import ModalScreen
    from textual.widgets import (
        Button,
        DataTable,
        Footer,
        Header,
        Input,
        Label,
        Select,
        Static,
    )
except ImportError:  # friendly error when venv not activated
    print("Textual is not installed. Activate venv and run:  pip install -r requirements.txt")
    raise SystemExit(1)

from membership_registry.config import resolve_db_path  # noqa: E402
from membership_registry.db import get_connection, init_db  # noqa: E402
from membership_registry.phone_utils import format_phone_display  # noqa: E402
from membership_registry.repository import MemberRepository  # noqa: E402
from membership_registry.service import MemberService  # noqa: E402
from membership_registry.validators import ValidationError  # noqa: E402

TABLE_COLS = ["Code", "First", "Last", "Email", "Phone", "Type", "Status", "Joined"]
STATUS_OPTIONS = ["ALL", "ACTIVE", "INACTIVE", "SUSPENDED", "EXPIRED"]
STATUS_CYCLE = ["ACTIVE", "INACTIVE", "SUSPENDED", "EXPIRED"]


def row_to_list(r) -> list[str]:
    return [str(r["member_code"] or ""), str(r["first_name"] or ""),
            str(r["last_name"] or ""), str(r["email"] or ""),
            format_phone_display(r["phone"]), str(r["membership_type"] or ""),
            str(r["status"] or ""), str(r["join_date"] or "")]


# ---------------------------------------------------------------- modals

class MemberFormScreen(ModalScreen):
    """Add/Edit form. Dismisses with dict of fields, or None on cancel."""

    def __init__(self, existing: dict | None = None, title: str = "Register member"):
        super().__init__()
        self.existing = existing or {}
        self.form_title = title
        self.error_box: Static | None = None

    def compose(self) -> ComposeResult:
        e = self.existing
        with Vertical(id="form-box"):
            yield Label(self.form_title, id="form-title")
            yield Input(str(e.get("first_name", "")), placeholder="First name", id="f-first")
            yield Input(str(e.get("last_name", "")), placeholder="Last name", id="f-last")
            yield Input(str(e.get("email", "") or ""), placeholder="Email", id="f-email")
            yield Input(str(e.get("phone", "") or ""), placeholder="Phone +63-...", id="f-phone")
            yield Input(str(e.get("date_of_birth", "") or ""), placeholder="Birthdate YYYY-MM-DD", id="f-dob")
            yield Input(str(e.get("membership_type", "REGULAR")), placeholder="Type REGULAR/STUDENT/...", id="f-type")
            yield Input(str(e.get("status", "ACTIVE")), placeholder="Status ACTIVE/INACTIVE/...", id="f-status")
            yield Input(str(e.get("join_date", "") or ""), placeholder="Join date YYYY-MM-DD", id="f-join")
            yield Input(str(e.get("address", "") or ""), placeholder="Address", id="f-addr")
            yield Input(str(e.get("notes", "") or ""), placeholder="Notes", id="f-notes")
            yield Static("", id="form-error")
            with Horizontal(id="form-btns"):
                yield Button("Save", variant="primary", id="form-save")
                yield Button("Cancel", id="form-cancel")

    def _collect(self) -> dict:
        g = lambda i: self.query_one(f"#{i}", Input).value.strip()  # noqa: E731
        return {"first_name": g("f-first"), "last_name": g("f-last"),
                "email": g("f-email"), "phone": g("f-phone"),
                "date_of_birth": g("f-dob"), "membership_type": g("f-type"),
                "status": g("f-status"), "join_date": g("f-join"),
                "address": g("f-addr"), "notes": g("f-notes")}

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "form-save":
            self.dismiss(self._collect())
        else:
            self.dismiss(None)


class DetailScreen(ModalScreen):
    """Read-only detail; double-click target. Buttons: Edit / Close."""

    def __init__(self, row: dict):
        super().__init__()
        self.row = row

    def compose(self) -> ComposeResult:
        lines = "\n".join(f"{k:16}: {v or ''}" for k, v in self.row.items())
        with Vertical(id="detail-box"):
            yield Label(f"{self.row.get('member_code')} — {self.row.get('first_name')} {self.row.get('last_name')}",
                        id="detail-title")
            yield Static(lines, id="detail-body")
            with Horizontal(id="detail-btns"):
                yield Button("Edit", variant="primary", id="detail-edit")
                yield Button("Close", id="detail-close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss("edit" if event.button.id == "detail-edit" else None)


class ActionMenuScreen(ModalScreen):
    """Right-click quick-action menu for the selected row."""

    def __init__(self, code: str):
        super().__init__()
        self.code = code

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-box"):
            yield Label(f"Actions — {self.code}", id="menu-title")
            yield Button("View details", id="m-view")
            yield Button("Edit", id="m-edit")
            yield Button("Cycle status", id="m-status")
            yield Button("Delete", variant="error", id="m-delete")
            yield Button("Cancel", id="m-cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id if event.button.id != "m-cancel" else None)


# ---------------------------------------------------------------- main app

class MembershipApp(App):
    """Event-driven TUI. All mutations funnel through refresh_all()."""

    CSS = """
    #toolbar { height: 3; }
    #search { width: 1fr; }
    #status-filter { width: 22; }
    #btn-add { width: 12; }
    #main { height: 1fr; }
    #left { width: 70%; }
    #members { height: 1fr; }
    #hint { height: 2; color: $text-muted; }
    #sidebar { width: 30%; border-left: solid $primary; padding: 0 1; }
    #stats { height: auto; border: solid $primary; padding: 0 1; }
    #detail { height: 1fr; border: solid $primary; padding: 0 1; }
    #side-btns { height: auto; }
    #side-btns Button { width: 1fr; }  /* uniform width: longest label no longer sticks out */
    #form-box, #detail-box, #menu-box {
        width: 60; height: auto; padding: 1 2;
        border: solid $primary; background: $surface;
    }
    #form-error { color: $error; height: auto; }
    """

    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh"),
                ("n", "add", "Add"), ("m", "menu", "Menu (right-click)")]

    def __init__(self, svc: MemberService, **kw):
        super().__init__(**kw)
        self.svc = svc
        self.rows: list = []          # currently displayed sqlite Rows
        self.selected_id: int | None = None
        self._last_click_t: float = 0.0
        self._last_click_key = None

    # ----- layout -----
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="toolbar"):
            yield Input(placeholder="Search code / name / email / phone (live)…", id="search")
            yield Select([(s, s) for s in STATUS_OPTIONS], value="ALL", id="status-filter")
            yield Button("+ Add", variant="primary", id="btn-add")
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield DataTable(id="members", cursor_type="row", zebra_stripes=True)
                yield Static("click=select · double-click=details · right-click=actions · q=quit",
                             id="hint")
            with Vertical(id="sidebar"):
                yield Static("stats…", id="stats")
                yield Static("Select a row to see details.", id="detail")
                with Vertical(id="side-btns"):
                    yield Button("Edit selected", id="btn-edit")
                    yield Button("Cycle status", id="btn-status")
                    yield Button("Delete selected", variant="error", id="btn-delete")
                    yield Button("Refresh", id="btn-refresh")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#members", DataTable)
        for c in TABLE_COLS:
            table.add_column(c, key=c)
        self.refresh_all()                       # <-- table auto-loads here
        self.query_one("#search", Input).focus()

    # ----- central refresh: EVERY mutation ends here -----
    def refresh_all(self) -> None:
        self.refresh_table()
        self.refresh_sidebar()

    def _filter(self) -> tuple[str, str | None]:
        q = self.query_one("#search", Input).value
        s = self.query_one("#status-filter", Select).value
        return q, (None if s == "ALL" else str(s))

    def refresh_table(self) -> None:
        q, status = self._filter()
        try:
            rows = self.svc.lookup(q, status=status) if q.strip() else \
                self.svc.repo.list_all(status=status)
        except Exception as e:  # noqa: BLE001
            self.notify(f"Search failed: {e}", severity="error")
            return
        self.rows = rows
        table = self.query_one("#members", DataTable)
        table.clear()
        for r in rows:
            table.add_row(*row_to_list(r), key=str(r["id"]))
        # keep selection valid
        if self.selected_id is not None and all(r["id"] != self.selected_id for r in rows):
            self.selected_id = None

    def refresh_sidebar(self) -> None:
        total = self.svc.repo.count_total()
        by = self.svc.repo.count_by_status()
        stat_lines = [f"Total: {total}"] + [f"{k:10} {v}" for k, v in sorted(by.items())]
        shown = f" | showing {len(self.rows)} row(s)"
        self.query_one("#stats", Static).update(
            "[b]Statistics[/b]\n" + "\n".join(stat_lines) + f"\n{shown}")
        self._render_detail()

    def _render_detail(self) -> None:
        box = self.query_one("#detail", Static)
        if self.selected_id is None:
            box.update("[b]Details[/b]\nSelect a row to see details.")
            return
        r = self.svc.repo.get_by_id(self.selected_id)
        if r is None:
            box.update("[b]Details[/b]\n(record deleted)")
            return
        d = dict(r)
        box.update("[b]Details[/b]\n" + "\n".join(
            f"{k}: {d.get(k) or ''}" for k in
            ("member_code", "first_name", "last_name", "email", "phone",
             "membership_type", "status", "join_date", "address", "notes")))

    def _selected_row(self):
        if self.selected_id is None:
            return None
        return self.svc.repo.get_by_id(self.selected_id)

    # ----- live search / filter -----
    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.refresh_all()

    async def on_select_changed(self, event: Select.Changed) -> None:
        self.refresh_all()

    # ----- single / double click -----
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            self.selected_id = int(event.row_key.value)
        except (ValueError, AttributeError):
            return
        now = time.monotonic()
        double = (event.row_key == self._last_click_key and now - self._last_click_t < 0.4)
        self._last_click_t, self._last_click_key = now, event.row_key
        self._render_detail()
        if double:  # double-click -> detail modal
            await self.action_view()

    # ----- right click -> action menu -----
    async def on_click(self, event: Click) -> None:
        button = getattr(event, "button", 1)
        if button != 3:  # 3 == right button in Textual; anything non-left treated as menu only if != 1
            return
        if self.selected_id is None:
            self.notify("Select a row first (left-click), then right-click.", severity="warning")
            return
        # only trigger menu when the click is inside the table region
        try:
            table = self.query_one("#members", DataTable)
            if table.region.contains(event.screen_x, event.screen_y):
                await self.action_menu()
        except Exception:  # noqa: BLE001
            await self.action_menu()

    # ----- buttons / actions (all end with refresh_all) -----
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-add":
            await self.action_add()
        elif bid == "btn-edit":
            await self.action_edit()
        elif bid == "btn-status":
            await self.action_cycle_status()
        elif bid == "btn-delete":
            await self.action_delete()
        elif bid == "btn-refresh":
            self.refresh_all()
            self.notify("Refreshed.")

    async def action_refresh(self) -> None:
        self.refresh_all()

    async def action_add(self) -> None:
        def done(data: dict | None) -> None:
            if not data:
                return
            try:
                row = self.svc.register(data)
                self.selected_id = row["id"]
                self.notify(f"Registered {row['member_code']}.")
            except (ValidationError, ValueError) as e:
                self.notify(f"Validation failed: {e}", severity="error")
                return
            self.refresh_all()
        self.push_screen(MemberFormScreen(), done)

    async def action_edit(self) -> None:
        r = self._selected_row()
        if r is None:
            self.notify("Select a row first.", severity="warning")
            return
        existing = dict(r)

        def done(data: dict | None) -> None:
            if not data:
                return
            try:
                self.svc.edit(existing["id"], data)
                self.notify(f"Updated {existing['member_code']}.")
            except (ValidationError, ValueError) as e:
                self.notify(f"Update failed: {e}", severity="error")
                return
            self.refresh_all()
        self.push_screen(MemberFormScreen(existing, title=f"Edit {existing['member_code']}"), done)

    async def action_view(self) -> None:
        r = self._selected_row()
        if r is None:
            return

        def done(choice: str | None) -> None:
            if choice == "edit":
                self.run_worker(self.action_edit())
        self.push_screen(DetailScreen(dict(r)), done)

    async def action_cycle_status(self) -> None:
        r = self._selected_row()
        if r is None:
            self.notify("Select a row first.", severity="warning")
            return
        cur = str(r["status"]).upper()
        nxt = STATUS_CYCLE[(STATUS_CYCLE.index(cur) + 1) % len(STATUS_CYCLE)] \
            if cur in STATUS_CYCLE else "ACTIVE"
        try:
            self.svc.set_status(r["id"], nxt)
            self.notify(f"{r['member_code']}: {cur} -> {nxt}")
        except (ValidationError, ValueError) as e:
            self.notify(str(e), severity="error")
        self.refresh_all()

    async def action_delete(self) -> None:
        r = self._selected_row()
        if r is None:
            self.notify("Select a row first.", severity="warning")
            return

        def done(choice: str | None) -> None:
            if choice != "m-delete":
                return
            if self.svc.repo.delete(r["id"]):
                self.selected_id = None
                self.notify(f"Deleted {r['member_code']}.")
            self.refresh_all()
        self.push_screen(ActionMenuScreen(str(r["member_code"])), done)

    async def action_menu(self) -> None:
        """Right-click (or 'm' key) menu for the selected row."""
        r = self._selected_row()
        if r is None:
            self.notify("Select a row first.", severity="warning")
            return

        def done(choice: str | None) -> None:
            if choice == "m-view":
                self.run_worker(self.action_view())
            elif choice == "m-edit":
                self.run_worker(self.action_edit())
            elif choice == "m-status":
                self.run_worker(self.action_cycle_status())
            elif choice == "m-delete":
                self.run_worker(self.action_delete())
        self.push_screen(ActionMenuScreen(str(r["member_code"])), done)


def build_service(db: str | None) -> tuple[MemberService, Path]:
    path = init_db(db)
    return MemberService(MemberRepository(get_connection(path))), path


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Membership Registry — interactive Textual TUI")
    p.add_argument("--db", default=None, help="SQLite file (default ./data/membership.db or $MEMBERSHIP_DB)")
    args = p.parse_args(argv)
    svc, path = build_service(args.db)
    print(f"[db] {path}")
    MembershipApp(svc).run()


if __name__ == "__main__":
    main()
