# Low Credit AI Tester Kit (`lct`)

Copilot does the thinking; `lct` commands do the work and print 1–2 lines. That's what keeps AI credits low.

## Install (once per laptop)

1. Copy the `.github` folder into your repo root. If the repo already has a `.github`, copy only `.github\low-credit-ai-tester` into it.
2. In a terminal in the repo root, run:
   ```powershell
   uv venv .venv
   uv pip install --python .venv\Scripts\python.exe --index-url https://<company-index>/simple -r .github\low-credit-ai-tester\requirements.txt -e .github\low-credit-ai-tester
   .venv\Scripts\lct init
   ```
   You can also ask Copilot: *".github/low-credit-ai-tester/README.md follow karke kit install karo, index URL: …"*.
   If you get an SSL/certificate error, add `--native-tls` to the `uv pip install` command.
3. Reload VS Code.
4. Fill in `qa/.env`: for each app, add `APP_<NAME>_URL`, `APP_<NAME>_USER` and `APP_<NAME>_PASS`, plus `JIRA_URL`.

`lct init` puts the Copilot rules and skills into `.github/`. It also creates `qa/` and VS Code settings. No browser download is needed: the kit uses your Edge.

## Use (ask Copilot in any order, Agent mode, model **Auto**)

| Say | What happens |
|---|---|
| "Jira open karo" / `/jira-card <link>` | Edge opens. You log in once (it stays remembered), and the card is saved as a short text file |
| "App mein login karo, Phone field check karo" / `/run-test PROJ-123` | Logs in from `qa/.env`. Each step: action, check, red box, full-screen HD snap |
| "DOCX bana do" / `lct report` | Word report: URL, environment, username, password, Jira card, description, steps + snaps (0 tokens) |
| "Repo X refer karke Ruby/Playwright script likho" / `/write-automation` | Searches the indexes, opens max 2 files. GitHub MCP: 4 read-only tools |
| Copilot asks "Kit fix kar doon?" | It found a problem in the kit. Say yes and it fixes the kit (skill `improve-kit`), tests the fix and logs it in `CHANGELOG.md`. Push `.github` to share the fix |

Notes:
- Don't use the PC while the AI is testing: the browser comes to the front for each snap. Set `QA_SNAP_MODE=page` in `qa/.env` to keep working, or `LCT_HEADLESS=1` to keep the browser hidden.
- Keep passwords in `qa/.env` only, not in chat.
- Start a new chat for each card.
- Reference repos: `git clone --depth 1 <url> qa/repos/<name>`, then `lct index`.

## Commands

`lct status` · `open <url|app|jira>` · `login <app>` · `page [word]` · `act ...` · `step <id> <n> ...` · `snap <id> [--hotkey]` · `jira <link>` · `index` · `report [id]` · `demo` · `close`. Run `lct -h` for details.

Try it: run `lct demo`, then in Copilot `/run-test DEMO-101`, then `lct report`.

## Problems

| Message | Fix |
|---|---|
| `debugging port didn't open` | The company blocks Edge remote debugging. Ask IT, or set `LCT_CDP_PORT` if another program uses port 9333 |
| `lct` not found | Reload VS Code, or use `.venv\Scripts\lct` |
| Login form not filled | Set `APP_<NAME>_USER_FIELD`, `_PASS_FIELD` and `_SUBMIT` (CSS selectors) in `qa/.env` |
| `Not logged in to Jira` | Log in in the kit's Edge window, then run again |
| `browser-only capture` | The screen was locked or you were using another window |
