"""`lct` command line. Every command prints one or a few lines so Copilot reads very little."""

from __future__ import annotations

import argparse
import io
import os
import sys

from .actions import ACTIONS_HELP

COMMANDS = """commands (run from the repo root):
  status                       one line: browser page, last test id + results, last report
  init                         set up qa/, .vscode settings, GitHub MCP config, .gitignore
  open URL|APP|jira            open a page (app URL from qa/.env, or JIRA_URL) in the kit browser
  login APP                    log in with APP_<APP>_URL/_USER/_PASS from qa/.env
  page [WORD] [--hidden]       numbered page map (iframes + shadow DOM); WORD filters; --hidden lists hidden ones
  text [SELECTOR]              visible text of the page (or one element), max 2000 chars
  shot [N]                     screenshot of the page (or element N) to LOOK at: costs image tokens, ask first
  act ACTIONS...               do actions/checks without evidence
  step ID N ACTIONS...         one test step: act, check, red box, full-screen snap, Pass/Fail into JSON
  snap ID [N] [--hotkey]       full-screen snap; --hotkey for your own testing (Ctrl+Alt+P / Ctrl+Alt+Q)
  jira KEY|LINK [--attachments] Jira card -> qa/jira/KEY.md (uses your browser login)
  index [PATHS...]             qa/test-index.md + qa/steps-index.md from qa/repos/* and this repo
  report [IDS...] [--all] [--hide-password]  Word report -> qa/reports/ (no id: last test)
  demo                         local demo app on http://127.0.0.1:5175
  close                        close the kit browser
"""


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):  # page titles can have characters the console code page lacks
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="lct", description="Low Credit AI Tester Kit",
                                     epilog=COMMANDS + "\n" + ACTIONS_HELP,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
    sub.add_parser("status")
    sub.add_parser("init")
    sub.add_parser("open").add_argument("target")
    sub.add_parser("login").add_argument("app")
    page_cmd = sub.add_parser("page")
    page_cmd.add_argument("filter", nargs="?", default="")
    page_cmd.add_argument("--hidden", action="store_true")
    page_cmd.add_argument("--view", action="store_true")
    sub.add_parser("text").add_argument("selector", nargs="?", default="")
    sub.add_parser("shot").add_argument("ref", nargs="?", default="")
    sub.add_parser("act")
    step = sub.add_parser("step")
    step.add_argument("id")
    step.add_argument("n", type=int)
    snap = sub.add_parser("snap")
    snap.add_argument("id")
    snap.add_argument("n", type=int, nargs="?")
    snap.add_argument("--hotkey", action="store_true")
    snap.add_argument("--key", default="P")
    jira = sub.add_parser("jira")
    jira.add_argument("card")
    jira.add_argument("--attachments", action="store_true")
    sub.add_parser("index").add_argument("paths", nargs="*")
    report = sub.add_parser("report")
    report.add_argument("ids", nargs="*")
    report.add_argument("--all", action="store_true")
    report.add_argument("--hide-password", action="store_true")
    sub.add_parser("demo")
    sub.add_parser("close")

    args, extra = parser.parse_known_args()
    if extra and args.cmd not in ("act", "step"):
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    try:
        run(args, extra)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as e:  # one line instead of a long traceback: fewer tokens for Copilot
        message = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        print(f"ERROR: {message[:300]}", file=sys.stderr)
        raise SystemExit(1) from None


def run(args: argparse.Namespace, extra: list[str]) -> None:
    # Imports are per command so light commands (report, index) start fast.
    cmd = args.cmd
    if cmd == "status":
        _status()
    elif cmd == "init":
        from .init import run as init

        init()
    elif cmd == "index":
        from .index import build

        build(args.paths)
    elif cmd == "report":
        from .report import build as report

        report(args.ids, args.hide_password, args.all)
    elif cmd == "demo":
        from .demo import serve

        serve()
    elif cmd == "login":
        from .login import login

        login(args.app)
    elif cmd == "jira":
        from .jira import read_card

        read_card(args.card, args.attachments)
    elif cmd == "close":
        from .browser import close

        close()
    elif cmd == "snap" and args.hotkey:
        from .snap import hotkey_mode

        hotkey_mode(args.id, args.key)
    else:
        _browser_command(args, extra)


def _status() -> None:
    """One line so Copilot can pick up where things are, whatever order requests come in."""
    import json

    from .browser import current_page, is_running, session
    from .config import QA, rel, state

    s = state()
    parts = []
    if is_running():
        with session() as context:
            page = current_page(context)
            parts.append(f"Browser: {page.title()} | {page.url}")
    else:
        parts.append("Browser: closed")
    last = s.get("last_id")
    if last:
        file = QA / "testcases" / f"{last}.json"
        steps = json.loads(file.read_text(encoding="utf-8")).get("steps", []) if file.exists() else []
        results = " ".join(st.get("result") or "-" for st in steps)
        snaps = len(list((QA / "evidence" / last).glob("step-*.png")))
        case = f"{rel(file)}, steps {results}" if file.exists() else "no test case yet"
        parts.append(f"Last test: {last} ({case}, {snaps} snaps)")
    if s.get("report"):
        parts.append(f"Last report: {s['report']}")
    print(" | ".join(parts))


def _browser_command(args: argparse.Namespace, extra: list[str]) -> None:
    from .actions import page_map, page_text, parse_actions, run_actions, unmark, write_result
    from .browser import current_page, session, show_url
    from .config import QA, app_env, load_env, remember

    load_env()  # LCT_BUSY_SELECTOR / LCT_SETTLE_MS for AJAX apps
    cmd = args.cmd
    if cmd == "open":
        load_env()
        target = args.target
        named = os.environ.get("JIRA_URL") if target.lower() == "jira" else app_env(target, "URL")
        url = target if "://" in target else named or f"https://{target}"
        with session(url) as context:
            page = show_url(context, url)
            print(f"{page.title()} | {page.url}")
        return

    actions = parse_actions(extra) if cmd in ("act", "step") else []
    with session() as context:
        page = current_page(context)
        if cmd == "page":
            print(page_map(page, args.filter, args.hidden, args.view))
        elif cmd == "text":
            print(page_text(page, args.selector))
        elif cmd == "shot":
            from .actions import locate
            from .config import rel

            path = QA / "shots" / f"view-{args.ref or 'page'}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            if args.ref:
                locate(page, args.ref).screenshot(path=str(path))
            else:
                page.screenshot(path=str(path), scale="css")
            print(f"{rel(path)} (open this image only if the user agreed: images cost more tokens)")
        elif cmd == "act":
            ok, actual, page = run_actions(page, actions)
            print(f"{'OK' if ok else 'FAIL'}: {actual}")
            if not ok:
                raise SystemExit(1)
        elif cmd == "step":
            from .snap import snap_step

            ok, actual, page = run_actions(page, actions)
            shot = snap_step(page, args.id, args.n)
            unmark(page)
            write_result(args.id, args.n, ok, actual)
            remember(last_id=args.id)
            print(f"Step {args.n} {'Pass' if ok else 'Fail'}: {actual} | {shot}")
        elif cmd == "snap":
            from .snap import snap_step

            n = args.n
            if n is None:
                folder = QA / "evidence" / args.id
                n = max((int(p.stem[5:]) for p in folder.glob("step-*.png") if p.stem[5:].isdigit()), default=0) + 1
            print(f"Saved {snap_step(page, args.id, n)}")
            remember(last_id=args.id)


if __name__ == "__main__":
    main()
