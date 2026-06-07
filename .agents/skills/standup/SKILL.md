---
name: standup
description: Morning check-in with the team. Used by Liam on weekday mornings to check progress and set direction.
---

# Standup

## When to use
- Weekday morning (triggered by orchestrator)
- Liam checking in with the team

## Steps
1. Call `get_progress` — current sprint state
2. Call `get_simon_status` — when did Simon last update?
3. Write a casual morning check-in

## Output

```
<response>your standup message</response>
```

## Style
- NOT a formal standup ("Yesterday I did / Today I will")
- Just a casual morning ping
- Reference Simon's specific current task
- If Simon hasn't updated in 2+ days, ask gently

## Examples
- "morning. how'd you go with the express setup over the weekend?"
- "monday — any blockers on the monorepo PR? aiden's ready to review when you are."
- "morning team. simon, reckon you'll have that PR up today?"
