"""Tiny local app to try the whole flow safely (login -> check a field -> evidence -> report).
Test login comes from qa/.env: APP_DEMO_USER / APP_DEMO_PASS."""

from __future__ import annotations

import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from .config import app_env, fail, load_env

PORT = 5175
STYLE = """body{margin:0;font:15px Segoe UI,Arial,sans-serif;background:#f3f5f9;color:#1f2937}
header{background:#1e3a8a;color:#fff;padding:14px 28px;display:flex;justify-content:space-between;align-items:center}
header a{color:#c7d2fe}main{max-width:760px;margin:40px auto;background:#fff;border-radius:10px;padding:28px 36px;box-shadow:0 2px 10px #0001}
label{display:block;font-weight:600;margin:14px 0 4px}input{width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font:inherit;box-sizing:border-box}
button{margin-top:20px;background:#1e40af;color:#fff;border:0;border-radius:6px;padding:10px 22px;font:inherit;cursor:pointer}
.err{color:#b91c1c;margin-top:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 24px}h2{margin-top:28px;font-size:17px;color:#1e3a8a}"""


def _page(title: str, body: str) -> bytes:
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Demo CRM - {title}</title>'
            f"<style>{STYLE}</style></head><body>{body}</body></html>").encode()


def _login_form(error: str = "") -> bytes:
    err = f'<p class="err">{error}</p>' if error else ""
    return _page("Sign in", '<header><b>Demo CRM</b></header><main><h1>Sign in</h1><form method="post" action="/login">'
                 '<label for="username">Username</label><input id="username" name="username" autocomplete="username">'
                 '<label for="password">Password</label><input id="password" name="password" type="password" '
                 f'autocomplete="current-password"><button type="submit">Sign in</button>{err}</form></main>')


def _field(i: str, label: str, value: str) -> str:
    return f'<div><label for="{i}">{label}</label><input id="{i}" value="{value}" readonly></div>'


def _profile(user: str) -> bytes:
    field = _field
    return _page("Customer 1042", f'<header><b>Demo CRM</b><span>Logged in as {user} &nbsp; <a href="/logout">Logout</a>'
                 '</span></header><main><h1>Customer profile</h1><p>Customer ID: 1042</p><h2>Personal</h2><div class="grid">'
                 + field("name", "Full name", "Asha Verma") + field("dob", "Date of birth", "1990-04-12")
                 + '</div><h2>Contact</h2><div class="grid">' + field("email", "Email", "asha.verma@example.com")
                 + field("phone", "Phone", "+91 98765 43210") + "</div>"
                 + '<label for="address">Address</label><input id="address" value="221 MG Road, Pune 411001" readonly></main>')


def serve() -> None:
    load_env()
    user, password = app_env("demo", "USER"), app_env("demo", "PASS")
    if not (user and password):
        fail("Set APP_DEMO_USER and APP_DEMO_PASS in qa/.env (lct init creates them).")
    sessions: set[str] = set()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def _send(self, code: int, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _sid(self) -> str | None:
            morsel = SimpleCookie(self.headers.get("Cookie", "")).get("sid")
            return morsel.value if morsel and morsel.value in sessions else None

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/logout":
                sessions.discard(self._sid() or "")
                return self._send(302, headers={"Location": "/login", "Set-Cookie": "sid=; Max-Age=0; Path=/"})
            if self.path == "/customers/1042":
                return self._send(200, _profile(str(user))) if self._sid() else self._send(302, headers={"Location": "/login"})
            if self.path == "/login":
                return self._send(302, headers={"Location": "/customers/1042"}) if self._sid() else self._send(200, _login_form())
            self._send(302, headers={"Location": "/login"})

        def do_POST(self) -> None:  # noqa: N802
            form = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
            if form.get("username", [""])[0] == user and form.get("password", [""])[0] == password:
                sid = secrets.token_hex(16)
                sessions.add(sid)
                return self._send(302, headers={"Location": "/customers/1042", "Set-Cookie": f"sid={sid}; HttpOnly; Path=/"})
            self._send(401, _login_form("Invalid username or password"))

    print(f"Demo app: http://127.0.0.1:{PORT}/login  (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
