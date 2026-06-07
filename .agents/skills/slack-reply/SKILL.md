---
name: slack-reply
description: Respond to a Slack message in character. Use when an agent needs to reply to a human or bot message in the team channel.
---

# Slack Reply

## When to use
- A human (Simon) sent a message relevant to your role
- Another team member @mentioned you
- A topic clearly in your domain came up

## Instructions

1. Decide: **reply or silence**
   - Topic NOT in your domain → silence
   - Someone else already covered it → silence
   - Directly mentioned or clearly relevant → reply
2. If replying, write in YOUR voice (see agents.md constraints)
3. This is Slack. Keep it short. Not an essay.

## Output format

```
<decision>reply OR silence</decision>
<delay>immediate OR short OR medium OR long</delay>
<response>your message</response>
```

## Delay guide
- immediate: urgent, direct question to you
- short: normal conversation flow
- medium: you're busy, low priority
- long: you'll get to it later

## Rules
- Write like you're on your phone between tasks
- If unsure whether to reply → silence is always safe
- Never repeat what another agent already said
