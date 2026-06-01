# Wiki Document Format Guide for Virtual Office Agents
# =============================================================
# This file defines the EXACT markdown structure that agents must output
# when using the [WIKI_WRITE: Page Title] trigger.
#
# RULE: The content after [WIKI_WRITE: Page Title] must follow the
# appropriate template below based on the document type.
# =============================================================


# ──────────────────────────────────────────────
# TEMPLATE 1: TECHNICAL SPEC / ADR
# Use when: documenting an architecture decision, system design, or tech spec.
# Page title convention: "ADR-{N}-{Short-Title}" e.g. "ADR-001-Auth-Strategy"
# ──────────────────────────────────────────────

TECH_SPEC_TEMPLATE = """
# {PAGE_TITLE}

> **Author:** {AGENT_NAME} ({AGENT_ROLE})
> **Date:** {DATE}
> **Status:** Draft | Proposed | Accepted | Superseded

---

## 🧭 Context

<!-- Why does this decision / spec need to exist? What problem are we solving? -->
{CONTEXT}

## 🎯 Decision / Proposed Approach

<!-- What are we doing? Be concrete. -->
{DECISION}

## 🔀 Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| {OPTION_1} | {PROS_1} | {CONS_1} |
| {OPTION_2} | {PROS_2} | {CONS_2} |

## 📐 Technical Details

{TECHNICAL_DETAILS}

## ✅ Acceptance / Success Criteria

- {CRITERION_1}
- {CRITERION_2}

## ⚠️ Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| {RISK_1} | High/Med/Low | {MITIGATION_1} |

## 🔗 Related

- Issues: #{ISSUE_NUMBER}
- Slack thread: {SLACK_LINK}

---
*Last updated by {AGENT_NAME} on {DATE}*
"""


# ──────────────────────────────────────────────
# TEMPLATE 2: SPRINT RETROSPECTIVE / STANDUP SUMMARY
# Use when: Liam posts sprint notes, retro outcomes, or weekly summaries.
# Page title convention: "Sprint-{N}-Retro" or "Week-{YYYY-WW}-Summary"
# ──────────────────────────────────────────────

SPRINT_SUMMARY_TEMPLATE = """
# {PAGE_TITLE}

> **Author:** Liam (PM)
> **Date:** {DATE}
> **Sprint:** {SPRINT_NUMBER}

---

## ✅ What we shipped

{SHIPPED_ITEMS}

## 🚧 What's still in progress

{IN_PROGRESS_ITEMS}

## 🔴 Blockers & Risks

{BLOCKERS}

## 💬 Team Highlights

{TEAM_HIGHLIGHTS}

## 📅 Next sprint focus

{NEXT_SPRINT}

## 📊 Metrics snapshot

| Metric | Value |
|--------|-------|
| Velocity | {VELOCITY} pts |
| Bugs opened | {BUGS_OPENED} |
| Bugs closed | {BUGS_CLOSED} |

---
*Compiled by Liam (PM) on {DATE}*
"""


# ──────────────────────────────────────────────
# TEMPLATE 3: RESEARCH / MARKET NOTES
# Use when: Chloe or Sarah drops competitive research, market notes, or GTM docs.
# Page title convention: "Research-{Topic}" e.g. "Research-Competitor-SuperApp"
# ──────────────────────────────────────────────

RESEARCH_TEMPLATE = """
# {PAGE_TITLE}

> **Author:** {AGENT_NAME} ({AGENT_ROLE})
> **Date:** {DATE}

---

## 🎯 Research Goal

{RESEARCH_GOAL}

## 🔍 Key Findings

{KEY_FINDINGS}

## 📊 Competitive Landscape

| Competitor | Strengths | Weaknesses | Our angle |
|-----------|-----------|------------|-----------|
| {COMP_1} | {STR_1} | {WEAK_1} | {ANGLE_1} |

## 💡 Recommendations

{RECOMMENDATIONS}

## 🔗 Sources

{SOURCES}

---
*Research compiled by {AGENT_NAME} on {DATE}*
"""


# ──────────────────────────────────────────────
# TEMPLATE 4: HOW-TO / RUNBOOK
# Use when: Aiden documents a process, deployment step, or operational runbook.
# Page title convention: "Runbook-{Topic}" e.g. "Runbook-Deploy-Prod"
# ──────────────────────────────────────────────

RUNBOOK_TEMPLATE = """
# {PAGE_TITLE}

> **Author:** {AGENT_NAME} ({AGENT_ROLE})
> **Date:** {DATE}
> **Last tested:** {LAST_TESTED}

---

## 🧭 Overview

{OVERVIEW}

## ⚡ Prerequisites

- {PREREQ_1}
- {PREREQ_2}

## 🪜 Steps

### Step 1 — {STEP_1_TITLE}

{STEP_1_DETAILS}

```bash
{STEP_1_COMMAND}
```

### Step 2 — {STEP_2_TITLE}

{STEP_2_DETAILS}

## ✅ Verification

{VERIFICATION}

## 🚨 Rollback

{ROLLBACK_STEPS}

## 🔗 Related

- Issue: #{ISSUE_NUMBER}

---
*Written by {AGENT_NAME} on {DATE}*
"""


# ──────────────────────────────────────────────
# AGENT RULES FOR WIKI WRITING
# ──────────────────────────────────────────────
#
# 1. ALWAYS pick the correct template type for the content.
# 2. Fill in ALL {PLACEHOLDER} fields. Empty placeholders = invalid doc.
# 3. Page title (arg after WIKI_WRITE:) becomes the filename. Use kebab-case:
#    e.g. "ADR-001-Auth-Strategy" → ADR-001-Auth-Strategy.md
# 4. Do NOT wrap the content in code fences — write raw markdown.
# 5. Every doc must have an author line and date at the top.
# 6. Keep docs under ~500 lines. Long docs should be split into sub-pages.
#
# WHO WRITES WHAT:
#   - Aiden (Tech Lead)  → Tech specs, ADRs, runbooks
#   - Liam (PM)          → Sprint summaries, retros, project plans
#   - Sarah (CEO)        → OKRs, strategic notes (rarely)
#   - Chloe (Sales/Mkt)  → Research notes, GTM docs, competitor analysis
