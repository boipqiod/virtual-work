"""
AI Integration — Calls agy (Antigravity CLI) using native subagents.

Architecture:
- Personas are defined in .gemini/agents/*.md (loaded by agy as system instruction)
- We invoke subagents via @agent_name mention in the prompt
- agy reads GEMINI.md for global rules automatically
- Context (conversation history, project state) is passed as user prompt
- Fallback: Gemini API with inline persona if agy is unavailable
"""

import os
import re
import json
import subprocess
from typing import Optional


WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AIClient:
    def __init__(self):
        self.use_agy = self._check_agy()
        self._api_configured = bool(os.environ.get("GEMINI_API_KEY"))
        
        # Circuit breaker state (agy)
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_open_until = 0  # timestamp
        self._failure_threshold = 3
        self._cooldown_seconds = 300  # 5 min cooldown after circuit opens
        
        # Circuit breaker state (Gemini)
        self._gemini_consecutive_failures = 0
        self._gemini_circuit_open = False
        self._gemini_circuit_open_until = 0

        
        backend = "agy (subagent)" if self.use_agy else "gemini-api" if self._api_configured else "NONE"
        print(f"[AI] Backend: {backend}")
    
    def _check_agy(self) -> bool:
        """Check if agy CLI is available."""
        try:
            result = subprocess.run(
                ["agy", "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    # -------------------------------------------------------------------------
    # Core AI call methods
    # -------------------------------------------------------------------------
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open (AI calls disabled temporarily)."""
        if not self._circuit_open:
            return False
        import time
        if time.time() >= self._circuit_open_until:
            # Cooldown expired — half-open, allow one attempt
            self._circuit_open = False
            self._consecutive_failures = 0
            print("[AI] Circuit breaker reset. Retrying agy.")
            return False
        return True
    
    def _record_success(self):
        """Reset failure counter on successful AI call."""
        self._consecutive_failures = 0
    
    def _record_failure(self):
        """Track failure and open circuit if threshold reached."""
        import time
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._circuit_open = True
            self._circuit_open_until = time.time() + self._cooldown_seconds
            print(f"[AI] Circuit breaker OPEN — {self._failure_threshold} consecutive failures. "
                  f"Cooldown {self._cooldown_seconds}s.")
    
    def _is_gemini_circuit_open(self) -> bool:
        """Check if Gemini circuit breaker is open."""
        if not self._gemini_circuit_open:
            return False
        import time
        if time.time() >= self._gemini_circuit_open_until:
            self._gemini_circuit_open = False
            self._gemini_consecutive_failures = 0
            print("[AI] Gemini circuit breaker reset.")
            return False
        return True
    
    def _record_gemini_success(self):
        self._gemini_consecutive_failures = 0
    
    def _record_gemini_failure(self):
        import time
        self._gemini_consecutive_failures += 1
        if self._gemini_consecutive_failures >= self._failure_threshold:
            self._gemini_circuit_open = True
            self._gemini_circuit_open_until = time.time() + self._cooldown_seconds
            print(f"[AI] Gemini circuit breaker OPEN — {self._failure_threshold} consecutive failures. "
                  f"Cooldown {self._cooldown_seconds}s.")
    
    def _strip_preamble(self, raw: str) -> str:
        """Strip any agy preamble/logging before the actual XML-tagged response."""
        first_tag = re.search(
            r'<(decision|response|delay|work_plan|wiki_content|issue_body|comment_body|slack_message|actions)',
            raw
        )
        if first_tag:
            return raw[first_tag.start():]
        return raw
    
    def _call_subagent(self, agent_name: str, user_prompt: str) -> Optional[str]:
        """
        Call agy with @agent_name mention.
        agy automatically loads:
          - GEMINI.md (global rules)
          - .gemini/agents/{agent_name}.md (persona as system instruction)
        We only pass the context and task as user prompt.
        """
        if self._is_circuit_open():
            return None
        
        prompt = f"@{agent_name.lower()}\n\n{user_prompt}"
        
        try:
            env = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}
            proc = subprocess.Popen(
                [
                    "agy",
                    "--add-dir", WORKSPACE_DIR,
                    "--dangerously-skip-permissions",
                    "-p", prompt,
                ],
                cwd=WORKSPACE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=env,
            )
            try:
                stdout, stderr = proc.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), 9)
                proc.wait()
                print("[AI] agy timed out")
                self._record_failure()
                return None
            if proc.returncode == 0:
                self._record_success()
                return self._strip_preamble(stdout.strip())
            else:
                print(f"[AI] agy error: {stderr[:200]}")
                self._record_failure()
                return None
        except Exception as e:
            print(f"[AI] agy error: {e}")
            self._record_failure()
            return None
    
    def _call_gemini_api(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> Optional[str]:
        """Fallback: Call Gemini API directly with inline persona."""
        if self._is_gemini_circuit_open():
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            model = genai.GenerativeModel(
                "gemini-2.0-flash",
                system_instruction=system_prompt
            )
            response = model.generate_content(
                user_prompt,
                generation_config={"temperature": temperature}
            )
            self._record_gemini_success()
            return response.text
        except Exception as e:
            print(f"[AI] Gemini API error: {e}")
            self._record_gemini_failure()
            return None
    
    def _call_ai(self, agent_name: str, user_prompt: str, agent=None) -> Optional[str]:
        """
        Route to the appropriate backend.
        - agy: uses native subagent (@mention)
        - Gemini API: falls back to inline persona
        """
        if self.use_agy:
            result = self._call_subagent(agent_name, user_prompt)
            if result is not None:
                return result
            # Fallback to Gemini when agy fails/circuit open
            if self._api_configured and agent:
                system_prompt = self._build_inline_system_prompt(agent)
                return self._call_gemini_api(system_prompt, user_prompt, temperature=agent.temperature)
            return None
        elif self._api_configured and agent:
            # Fallback: build inline system prompt from persona file
            system_prompt = self._build_inline_system_prompt(agent)
            return self._call_gemini_api(system_prompt, user_prompt, temperature=agent.temperature)
        else:
            print("[AI] No AI backend available")
            return None
    
    def _call_ai_raw(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Raw AI call without subagent (for routing, compression, etc.).
        Does NOT use --add-dir to avoid loading .gemini/agents/ subagents.
        """
        if self.use_agy:
            if self._is_circuit_open():
                # Fall through to Gemini API if available
                if self._api_configured:
                    return self._call_gemini_api(system_prompt, user_prompt)
                return None
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
            try:
                env = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}
                proc = subprocess.Popen(
                    [
                        "agy",
                        "--dangerously-skip-permissions",
                        "-p", full_prompt,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                    env=env,
                )
                try:
                    stdout, stderr = proc.communicate(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(proc.pid), 9)
                    proc.wait()
                    self._record_failure()
                    return None
                if proc.returncode == 0:
                    self._record_success()
                    return self._strip_preamble(stdout.strip())
                self._record_failure()
                return None
            except Exception:
                self._record_failure()
                return None
        elif self._api_configured:
            return self._call_gemini_api(system_prompt, user_prompt)
        return None
    
    # -------------------------------------------------------------------------
    # Public methods
    # -------------------------------------------------------------------------
    
    def generate_response(self, agent, message: dict, context: str,
                          previous_responses: list = None) -> Optional[dict]:
        """
        Generate a response for an agent given a new message.
        Returns {"text": ..., "delay": ..., "actions": [...]} or None for silence.
        """
        prev_text = ""
        if previous_responses:
            for pr in previous_responses:
                prev_text += f"[{pr.get('agent_name', '?')}]: {pr.get('text', '')}\n"
        
        # B-4: Expose behavioral pattern to model
        delay_default = agent.pattern.get("response_delay_default", "short")
        engagement = agent.pattern.get("engagement", "medium")
        
        user_prompt = f"""You are {agent.name}. Stay in character.
Your engagement level: {engagement}. Your typical response speed: {delay_default}.
Default to silence unless this message is clearly relevant to your role.

## Current Context
{context}

## New Message
From: {message.get('username', message.get('user', 'Kong'))}
Text: {message.get('text', '')}

## Other Responses Already Scheduled
{prev_text if prev_text else '(none)'}

## Task
Decide whether to respond and what to say. Consider your role and interests.

Output format:
<decision>reply OR silence</decision>
<delay>immediate OR short OR medium OR long</delay>
<response>your message here</response>
<actions>[]</actions>
"""
        
        raw = self._call_ai(agent.name, user_prompt, agent)
        if raw is None:
            return None
        
        return self._parse_response(raw)
    
    def plan_work(self, agent, context: str, project_state: str = "") -> Optional[dict]:
        """Ask the agent what autonomous work to do."""
        github_section = f"\n## Current GitHub State\n{project_state}\n" if project_state else ""
        user_prompt = f"""You are {agent.name}. Stay in character.

## Context
{context}
{github_section}
## Task
It's your work block. What ONE thing will you work on?

Options based on your role:
- "wiki_write": Write or update a wiki document
- "issue_create": Create a new GitHub issue with acceptance criteria
- "issue_comment": Comment on an existing issue (must specify issue_number)
- "none": Nothing needs doing right now

Be realistic. Only do work that's actually needed.

Output:
<work_plan>
{{
  "action": "wiki_write" | "issue_create" | "issue_comment" | "none",
  "issue_number": 7,
  "title": "short title",
  "description": "one sentence on why"
}}
</work_plan>

Note: "issue_number" is required for "issue_comment". Use a number from the GitHub State above.
"""
        
        raw = self._call_ai(agent.name, user_prompt, agent)
        if raw is None:
            return None
        
        match = re.search(r'<work_plan>(.*?)</work_plan>', raw, re.DOTALL)
        if match:
            try:
                json_str = self._fix_json(match.group(1).strip())
                plan = json.loads(json_str)
                if plan.get("action") == "none":
                    return None
                return plan
            except json.JSONDecodeError:
                return None
        return None
    
    def execute_work(self, agent, work_plan: dict, context: str) -> Optional[dict]:
        """Execute a planned work item and return the result."""
        action = work_plan["action"]
        
        if action == "wiki_write":
            user_prompt = f"""## Context
{context}

## Task
Write a wiki document titled: "{work_plan['title']}"
Reason: {work_plan['description']}

Write the full markdown content. Be thorough but concise.
Also write a short Slack message (1-2 sentences) announcing this.

Output:
<wiki_content>
(full markdown document)
</wiki_content>
<slack_message>your short announcement</slack_message>
"""
        elif action == "issue_create":
            user_prompt = f"""## Context
{context}

## Task
Create a GitHub issue titled: "{work_plan['title']}"
Reason: {work_plan['description']}

Write the issue body with:
- Clear description (2-3 sentences)
- Acceptance criteria (3-5 bullet points)

Also write a short Slack message announcing the new issue.

Output:
<issue_body>
(full issue body in markdown)
</issue_body>
<slack_message>your short announcement</slack_message>
"""
        elif action == "issue_comment":
            user_prompt = f"""## Context
{context}

## Task
Write a comment for issue #{work_plan.get('issue_number', '?')}: "{work_plan['title']}"
Reason: {work_plan['description']}

Write a focused, useful comment.

Output:
<comment_body>
(your comment)
</comment_body>
<slack_message>your short announcement or empty if not worth announcing</slack_message>
"""
        else:
            return None
        
        raw = self._call_ai(agent.name, user_prompt, agent)
        if raw is None:
            return None
        
        return self._parse_work_result(raw, action, work_plan)
    
    def generate_casual_chat(self, agent, context: str) -> Optional[dict]:
        """Generate a casual/ambient chat message."""
        user_prompt = f"""You are {agent.name}. Stay in character.

## Recent Context
{context}

## Task
It's a quiet moment. Write a casual message — not about work. Just team banter.
1-2 sentences. Must feel natural.
If nothing comes to mind, output SILENCE.

<response>your message or SILENCE</response>
"""
        
        raw = self._call_ai(agent.name, user_prompt, agent)
        if raw is None:
            return None
        
        match = re.search(r'<response>(.*?)</response>', raw, re.DOTALL)
        if match:
            text = match.group(1).strip()
            if text and text.upper() != "SILENCE":
                return {"text": text}
        return None
    
    def route_message(self, msg: dict, context: str) -> Optional[list]:
        """AI-based routing when keyword matching fails."""
        prompt = f"""Given this Slack message in a startup team channel:
"{msg.get('text', '')}"

Recent context:
{context[-500:]}

Who should respond? Pick 0-2 from: Liam, Aiden, Sarah, Chloe
If nobody needs to respond, return empty.

Output JSON array only:
[{{"name": "Name", "delay": "short"}}]
Or: []
"""
        
        raw = self._call_ai_raw("You are a routing assistant. Output only JSON.", prompt)
        if raw is None:
            return None
        
        # Extract JSON array from potentially noisy output
        json_str = self._extract_json_array(raw)
        if json_str is None:
            return None
        
        try:
            result = json.loads(json_str)
            if not isinstance(result, list):
                return None
            if not result:
                return []
            return [(r["name"], r.get("delay", "short")) for r in result]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
    
    # -------------------------------------------------------------------------
    # Parsing helpers
    # -------------------------------------------------------------------------
    
    def _extract_json_array(self, raw: str) -> Optional[str]:
        """Extract a JSON array from potentially noisy AI output."""
        # Strip markdown code fences first
        raw = re.sub(r'^```\w*\n?', '', raw.strip())
        raw = re.sub(r'\n?```$', '', raw.strip())
        
        # Try direct parse first
        stripped = raw.strip()
        if stripped.startswith("["):
            return self._fix_json(stripped)
        
        # Search for array pattern anywhere in text
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            return self._fix_json(match.group(0))
        
        return None
    
    def _fix_json(self, s: str) -> str:
        """Fix common JSON issues: trailing commas, single quotes."""
        s = s.replace("'", '"')
        # Remove trailing commas before } or ]
        s = re.sub(r',\s*([}\]])', r'\1', s)
        return s
    
    def _parse_response(self, raw: str) -> Optional[dict]:
        """Parse AI response with decision/delay/response/actions tags."""
        decision_match = re.search(r'<decision>(.*?)</decision>', raw, re.DOTALL)
        if decision_match:
            decision_text = decision_match.group(1).strip().lower()
            if decision_text in ("silence", "silent", "skip", "no", "ignore"):
                return None
        
        response_match = re.search(r'<response>(.*?)</response>', raw, re.DOTALL)
        delay_match = re.search(r'<delay>(.*?)</delay>', raw, re.DOTALL)
        actions_match = re.search(r'<actions>(.*?)</actions>', raw, re.DOTALL)
        
        text = response_match.group(1).strip() if response_match else None
        
        # M7 fallback: tag opened but never closed — grab everything after <response>
        if not text:
            open_match = re.search(r'<response>(.*)', raw, re.DOTALL)
            if open_match:
                text = open_match.group(1).strip()
                # Remove any trailing tags that might be from other fields
                text = re.sub(r'<(delay|decision|actions)>.*', '', text, flags=re.DOTALL).strip()
        
        if not text:
            return None
        
        # Reject prompt leakage
        if any(tag in text for tag in ["<decision>", "<delay>", "<response>", "## Task", "## Context"]):
            print("[AI] Prompt leakage detected. Discarding.")
            return None
        
        delay = delay_match.group(1).strip().lower() if delay_match else "short"
        if delay not in ("immediate", "short", "medium", "long"):
            delay = "short"
        
        actions = []
        if actions_match:
            try:
                parsed = json.loads(actions_match.group(1).strip())
                if isinstance(parsed, list):
                    actions = parsed
            except json.JSONDecodeError:
                pass
        
        return {"text": text, "delay": delay, "actions": actions}
    
    def _parse_work_result(self, raw: str, action: str, work_plan: dict) -> Optional[dict]:
        """Parse autonomous work output."""
        slack_match = re.search(r'<slack_message>(.*?)</slack_message>', raw, re.DOTALL)
        slack_msg = slack_match.group(1).strip() if slack_match else ""
        
        if not slack_msg:
            slack_msg = f"done with {work_plan['title']}"
        
        actions = []
        
        if action == "wiki_write":
            wiki_match = re.search(r'<wiki_content>(.*?)</wiki_content>', raw, re.DOTALL)
            if not wiki_match:
                # Fallback: tag opened but never closed
                wiki_match = re.search(r'<wiki_content>(.*)', raw, re.DOTALL)
            if wiki_match:
                content = re.sub(r'<(slack_message|actions)>.*', '', wiki_match.group(1), flags=re.DOTALL).strip()
                if content:
                    actions.append({
                        "type": "wiki_write",
                        "title": work_plan["title"],
                        "content": content
                    })
                else:
                    return None
            else:
                return None
        
        elif action == "issue_create":
            issue_match = re.search(r'<issue_body>(.*?)</issue_body>', raw, re.DOTALL)
            if not issue_match:
                issue_match = re.search(r'<issue_body>(.*)', raw, re.DOTALL)
            if issue_match:
                body = re.sub(r'<(slack_message|actions)>.*', '', issue_match.group(1), flags=re.DOTALL).strip()
                if body:
                    actions.append({
                        "type": "issue_create",
                        "title": work_plan["title"],
                        "body": body
                    })
                else:
                    return None
            else:
                return None
        
        elif action == "issue_comment":
            issue_number = work_plan.get("issue_number")
            # Validate issue_number exists and is usable
            if not issue_number:
                print("[AI] issue_comment missing issue_number. Discarding.")
                return None
            comment_match = re.search(r'<comment_body>(.*?)</comment_body>', raw, re.DOTALL)
            if not comment_match:
                comment_match = re.search(r'<comment_body>(.*)', raw, re.DOTALL)
            if comment_match:
                body = re.sub(r'<(slack_message|actions)>.*', '', comment_match.group(1), flags=re.DOTALL).strip()
                if body:
                    actions.append({
                        "type": "issue_comment",
                        "issue_number": str(issue_number),
                        "body": body
                    })
                else:
                    return None
            else:
                return None
        
        return {"slack_message": slack_msg, "actions": actions}
    
    def _build_inline_system_prompt(self, agent) -> str:
        """Fallback: build system prompt from persona file (for Gemini API mode)."""
        gemini_md_path = os.path.join(WORKSPACE_DIR, ".gemini", "GEMINI.md")
        global_rules = ""
        if os.path.exists(gemini_md_path):
            with open(gemini_md_path, "r") as f:
                global_rules = f.read()
        
        # Strip YAML frontmatter from persona (not useful for Gemini API)
        persona = agent.persona
        if persona.startswith("---"):
            end = persona.find("---", 3)
            if end != -1:
                persona = persona[end + 3:].strip()
        
        return f"{global_rules}\n\n{persona}"
