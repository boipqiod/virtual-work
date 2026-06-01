# Shout Virtual Office - System Architecture & Integration Guide

This document defines the complete decoupled system architecture of the Shout Virtual Office simulator. It details the separation of concerns between input collection, AI reasoning, action execution, and the daily automated planning scheduler.

---

## 1. Architectural Philosophy: Decoupled Interests

To keep the system scalable, robust, and cost-effective, the simulator is split into three decoupled vertical programs and one autonomous scheduler:

```text
                     +---------------------------------------+
                     |            DEVELOPER (YOU)            |
                     +---------------------------------------+
                       /                 |                 \
                 Pushes Code         Checks Slack      Updates Issues
                       /                  |                   \
                      \/                  \/                  \/
                 [GitHub]              [Slack]          [GitHub Issues]
                      |                   |                    |
                      |                   |                    |
                      \/                  \/                   \/
             +-----------------------------------------------------+
             |              PROGRAM 1: THE SENSORS                 |  <-- Programmatic I/O
             |  (Slack Poller, GitHub Poller, GitHub Issue Poller) |      (No AI overhead)
             +-----------------------------------------------------+
                                         ||
                                Writes Event JSON to
                                         ||
                                         \/
                         📂 agent_io/inbox/current_event.json
                                         ||
                                  Triggers Pipeline
                                         ||
                                         \/
             +-----------------------------------------------------+
             |               PROGRAM 2: THE BRAIN                  |  <-- AI Injection Point
             |   (Router ==> Parallel Personas ==> Validator)      |      (LLM API Processing)
             +-----------------------------------------------------+
                                         ||
                                  Reads Evolving Specs from
                                         ||
                                         \/
                              📂 docs/ & agent_io/memory/
                                         ||
                                Writes Response JSON to
                                         ||
                                         \/
                         📂 agent_io/outbox/final_response.json
                                         ||
                                  Triggers Dispatcher
                                         ||
                                         \/
             +-----------------------------------------------------+
             |             PROGRAM 3: THE ACTUATORS                |  <-- Programmatic I/O
             |   (Slack Webhook, GitHub PR/Issue, GitHub Wiki)     |      (No AI overhead)
             +-----------------------------------------------------+
                     |                   |                    |
                     \/                  \/                   \/
                [Slack Web]         [GitHub PR]         [GitHub Issue]
```

---

## 2. Component Specifications

### 📡 Program 1: The Sensors (Deterministic Input)
- **Responsibility**: Checks for changes in the external communication tools. It has no AI logic and runs quickly to parse raw data.
- **Operations**:
  - `slack_client.sh`: Polls Slack and parses message details.
  - `github_client.sh`: Monitors commits, PR creations, reviews, and issue status changes using `gh api`.
- **Output**: Writes a standard JSON payload to `agent_io/inbox/current_event.json` and halts.

### 🧠 Program 2: The Brain (AI Processor)
- **Responsibility**: Handles cognitive evaluation. It is the **only** AI injection point in the architecture, saving costs by only invoking the LLM when an event is queued.
- **Operations**:
  - **Router**: Analyzes the event and chooses who replies and where (Slack, GitHub Issues, GitHub PR, or GitHub Wiki).
  - **Persona Engines**: Selected agents write drafts. They dynamically query the `docs/` folder (the live source of truth for the company) to verify if their feedback matches the project goals.
  - **Validator**: Checks for robotic or overly polite phrases, forcing a strict Aussie/Irish casual tech tone.
- **Output**: Writes a response JSON payload containing target destination keys to `agent_io/outbox/final_response.json`.

### ⚙️ Program 3: The Actuators (Deterministic Output)
- **Responsibility**: Takes finalized responses and maps them to their respective endpoints.
- **Operations**:
  - **Slack Dispatches**: Posts to incoming webhooks.
  - **GitHub Dispatches**: Writes comments directly to the active PR review log (`gh pr comment`) or GitHub Issues (`gh issue comment`).
  - **GitHub Wiki Dispatches**: Updates wiki pages via git push.
- **Prefix Formatting**: All bot actions are performed via your GitHub CLI session. To show who is speaking, the Actuator prepends the character’s profile header to the text body:
  - `🦊 [Liam - PM]: ...`
  - `🐨 [Aiden - Tech Lead]: ...`

---

## 📅 3. The Daily Planning Scheduler (Standup Engine)

To make the virtual team feel like active remote workers rather than passive responders, a daily cron job triggers the **Standup Engine**:

```text
[09:00 AM Cron Trigger]
        ||
        \/
1. Writes 'daily_planning_trigger' event to inbox/current_event.json
        ||
        \/
2. Brain reads:
   - Current files in docs/ (evolving specs)
   - Current issues in GitHub Issues (active sprint tickets)
   - Developer's recent git commit logs
        ||
        \/
3. Liam (PM) & Sarah (CEO) evaluate sprint health:
   - Identify blocking issues or lagging tickets.
   - Create new task requirements (user stories).
        ||
        \/
4. Actuator executes plan:
   - Creates new issues directly on your GitHub Issues.
   - Posts the "Daily Focus & Team Standup" briefing to the Slack channel.
```

---

## 📋 4. Evolving Goals & Source of Truth

- **Docs Directory as the Core**: Since startup goals shift, you (the developer) own the documentation in `docs/`. 
- **Dynamic Adaptability**: The Brain program reads these documents on every run. If you update the tech spec or product direction, the team immediately shifts their daily planning alignment and PR reviews to match the new rules.
