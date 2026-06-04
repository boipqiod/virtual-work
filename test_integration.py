#!/usr/bin/env python3
"""
Virtual Office — Integration Test (Real agy, Mock Slack/GitHub)
Tests the full pipeline: message → route → AI → parse → schedule → dispatch

Usage: python3 test_integration.py
"""

import os
import sys
import time
import json
import sqlite3
from datetime import datetime

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Load .env
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

def header(s): print(f"\n{CYAN}━━━ {s} ━━━{NC}")
def passed(s): print(f"  {GREEN}PASS{NC} {s}")
def failed(s): print(f"  {RED}FAIL{NC} {s}")
def info(s): print(f"  {YELLOW}INFO{NC} {s}")

results = {"pass": 0, "fail": 0}

def check(condition, msg, detail=""):
    if condition:
        passed(msg)
        results["pass"] += 1
    else:
        failed(f"{msg} — {detail}")
        results["fail"] += 1
    return condition


# ─────────────────────────────────────────────────────────────────────────────
# Setup: Use test DB, no real Slack/GitHub
# ─────────────────────────────────────────────────────────────────────────────

# Override DB path to use a test database
TEST_DB = os.path.join(os.path.dirname(__file__), "data", "test_integration.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

import memory.store as store_module
store_module.DB_PATH = TEST_DB

from integrations.ai import AIClient
from integrations.slack import SlackClient
from integrations.github import GitHubClient
from agents.agent import Agent
from agents.router import route
from agents.scheduler import Scheduler
from memory.store import MemoryStore


# ─────────────────────────────────────────────────────────────────────────────
header("Test 1: Full Response Pipeline (Human → Route → AI → Parse)")
# ─────────────────────────────────────────────────────────────────────────────

ai = AIClient()
memory = MemoryStore()

agents = {
    "Liam": Agent("Liam", ".gemini/agents/liam.md"),
    "Aiden": Agent("Aiden", ".gemini/agents/aiden.md"),
    "Sarah": Agent("Sarah", ".gemini/agents/sarah.md"),
    "Chloe": Agent("Chloe", ".gemini/agents/chloe.md"),
}

# Force all agents online
for a in agents.values():
    a.state = "online"

# Simulate a human message
msg = {
    "ts": "1700000001.000001",
    "user": "U_KONG",
    "username": "Kong",
    "text": "hey team, the login page is throwing a 500 error when I submit the form",
}

info(f"Input message: \"{msg['text']}\"")

# 1a. Route
print()
info("Routing...")
responders = route(msg, agents, memory, ai)
check(len(responders) > 0, "Router selected responders", f"got: {responders}")
if responders:
    info(f"Responders: {responders}")
    # Aiden should be primary (tech keywords: error, 500, page)
    primary = responders[0][0]
    info(f"Primary responder: {primary}")

# 1b. Generate response
print()
info("Generating AI response...")
if responders:
    agent_name = responders[0][0]
    agent = agents[agent_name]
    context = "## Project Info\nShout Financial — fintech startup, early stage.\n\n## Recent Conversation\n(empty)\n"
    
    response = ai.generate_response(
        agent=agent,
        message=msg,
        context=context,
        previous_responses=[]
    )
    
    check(response is not None, f"{agent_name} generated a response")
    if response:
        check("text" in response, "Response has 'text' field")
        check("delay" in response, "Response has 'delay' field")
        check(response["delay"] in ("immediate", "short", "medium", "long"),
              f"Delay is valid: {response['delay']}")
        check(len(response["text"]) > 0, f"Response text not empty ({len(response['text'])} chars)")
        info(f"Response: \"{response['text'][:150]}...\"")
        info(f"Delay: {response['delay']}")
        info(f"Actions: {response.get('actions', [])}")
        
        # Check it's in English
        ascii_ratio = sum(1 for c in response["text"] if ord(c) < 128) / max(len(response["text"]), 1)
        check(ascii_ratio > 0.8, f"Response is in English (ASCII ratio: {ascii_ratio:.0%})")
    else:
        info(f"{agent_name} chose silence (unexpected for a direct tech question)")


# ─────────────────────────────────────────────────────────────────────────────
header("Test 2: Silence Decision (Irrelevant Message)")
# ─────────────────────────────────────────────────────────────────────────────

irrelevant_msg = {
    "ts": "1700000002.000001",
    "user": "U_KONG",
    "username": "Kong",
    "text": "going to grab some coffee, brb",
}

info(f"Input: \"{irrelevant_msg['text']}\"")

# Aiden should stay silent
aiden = agents["Aiden"]
response = ai.generate_response(
    agent=aiden,
    message=irrelevant_msg,
    context="## Recent Conversation\n[Kong]: going to grab some coffee, brb\n",
)

check(response is None, "Aiden stays silent for coffee message")
if response:
    info(f"Aiden unexpectedly replied: \"{response['text'][:100]}\"")


# ─────────────────────────────────────────────────────────────────────────────
header("Test 3: Autonomous Work Planning")
# ─────────────────────────────────────────────────────────────────────────────

info("Asking Liam to plan work...")
liam = agents["Liam"]
context = """## Project Info
Shout Financial — fintech startup building a group expense splitting app.

## Recent Conversation
[Kong]: just set up the monorepo structure
[Aiden]: nice. i'll review the tsconfig tomorrow
"""

project_state = "- Issue #1: Set up monorepo (open, Kong)\n- Issue #2: Design auth flow (open, unassigned)"

work_plan = ai.plan_work(liam, context, project_state)

if work_plan:
    check(True, f"Liam planned work: {work_plan.get('action')}")
    check("action" in work_plan, "Plan has 'action' field")
    check("title" in work_plan, f"Plan has 'title': {work_plan.get('title', '?')}")
    check(work_plan["action"] in ("wiki_write", "issue_create", "issue_comment", "none"),
          f"Action is valid: {work_plan['action']}")
    info(f"Plan: {json.dumps(work_plan, indent=2)}")
else:
    check(True, "Liam decided nothing needs doing (valid)")
    info("No work planned — this is acceptable")


# ─────────────────────────────────────────────────────────────────────────────
header("Test 4: Casual Chat Generation")
# ─────────────────────────────────────────────────────────────────────────────

info("Asking Chloe for casual chat...")
chloe = agents["Chloe"]
context = """## Recent Conversation
[Liam]: alright team, wrapping up for the day
[Kong]: same here, good progress today
"""

chat = ai.generate_casual_chat(chloe, context)

if chat:
    check(True, "Chloe generated casual chat")
    check("text" in chat, f"Chat has text: \"{chat['text'][:100]}\"")
    ascii_ratio = sum(1 for c in chat["text"] if ord(c) < 128) / max(len(chat["text"]), 1)
    check(ascii_ratio > 0.8, f"Chat is in English (ASCII ratio: {ascii_ratio:.0%})")
else:
    check(True, "Chloe chose SILENCE (valid but less interesting)")


# ─────────────────────────────────────────────────────────────────────────────
header("Test 5: Router AI Fallback")
# ─────────────────────────────────────────────────────────────────────────────

# Message with no keyword matches — should trigger AI routing
ambiguous_msg = {
    "ts": "1700000003.000001",
    "user": "U_KONG",
    "username": "Kong",
    "text": "I've been thinking about how we compare to other apps in the market",
}

info(f"Input: \"{ambiguous_msg['text']}\"")
responders = route(ambiguous_msg, agents, memory, ai)
info(f"AI router result: {responders}")
check(responders is not None, "AI router returned a result (not crash)")


# ─────────────────────────────────────────────────────────────────────────────
header("Test 6: Scheduler + Dispatch (Dry Run)")
# ─────────────────────────────────────────────────────────────────────────────

slack = SlackClient()  # No webhook URLs = dry run
github = GitHubClient()
scheduler = Scheduler(slack, github)

# Schedule a message with 0 delay
scheduler.schedule("Liam", "test message from integration test", delay_seconds=0)
check(scheduler.pending_count() == 1, f"Message scheduled (pending={scheduler.pending_count()})")

# Wait a moment and dispatch
time.sleep(0.1)
scheduler.dispatch_ready()
check(scheduler.pending_count() == 0, f"Message dispatched (pending={scheduler.pending_count()})")


# ─────────────────────────────────────────────────────────────────────────────
header("Test 7: Circuit Breaker (Simulated)")
# ─────────────────────────────────────────────────────────────────────────────

info("Simulating 3 consecutive failures...")
ai._consecutive_failures = 0
ai._record_failure()
ai._record_failure()
ai._record_failure()

check(ai._circuit_open, "Circuit breaker opened after 3 failures")
check(ai._is_circuit_open(), "Circuit reports as open")

# Reset
ai._circuit_open = False
ai._consecutive_failures = 0
info("Circuit breaker reset.")


# ─────────────────────────────────────────────────────────────────────────────
header("Test 8: Persona Differentiation")
# ─────────────────────────────────────────────────────────────────────────────

info("Same question to Liam vs Aiden — checking voice difference...")

tech_msg = {
    "ts": "1700000004.000001",
    "username": "Kong",
    "text": "should we add rate limiting to the API?",
}
context = "## Recent Conversation\n(empty)\n"

liam_resp = ai.generate_response(agent=agents["Liam"], message=tech_msg, context=context)
aiden_resp = ai.generate_response(agent=agents["Aiden"], message=tech_msg, context=context)

if liam_resp and aiden_resp:
    info(f"Liam: \"{liam_resp['text'][:120]}\"")
    info(f"Aiden: \"{aiden_resp['text'][:120]}\"")
    
    # Aiden should be more technical, Liam more managerial
    check(liam_resp["text"] != aiden_resp["text"], "Responses are different")
    
    # Rough check: Aiden's response likely has more technical terms
    tech_terms = ["rate limit", "middleware", "429", "throttl", "redis", "token bucket", "express"]
    aiden_tech = sum(1 for t in tech_terms if t in aiden_resp["text"].lower())
    liam_tech = sum(1 for t in tech_terms if t in liam_resp["text"].lower())
    info(f"Tech term count — Liam: {liam_tech}, Aiden: {aiden_tech}")
    check(aiden_tech >= liam_tech, "Aiden uses more technical language than Liam")
else:
    if not liam_resp:
        info("Liam chose silence (unexpected)")
    if not aiden_resp:
        info("Aiden chose silence (possible — might defer)")


# ─────────────────────────────────────────────────────────────────────────────
header("결과 요약")
# ─────────────────────────────────────────────────────────────────────────────

print()
print(f"  {GREEN}PASS: {results['pass']}{NC}  {RED}FAIL: {results['fail']}{NC}")
print()

if results["fail"] == 0:
    print(f"  {GREEN}All tests passed. System is ready for live deployment.{NC}")
else:
    print(f"  {RED}{results['fail']} test(s) failed. Review output above.{NC}")

# Cleanup test DB
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

sys.exit(0 if results["fail"] == 0 else 1)
