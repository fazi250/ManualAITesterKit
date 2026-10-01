---
name: install-kit
description: Install or update the Low Credit AI Tester Kit (lct) in this repo. Use when the user asks to install, set up or update the kit.
argument-hint: '<company python index url ending in /simple>'
---
Run from the repo root, one by one (kit folder: `.github\low-credit-ai-tester`):
1. `uv venv .venv` (skip if `.venv` exists)
2. `uv pip install --python .venv\Scripts\python.exe --index-url <index url> -r .github\low-credit-ai-tester\requirements.txt -e .github\low-credit-ai-tester` (SSL/certificate error: add `--native-tls`)
3. `.venv\Scripts\lct init`

Reply in 2 lines: done or the error, then "Reload VS Code and fill qa/.env".
