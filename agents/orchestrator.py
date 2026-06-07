"""
Orchestrator — The main loop that drives the Virtual Office.
Single process, time-based, no race conditions.

Architecture:
- 30-second tick loop
- Each agent has their own daily schedule (wake/sleep/work blocks)
- Wiki synced via git pull/push
- Skills triggered automatically by time/conditions
- GitHub context (issues, PRs) fetched and injected into prompts
"""

import os
import random
import subprocess
import time
from datetime import datetime, timedelta
from typing import Optional

from agents.agent import Agent
from agents.scheduler import Scheduler
from agents.router import route
from integrations.slack import SlackClient
from integrations.github import GitHubClient
from integrations.ai import AIClient
from memory.store import MemoryStore


WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI_DIR = os.path.join(WORKSPACE_DIR, "shout_wiki")


class Orchestrator:
    def __init__(self):
        self.slack = SlackClient()
        self.github = GitHubClient()
        self.ai = AIClient()
        self.memory = MemoryStore()
        self.scheduler = Scheduler(self.slack, self.github)
        
        self.agents = {
            "Liam": Agent("Liam", ".gemini/agents/liam.md"),
            "Aiden": Agent("Aiden", ".gemini/agents/aiden.md"),
            "Sarah": Agent("Sarah", ".gemini/agents/sarah.md"),
            "Chloe": Agent("Chloe", ".gemini/agents/chloe.md"),
        }
        
        self.bot_usernames = {
            "Liam (PM)", "Aiden (Tech Lead)",
            "Sarah (CEO)", "Chloe (Sales)"
        }
        
        self._last_daily_compress = None
        self._last_wiki_sync = None
        self._last_standup = None
        self._last_plan = None
        self._tick_count = 0
        self._tick_context_cache = None
        
        # Initial wiki sync
        self._sync_wiki()
        
        print(f"[Orchestrator] Initialized.")
        print(f"[Orchestrator] Wiki dir: {WIKI_DIR}")
        print(f"[Orchestrator] Agents: {list(self.agents.keys())}")
    
    def tick(self):
        """Main loop iteration. Called every ~30 seconds."""
        now = datetime.now()
        self._tick_count += 1
        self._tick_context_cache = None
        
        # 1. Dispatch any ready scheduled messages
        self.scheduler.dispatch_ready()
        
        # 2. Update agent states (online/offline/busy based on time)
        for agent in self.agents.values():
            agent.update_state(now)
        
        # 3. Check for new Slack messages
        self._check_slack()
        
        # 4. Check for new GitHub events (every 5 min)
        if self._tick_count % 10 == 0:
            self._check_github()
        
        # 5. Wiki sync (every 10 min)
        if self._tick_count % 20 == 0:
            self._sync_wiki()
        
        # 6. Skill triggers (time-based)
        self._check_skill_triggers(now)
        
        # 7. Autonomous work for each agent
        for agent in self.agents.values():
            if agent.should_do_work(now):
                self._do_autonomous_work(agent)
        
        # 8. Ambient chat (very rare)
        self._maybe_ambient_chat(now)
        
        # 9. Daily compression at midnight
        self._maybe_daily_compress(now)
    
    # -------------------------------------------------------------------------
    # Slack handling
    # -------------------------------------------------------------------------
    
    def _check_slack(self):
        """Fetch and process new Slack messages."""
        last_ts = self.memory.get_last_ts()
        messages = self.slack.fetch_new_messages(last_ts)
        
        if not messages:
            return
        
        # Cap messages processed per tick to prevent cascading freeze
        MAX_PER_TICK = 3
        to_process = messages[:MAX_PER_TICK]
        overflow = messages[MAX_PER_TICK:]
        
        if overflow:
            print(f"[Orchestrator] {len(overflow)} messages deferred to next tick")
        
        latest_ts = max((m.get('ts','') for m in to_process if m.get('ts')), default=last_ts)
        for msg in to_process:
            # Enrich: resolve user IDs + decode Slack formatting
            msg = self.slack.enrich_message(msg)
            self.memory.save_message(msg)
            
            try:
                if self._is_bot_message(msg):
                    self._handle_bot_message(msg)
                else:
                    self._handle_human_message(msg)
            except Exception as e:
                print(f"[Orchestrator] Error processing message: {e}")
        
        # Overflow messages are NOT saved here — they will be re-fetched and
        # properly processed next tick (since latest_ts only covers to_process).
        
        # Update last_ts only for processed messages
        if latest_ts != last_ts:
            self.memory.set_last_ts(latest_ts)
    
    def _handle_human_message(self, msg: dict):
        """Process a message from Kong (human)."""
        text = msg.get('text', '')
        print(f"[Orchestrator] Human message: {text[:60]}...")
        
        # Route: who should respond?
        try:
            responders = route(msg, self.agents, self.memory, self.ai)
        except Exception as e:
            print(f"[Orchestrator] route() failed: {e}")
            responders = []
        
        if not responders:
            print("[Orchestrator] No responders selected.")
            return
        
        # Deduplicate: keep first occurrence of each agent
        seen = set()
        unique_responders = []
        for item in responders:
            if item[0] not in seen:
                seen.add(item[0])
                unique_responders.append(item)
        responders = unique_responders
        
        # Build context with GitHub state
        context = self._build_rich_context()
        
        for i, (agent_name, delay_hint) in enumerate(responders):
            try:
                agent = self.agents.get(agent_name)
                if not agent or not agent.is_available():
                    continue
                
                # Get already-scheduled responses for this trigger
                previous = [
                    {"agent_name": m.agent_name, "text": m.text}
                    for m in self.scheduler.get_pending_for_trigger(msg.get("ts", ""))
                ]
                
                response = self.ai.generate_response(
                    agent=agent,
                    message=msg,
                    context=context,
                    previous_responses=previous
                )
                
                if response is None:
                    print(f"[Orchestrator] {agent_name} chose silence.")
                    continue
                
                delay = self._calculate_delay(agent, response.get("delay", delay_hint), i)
                
                self.scheduler.schedule(
                    agent_name=agent_name,
                    text=response["text"],
                    delay_seconds=delay,
                    trigger_msg_ts=msg.get("ts", ""),
                    actions=response.get("actions", [])
                )
            except Exception as e:
                print(f"[Orchestrator] Error processing responder {agent_name}: {e}")
    
    def _handle_bot_message(self, msg: dict):
        """Process a message from another bot. Only respond if directly mentioned."""
        # Count both DB messages and pending scheduled messages
        db_count = self.memory.count_recent_bot_messages(minutes=10)
        pending_bot_count = len([m for m in self.scheduler.pending
                                 if m.agent_name in self.agents])
        if db_count + pending_bot_count >= 3:
            return  # Hard stop: 3-turn limit (includes scheduled but unsent)
        
        text = msg.get("text", "").lower()
        sender = msg.get("username", "")
        
        # Only respond if directly @mentioned
        for name, agent in self.agents.items():
            # Don't respond to yourself
            if name.lower() in sender.lower():
                continue
            
            if f"@{name.lower()}" in text:
                if agent.is_available():
                    delay = random.randint(300, 900)  # 5-15 min for bot-to-bot
                    context = self._build_rich_context()
                    
                    response = self.ai.generate_response(
                        agent=agent,
                        message=msg,
                        context=context
                    )
                    
                    if response:
                        self.scheduler.schedule(
                            agent_name=name,
                            text=response["text"],
                            delay_seconds=delay,
                            trigger_msg_ts=msg.get("ts", "")
                        )
                    break  # Only one bot responds
                else:
                    continue
    
    # -------------------------------------------------------------------------
    # GitHub handling
    # -------------------------------------------------------------------------
    
    def _check_github(self):
        """Fetch and process new GitHub events."""
        last_id = self.memory.get_last_github_event_id()
        events = self.github.fetch_new_events(last_id)
        
        latest_event_id = None
        for event in events:
            event_id = str(event.get("id", ""))
            if event_id:
                latest_event_id = event_id
            
            self.memory.save_event(event)
            try:
                self._handle_github_event(event)
            except Exception as e:
                print(f"[Orchestrator] Error handling GitHub event: {e}")
        
        if latest_event_id:
            self.memory.set_last_github_event_id(latest_event_id)
    
    def _handle_github_event(self, event: dict):
        """React to GitHub events (PR opened, issue created, etc.)."""
        event_type = event.get("type", "")
        payload = event.get("payload", {})
        
        if event_type == "PullRequestEvent":
            action = payload.get("action", "")
            if action == "opened":
                pr = payload.get("pull_request", {})
                pr_title = pr.get("title", "unknown")
                pr_number = pr.get("number", "")
                
                # Aiden reviews (1-3 hours later)
                aiden = self.agents["Aiden"]
                if aiden.is_available():
                    # Fetch PR diff for context
                    diff_context = self._get_pr_diff(pr_number)
                    delay = random.randint(3600, 10800)
                    
                    context = self._build_rich_context()
                    context += f"\n\n## PR #{pr_number}: {pr_title}\n{diff_context}"
                    
                    response = self.ai.generate_response(
                        agent=aiden,
                        message={"text": f"New PR: {pr_title}", "username": "GitHub"},
                        context=context
                    )
                    
                    if response:
                        self.scheduler.schedule(
                            agent_name="Aiden",
                            text=response["text"],
                            delay_seconds=delay,
                            trigger_msg_ts=str(event.get("id", ""))
                        )
                
                # Liam acknowledges (30-60 min)
                liam = self.agents["Liam"]
                if liam.is_available():
                    delay = random.randint(1800, 3600)
                    context = self._build_rich_context()
                    
                    response = self.ai.generate_response(
                        agent=liam,
                        message={"text": f"New PR opened: \"{pr_title}\" (#{pr_number})", "username": "GitHub"},
                        context=context
                    )
                    
                    if response:
                        self.scheduler.schedule(
                            agent_name="Liam",
                            text=response["text"],
                            delay_seconds=delay,
                            trigger_msg_ts=str(event.get("id", ""))
                        )
        
        elif event_type == "IssuesEvent":
            action = payload.get("action", "")
            if action == "opened":
                issue = payload.get("issue", {})
                # Only react if we didn't create it ourselves
                creator = issue.get("user", {}).get("login", "")
                if creator not in ("liam", "aiden", "sarah", "chloe"):
                    issue_title = issue.get("title", "")
                    liam = self.agents["Liam"]
                    if liam.is_available():
                        delay = random.randint(1800, 3600)
                        context = self._build_rich_context()
                        
                        response = self.ai.generate_response(
                            agent=liam,
                            message={"text": f"New issue opened: \"{issue_title}\"", "username": "GitHub"},
                            context=context
                        )
                        
                        if response:
                            self.scheduler.schedule(
                                agent_name="Liam",
                                text=response["text"],
                                delay_seconds=delay,
                                trigger_msg_ts=str(event.get("id", ""))
                            )
    
    def _get_pr_diff(self, pr_number) -> str:
        """Fetch PR diff via gh CLI."""
        repo = os.environ.get("GITHUB_REPO", "")
        if not repo or not pr_number:
            return "(diff not available)"
        
        try:
            result = subprocess.run(
                ["gh", "pr", "diff", str(pr_number), "-R", repo],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                diff = result.stdout
                # Truncate if too long (keep first 3000 chars)
                if len(diff) > 3000:
                    diff = diff[:3000] + "\n... (truncated)"
                return diff
            return "(diff fetch failed)"
        except Exception:
            return "(diff not available)"
    
    # -------------------------------------------------------------------------
    # Wiki sync
    # -------------------------------------------------------------------------
    
    def _sync_wiki(self):
        """Pull latest wiki changes."""
        wiki_url = os.environ.get("WIKI_REPO_URL", "")
        
        if os.path.exists(os.path.join(WIKI_DIR, ".git")):
            # Already cloned — just pull
            try:
                res = subprocess.run(
                    ["git", "-C", WIKI_DIR, "pull", "--quiet"],
                    capture_output=True, timeout=15
                )
                if res.returncode == 0:
                    print("[Orchestrator] Wiki synced (pull).")
                else:
                    err_msg = res.stderr.decode(errors='ignore').strip()
                    print(f"[Orchestrator] Wiki pull failed (code {res.returncode}): {err_msg}")
            except Exception as e:
                print(f"[Orchestrator] Wiki pull failed: {e}")
        elif wiki_url:
            # First run — clone
            try:
                res = subprocess.run(
                    ["git", "clone", wiki_url, WIKI_DIR],
                    capture_output=True, timeout=30
                )
                if res.returncode == 0:
                    print(f"[Orchestrator] Wiki cloned to {WIKI_DIR}")
                else:
                    err_msg = res.stderr.decode(errors='ignore').strip()
                    print(f"[Orchestrator] Wiki clone failed (code {res.returncode}): {err_msg}")
            except Exception as e:
                print(f"[Orchestrator] Wiki clone failed: {e}")
        else:
            # No wiki URL configured — create local dir
            os.makedirs(WIKI_DIR, exist_ok=True)
    
    # -------------------------------------------------------------------------
    # Skill triggers
    # -------------------------------------------------------------------------
    
    def _check_skill_triggers(self, now: datetime):
        """Check if any skills should be triggered based on time/conditions."""
        
        # Standup: weekdays, 9-10am, once per day
        if (now.weekday() < 5 and 9 <= now.hour < 10 
                and self._last_standup != now.date()):
            if random.random() < 0.02:  # ~once in 25 ticks (12.5 min window)
                self._trigger_standup(now)
        
        # Sprint plan: Monday morning, once per week
        if (now.weekday() == 0 and 9 <= now.hour < 11
                and self._last_plan != now.date()):
            if random.random() < 0.01:
                self._trigger_plan(now)
    
    def _trigger_standup(self, now: datetime):
        """Trigger morning standup (Liam)."""
        liam = self.agents["Liam"]
        if not liam.is_available():
            return
        
        self._last_standup = now.date()
        context = self._build_rich_context()
        
        response = self.ai.generate_response(
            agent=liam,
            message={"text": "[STANDUP TRIGGER] Time for morning check-in.", "username": "System"},
            context=context
        )
        
        if response:
            delay = random.randint(0, 300)  # 0-5 min
            self.scheduler.schedule(
                agent_name="Liam",
                text=response["text"],
                delay_seconds=delay
            )
            print("[Orchestrator] Standup triggered.")
    
    def _trigger_plan(self, now: datetime):
        """Trigger sprint planning (Liam)."""
        liam = self.agents["Liam"]
        if not liam.is_available():
            return
        
        self._last_plan = now.date()
        context = self._build_rich_context()
        
        # Plan work
        work_plan = self.ai.plan_work(liam, context, "")
        if work_plan:
            result = self.ai.execute_work(liam, work_plan, context)
            if result:
                delay = random.randint(300, 1800)
                self.scheduler.schedule(
                    agent_name="Liam",
                    text=result["slack_message"],
                    delay_seconds=delay,
                    actions=result.get("actions", [])
                )
                print("[Orchestrator] Sprint plan triggered.")
    
    # -------------------------------------------------------------------------
    # Autonomous work
    # -------------------------------------------------------------------------
    
    def _do_autonomous_work(self, agent: Agent):
        """Trigger autonomous work for an agent."""
        try:
            print(f"[Orchestrator] {agent.name} starting autonomous work...")
            
            context = self._build_rich_context()
            
            work_plan = self.ai.plan_work(agent, context, "")
            
            if work_plan is None:
                print(f"[Orchestrator] {agent.name} decided nothing needs doing.")
                agent._work_fail_count = 0  # Reset on intentional skip
                agent.set_next_work_time()
                return
            
            print(f"[Orchestrator] {agent.name} working on: {work_plan.get('title', '?')}")
            
            result = self.ai.execute_work(agent, work_plan, context)
            
            if result:
                delay = random.randint(1800, 7200)
                self.scheduler.schedule(
                    agent_name=agent.name,
                    text=result["slack_message"],
                    delay_seconds=delay,
                    actions=result.get("actions", [])
                )
                agent._work_fail_count = 0  # Reset on success
                agent.set_next_work_time()
            else:
                agent._work_fail_count += 1
                if agent._work_fail_count >= agent._max_work_failures:
                    print(f"[Orchestrator] {agent.name} work failed {agent._work_fail_count}x. Resuming normal interval.")
                    agent._work_fail_count = 0
                    agent.set_next_work_time()
                else:
                    retry_hours = random.uniform(1, 2)
                    agent.next_work_time = datetime.now() + timedelta(hours=retry_hours)
                    print(f"[Orchestrator] {agent.name} work failed ({agent._work_fail_count}/{agent._max_work_failures}). Retry in {retry_hours:.1f}h")
        except Exception as e:
            print(f"[Orchestrator] {agent.name} autonomous work exception: {e}")
            agent.set_next_work_time()
    
    # -------------------------------------------------------------------------
    # Ambient chat
    # -------------------------------------------------------------------------
    
    def _maybe_ambient_chat(self, now: datetime):
        """Occasionally trigger casual team chat."""
        last_chat = self.memory.get_last_ambient_chat_time()
        
        if last_chat is not None:
            hours_since = (now - last_chat).total_seconds() / 3600
            if hours_since < 6:
                return
        
        # Very low probability per tick
        if random.random() > 0.003:
            return
        
        available = [a for a in self.agents.values() if a.is_available()]
        if not available:
            return
        
        initiator = random.choice(available)
        context = self._build_rich_context()
        
        chat = self.ai.generate_casual_chat(initiator, context)
        if chat:
            delay = random.randint(0, 300)
            self.scheduler.schedule(
                agent_name=initiator.name,
                text=chat["text"],
                delay_seconds=delay
            )
            self.memory.set_last_ambient_chat_time()
            print(f"[Orchestrator] Ambient chat by {initiator.name}")
    
    # -------------------------------------------------------------------------
    # Daily compression
    # -------------------------------------------------------------------------
    
    def _maybe_daily_compress(self, now: datetime):
        """Run daily compression at midnight."""
        today = now.date()
        
        if self._last_daily_compress == today:
            return
        
        if now.hour == 0 and now.minute < 30:
            from memory.compression import compress_today
            print("[Orchestrator] Running daily compression...")
            compress_today(self.memory, self.ai)
            self._last_daily_compress = today
    
    # -------------------------------------------------------------------------
    # Context building
    # -------------------------------------------------------------------------
    
    def _build_rich_context(self) -> str:
        """Build full context including project state and GitHub info. Capped at 6000 chars."""
        if self._tick_context_cache is not None:
            return self._tick_context_cache
        
        base_context = self.memory.get_context()
        project_state = self.github.get_project_state()
        
        full = f"""{base_context}

## Current GitHub State
{project_state}
"""
        if len(full) > 6000:
            full = full[:5950] + "\n\n(... context truncated)"
        self._tick_context_cache = full
        return full
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    
    def _calculate_delay(self, agent: Agent, delay_hint: str, position: int) -> int:
        """Calculate actual delay in seconds."""
        delay_ranges = {
            "immediate": (15, 60),
            "short": (60, 300),
            "medium": (600, 1800),
            "long": (3600, 7200),
        }
        
        min_d, max_d = delay_ranges.get(delay_hint, (60, 300))
        base = random.randint(min_d, max_d)
        
        # Additional delay for second/third responders
        base += position * random.randint(120, 600)
        
        return base
    
    def _is_bot_message(self, msg: dict) -> bool:
        """Check if a message was sent by one of our bots."""
        username = msg.get("username", "")
        if username in self.bot_usernames:
            return True
        if msg.get("subtype") == "bot_message":
            return True
        if msg.get("bot_id"):
            return True
        return False
