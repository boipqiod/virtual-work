---
name: progress-check
description: Ask Simon about progress on his current task. Use when enough time has passed since his last update or when dependencies are waiting.
---

# Progress Check

## When to use
- Simon hasn't updated in 2+ days
- A task deadline is approaching
- Another team member's work depends on Simon's output

## Steps
1. Call `get_simon_status` — last activity, current task
2. Call `get_progress` — what's blocked or waiting
3. Write a casual check-in (NOT micromanaging)

## Output

```
<response>your check-in message</response>
```

## Style by agent
- **Liam**: "hey mate, how's X going? need anything?"
- **Aiden**: "any blockers on X?" (only if technical, very terse)
- **Sarah**: "where are we at with X?" (only if affects demo/investors)
- **Chloe**: rarely uses this skill

## Rules
- Don't ask if Simon updated recently (check first!)
- Don't pile on — if someone already asked today, stay silent
- Offer help, not pressure
