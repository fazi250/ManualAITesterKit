"""Browser actions by what a person sees (button names, labels, text) + tiny page summaries.

Everything here prints a line or two, never a full page snapshot, to keep Copilot's tokens low.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from importlib.resources import files
from typing import Literal

from playwright.sync_api import Locator, Page

from .config import QA, fail

Kind = Literal["goto", "click", "hover", "check", "fill", "select", "press", "expect", "read", "mark", "wait"]
KINDS: tuple[Kind, ...] = ("goto", "click", "hover", "check", "fill", "select", "press", "expect", "read", "mark", "wait")
SELECTOR_PREFIXES = ("css=", "xpath=", "role=", "text=", "id=", "#", "//", "[")

ACTIONS_HELP = """actions run in the order given:
  --goto URL  --click TEXT  --hover TEXT (menus that open on hover)  --check TEXT (radio/checkbox)
  --fill "LABEL=VALUE"  --select "LABEL=OPTION"  --press KEY  --wait SECONDS
checks (decide Pass/Fail):
  --expect TEXT   text must be visible on the page
  --read LABEL    field must be visible and not empty (its value is reported)
evidence (lct step):
  fields you fill/select/check/read get a red box automatically; --mark LABEL adds one to anything else
TEXT/LABEL: best a number from `lct page` (e.g. --click 7), else visible text/label,
or a Playwright selector: css=..., role=button[name="Save"], #id, //xpath"""


@dataclass(frozen=True)
class Action:
    kind: Kind
    target: str
    value: str = ""


def parse_actions(argv: list[str]) -> list[Action]:
    actions: list[Action] = []
    it = iter(argv)
    for flag in it:
        name = flag.removeprefix("--")
        arg = next(it, None)
        if name not in KINDS or arg is None:
            fail(f'Bad option near "{flag}"\n{ACTIONS_HELP}')
        kind: Kind = name  # narrowed by the KINDS check above
        if kind in ("fill", "select"):
            label, sep, value = arg.partition("=")
            if not sep or not label:
                fail(f'--{kind} needs "Label=value"')
            actions.append(Action(kind, label, value))
        else:
            actions.append(Action(kind, arg))
    return actions


# AJAX apps re-create elements, which drops the data-lct-ref number. Re-find the element from what
# `lct page` remembered about it (id > name > label > text, same tag) and put the number back.
# Ambiguous matches (two equally good elements without an id match) are refused, never guessed.
_HEAL_JS = """(n) => {
  const d = (window.__lctDesc || {})[n]; if (!d) return false;
  const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
  const label = (e) => norm(e.getAttribute('aria-label') || (e.labels && e.labels[0] && e.labels[0].innerText) || e.placeholder);
  const found = [];
  const walk = (root) => { for (const e of root.querySelectorAll('*')) {
    if (e.shadowRoot) walk(e.shadowRoot);
    if (e.tagName === d.tag) found.push(e);
  } };
  walk(document);
  const score = (e) => (d.id && e.id === d.id ? 8 : 0) + (d.name && e.getAttribute('name') === d.name ? 2 : 0)
    + (d.label && label(e) === d.label ? 2 : 0) + (d.text && norm(e.innerText) === d.text ? 2 : 0);
  const ranked = found.map((e) => [score(e), e]).filter(([s]) => s >= 2).sort((a, b) => b[0] - a[0]);
  if (!ranked.length || (ranked.length > 1 && ranked[0][0] === ranked[1][0] && ranked[0][0] < 8)) return false;
  const e = ranked[0][1];
  e.setAttribute('data-lct-ref', String(n)); (window.__lctRefs = window.__lctRefs || []).push(e);
  return true;
}"""


def locate(page: Page, target: str) -> Locator:
    """A number from `lct page` (e.g. 7), a selector, or what a person sees: role name, label, placeholder, text."""
    if target.isdigit():  # numbers live in the main page, iframes and (open) shadow DOM
        for attempt in range(2):
            for frame in page.frames:
                element = frame.locator(f'[data-lct-ref="{target}"]').first
                if element.count():
                    return element
            if attempt == 0:  # element was re-rendered: heal the number once
                for frame in page.frames:
                    try:
                        frame.evaluate(_HEAL_JS, int(target))
                    except Exception:
                        continue
        raise LookupError(f"Ref {target} is gone (page changed): run `lct page` again")
    if target.startswith(SELECTOR_PREFIXES):
        ways = [page.locator(target)]
    else:
        ways = [page.get_by_role(role, name=target)
                for role in ("button", "link", "menuitem", "tab", "checkbox", "radio", "option")]
        ways += [page.get_by_label(target), page.get_by_placeholder(target), page.get_by_text(target)]
    for way in ways:
        element = way.filter(visible=True).first
        if element.count():
            return element
    raise LookupError(f"Not found on page: {target}")


