---
name: improve-kit
description: Fix or improve the Low Credit AI Tester Kit itself (lct commands, its skills or rules) after the user said yes. Use when an lct command misbehaves (error, wrong element, missing red box or snap, bad report) or a skill instruction is unclear, and the user agreed to update the kit.
argument-hint: '<what went wrong>'
---
Only after the user said yes to "Kit fix kar doon?". Keep the fix small and generic: it must work on any site, never only one site.

Where things live (repo root):
- Code: `.github/low-credit-ai-tester/src/lct/` (actions.py = page map/actions, browser.py, snap.py, report.py, jira.py, login.py, cli.py).
- Skills and rules: edit ONLY the sources in `.github/low-credit-ai-tester/src/lct/templates/github/` (skills/*/SKILL.md, copilot-instructions.md), then run `lct init` to copy them into `.github/`. Never edit `.github/skills/` directly (init overwrites it).
- Dependencies: `.github/low-credit-ai-tester/pyproject.toml` + `requirements.txt`. If they change, reinstall with the README install command. Code changes need no reinstall (editable install).

Steps:
1. Reproduce once with the smallest `lct` command; read only the function involved, not whole files.
2. Fix it. Keep: passwords never printed, Jira read-only, ask before viewing screenshots, one-line command output.
3. Verify: rerun the failing command, then `python -m compileall -q .github/low-credit-ai-tester/src` (and `uvx ruff check .github/low-credit-ai-tester/src` if available).
4. Add one line to `.github/low-credit-ai-tester/CHANGELOG.md`: `- YYYY-MM-DD: <what changed and why>`.
5. Reply in 2-3 lines: what was wrong, what changed, how it was verified. Mention that pushing the kit to GitHub shares the fix.
