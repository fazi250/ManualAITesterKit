"""Paths and qa/.env loading. Every command runs from the repo root (or any folder below it)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import NoReturn


def _find_root() -> Path:
    here = Path.cwd().resolve()
    for folder in (here, *here.parents):
        if any((folder / name).is_dir() for name in ("qa", ".github", "low-credit-ai-tester")):
            return folder
    return here


ROOT = _find_root()
QA = Path(os.environ.get("LCT_QA_DIR", ROOT / "qa"))
PROFILE = QA / ".browser-profile"


def load_env() -> None:
    """Loads qa/.env into os.environ (existing variables win). Values are never printed."""
    env_file = QA / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def app_prefix(app: str) -> str:
    return "APP_" + "".join(c if c.isalnum() else "_" for c in app.upper()) + "_"


def app_env(app: str, key: str) -> str | None:
    """APP_<APP>_<KEY> from qa/.env, e.g. app_env('myapp', 'URL')."""
    return os.environ.get(app_prefix(app) + key) or None


STATE_FILE = QA / ".lct-state.json"


def state() -> dict[str, str]:
    """Small memory between commands, e.g. the last test id, so requests can come in any order."""
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except (OSError, ValueError, AttributeError):
        return {}


def remember(**values: str) -> None:
    QA.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({**state(), **values}), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def fail(message: str, code: int = 1) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(code)
