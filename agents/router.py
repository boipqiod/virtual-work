"""
Router — Decides which agents should respond to a message.
Uses keyword matching first, falls back to AI routing.
"""

import re
import random
from typing import Optional


def route(msg: dict, agents: dict, memory, ai_client) -> list:
    """
    Determine who should respond to a message.
    
    Returns: [(agent_name, delay_hint), ...]
             delay_hint is one of: "immediate", "short", "medium", "long"
    """
    text = (msg.get("text") or "").lower()
    
    # 1. Direct mention — highest priority
    mentioned = _check_mentions(text, agents)
    if mentioned:
        return mentioned
    
    # 2. Keyword-based routing (no AI call needed)
    keyword_result = _keyword_route(text, agents)
    if keyword_result:
        return keyword_result
    
    # 3. AI-based routing (fallback)
    context = memory.get_context()
    ai_result = ai_client.route_message(msg, context)
    
    if ai_result is not None:
        return ai_result
    
    # 4. Ultimate fallback: Liam (PM catches everything)
    if agents["Liam"].is_available():
        return [("Liam", "short")]
    
    return []


def _check_mentions(text: str, agents: dict) -> list:
    """Check for direct @mentions."""
    results = []
    for name, agent in agents.items():
        if f"@{name.lower()}" in text:
            if agent.is_available():
                delay = agent.get_response_delay_default()
                results.append((name, delay))
    return results


def _keyword_route(text: str, agents: dict) -> Optional[list]:
    """Route based on topic keywords."""
    
    # Technical topics → Aiden
    tech_keywords = [
        "code", "bug", "error", "typescript", "node", "api",
        "database", "db", "pr", "review", "deploy", "package",
        "eslint", "config", "socket", "endpoint", "schema",
        "function", "import", "module",
    ]
    
    # PM topics → Liam
    pm_keywords = [
        "sprint", "issue", "ticket", "deadline", "blocker",
        "progress", "status", "timeline", "backlog",
        "standup", "retro", "board", "priority",
    ]
    
    # Business topics → Sarah
    biz_keywords = [
        "investor", "revenue", "demo", "milestone", "funding",
        "metric", "growth", "valuation", "pitch", "raise",
        "business", "strategy",
    ]
    
    # Marketing/UX topics → Chloe
    mkt_keywords = [
        "design", "ui", "ux", "competitor", "marketing",
        "onboarding", "flow", "brand", "campaign", "referral",
        "splitwise", "beem",
    ]
    
    # Score each agent
    scores = {
        "Aiden": sum(1 for kw in tech_keywords if re.search(rf'\b{kw}\b', text)),
        "Liam": sum(1 for kw in pm_keywords if re.search(rf'\b{kw}\b', text)),
        "Sarah": sum(1 for kw in biz_keywords if re.search(rf'\b{kw}\b', text)),
        "Chloe": sum(1 for kw in mkt_keywords if re.search(rf'\b{kw}\b', text)),
    }
    
    # Get the top scorer(s)
    max_score = max(scores.values())
    if max_score == 0:
        return None  # No keyword match, fall through to AI
    
    # Primary responder
    primary = max(scores, key=scores.get)
    if not agents[primary].is_available():
        return None
    
    result = [(primary, agents[primary].get_response_delay_default())]
    
    # Maybe add a secondary responder (30% chance, if another agent also scored)
    others = [name for name, score in scores.items() 
              if score > 0 and name != primary and agents[name].is_available()]
    
    if others and random.random() < 0.3:
        secondary = random.choice(others)
        result.append((secondary, "medium"))
    
    return result
