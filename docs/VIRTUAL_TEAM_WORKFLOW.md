# Shout Virtual Office - Remote Team Collaboration Workflow

This document defines how the virtual remote team members (Sarah, Liam, Chloe, Aiden) perform their "work" asynchronously using **GitHub Projects (Kanban Board)**, **GitHub Issues (Tickets)**, **GitHub Wiki (Specs)**, **Slack (Chat)**, and **GitHub PRs (Code)**.

---

## 1. Remote Team Tool Suite

```text
  [Slack]           <== Async Chat & Alerts ==>  Daily Standups, Discussions
  [GitHub Project]  <== Tasks & Board Columns ==> Todo -> In Progress -> Done (Kanban)
  [GitHub Issues]   <== Detailed Tickets =======> Created from Slack/Board, Comment Threads
  [GitHub Wiki]     <== PRDs, Specs, Wiki =====> Spec Sheets, API Definitions
  [GitHub PRs]      <== Code Repository ========> Commits, Pull Request Diff
```

All interactions use your **GitHub CLI session** and Slack Webhooks. Comments written by the AI are prefixed with their names and emojis (e.g. `🐨 [Aiden - Tech Lead]`) to show who is speaking.

---

## 2. Daily Coworker Routine & "Work"

### 🦊 Liam (Product Manager)
- **Daily Project Triage**: Checks the status of the GitHub Project board. If you transition an issue or update a task's column, Liam writes a comment acknowledging it on the corresponding GitHub Issue: *"Awesome, Kong! Let me know if you need any clarification on the user stories."*
- **Creating Tickets**: If a new sprint begins or a new feature is discussed in Slack, Liam automatically creates a GitHub Issue (e.g. `[ISSUE_CREATE: Summary | Description]`) and files it.
- **Spec Documentation**: When creating a ticket, Liam writes a detailed PRD in **GitHub Wiki** (`[WIKI_WRITE: Page Title]`) and links it in the issue description.

### 🐨 Aiden (Tech Lead)
- **PR Code Review**: When you push code and open a PR on GitHub, Aiden reads the git diff. He analyzes it for edge cases (especially WebSocket sync, database connection drops, or state consistency) and leaves code review comments on the PR.
- **Tech Spec Writing**: If database models or system architecture need to be documented, Aiden edits the GitHub Wiki pages to update the database models and types.
- **Tech Lead Catchphrases**: Leaves warnings like: *"Looks fine, but what happens when the DB connection drops?"* on GitHub and Slack.

### 🦄 Chloe (Sales & Marketing)
- **UI Reference Harvesting**: When Liam opens a UI-related issue (e.g. "Stripe payment selection page"), Chloe triggers a web search to find competitor UI layouts, Dribbble, or Behance references, writing them as comments in the GitHub Issue: *"Hey Kong, love the vibe! Here are some cool UI layouts I found on the web for card checkout: [link1], [link2]."*
- **Customer Feedback Injection**: Periodically injects mock feedback from beta testers into GitHub Issues: *"Users are saying the payment card button is too hard to tap on mobile screens. We need to increase the touch target."*

### 🦁 Sarah (CEO)
- **Directives & Milestones**: Checks the calendar countdown to investor meetings. Posts urgency alerts on Slack and GitHub Issues: *"We have 14 days before the board review. Kong, is the payment gateway loop on track?"*
- **Financial Metric Reviews**: If you implement a transaction calculation, Sarah reviews the fee calculation logic in the PR to ensure the startup makes its 1.5% margin.

---

## 3. How the Local Simulator Drives the Team

The simulator runs locally on your machine. When you run `./app/main.sh` (or trigger it on code pushes/GitHub Project card changes), it runs the following loop:

```text
[Loop Check]
   ||
   +--> 1. Check GitHub Project cards for transitions (Todo -> In Progress -> Done)
   |       ==> Notify Liam to react or update GitHub Wiki.
   |
   +--> 2. Check GitHub for new Commits/PRs
   |       ==> Notify Aiden to review diffs and leave PR comments.
   |
   +--> 3. Check Slack for user queries / discussions
   |       ==> Route to appropriate characters, draft, validate, and reply.
   |
   +--> 4. Trigger scheduled business events (e.g. Chloe's UI references or Sarah's deadline pings)
```
This event-driven execution ensures the team is alive, active, and coordinating with you exactly like real remote coworkers.