READ_JS = """(e) => [(e.labels && e.labels[0] && e.labels[0].innerText) || e.getAttribute('aria-label') || e.placeholder
  || e.name || '', ('value' in e && e.value) || e.textContent || '']"""
MARK_JS = """(e) => { if (e.hasAttribute('data-qa-mark')) return; e.setAttribute('data-qa-mark', e.style.outline || '');
  (window.__lctMarked = window.__lctMarked || []).push(e);
  e.style.outline = '4px solid #e00000'; e.style.outlineOffset = '3px'; }"""
# Scroll so the marked elements are on screen together (top of the group a little below the top).
SHOW_MARKS_JS = """() => { const els = (window.__lctMarked || []).filter((e) => e.isConnected); if (!els.length) return;
  const top = Math.min(...els.map((e) => e.getBoundingClientRect().top + window.scrollY));
  window.scrollTo({ top: Math.max(0, top - 140), behavior: 'instant' }); }"""
UNMARK_JS = """() => { (window.__lctMarked || []).forEach((e) => {
  e.style.outline = e.getAttribute('data-qa-mark') || ''; e.style.outlineOffset = ''; e.removeAttribute('data-qa-mark'); });
  window.__lctMarked = []; }"""


# Waits for AJAX to finish: no fetch/XHR in flight, no DOM additions/removals for a short quiet time,
# and no visible busy indicator (aria-busy, or the app's own spinner via LCT_BUSY_SELECTOR in qa/.env).
_SETTLE_JS = """async ({ quiet, timeout, busy }) => {
  if (!window.__lctNet) {
    const net = window.__lctNet = { n: 0, last: Date.now() };
    const done = () => { net.n = Math.max(0, net.n - 1); net.last = Date.now(); };
    const realFetch = window.fetch;
    if (realFetch) window.fetch = function (...a) { net.n++; return realFetch.apply(this, a).finally(done); };
    const realSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (...a) { net.n++; this.addEventListener('loadend', done, { once: true });
      return realSend.apply(this, a); };
    new MutationObserver(() => { net.last = Date.now(); }).observe(document, { subtree: true, childList: true });
  }
  const net = window.__lctNet;
  const visible = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const busyNow = () => [...document.querySelectorAll('[aria-busy="true"]' + (busy ? ',' + busy : ''))].some(visible);
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (net.n === 0 && Date.now() - net.last >= quiet && !busyNow()) return true;
    await new Promise((r) => setTimeout(r, 100));
  }
  return false;
}"""


def settle(page: Page) -> None:
    """Waits (max LCT_SETTLE_MS, default 8000) until page loads and AJAX activity are over in every frame."""
    options = {"quiet": 400, "timeout": int(os.environ.get("LCT_SETTLE_MS", "8000")),
               "busy": os.environ.get("LCT_BUSY_SELECTOR", "")}
    for _ in range(3):  # a navigation can start while we wait: then wait for the new page and check again
        try:
            page.wait_for_load_state("load", timeout=15_000)
            for frame in page.frames:
                if not frame.is_detached():
                    frame.evaluate(_SETTLE_JS, options)
            return
        except Exception:
            page.wait_for_timeout(300)


def _expect_text(page: Page, text: str, timeout_s: float = 10) -> None:
    """Waits until the text is visible in the page, any iframe or open shadow DOM."""
    deadline = time.monotonic() + timeout_s
    while True:
        for frame in page.frames:
            try:
                if frame.get_by_text(text).filter(visible=True).count():
                    return
            except Exception:
                continue
        if time.monotonic() > deadline:
            raise LookupError(f'Not shown on page: "{text}"')
        page.wait_for_timeout(300)


