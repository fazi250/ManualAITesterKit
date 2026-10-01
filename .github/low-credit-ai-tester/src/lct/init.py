"""`lct init`: puts the Copilot rules + skills into .github/, and sets up qa/, VS Code settings,
GitHub MCP config and .gitignore in this repo. Safe to run again (it updates only kit-owned parts)."""

from __future__ import annotations

import json
import re
import secrets
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from .config import QA, ROOT, rel

TEMPLATES = files("lct") / "templates"
GITIGNORE_MARK = "# Low Credit AI Tester Kit"
BLOCK = re.compile(r"<!-- low-credit-ai-tester:start -->.*?<!-- low-credit-ai-tester:end -->\n?", re.S)


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _write_new(path: Path, text: str, done: list[str]) -> None:
    if path.exists():
        done.append(f"kept     {rel(path)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    done.append(f"created  {rel(path)}")


def _copy_skills(src: Traversable, dst: Path, done: list[str]) -> None:
    """Kit-owned files: always replaced with the kit's version."""
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_skills(item, target, done)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
            done.append(f"wrote    {rel(target)}")


def _copilot_instructions(done: list[str]) -> None:
    """Adds (or refreshes) only the kit's marked block; the rest of the file stays yours."""
    path = ROOT / ".github" / "copilot-instructions.md"
    ours = _template("github/copilot-instructions.md")
    if not path.exists():
        _write_new(path, ours, done)
        return
    text = path.read_text(encoding="utf-8")
    new = BLOCK.sub(lambda _: ours, text) if BLOCK.search(text) else text.rstrip("\n") + "\n\n" + ours
    path.write_text(new, encoding="utf-8")
    done.append(f"updated  {rel(path)} (kit block)")


def _merge_settings(done: list[str]) -> None:
    path = ROOT / ".vscode" / "settings.json"
    ours: dict[str, object] = json.loads(_template("settings.json"))
    if not path.exists():
        _write_new(path, json.dumps(ours, indent=2) + "\n", done)
        return
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:  # has comments: don't rewrite the user's file
        side = path.with_name("lct.settings.json")
        side.write_text(json.dumps(ours, indent=2) + "\n", encoding="utf-8")
        done.append(f"created  {rel(side)}  <- copy these keys into .vscode/settings.json")
        return
    added = [k for k in ours if k not in current]
    current.update({k: ours[k] for k in added})
    path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    done.append(f"updated  {rel(path)} (+{len(added)} settings)" if added else f"kept     {rel(path)}")


def run() -> None:
    done: list[str] = []
    _copilot_instructions(done)
    _copy_skills(TEMPLATES / "github" / "skills", ROOT / ".github" / "skills", done)

    for sub in ("testcases", "evidence", "reports", "jira", "repos"):
        (QA / sub).mkdir(parents=True, exist_ok=True)
    (QA / "testcases" / "testcase.schema.json").write_text(_template("testcase.schema.json"), encoding="utf-8")
    _write_new(QA / "testcases" / "DEMO-101.json", _template("DEMO-101.json"), done)
    (QA / ".env.example").write_text(_template("env.example"), encoding="utf-8")
    demo_pass = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(16))
    _write_new(QA / ".env", _template("env.example").replace("APP_DEMO_PASS=", f"APP_DEMO_PASS={demo_pass}"), done)

    _merge_settings(done)
    _write_new(ROOT / ".vscode" / "mcp.json", _template("mcp.json"), done)

    gitignore = ROOT / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if GITIGNORE_MARK not in text:
        gitignore.write_text(text.rstrip("\n") + "\n" + _template("gitignore.txt"), encoding="utf-8")
        done.append(f"updated  {rel(gitignore)}")
    else:  # kit updated: add only the lines that are new
        have = set(text.splitlines())
        new = [line for line in _template("gitignore.txt").splitlines() if line.strip() and line not in have]
        if new:
            gitignore.write_text(text.rstrip("\n") + "\n" + "\n".join(new) + "\n", encoding="utf-8")
            done.append(f"updated  {rel(gitignore)} (+{len(new)} lines)")

    print("\n".join(done))
    print("Next: reload VS Code, fill qa/.env (APP_<NAME>_URL/_USER/_PASS, JIRA_URL).")
