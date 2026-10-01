"""Builds two small files Copilot searches instead of crawling repos (zero AI tokens):
qa/test-index.md   every scenario / test title with file + line
qa/steps-index.md  every Cucumber step definition, plus page-object methods
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

from .config import QA, ROOT

SKIP = {"node_modules", ".git", "dist", "build", "out", "bin", "obj", "coverage", "vendor", ".venv", "venv",
        "__pycache__", "playwright-report", "test-results", "allure-results", "target", ".gradle", "tmp", "log"}
TEST_FILE = re.compile(r"(\.(spec|test|cy|e2e)\.[cm]?[jt]sx?$)|(^test_.*\.(py|rb)$)|(_(test|spec)\.(py|rb)$)|"
                       r"(Tests?\.(java|cs|kt)$)|(\.feature$)")
STEP_DEF = re.compile(r"""^\s*(Given|When|Then|And|But|Step)\s*\(?\s*(/.+?/[a-z]*|'[^']*'|"[^"]*")""")

Hit = tuple[int, str]


def _walk(folder: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP and Path(dirpath, d) != QA)
        for name in sorted(filenames):
            yield Path(dirpath, name)


def _scan(lines: list[str], match: Callable[[str], str | None]) -> list[Hit]:
    return [(i + 1, t) for i, line in enumerate(lines) if (t := match(line))]


def _group(rx: str, line: str, group: int = 1) -> str | None:
    m = re.match(rx, line)
    return m.group(group).strip() if m else None


def tests_in(path: Path, lines: list[str]) -> list[Hit]:
    ext = path.suffix.lower()
    if ext == ".feature":
        return _scan(lines, lambda s: _group(r"^\s*Scenario(?: Outline)?:\s*(.+)$", s))
    if re.fullmatch(r"\.[cm]?[jt]sx?", ext):
        js_test = r"""^\s*(?:test|it)(?:\.(?:only|skip|fixme|fail|slow))?\s*\(\s*(['"`])(.+?)\1"""
        return _scan(lines, lambda s: _group(js_test, s, 2))
    if ext == ".py":
        return _scan(lines, lambda s: _group(r"^\s*(?:async\s+)?def\s+(test_\w+)", s))
    if ext == ".rb":
        return _scan(lines, lambda s: _group(r"""^\s*(?:it|scenario|specify|example|test)\s*\(?\s*(['"])(.+?)\1""", s, 2)
                     or _group(r"^\s*def\s+(test_\w+)", s))
    hits: list[Hit] = []
    after_attr = False
    for i, line in enumerate(lines):
        if re.search(r"@Test\b|\[(?:Test|Fact|Theory|TestMethod|TestCase)\b", line):
            after_attr = True
        elif after_attr and (m := re.search(r"(?:void|Task|fun)\s+(\w+)\s*\(", line)):
            hits.append((i + 1, m.group(1)))
            after_attr = False
    return hits


def steps_in(lines: list[str]) -> list[Hit]:
    return _scan(lines, lambda s: f"{m.group(1)} {m.group(2)}" if (m := STEP_DEF.match(s)) else None)


def methods_in(lines: list[str]) -> list[Hit]:
    """One line per Ruby class/module with its method names (page objects, helpers)."""
    hits: list[Hit] = []
    for i, line in enumerate(lines):
        if m := re.match(r"^\s*(?:class|module)\s+([A-Z]\w*(?:::\w+)*)", line):
            hits.append((i + 1, f"{m.group(1)}:"))
        elif (m := re.match(r"^\s*def\s+(?:self\.)?([a-z_]\w*[?!=]?)", line)) and hits and m.group(1) != "initialize":
            hits[-1] = (hits[-1][0], f"{hits[-1][1]} {m.group(1)}")
    return [h for h in hits if " " in h[1]]


def _add(out: list[str], shown: str, hits: list[Hit]) -> None:
    if hits:
        out += [f"## {shown}", *(f"- {n}: {t}" for n, t in hits), ""]


def build(paths: list[str]) -> None:
    repos = QA / "repos"
    sources = [Path(p).resolve() for p in paths] or [*sorted(d for d in repos.glob("*") if d.is_dir()), ROOT]
    tests_md: list[str] = []
    steps_md: list[str] = []
    pages_md: list[str] = []
    n_tests = n_steps = 0

    for src in sources:
        for file in _walk(src):
            is_test, is_ruby = bool(TEST_FILE.search(file.name)), file.suffix == ".rb"
            if not (is_test or is_ruby):
                continue
            lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
            try:
                shown = file.relative_to(ROOT).as_posix()
            except ValueError:
                shown = file.as_posix()

            if is_test:
                hits = tests_in(file, lines)
                _add(tests_md, shown, hits)
                n_tests += len(hits)
            if is_ruby:
                defs = steps_in(lines)
                _add(steps_md, shown, defs)
                n_steps += len(defs)
                if not defs and not is_test:
                    _add(pages_md, shown, methods_in(lines))

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    (QA / "test-index.md").write_text(
        "\n".join([f"# Test index (generated {stamp} by `lct index`, do not edit) | {n_tests} tests", "", *tests_md]),
        encoding="utf-8")
    (QA / "steps-index.md").write_text("\n".join([
        f"# Step definitions and page objects (generated {stamp}, do not edit) | {n_steps} steps", "", *steps_md,
        *(["# Page objects / helpers (class: methods)", "", *pages_md] if pages_md else []),
    ]), encoding="utf-8")
    print(f"qa/test-index.md: {n_tests} tests | qa/steps-index.md: {n_steps} step definitions")