def run_actions(page: Page, actions: list[Action], auto_mark: bool = False) -> tuple[bool, str, Page]:
    """Runs actions in order. Returns (ok, what was seen / why it failed, the page now in use).
    auto_mark (lct step): every field filled/selected/checked/read gets a red box for the snap."""
    from .browser import use_tab

    def touched(element: Locator) -> None:
        if auto_mark:
            element.evaluate(MARK_JS)

    seen: list[str] = []
    try:
        for a in actions:
            if a.kind == "goto":
                page.goto(a.target)
            elif a.kind == "click":
                before = list(page.context.pages)
                locate(page, a.target).click()
                page.wait_for_timeout(500)  # let a navigation / new tab start before waiting for it
                opened = [p for p in page.context.pages if p not in before]
                if opened:  # the click opened a new tab: continue there
                    page = use_tab(opened[-1])
            elif a.kind == "hover":
                element = locate(page, a.target)
                element.hover()
                touched(element)
                page.wait_for_timeout(400)  # hover menus animate open
            elif a.kind == "check":
                element = locate(page, a.target)
                element.check()
                touched(element)
            elif a.kind == "fill":
                element = locate(page, a.target)
                element.fill(a.value)
                touched(element)
            elif a.kind == "select":
                element = locate(page, a.target)
                element.select_option(label=a.value)
                touched(element)
            elif a.kind == "press":
                page.keyboard.press(a.target)
            elif a.kind == "wait":
                page.wait_for_timeout(float(a.target) * 1000)
            elif a.kind == "expect":
                _expect_text(page, a.target)
                seen.append(f'"{a.target}" shown')
            elif a.kind == "read":
                element = locate(page, a.target)
                name, value = element.evaluate(READ_JS)
                label = str(name).strip() if a.target.isdigit() and str(name).strip() else a.target
                if not str(value).strip():
                    raise ValueError(f"{label} is empty")
                touched(element)
                seen.append(f"{label}: {' '.join(str(value).split())[:80]}")
            elif a.kind == "mark":
                locate(page, a.target).evaluate(MARK_JS)
            if a.kind in ("goto", "click", "check", "fill", "select", "press"):
                settle(page)
    except Exception as e:  # report the first line only
        return False, (str(e).strip().splitlines()[0][:200] if str(e).strip() else type(e).__name__), page
    for frame in page.frames:  # marked fields on screen for the snap
        try:
            frame.evaluate(SHOW_MARKS_JS)
        except Exception:
            continue
    return True, "; ".join(seen) or "Done", page


def unmark(page: Page) -> None:
    for frame in page.frames:
        try:
            frame.evaluate(UNMARK_JS)
        except Exception:
            pass


# Typed, numbered element table (same idea as agent-browser refs / jev-ultrafast's indexed table):
# every visible interactive element gets [N] role "name" = value, and the number is stored on the
# element (data-lct-ref) so the next command can act on it: `lct act --click 7`. Works on any site.
PAGE_MAP_JS = """({ filter, max }) => {
  const f = (filter || '').toLowerCase();
  const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 50);
  const visible = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const roleOf = (e) => {
    const r = e.getAttribute('role'); if (r) return r;
    const t = e.tagName.toLowerCase(), type = (e.type || '').toLowerCase();
    if (t === 'a') return 'link'; if (t === 'button' || ['submit', 'button', 'reset'].includes(type)) return 'button';
    if (t === 'select') return 'combobox'; if (t === 'textarea' || e.isContentEditable) return 'textbox';
    if (['checkbox', 'radio'].includes(type)) return type; if (type === 'file') return 'file';
    return type && type !== 'text' ? type : 'textbox';
  };
  const nameOf = (e) => clean(e.getAttribute('aria-label') || (e.labels && e.labels[0] && e.labels[0].innerText)
    || e.placeholder || (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName) ? '' : e.innerText) || e.value
    || e.title || e.name || e.id);
  const valueOf = (e) => {
    if (e.type === 'password') return e.value ? '***' : '';
    if (['checkbox', 'radio'].includes(e.type)) return e.checked ? 'checked' : '';
    if (e.tagName === 'SELECT') return clean([...e.selectedOptions].map((o) => o.text).join(', '));
    if (['INPUT', 'TEXTAREA'].includes(e.tagName)) return clean(e.value);
    return '';
  };
  document.querySelectorAll('[data-lct-ref]').forEach((e) => e.removeAttribute('data-lct-ref'));
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,[contenteditable=true],[role=button],[role=link],'
    + '[role=tab],[role=menuitem],[role=checkbox],[role=radio],[role=option],[role=combobox],[role=switch],[role=textbox]';
  // Every element gets its number, filter or not, so numbers stay the same across `lct page` calls.
  const rows = []; let n = 0, more = false;
  for (const e of document.querySelectorAll(sel)) {
    if (!visible(e) || e.disabled) continue;
    e.setAttribute('data-lct-ref', String(++n));
    const role = roleOf(e), name = nameOf(e), value = valueOf(e);
    const line = role + ' "' + name + '"' + (value ? ' = ' + value : '');
    if (f && !line.toLowerCase().includes(f)) continue;
    if (rows.length < max) rows.push('[' + n + '] ' + line); else more = true;
  }
  const heads = [...document.querySelectorAll('h1,h2,h3')].filter(visible).map((e) => clean(e.innerText)).filter(Boolean);
  const alerts = [...document.querySelectorAll('[role=alert],.error,.alert')].filter(visible).map((e) => clean(e.innerText))
    .filter(Boolean);
  return { title: document.title, url: location.href, heads: heads.slice(0, 8), alerts: alerts.slice(0, 3), rows, more };
}"""


