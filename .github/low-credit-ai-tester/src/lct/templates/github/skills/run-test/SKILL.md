---
name: run-test
description: Anything in a web page - open a URL, log in, navigate, click, fill or check forms and fields, highlight, take full-screen evidence snaps, run a test case step by step. Use for app URL/login/username/password, forms, snaps or screenshots, retest and manual testing.
argument-hint: '<test id> or what to do on the page'
---
- Use the kit browser (`lct`), not VS Code browser tools, unless the user names "VS Code browser".
- Login: `lct login <app>` (APP_<APP>_URL/_USER/_PASS in `qa/.env`). If the user gave URL/username/password in chat, save them there first. Never repeat the password.
- See the page: `lct page [word]` = numbered map of the whole page incl. iframes and shadow DOM, e.g. `[7]<button >Submit />`. Know what you need? Add a word to keep it short. Hidden elements: `lct page --hidden`.
- Big/AJAX screens (ClaimCenter etc.): `lct page --view` = only what is on screen; or `lct page <word>`. lct waits for AJAX after every action by itself; don't add `--wait`.
- Act by NUMBER: `lct act --click 7 --fill "11=9876543210" --select "20=India"`. Re-rendered elements keep their number; if lct says a ref is gone, run `lct page` again.
- No test case yet: create `qa/testcases/<ID>.json` (ID = Jira key or TC-<n>; steps = what you'll check).
- Each test step = ONE command (acts, checks, red box, full-screen snap, Pass/Fail into the JSON):
  `lct step <id> <n> [--click N] [--fill "N=value"] [--select "N=option"] [--press <key>] --expect "<text>" | --read N [--mark N]`
- Always give `--expect` or `--read`. Max 2 tries per step; on Fail continue.
- Can't understand something from text (canvas, chart, image-only, layout)? ASK first: "Kya main screenshot dekh sakta hoon? Isme zyada tokens lagenge." Only after yes: `lct shot [N]` (N = just that element, fewer tokens), then open the printed image.
- Never look at evidence snaps. Reply with only the result lines.
