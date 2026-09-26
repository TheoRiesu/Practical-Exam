"""Central configuration. Override DB path via env var MEMBERSHIP_DB."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "membership.db"


def resolve_db_path(explicit: str | None = None) -> Path:
    """Precedence: explicit arg > $MEMBERSHIP_DB > ./data/membership.db."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("MEMBERSHIP_DB")
    if env:
        return Path(env).expanduser()
    return DEFAULT_DB_PATH
