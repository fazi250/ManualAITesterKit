"""The kit's own headed Edge: maximized, persistent login profile, reused between commands.

Edge runs with a local debugging port, and each `lct` command connects, works, and disconnects,
so the browser (and your Jira / app logins) stay open between commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, sync_playwright

from .config import PROFILE, fail, remember, state

PORT = int(os.environ.get("LCT_CDP_PORT", "9333"))
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Same idea as Playwright's own launch flags: no sync / account sign-in, extensions, first-run pages,
# or background services in the kit profile, so nothing personal or company-synced gets in and no
# popup covers the evidence.
_FLAGS = [
    "--start-maximized", "--no-first-run", "--no-default-browser-check", "--hide-crash-restore-bubble",
    "--disable-sync", "--disable-background-networking", "--disable-component-update", "--disable-default-apps",
    "--disable-extensions", "--no-service-autorun", "--password-store=basic", "--disable-search-engine-choice-screen",
    "--edge-skip-compat-layer-relaunch",
    "--disable-features=msForceBrowserSignIn,msImplicitSignin,Translate,OptimizationHints,LensOverlay,MediaRouter,"
    "GlobalMediaControls,DialMediaRouteProvider",
]

_BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def _browser_exe() -> str:
    for exe in [os.environ.get("LCT_BROWSER"), *_BROWSERS]:
        if exe and Path(exe).exists():
            return exe
    fail("Edge/Chrome not found. Set LCT_BROWSER in qa/.env to the browser .exe path.")


def _ws_endpoint() -> str | None:
    try:
        with _NO_PROXY.open(f"http://127.0.0.1:{PORT}/json/version", timeout=0.5) as r:
            return str(json.load(r)["webSocketDebuggerUrl"])
    except (OSError, ValueError, KeyError):
        return None


def is_running() -> bool:
    return _ws_endpoint() is not None


def _quiet_profile() -> None:
    """Turns off "Save password?" and autofill popups so they never cover evidence."""
    prefs_file = PROFILE / "Default" / "Preferences"
    prefs_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        prefs = json.loads(prefs_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prefs = {}
    prefs["credentials_enable_service"] = False
    prefs.setdefault("profile", {})["password_manager_enabled"] = False
    prefs.setdefault("autofill", {}).update(profile_enabled=False, credit_card_enabled=False)
    prefs_file.write_text(json.dumps(prefs), encoding="utf-8")


def _launch(url: str) -> str:
    _quiet_profile()
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [_browser_exe(), f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}", *_FLAGS, url],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags, close_fds=True,
    )
    for _ in range(60):
        time.sleep(0.25)
        ws = _ws_endpoint()
        if ws:
            return ws
    fail("Edge started but its debugging port didn't open. Your company may block remote debugging "
         "(Edge policy RemoteDebuggingAllowed); use VS Code browser tools instead.")


@contextmanager
def session(start_url: str = "about:blank") -> Iterator[BrowserContext]:
    """Connects to the kit browser (starting it if needed) and yields its context."""
    ws = _ws_endpoint()
    launched = ws is None
    ws = ws or _launch(start_url)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(ws)
        context = browser.contexts[0]
        context.set_default_timeout(10_000)
        if launched:  # close welcome / promo tabs the browser opens on its own
            time.sleep(1)
            site = urlparse(start_url)[:2]
            extras = [p for p in context.pages if urlparse(p.url)[:2] != site]
            if len(extras) < len(context.pages):  # keep at least the tab we opened
                for extra in extras:
                    extra.close()
        yield context


def _tab_id(page: Page) -> str:
    cdp = page.context.new_cdp_session(page)
    try:
        return str(cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"])
    finally:
        cdp.detach()


def use_tab(page: Page) -> Page:
    """Makes this the kit's working tab for the next commands."""
    page.bring_to_front()
    remember(tab=_tab_id(page))
    return page


def current_page(context: BrowserContext) -> Page:
    """The tab the last command worked in; else the visible tab; else the last tab."""
    pages = [p for p in context.pages if not p.url.startswith(("devtools://", "edge://", "chrome://"))]
    if not pages:
        return use_tab(context.new_page())
    last = state().get("tab")
    for page in pages:
        try:
            if last and _tab_id(page) == last:
                return page
        except Exception:
            continue
    for page in reversed(pages):
        try:
            if page.evaluate("document.visibilityState") == "visible":
                return use_tab(page)
        except Exception:
            continue
    return use_tab(pages[-1])


def show_url(context: BrowserContext, url: str) -> Page:
    """Opens url in the tab already on that site, else in a blank or new tab."""
    site = urlparse(url)[:2]  # (scheme, host:port)
    target = next((p for p in context.pages if urlparse(p.url)[:2] == site), None)
    target = target or next((p for p in context.pages if p.url in ("about:blank", "edge://newtab/")), None)
    page = use_tab(target or context.new_page())
    page.goto(url)
    return page


def close() -> None:
    if not _ws_endpoint():
        print("Browser is not running")
        return
    with session() as context:
        cdp = context.browser.new_browser_cdp_session() if context.browser else None
        if cdp:
            cdp.send("Browser.close")
    print("Browser closed")
