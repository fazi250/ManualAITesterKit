---
name: run-test
description: Anything in a web page - open a URL, log in, navigate menus, click, fill or check forms and fields, highlight, take full-screen evidence snaps, run a test case step by step. Use for app URL/login/username/password, forms, menus, snaps or screenshots, retest and manual testing.
argument-hint: '<test id> or what to do on the page'
---
- Use the kit browser (`lct`), not VS Code browser tools, unless the user names "VS Code browser".
- Login: `lct login <app>` (APP_<APP>_URL/_USER/_PASS in `qa/.env`). If the user gave URL/username/password in chat, save them there first. Never repeat the password.
- See the page: `lct page [word]` = numbered map incl. iframes and shadow DOM, e.g. `[7]<button >Submit />`. Add a word to keep it short. Big/AJAX screens: `lct page --view`. Hidden: `lct page --hidden`.
- Act by NUMBER. Menus that open on hover (mega menus): `--hover N`, then `lct page <word>` to get the sub-item number.

Test case rules (the report is built from these, so follow them exactly):
1. First write `qa/testcases/<ID>.json` (ID = Jira key or TC-<n>): ONE step per screen/state you want a screenshot of.
   Example: "Fill Name/Email/Phone" = 1 step; "Hover menu, click Online Trainings" = 1 step; "New page opened" = next step.
2. Run EVERY step with `lct step` - that is what takes the snap, draws the red boxes and writes Pass/Fail:
   `lct step <id> <n> [--hover N] [--click N] [--fill "N=value"] [--select "N=option"] [--check N] [--press <key>] --expect "<text>" | --read N`
   Fields you fill/select/check/read get a red box automatically; `--mark N` boxes anything else.
3. Never use `lct act` or `lct snap` for a test step, and never write `result`/`actual` into the JSON yourself.
4. Always give `--expect` or `--read`. Max 2 tries per step; on Fail continue. Use `lct act` only to get somewhere between steps.

- Can't understand something from text (canvas, chart, image-only)? ASK first: "Kya main screenshot dekh sakta hoon? Isme zyada tokens lagenge." Only after yes: `lct shot [N]`, then open the printed image.
- Never look at evidence snaps. Reply with only the `lct step` result lines.