def _fallback_map(page: Page, text_filter: str, limit: int = 60) -> list[str]:
    """Our own small extractor, used only if page-controller can't load on a page."""
    m = page.evaluate(PAGE_MAP_JS, {"filter": text_filter, "max": limit})
    lines = [f"headings: {' | '.join(m['heads'])}"] if m["heads"] else []
    lines += [f"alerts: {' | '.join(m['alerts'])}"] if m["alerts"] else []
    lines += [str(row) for row in m["rows"]]
    return lines + (["... more elements: narrow with `lct page <word>`"] if m["more"] else [])


# Main extractor: Alibaba page-agent's page-controller (DOM processing derived from browser-use),
# vendored as one MIT-licensed file. Indexed interactive elements + the text around them, whole page,
# open shadow DOM included. Each [N] is also stored on the element (data-lct-ref) for `--click N`.
_PC_INIT = (files("lct") / "vendor" / "page-controller.js").read_text(encoding="utf-8") + (
    "\n;const lctOpts = { highlightOpacity: 0, highlightLabelOpacity: 0 };"
    "\nwindow.__lctPC = window.__lctPC || new LctPageController.PageController({ ...lctOpts, viewportExpansion: -1 });"
    "\nwindow.__lctPCv = window.__lctPCv || new LctPageController.PageController({ ...lctOpts, viewportExpansion: 0 }); true")
_PC_STATE = """async ({ offset, view }) => {
  const pc = view ? window.__lctPCv : window.__lctPC;
  const s = await pc.getBrowserState();
  await pc.cleanUpHighlights();
  (window.__lctRefs || []).forEach((e) => e.removeAttribute('data-lct-ref'));
  window.__lctRefs = []; window.__lctDesc = {};
  const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
  let count = 0; const values = {};
  pc.selectorMap.forEach((node, i) => {
    const e = node.ref;
    e.setAttribute('data-lct-ref', String(offset + i)); window.__lctRefs.push(e); count = Math.max(count, i + 1);
    window.__lctDesc[offset + i] = { tag: e.tagName, id: e.id || '', name: e.getAttribute('name') || '', text: norm(e.innerText),
      label: norm(e.getAttribute('aria-label') || (e.labels && e.labels[0] && e.labels[0].innerText) || e.placeholder) };
    // current values (what was typed/selected), which the HTML attributes don't show
    if (e.tagName === 'SELECT') values[i] = [...e.selectedOptions].map((o) => o.text.trim()).join(', ');
    else if (e.tagName === 'TEXTAREA' || (e.tagName === 'INPUT' && !['checkbox', 'radio', 'submit', 'button', 'file']
      .includes(e.type))) values[i] = e.type === 'password' ? (e.value ? '***' : '') : e.value;
  });
  return { content: s.content, count, values };
}"""
# Same-origin iframes are already inside the parent's map; only cross-origin ones need their own pass.
_FRAME_COVERED_JS = "(el) => { try { return !!el.contentDocument; } catch (e) { return false; } }"
# Hidden interactive elements (display:none, zero size...), incl. open shadow DOM. Names only.
_HIDDEN_JS = """(list) => {
  const out = []; let n = 0;
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[role=tab],[role=menuitem]';
  const name = (e) => ((e.getAttribute('aria-label') || (e.labels && e.labels[0] && e.labels[0].innerText) || e.placeholder
    || e.textContent || e.value || e.name || e.id || '') + '').replace(/\\s+/g, ' ').trim().slice(0, 40);
  const walk = (root) => { for (const e of root.querySelectorAll('*')) {
    if (e.shadowRoot) walk(e.shadowRoot);
    if (!e.matches(sel)) continue;
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    if (r.width && r.height && s.visibility !== 'hidden' && s.display !== 'none') continue;
    n++; if (list && out.length < 40) out.push(e.tagName.toLowerCase() + ' "' + name(e) + '"');
  } };
  walk(document);
  return { n, out };
}"""


