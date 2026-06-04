"""
Agent — Represents a single virtual team member with state, schedule, and persona.
"""

import os
import json
import random
import re
from datetime import datetime, timedelta
from typing import Optional


class Agent:
    def __init__(self, name: str, persona_path: str):
        self.name = name
        self.persona = self._load_persona(persona_path)
        self.temperature = self._parse_frontmatter_field("temperature", 0.7)
        self.state = "offline"  # offline / online / busy
        self.energy = 1.0
        self.next_work_time: Optional[datetime] = None
        self.last_slack_check: Optional[datetime] = None
        self._work_fail_count = 0
        self._max_work_failures = 3
        self.pattern = self._load_pattern()
    
    def _load_persona(self, path: str) -> str:
        """Load persona markdown file."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"[Agent] Warning: persona file not found: {full_path}")
            return f"You are {self.name}, a team member at Shout Financial."
    
    def _parse_frontmatter_field(self, field: str, default=None):
        """Extract a field from YAML frontmatter in persona file."""
        if not self.persona.startswith("---"):
            return default
        end = self.persona.find("---", 3)
        if end == -1:
            return default
        frontmatter = self.persona[3:end]
        match = re.search(rf'^{field}:\s*(.+)$', frontmatter, re.MULTILINE)
        if match:
            val = match.group(1).strip()
            # Try numeric conversion
            try:
                return float(val)
            except ValueError:
                return val
        return default
    
    def _load_pattern(self) -> dict:
        """Load daily pattern from config."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "daily_patterns.json")
        try:
            with open(config_path, "r") as f:
                patterns = json.load(f)
                return patterns.get(self.name, {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def update_state(self, now: datetime):
        """Update agent state based on current time and daily pattern."""
        hour = now.hour
        
        wake = self.pattern.get("wake_hour", 9)
        sleep = self.pattern.get("sleep_hour", 23)
        
        # Offline outside working hours
        if hour < wake or hour >= sleep:
            self.state = "offline"
            self.energy = 1.0  # Reset energy overnight
            return
        
        # Check if in a work block (busy = deep work, less likely to check slack)
        work_blocks = self.pattern.get("work_blocks", [])
        for block in work_blocks:
            start_h, end_h = block
            if start_h <= hour < end_h:
                self.state = "busy"
                return
        
        self.state = "online"
    
    def is_available(self) -> bool:
        """Can this agent see and respond to messages?"""
        return self.state in ("online", "busy")
    
    def should_check_slack(self, now: datetime) -> bool:
        """Has enough time passed since last Slack check?"""
        if not self.is_available():
            return False
        
        if self.last_slack_check is None:
            self.last_slack_check = now
            return True
        
        # Get check interval from pattern (in minutes)
        interval_range = self.pattern.get("slack_check_interval_minutes", [30, 60])
        min_interval = interval_range[0]
        max_interval = interval_range[1] if len(interval_range) > 1 else min_interval
        
        # Randomize the interval each time
        interval_minutes = random.randint(min_interval, max_interval)
        
        elapsed = (now - self.last_slack_check).total_seconds() / 60
        if elapsed >= interval_minutes:
            self.last_slack_check = now
            return True
        
        return False
    
    def should_do_work(self, now: datetime) -> bool:
        """Is it time for autonomous work?"""
        if not self.is_available():
            return False
        
        if self.next_work_time is None:
            self._init_next_work_time(now)
            return False
        
        return now >= self.next_work_time
    
    def set_next_work_time(self):
        """Schedule next autonomous work (6-18 hours from now, based on pattern)."""
        interval_range = self.pattern.get("autonomous_work_interval_hours", [8, 14])
        min_h = interval_range[0]
        max_h = interval_range[1] if len(interval_range) > 1 else min_h
        
        hours = random.uniform(min_h, max_h)
        self.next_work_time = datetime.now() + timedelta(hours=hours)
        print(f"[Agent] {self.name} next work in {hours:.1f}h")
    
    def _init_next_work_time(self, now: datetime):
        """Set initial work time (1-4 hours from start)."""
        hours = random.uniform(1, 4)
        self.next_work_time = now + timedelta(hours=hours)
    
    def get_response_delay_default(self) -> str:
        """Get this agent's default response speed."""
        return self.pattern.get("response_delay_default", "short")
    
    def __repr__(self):
        return f"Agent({self.name}, state={self.state})"
