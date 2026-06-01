# 📐 GitHub Template Formats for Virtual Office Agents

This folder defines the formatting standards that all Virtual Office agents must follow
when writing to GitHub — Issues, Wiki pages, and PR/Issue comments.

---

## 📂 Files

| File | Purpose |
|------|---------|
| [`issue_format.py`](./issue_format.py) | Templates for `[ISSUE_CREATE:]` — Bug, Feature, Task |
| [`wiki_format.py`](./wiki_format.py) | Templates for `[WIKI_WRITE:]` — Tech Spec, Sprint Summary, Research, Runbook |
| [`pr_comment_format.py`](./pr_comment_format.py) | Per-persona comment templates for PR/Issue replies |

---

## 🏗️ How It All Connects

```
Agent output text
      │
      ├─── [WIKI_WRITE: Page Title]   ──► wiki_format.py    ──► queue_manager.sh → GitHub Wiki
      │
      ├─── [ISSUE_CREATE: Title | Body] ► issue_format.py   ──► queue_manager.sh → GitHub Issues
      │
      └─── target_channel: "github"    ► pr_comment_format.py ► queue_manager.sh → Issue/PR comment
```

---

## 👤 Who Writes What

| Agent | Issues | Wiki | PR Comments |
|-------|--------|------|-------------|
| **Aiden** (Tech Lead) | Bug reports, sprint tasks | Tech specs, ADRs, runbooks | Code review (`CODE_REVIEW_TEMPLATE`) |
| **Liam** (PM) | Feature requests, sprint tasks | Sprint summaries, retros | PM sign-off (`PM_REVIEW_TEMPLATE`) |
| **Sarah** (CEO) | Feature requests (strategic) | OKRs, strategy docs | Business impact (`CEO_COMMENT_TEMPLATE`) |
| **Chloe** (Sales) | Feature requests (GTM/UX) | Research, competitor notes | Customer feedback (`SALES_COMMENT_TEMPLATE`) |

---

## 📋 GitHub-Native Templates (shout repo)

The `shout/.github/` directory contains GitHub-native templates that are used
when anyone (human or agent) creates an issue or PR via the GitHub UI.

```
shout/.github/
├── ISSUE_TEMPLATE/
│   ├── config.yml          # Disables blank issues, links to Slack
│   ├── bug_report.md       # 🐛 Bug report template
│   ├── feature_request.md  # ✨ Feature request template
│   └── sprint_task.md      # 🏃 Sprint task template
└── pull_request_template.md  # PR description template
```

These are the **human-facing** equivalents of the agent format guides above.
Agent-generated issues and wiki pages should match the same structure.

---

## 📏 Key Rules (TL;DR for agents)

1. **Pick the right template** — don't use a feature template for a bug.
2. **Fill every placeholder** — `{PLACEHOLDER}` in output = fail.
3. **End with your catchphrase** — PR comments only. No exceptions.
4. **Keep wiki titles kebab-case** — `ADR-001-Auth-Strategy`, not `ADR 001 auth strategy`.
5. **PR comments under 20 lines** — reviewers won't read walls of text.
6. **Never duplicate** — if another agent already covered it, stay silent.
