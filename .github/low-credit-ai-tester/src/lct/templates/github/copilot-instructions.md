<!-- low-credit-ai-tester:start -->
# QA kit (`lct`): keep tokens low
- Requests come in any order. Unsure which test/page we're on: `lct status` (one line).
- Any web page work (open URL, login, click, forms, snaps) uses the kit browser via `lct` (skill run-test), not VS Code browser tools, unless I say "VS Code browser".
- Use the skills jira-card, run-test, test-report, write-automation. `lct` commands print 1-2 lines. If `lct` isn't found, use `.venv\Scripts\lct`.
- Choose page elements by the numbers `lct page` prints (`--click 7`), don't guess selectors.
- Answers: short bullets, no summaries, don't repeat my input or file contents.
- Need to see an image? Ask me first (images cost more tokens), then `lct shot [N]`.
- Never: read screenshots without my yes, print passwords, create/edit/comment on Jira, write reports yourself, read `qa/*-index.md` whole.
<!-- low-credit-ai-tester:end -->
