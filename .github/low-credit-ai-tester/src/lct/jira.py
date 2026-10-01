"""Reads a Jira card with your logged-in browser session (no API key) into a short qa/jira/<KEY>.md."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from .browser import session, show_url
from .config import QA, fail, load_env, rel, remember

KEY_RE = re.compile(r"[A-Z][A-Z0-9_]+-\d+")
NOISE = re.compile(r"rank|development|sprint|flag|team|parent|epic|satisfaction|request|vulnerab|chart|point|time|"
                   r"date|watch|vote|viewed|security|status category|issue color|start|count|automatic", re.I)


def _parse(arg: str) -> tuple[str, str]:
    if re.match(r"https?://", arg, re.I):
        url = urlparse(arg)
        if "/browse/" in arg:
            base, rest = arg.split("/browse/", 1)
            m = KEY_RE.match(rest)
        else:
            base = f"{url.scheme}://{url.netloc}"
            m = KEY_RE.search(parse_qs(url.query).get("selectedIssue", [""])[0]) or KEY_RE.search(arg)
        if not m:
            fail(f'No Jira key found in "{arg}"')
        return base.rstrip("/"), m.group(0)
    base = (os.environ.get("JIRA_URL") or "").rstrip("/")
    if not base:
        fail("Give the full card link, or set JIRA_URL in qa/.env")
    if not KEY_RE.fullmatch(arg.upper()):
        fail(f'"{arg}" is not a Jira key')
    return base, arg.upper()


def _txt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (str, int, float)) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, list):
        return ", ".join(t for t in (_txt(x) for x in v) if t)
    if isinstance(v, dict):
        return str(v.get("value") or v.get("name") or v.get("displayName") or "")
    return ""


def _clean(s: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", s.replace("\r", "")).strip()


def read_card(arg: str, attachments: bool = False) -> None:
    load_env()
    base, key = _parse(arg)
    card_url = f"{base}/browse/{key}"
    with session(card_url) as context:
        page = show_url(context, card_url)
        res = context.request.get(f"{base}/rest/api/2/issue/{key}?expand=names",
                                  headers={"Accept": "application/json"}, fail_on_status_code=False)
        if res.status in (401, 403) or "json" not in res.headers.get("content-type", ""):
            fail("Not logged in to Jira. Log in once in the kit browser window, then run this again.", 2)
        if not res.ok:
            fail(f"Jira returned HTTP {res.status} for {key}")
        issue = res.json()
        f, names = issue["fields"], issue.get("names", {})

        meta = {"Type": f.get("issuetype"), "Status": f.get("status"), "Priority": f.get("priority"),
                "Assignee": f.get("assignee"), "Reporter": f.get("reporter"), "Labels": f.get("labels"),
                "Components": f.get("components"), "Affects": f.get("versions"), "Fix": f.get("fixVersions"),
                "Environment": f.get("environment")}
        md = [f"# {issue['key']}: {f.get('summary', '')}",
              " | ".join(f"{k}: {_txt(v)}" for k, v in meta.items() if _txt(v)), f"URL: {card_url}", ""]
        if f.get("description"):
            md += ["## Description", _clean(_txt(f["description"]))[:6000], ""]
        customs = [(names.get(k, k), _txt(v).strip()) for k, v in f.items() if k.startswith("customfield_")]
        for name, value in [c for c in customs if c[1] and len(c[1]) < 4000 and not NOISE.search(c[0])
                            and not re.fullmatch(r"\{.*\}|true|false|[\d.]+", c[1], re.S)][:12]:
            md += [f"## {name}", _clean(value), ""]
        comments = ((f.get("comment") or {}).get("comments") or [])[-3:]
        if comments:
            md.append("## Last comments")
            md += [f"- {_txt(c.get('author'))}, {str(c.get('created', ''))[:10]}: {' '.join(_txt(c.get('body')).split())[:800]}"
                   for c in comments]
            md.append("")
        files = f.get("attachment") or []
        if files:
            md.append("## Attachments")
            folder = QA / "jira" / key
            for a in files:
                note = ""
                if attachments and str(a.get("mimeType", "")).startswith("image/") and a.get("size", 0) <= 5_000_000:
                    data = context.request.get(a["content"], fail_on_status_code=False)
                    if data.ok:
                        folder.mkdir(parents=True, exist_ok=True)
                        target = folder / re.sub(r'[\\/:*?"<>|]', "_", a["filename"])
                        target.write_bytes(data.body())
                        note = f" -> {rel(target)}"
                md.append(f"- {a['filename']} ({a.get('mimeType')}, {round(a.get('size', 0) / 1024)} KB){note}")
            md.append("")
        page.bring_to_front()

    out = QA / "jira" / f"{key}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(md)
    out.write_text(text, encoding="utf-8")
    remember(last_id=key, jira=card_url)
    print(f"{rel(out)} ({len(text)} chars, {len(files)} attachments)")
