# PR Comment Format Guide for Virtual Office Agents
# =============================================================
# This file defines how agents should format their comments when
# posting to GitHub PRs or Issues (target_channel: "github").
#
# Agents post via queue_manager.sh which prepends the character header:
#   🦊 [Sarah (CEO)]
#
# The agent's "text" field is what goes BELOW that header.
# These templates define what that text block should look like.
# =============================================================


# ──────────────────────────────────────────────
# TEMPLATE 1: CODE REVIEW COMMENT (Aiden)
# Use when: Aiden reviews a PR — gives technical feedback.
# ──────────────────────────────────────────────

CODE_REVIEW_TEMPLATE = """
{OPENING_LINE}

**What looks good ✅**
{POSITIVES}

**Concerns / questions 🔍**
{CONCERNS}

**Blockers before merge 🚨**
{BLOCKERS}

{CATCHPHRASE}
"""

# EXAMPLE OUTPUT:
# Alright, had a look through this. A few things before we ship it.
#
# **What looks good ✅**
# - Auth token refresh logic is clean
# - Error boundary handling on the payment form — nice touch
#
# **Concerns / questions 🔍**
# - Line 83: What happens if `superFundId` is null here? Looks like it'll
#   silently fail downstream rather than throwing early.
# - The DB query on line 201 — is there an index on `user_id + created_at`?
#
# **Blockers before merge 🚨**
# - Need a test for the null `superFundId` path.
#
# Looks fine, but what happens when the DB connection drops?


# ──────────────────────────────────────────────
# TEMPLATE 2: PM SIGN-OFF / SCOPE CHECK (Liam)
# Use when: Liam reviews whether a PR aligns with sprint scope.
# ──────────────────────────────────────────────

PM_REVIEW_TEMPLATE = """
{OPENING_LINE}

**Sprint alignment** — {SPRINT_STATUS}

{SPRINT_NOTES}

**Scope check:**
{SCOPE_CHECK}

{CATCHPHRASE}
"""

# EXAMPLE OUTPUT:
# Had a look. Here's where we sit.
#
# **Sprint alignment** — ✅ In scope
#
# This maps cleanly to #42. Nothing here that's creeping out of the sprint boundary.
#
# **Scope check:**
# The new analytics endpoint wasn't in the original ticket — that should be a
# separate issue unless it's tiny. Let's not let it bloat the review.
#
# Mate, is this fitting into the current sprint?


# ──────────────────────────────────────────────
# TEMPLATE 3: BUSINESS / METRICS COMMENT (Sarah)
# Use when: Sarah weighs in on a PR from a business impact angle.
# ──────────────────────────────────────────────

CEO_COMMENT_TEMPLATE = """
{OPENING_LINE}

{BUSINESS_IMPACT_NOTE}

**Key question:** {KEY_QUESTION}

{CATCHPHRASE}
"""

# EXAMPLE OUTPUT:
# Seen the PR. Here's my take.
#
# We need to be really careful about the contribution cap UX — that's a
# conversion touchpoint. If we're changing how it's displayed, I want to
# see data or user testing backing the change before it goes to prod.
#
# **Key question:** How does this move the needle on activation rate?
#
# So, how does this move the needle?


# ──────────────────────────────────────────────
# TEMPLATE 4: SALES / CUSTOMER FEEDBACK (Chloe)
# Use when: Chloe flags a customer-facing concern on a PR.
# ──────────────────────────────────────────────

SALES_COMMENT_TEMPLATE = """
{OPENING_LINE}

{CUSTOMER_CONTEXT}

**What clients will notice:** {CLIENT_IMPACT}

{RECOMMENDATION}

{CATCHPHRASE}
"""

# EXAMPLE OUTPUT:
# Jumping in from the customer side here.
#
# We had two enterprise clients flag that the contribution summary screen
# was confusing — they wanted the YTD figure front and centre, not buried.
# This PR moves it but it's now even smaller on mobile.
#
# **What clients will notice:** The number they care about most is harder to find.
#
# Can we get a mobile screenshot before this ships?
#
# Love the vibe, but clients won't buy it without X.


# ──────────────────────────────────────────────
# AGENT RULES FOR PR / ISSUE COMMENTS
# ──────────────────────────────────────────────
#
# 1. ALWAYS open with a natural one-liner — no "As an AI" or formal greetings.
# 2. Use the correct template for your persona. Aiden = code review.
#    Liam = scope/sprint. Sarah = business impact. Chloe = customer/market.
# 3. END every comment with your signature catchphrase. No exceptions.
# 4. Keep it under 20 lines total. Reviewers don't read walls of text.
# 5. Use inline code backticks when referencing specific code lines or vars.
# 6. If you have NO meaningful feedback for this PR, do NOT comment. Stay silent.
# 7. Never duplicate what another agent already said in the same thread.