def page_map(page: Page, text_filter: str = "", hidden: bool = False, view: bool = False, max_chars: int = 8000) -> str:
    """Everything on the page AI needs, numbered: main page, iframes, open shadow DOM. Act with `--click N`.
    view=True: only what is on screen now (smaller for huge AJAX screens)."""
    settle(page)
    body: list[str] = []
    offset, hidden_count, hidden_names = 1, 0, []
    for frame in page.frames:
        if frame.is_detached() or (frame != page.main_frame and frame.url in ("", "about:blank")):
            continue
        if frame != page.main_frame:
            try:
                owner = frame.frame_element()
                if owner.evaluate(_FRAME_COVERED_JS):
                    continue
            except Exception:
                pass
        try:
            if not frame.evaluate("() => !!window.__lctPC"):
                frame.evaluate(_PC_INIT)
            state = frame.evaluate(_PC_STATE, {"offset": offset, "view": view})
            base, values = offset, {int(k): str(v) for k, v in dict(state["values"]).items() if str(v).strip()}

            def renumber(m: re.Match[str], base: int = base, values: dict[int, str] = values) -> str:
                i, rest = int(m.group(1)), m.group(2)
                current = " ".join(values.get(i, "").split())[:60]
                shown = current and f"value={current} " not in rest + " "
                return f"[{base + i}]<{rest}" + (f" = {current}" if shown else "")

            content = re.sub(r"^(\s*)\*", r"\1", str(state["content"]), flags=re.M)  # drop "new element" stars
            content = re.sub(r"\[(\d+)\]<(.*)$", renumber, content, flags=re.M)
            offset += int(state["count"])
        except Exception:
            if frame != page.main_frame:
                continue
            content = "\n".join(_fallback_map(page, ""))
        if frame != page.main_frame:
            body.append(f"--- iframe {frame.name or ''} {frame.url[:80]}")
        body += [line for line in content.splitlines() if line.strip()]
        try:
            h = frame.evaluate(_HIDDEN_JS, hidden)
            hidden_count += int(h["n"])
            hidden_names += [str(x) for x in h["out"]]
        except Exception:
            pass

    if text_filter:
        body = [line for line in body if text_filter.lower() in line.lower() or line.startswith("--- iframe")]
    lines = [f"{page.title()} | {page.url}"]
    size = 0
    for i, line in enumerate(body):
        size += len(line) + 1
        if size > max_chars:
            lines.append(f"... {len(body) - i} more lines: narrow with `lct page <word>`")
            break
        lines.append(line)
    if hidden:
        lines.append(f"hidden ({hidden_count}): " + (" | ".join(hidden_names) or "none"))
    elif hidden_count:
        lines.append(f"hidden elements: {hidden_count} (names: `lct page --hidden`)")
    return "\n".join(lines)


def page_text(page: Page, selector: str = "", limit: int = 2000) -> str:
    target = page.locator(selector).first if selector else page.locator("main, [role=main], body").first
    text = " ".join(str(target.inner_text()).split())
    return text[:limit] + (f" ... ({len(text)} chars, use a selector to narrow)" if len(text) > limit else "")


def write_result(test_id: str, step: int, ok: bool, actual: str) -> None:
    """Stores Pass/Fail + actual for one step in qa/testcases/<id>.json."""
    file = QA / "testcases" / f"{test_id}.json"
    if not file.exists():
        return
    tc = json.loads(file.read_text(encoding="utf-8"))
    steps = tc.get("steps", [])
    if 0 < step <= len(steps):
        steps[step - 1]["result"] = "Pass" if ok else "Fail"
        steps[step - 1]["actual"] = actual
        file.write_text(json.dumps(tc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
