"""Logs in to an app with test credentials from qa/.env. The password is never printed."""

from __future__ import annotations

from .browser import session, show_url
from .config import app_env, app_prefix, fail, load_env

DEFAULT_USER_FIELD = ("input[type=email], input[autocomplete=username], input[name*=user i], input[id*=user i], "
                      "input[name*=login i], input[name*=email i]")


def login(app: str) -> None:
    load_env()
    url, user, password = app_env(app, "URL"), app_env(app, "USER"), app_env(app, "PASS")
    if not (url and user and password):
        p = app_prefix(app)
        fail(f"Missing {p}URL / {p}USER / {p}PASS in qa/.env")
    user_sel = app_env(app, "USER_FIELD") or DEFAULT_USER_FIELD
    pass_sel = app_env(app, "PASS_FIELD") or "input[type=password]"
    submit_sel = app_env(app, "SUBMIT")

    with session(url) as context:
        page = show_url(context, url)
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        user_box = page.locator(user_sel).filter(visible=True).first
        pass_box = page.locator(pass_sel).filter(visible=True).first
        if not user_box.count() and not pass_box.count():
            print(f"already-logged-in: {page.title()} ({page.url})")
            return
        if user_box.count():
            user_box.fill(user)
        if not pass_box.count():  # two-step login: user -> Next -> password
            page.keyboard.press("Enter")
            pass_box.wait_for(timeout=15_000)
        pass_box.fill(password)
        if submit_sel:
            page.locator(submit_sel).first.click()
        else:
            pass_box.press("Enter")
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        stuck = page.locator(pass_sel).filter(visible=True).count() > 0
        print(f"{'still-on-login-page' if stuck else 'logged-in'}: {page.title()} ({page.url})")
        if stuck:
            raise SystemExit(2)
