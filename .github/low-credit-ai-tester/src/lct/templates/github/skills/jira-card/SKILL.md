---
name: jira-card
description: Open Jira/Atlassian, read a Jira card (story, bug, retest) and write its test case. Use when the user mentions Jira, Atlassian, a card, ticket, story, bug or a key like PROJ-123.
argument-hint: '<card link or key> [app=<name>] [env=<QA|UAT>]'
---
- Jira login: `lct open jira` (or the card link). If a login page shows, tell the user to log in in that Edge window, then continue.
- Read a card: `lct jira <link|key>`, then read only the `qa/jira/<KEY>.md` it prints. Images only if the text is unclear: rerun with `--attachments` and open one.
- Test case: write `qa/testcases/<KEY>.json` (schema `qa/testcases/testcase.schema.json`): `description` in 1-2 lines, short steps with one expected result each, `jira` link, `environment.app/url/name` if given.
- Reply: max 5 bullets (what changed, what will be checked).
- Never create, edit, move or comment on Jira issues.
