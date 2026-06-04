"""
Memory Compression — Daily summary generation.
Runs at midnight to compress today's conversation into a short summary.
"""

from datetime import datetime
from memory.store import MemoryStore


# Max characters to send in a single compression prompt (~8k tokens)
MAX_CONTEXT_CHARS = 30000


def compress_today(memory: MemoryStore, ai_client) -> str:
    """
    Compress today's conversation into a 5-10 line summary.
    Called at midnight by the orchestrator.
    """
    messages = memory.get_recent_messages(limit=100)
    
    if not messages:
        return "No activity today."
    
    conversation = ""
    for msg in messages:
        line = f"[{msg['username']}]: {msg['text']}\n"
        if len(conversation) + len(line) > MAX_CONTEXT_CHARS:
            conversation += "(... earlier messages truncated)\n"
            break
        conversation += line
    
    prompt = f"""
Summarize today's team conversation in 5-10 bullet points.
Focus on:
- Decisions made
- Tasks completed or started
- Blockers identified
- Key technical or business discussions

Conversation:
{conversation}

Output a concise summary (5-10 bullet points):
"""
    
    summary = ai_client._call_ai_raw(
        "You are a concise note-taker summarizing a startup team's daily Slack conversation.",
        prompt
    )
    
    if summary:
        today = datetime.now().strftime("%Y-%m-%d")
        memory.save_daily_summary(today, summary)
        return summary
    
    return "Failed to generate summary."
