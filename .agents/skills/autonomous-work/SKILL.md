---
name: autonomous-work
description: Plan and execute autonomous work like wiki writing, issue creation, or issue comments. Use during an agent's work block when they should proactively contribute to the project.
---

# Autonomous Work

## When to use
- It's your work block and you should check if anything needs doing

## Steps

1. Call `get_progress` — what's the sprint state?
2. Call `get_my_actions` — what have I already done?
3. Call `get_wiki_list` or `get_open_issues` — what already exists?
4. Decide: is there ONE thing that genuinely moves the project forward?

## Actions available
- **wiki_write**: Write/update a wiki document
- **issue_create**: Create a GitHub issue with acceptance criteria
- **issue_comment**: Comment on an existing issue (must have issue number)
- **none**: Nothing needs doing right now (this is fine!)

## Output format

```
<work_plan>
{
  "action": "wiki_write | issue_create | issue_comment | none",
  "title": "short title",
  "reason": "one sentence why this is needed NOW",
  "builds_on": "what previous work this continues (or null)"
}
</work_plan>
```

If action is not "none", also output the content:

For wiki_write:
```
<wiki_content>
(full markdown document)
</wiki_content>
<slack_message>short announcement in your voice</slack_message>
```

For issue_create:
```
<issue_body>
(issue body with description + acceptance criteria)
</issue_body>
<slack_message>short announcement in your voice</slack_message>
```

For issue_comment:
```
<comment_body>
(your comment)
</comment_body>
<slack_message>short update or empty if not worth announcing</slack_message>
```

## Critical rules
- NEVER create something that already exists
- Each action must BUILD ON previous work
- If unsure → "none" is always the right answer
- Announcements must be in your voice (see voice rules)
- After completing work, call `update_progress` to log it
