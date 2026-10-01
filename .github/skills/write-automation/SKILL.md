---
name: write-automation
description: Write or change automation scripts - Cucumber Ruby features/step definitions, Playwright API or UI tests - reusing the existing framework and references from dev repos or GitHub. Use for new scripts, scenarios, step definitions, API tests, or "refer to repo X".
argument-hint: '<what to automate> [repo]'
---
1. Search `qa/steps-index.md` (step definitions, page objects) and `qa/test-index.md` (tests) for the closest match. Don't read them whole. Missing or old: `lct index`.
2. Open at most 2 files, only around the listed lines.
3. Repo not in `qa/repos/`: GitHub `search_code` with `repo:`/`org:` and `path:` qualifiers, then `get_file_contents` for one file. (Often-used repo: clone it into `qa/repos/` and run `lct index`, cheaper.)
4. Reuse existing steps, page objects and helpers; match step wording exactly. New step definitions go next to similar ones, same style. API tests: typed response interfaces, assert status then only the needed fields.
5. Code only, no explanation.
