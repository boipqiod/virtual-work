# Shout Virtual Office - Simulator Flow & Architecture

This document explains how the virtual startup simulator operates in the background. It details how messages flow from Slack, get processed by the AI team, and get posted back.

---

## 1. High-Level Flow (How it Works)

The simulator is split into two tracks: **Track A (The Runner Scripts)** and **Track B (The AI Harness)**. They communicate exclusively through files in the `agent_io/` folder.

```text
[Step 1: Ingestion]   ──> Polls Slack/GitHub and saves event to:
                          📂 agent_io/inbox/current_event.json
                                 ||
                                 \/
[Step 2: AI Runner]    ──> Triggers Python Orchestrator:
                          🐍 app/ai_runner.py
                                 ||
                                 \/
[Step 3: AI Pipeline]  ──> 1. Router: Chooses who speaks (Aiden, Liam, etc.)
                          2. Persona: Drafts replies using:
                             - config_harness/subagent_prompts/persona_*.txt
                             - docs/ (Your specs: CEO_Sarah, PM_Liam, etc.)
                             - agent_io/memory/ (Previous chat history)
                          3. Validator: Rejects robotic or too-polite text.
                                 ||
                                 \/
[Step 4: Output]       ──> Saves final replies to:
                          📂 agent_io/outbox/final_response.json
                                 ||
                                 \/
[Step 5: Dispatch]     ──> Sends webhooks back to Slack channel.
```

---

## 2. Directory Map (What is Where?)

### ⚙️ `app/` (The Engine)
- `main.sh`: The orchestrator loop. Runs in the background, checks for events, runs the AI, and dispatches responses.
- `ai_runner.py`: The brain. Manages the AI stages (Routing -> Drafting -> Validating).
- `slack_client.sh` & `github_client.sh`: Ingestion scripts that poll APIs and fetch new messages or events.
- `queue_manager.sh`: Sends finalized AI messages back to your Slack channel via webhooks.

### 📥 `agent_io/` (The Postbox & Memory)
- `inbox/current_event.json`: The latest message received from Slack.
- `outbox/final_response.json`: The queue of drafted messages waiting to be sent to Slack.
- `memory/`: Contains global context and daily rolling logs (`YYYY-MM-DD/`).
- `status.json`: Tracking file for the last processed timestamp (`last_ts`).

### 📜 `config_harness/` (The Prompts)
- Contains prompts for `router.txt`, `validator.txt`, and individual team member characters (`persona_*.txt`).

### 📂 `docs/` (The Dynamic Specs)
- **This is your domain.** Write your project specs here (e.g. `docs/PM_Liam.md`, `docs/TechLead_Aiden.md`). 
- When the AI drafts messages, it reads this folder to align its opinions and comments with your design rules.

---

## 3. How to Run & Test It

### Running the Loop
To start the background listener loop that polls your Slack channel:
```bash
./app/main.sh
```

### Simulating/Mock Testing
If you don't want to poll live Slack channels, you can simulate a user sending a message by running the mock trigger script:
```bash
./tests/mock_slack_trigger.sh
```
This writes a mock event into `agent_io/inbox/current_event.json` and runs the AI pipeline, so you can see how Aiden, Sarah, Chloe, and Liam respond to a simulated Slack prompt!
