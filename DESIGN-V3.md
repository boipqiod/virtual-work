# Virtual Office v3 — Architecture Design

## 목표

AI 에이전트 4명이 Slack에서 자연스럽게 협업하는 시뮬레이션.
Simon(너)이 진짜 호주 스타트업에서 리모트 주니어로 일하는 느낌.

**핵심 원칙:**
- Python = 배관 + 트리거 (언제, 누구를 호출할지)
- agy = AI 품질 (뭐라고 말할지, 뭘 할지, 어떤 톤으로)
- 대화가 반복되지 않고 계속 발전해야 함
- 코드 안 건드리고 `.agents/*.md`만 수정해서 품질 튜닝 가능

---

## 1. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│  Python Orchestrator (slim)                                  │
│  역할: 트리거, 배관, 타이밍만                                  │
│                                                              │
│  - 30초 tick loop                                            │
│  - Slack fetch (새 메시지 감지)                               │
│  - GitHub event polling (5분)                                │
│  - 시간대별 에이전트 on/off                                   │
│  - agy 호출 결정 (누구를, 언제)                               │
│  - 응답 스케줄링 + Slack 전송                                 │
│  - 진행 상태 파일 업데이트                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │  subprocess: agy --add-dir . -p "@agent skill-context"
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  agy (Antigravity CLI) — Native                              │
│  역할: AI 품질 전체 담당                                      │
│                                                              │
│  자동 로드:                                                   │
│  - .agents/agents.md      → 페르소나 (system instruction)     │
│  - .agents/skills/*/SKILL.md → 스킬별 지침                   │
│  - .agents/rules/*.md     → 항상 적용되는 제약               │
│                                                              │
│  agy가 판단:                                                  │
│  - 답할지 말지 (silence OK)                                  │
│  - 뭐라고 말할지 (voice 유지)                                │
│  - 뭘 할지 (스킬 선택)                                       │
│  - 액션 (이슈 생성, 위키 작성 등)                            │
└─────────────────────────────────────────────────────────────┘
```

### Python이 하는 것 (변하지 않는 것)
- Slack API 읽기/쓰기
- GitHub API 이벤트 감지
- 30초 tick loop
- 에이전트 시간표 관리 (daily_patterns.json)
- 딜레이 스케줄링 + 디스패치
- SQLite 메시지 히스토리
- 진행 상태 파일 관리 (state.json)
- Bot-to-bot 루프 방지 (카운트 기반)

### agy가 하는 것 (`.md` 파일로 제어)
- 페르소나 유지 (voice, tone, vocabulary)
- 대화 판단 (reply vs silence)
- 응답 생성
- 자율 작업 계획 + 실행
- 잡담 생성
- PR 리뷰
- 진행 상태 인식 (context로 주입)

---

## 2. 파일 구조

```
.agents/
├── agents.md                        ← 4명 페르소나 정의
├── rules/
│   ├── voice.md                     ← Always On: 톤/스타일 하드 제약
│   ├── progress-aware.md            ← Always On: 진행 상태 인식
│   └── no-repetition.md             ← Always On: 중복 행동 방지
├── skills/
│   ├── slack-reply/
│   │   └── SKILL.md                 ← Slack 메시지 응답
│   ├── autonomous-work/
│   │   └── SKILL.md                 ← 자율 작업 (위키/이슈/코멘트)
│   ├── casual-chat/
│   │   └── SKILL.md                 ← 팀 잡담
│   ├── code-review/
│   │   └── SKILL.md                 ← PR 리뷰 (Aiden)
│   ├── standup/
│   │   └── SKILL.md                 ← 아침 체크인 (Liam)
│   └── progress-check/
│       └── SKILL.md                 ← Simon에게 진행 확인
└── state/
    └── progress.md                  ← 현재 프로젝트 진행 상태 (자동 갱신)
```

---

## 3. agents.md

```markdown
# Shout Financial — Team

## Liam Carter (@liam) — Product Manager
Coordinates sprints, tracks progress, protects Simon from scope creep.
Australian male, friendly but structured. Uses "mate", "no dramas", "reckon".
1-4 sentences. Normal capitalization. Never discusses code details.

## Aiden O'Connor (@aiden) — Tech Lead  
Reviews PRs, sets architecture standards, gives blunt technical feedback.
Irish-Australian hybrid. Lowercase, terse, no exclamation marks ever.
1-2 sentences max. Goes straight to the point. Code snippets when needed.

## Sarah Jenkins (@sarah) — CEO
Business strategy, investor relations, demo readiness.
Short sharp sentences. Decisive. No fluff, no encouragement padding.
2-3 sentences max. Questions are pointed. Never discusses code.

## Chloe Bennett (@chloe) — Sales & Marketing
Competitor analysis, UX feedback, user growth, team morale.
Warm, energetic, 1-2 emojis occasionally. Casual Australian female.
1-4 sentences. References competitors and user experience.
```

**핵심:** 짧다. agy가 이걸 system instruction으로 로드하면 voice가 강하게 박힘. 지금처럼 수백 줄 페르소나보다 **제약이 선명**할수록 모델이 잘 따름.

---

## 4. Skills 설계

### 4.1 slack-reply (핵심 스킬)

```markdown
---
name: slack-reply
description: Respond to a Slack message in character. Use when an agent needs to reply to a human or bot message in the team channel.
---

# Slack Reply

## When to use
- A human (Simon) sent a message relevant to your role
- Another team member mentioned you
- A topic in your domain came up

## Instructions

1. Read the message and context provided
2. Decide: reply or silence
   - If the topic is NOT in your domain → silence
   - If someone else already covered it → silence
   - If directly mentioned or clearly relevant → reply
3. If replying, write in YOUR voice (see agents.md)
4. Keep it short. This is Slack, not an essay.

## Output format

<decision>reply OR silence</decision>
<delay>immediate OR short OR medium OR long</delay>
<response>your message</response>

## Critical rules
- NEVER start with "Hey team!"
- NEVER use corporate language ("I have published", "I am pleased to announce")
- Write like you're typing on your phone between tasks
- Aiden: lowercase, no !, max 2 sentences
- Liam: "mate", structured, max 4 sentences
- Sarah: sharp, decisive, max 3 sentences  
- Chloe: warm, 1 emoji max, max 4 sentences
```

### 4.2 autonomous-work

```markdown
---
name: autonomous-work
description: Plan and execute autonomous work (wiki writing, issue creation, comments). Use during an agent's work block when they should proactively contribute.
---

# Autonomous Work

## When to use
- It's the agent's work block
- There's something genuinely useful to do based on progress state

## Pre-check (MUST read first)
- Read .agents/state/progress.md for current project state
- Check what you've already done (listed in progress.md)
- Do NOT repeat anything already done

## Decision
Pick ONE action that moves the project forward:
- wiki_write: Write/update a wiki document
- issue_create: Create a GitHub issue with acceptance criteria
- issue_comment: Comment on an existing issue
- none: Nothing needs doing (this is fine!)

## Output format

<work_plan>
{
  "action": "wiki_write" | "issue_create" | "issue_comment" | "none",
  "title": "short title",
  "reason": "one sentence why this is needed NOW",
  "builds_on": "what previous work this continues (or null)"
}
</work_plan>

## Rules
- NEVER create an issue that already exists
- NEVER write a wiki page that already exists
- Each action must BUILD ON previous work, not repeat it
- If unsure, choose "none"
```

### 4.3 casual-chat

```markdown
---
name: casual-chat
description: Generate casual team banter. Use during quiet moments for natural team interaction unrelated to work.
---

# Casual Chat

## When to use
- It's a quiet moment, no active work discussion
- Team hasn't chatted casually in a while

## Instructions
- Write ONE casual message, NOT about work
- Must feel natural — something a real person would say in a team Slack
- Topics: weekend plans, food, TV shows, weather, local events, sports

## Output

<response>your casual message</response>

## Rules
- 1-2 sentences only
- No forced segues back to work
- Must be something YOUR CHARACTER would say
  - Liam: footy, weekend plans, barbecue
  - Aiden: dry humor, gaming, short observations
  - Sarah: rarely does this (very rare trigger)
  - Chloe: brunch spots, shows, team social ideas
```

### 4.4 code-review (Aiden 전용)

```markdown
---
name: code-review
description: Review a PR diff and provide technical feedback. Use when Aiden needs to review Simon's code.
---

# Code Review

## When to use
- A new PR was opened by Simon
- Aiden is available and in a work block

## Instructions
1. Read the diff provided in context
2. Focus on:
   - Does it follow CODING-STANDARDS.md?
   - Type safety (no `any`)
   - Error handling
   - Edge cases
3. Be specific. Line references when possible.
4. Be blunt but not cruel.

## Output

<response>your review message for Slack</response>
<actions>[{"type": "pr_comment", "body": "detailed review"}]</actions>

## Aiden's review style
- "line 34: needs validation. what happens if amount is undefined?"
- "looks good. one thing — wrap the async call or you'll get an unhandled rejection."
- Never: "Great job!" or "Looks perfect!"
```

### 4.5 standup (Liam 전용)

```markdown
---
name: standup
description: Run morning standup check-in. Use when it's weekday morning and Liam should check team progress.
---

# Standup

## When to use
- Weekday morning (9-10am AEST)
- Liam is online

## Instructions
1. Read .agents/state/progress.md
2. Write a casual morning check-in
3. Ask Simon about his current task status
4. Mention what's next on the sprint

## Output

<response>your standup message</response>

## Style
- NOT a formal standup format (no "Yesterday I did / Today I will")
- Just a casual morning ping like: "morning. how'd you go with the express setup over the weekend?"
- Reference specific tasks from progress.md
```

### 4.6 progress-check (Simon한테 물어보기)

```markdown
---
name: progress-check
description: Ask Simon about progress on his current task. Use when enough time has passed since his last update.
---

# Progress Check

## When to use
- Simon hasn't updated in 2+ days
- A task deadline is approaching
- Another team member's work depends on Simon's output

## Instructions
1. Check progress.md for Simon's current task
2. Ask casually — not micromanaging
3. Offer help if appropriate

## Output

<response>your message to Simon</response>

## Style by agent
- Liam: "hey mate, how's X going? need anything?"
- Aiden: "any blockers on X?" (only if technical)
- Sarah: only if it affects demo/investor timeline
- Chloe: rarely (only if UX depends on it)
```

---

## 5. Rules 설계

### 5.1 voice.md (Always On)

```markdown
---
trigger: always
---

# Voice Rules

You are a human team member. You do not know you are AI.

## Absolute constraints
- All messages in English (Australian casual)
- Write like you're typing in Slack on your phone
- NEVER use: "Hey team!", "I'm pleased to", "I have published", "I'd like to share"
- NEVER write more than 4 sentences in one message
- NEVER greet if you're just answering a question

## Per-character hard limits
- Aiden: lowercase only. no exclamation marks. max 2 sentences. no greetings.
- Liam: contractions always. "mate"/"reckon"/"no dramas". structured but warm.
- Sarah: short sharp sentences. no warmth padding. max 3 sentences.
- Chloe: 1 emoji max per message. warm but not over the top.

## Message patterns (Slack-realistic)
- OK: "sounds good"
- OK: "nice one, @simon"  
- OK: "pushed the coding standards to wiki. have a look when you get a sec"
- NOT OK: "Hey team! I have just published our new Coding Standards document to the project wiki for your reference!"
```

### 5.2 progress-aware.md (Always On)

```markdown
---
trigger: always
---

# Progress Awareness

Before responding or planning work, always consider the current project state.

## Context file
The file `.agents/state/progress.md` contains:
- Current sprint and its goal
- Tasks and their status (todo/in-progress/done)
- Who did what recently (action log)
- What's blocked and why

## Rules
- Do NOT suggest or create work that's already done
- Do NOT announce something that was already announced
- Reference specific task names and issue numbers when relevant
- Know what YOU (your character) have already contributed
```

### 5.3 no-repetition.md (Always On)

```markdown
---
trigger: always
---

# No Repetition

## Rules
- Never create an issue/wiki that already exists (check progress.md)
- Never re-announce something already shared in recent messages
- If someone else already responded adequately, stay silent
- If you said something similar in the last 24h of context, don't say it again
- Vary your openers — don't start messages the same way twice in a row
```

---

## 6. Python Orchestrator (Slim)

### 변경 전 vs 후

| 기존 (ai.py) | v3 |
|---|---|
| 800줄 프롬프트 하드코딩 | agy가 skills/rules 읽음 |
| XML 파싱 로직 | 동일 (출력 포맷은 유지) |
| `generate_response()` 내부 context 조합 | Python이 context 파일로 전달 |
| `plan_work()` 프롬프트 | `autonomous-work` 스킬로 이관 |
| `generate_casual_chat()` 프롬프트 | `casual-chat` 스킬로 이관 |
| Circuit breaker, Gemini fallback | 유지 (인프라니까) |

### Python이 하는 호출 패턴

```python
def call_agent(agent_name: str, skill_hint: str, context: str) -> str:
    """
    agy를 호출하되, 프롬프트는 최소화.
    skill은 agy가 context 보고 알아서 선택하게 둬도 되고,
    hint로 유도할 수도 있음.
    """
    prompt = f"""@{agent_name}

## Situation
{context}

## Task
{skill_hint}
"""
    # agy가 .agents/ 로드 → agents.md(페르소나) + rules(제약) + skills(행동) 자동 적용
    result = subprocess.run(
        ["agy", "--add-dir", WORKSPACE_DIR, "-p", prompt],
        capture_output=True, text=True, timeout=120
    )
    return result.stdout
```

### Tick 흐름 (슬림)

```python
def tick():
    # 1. Dispatch ready messages (배관)
    scheduler.dispatch_ready()
    
    # 2. Update agent online/offline (배관)
    update_agent_states()
    
    # 3. Slack 새 메시지 → 누구 호출할지만 결정 (배관)
    messages = slack.fetch_new()
    for msg in messages:
        agents_to_call = decide_responders(msg)  # 키워드 + 간단 규칙
        for agent_name in agents_to_call:
            # agy에게 넘기면 끝 — 뭐라고 말할진 agy가 결정
            response = call_agent(agent_name, "Reply to this message if relevant.", 
                                  build_context(msg))
            if response and not is_silence(response):
                scheduler.schedule(agent_name, response, calculate_delay(...))
    
    # 4. GitHub events (배관)
    events = github.fetch_events()
    for event in events:
        if is_own_action(event):  # ← 자기가 만든 이벤트 필터!
            continue
        agent = decide_github_responder(event)
        response = call_agent(agent, f"React to this GitHub event: {event}", 
                              build_context(event))
        ...
    
    # 5. Autonomous work (트리거만)
    for agent in agents:
        if agent.should_do_work(now):
            response = call_agent(agent.name, "Do autonomous work if needed.",
                                  build_context_with_progress())
            ...
    
    # 6. Ambient chat (트리거만)
    if should_trigger_chat():
        agent = pick_random_available()
        response = call_agent(agent.name, "Say something casual to the team.",
                              build_context_minimal())
        ...
```

### decide_responders() — 단순화

```python
def decide_responders(msg):
    """Python으로 빠르게 결정. AI 호출 안 함."""
    text = msg['text'].lower()
    
    # Direct mention → 해당 에이전트
    for name in agents:
        if f"@{name.lower()}" in text:
            return [name]
    
    # 키워드 기반 (기존 router.py와 동일)
    # ...
    
    # 매칭 없으면 → Liam (fallback)
    return ["Liam"]
```

**AI 기반 라우팅 제거.** 키워드 + @멘션으로 충분. 라우팅에 AI 쓰면 토큰 낭비 + 지연.

---

## 7. 진행 상태 관리

### `.agents/state/progress.md` (자동 갱신)

```markdown
# Project State

## Current Sprint: Sprint 1 — Foundation
Goal: Monorepo setup, Express backend, Next.js frontend, basic Socket.io chat room.

## Tasks
| # | Task | Assignee | Status | Issue |
|---|------|----------|--------|-------|
| 1 | Monorepo setup (npm workspaces) | Simon | in-progress | #10 |
| 2 | Express TypeScript backend | Simon | todo | - |
| 3 | Next.js frontend shell | Simon | todo | - |
| 4 | Basic Socket.io chat room | Simon | todo | - |

## Recent Actions (last 7 days)
- [Jun 2] Aiden: published Coding Standards wiki
- [Jun 2] Aiden: published WebSocket Resilience Guidelines wiki
- [Jun 3] Simon: created issue #10 (monorepo setup)
- [Jun 3] Liam: confirmed Simon starts this weekend
- [Jun 3] Aiden: posted architecture notes for monorepo structure
- [Jun 4] Sarah: published Investor Demo Scenario wiki

## What's Next
- Simon completes monorepo PR → Aiden reviews
- After merge → Express backend setup (Task #2)

## Blocked
- Nothing currently blocked
```

### 갱신 규칙

Python orchestrator가 **이벤트 발생 시** 이 파일을 업데이트:

```python
def update_progress(event_type, details):
    """progress.md에 한 줄 추가 또는 상태 변경."""
    # GitHub issue created → Tasks 테이블 업데이트
    # PR merged → Status 변경
    # Bot이 wiki 작성 → Recent Actions에 추가
    # 매일 자정 → 7일 이상 된 actions 정리
```

이러면 에이전트들이 항상 **"지금 어디까지 왔는지"** 를 알고, 거기서부터 다음 대화를 함.

---

## 8. 자기 행동 인지 (Self-awareness)

### 문제 해결: 봇이 만든 것을 봇이 모르는 현상

```python
# Python 레이어에서 해결:
OWN_ACTIONS_LOG = []  # 최근 24시간 내 봇이 실행한 action

def is_own_action(github_event):
    """봇이 만든 GitHub 이벤트인지 판별."""
    event_id = event.get("id")
    # 방법 1: action 실행 시 event_id 기록해두기
    if event_id in OWN_ACTIONS_LOG:
        return True
    # 방법 2: 제목 매칭 (최근 24시간 내 같은 제목 이슈 생성한 적 있으면)
    title = event.get("payload", {}).get("issue", {}).get("title", "")
    if title in recent_created_titles:
        return True
    return False
```

그리고 `progress.md`의 "Recent Actions"에 **누가 뭘 했는지** 기록되니까, 에이전트가 context로 읽을 때 "아 이건 내가 한 거네" 인식 가능.

---

## 9. 호출 흐름 예시

### Simon이 "monorepo setup done, PR ready" 보냄

```
[Python] slack.fetch → 새 메시지 감지
[Python] decide_responders("monorepo setup done, PR ready")
         → 키워드 "PR" → Aiden
         → 키워드 "setup" + "done" → Liam도 (30% 확률)
[Python] call_agent("Aiden", "Reply to this message if relevant.", context)
         context에 포함:
           - progress.md (현재 상태)
           - 최근 대화 20개
           - 새 메시지 텍스트
[agy] loads:
  - agents.md → Aiden 페르소나
  - rules/voice.md → "lowercase, no !, 2 sentences"
  - rules/progress-aware.md → "Task #1 monorepo, Simon assignee"
  - skills/slack-reply → "decide reply/silence, respond in voice"
[agy] output:
  <decision>reply</decision>
  <delay>medium</delay>
  <response>nice. i'll review it this arvo. make sure strict mode is on in tsconfig.</response>
[Python] parse → schedule("Aiden", text, delay=900초)
[Python] call_agent("Liam", ..., context)
[agy] output:
  <decision>reply</decision>
  <delay>short</delay>
  <response>sweet, nice one mate. @aiden let us know once you've had a look.</response>
[Python] schedule("Liam", text, delay=180초)

... 시간 경과 ...

[Python] scheduler.dispatch_ready()
         → Liam 메시지 전송 (3분 후)
         → Aiden 메시지 전송 (15분 후)
[Python] update_progress("Simon submitted PR for Task #1")
```

---

## 10. 대화 발전 메커니즘

### 왜 대화가 앞으로 가는가

1. **progress.md가 계속 갱신됨** → 에이전트가 "다음 뭐 하지?"를 항상 알 수 있음
2. **Recent Actions에 자기 기록** → 같은 거 반복 안 함
3. **What's Next 섹션** → 자율 작업이 이걸 보고 "다음 단계"를 함
4. **Blocked 섹션** → 블로커 있으면 물어보기 트리거

### 대화 소재 공급 흐름

```
Sprint 시작
  → Liam이 태스크 안내
  → Simon이 작업
  → Aiden이 리뷰
  → 머지 → 다음 태스크
  → (중간에) Chloe가 경쟁사 뉴스 공유
  → (중간에) Sarah가 데모 준비 상태 체크
  → Sprint 끝 → 회고 → 다음 Sprint
```

이게 자연스럽게 돌려면:
- `progress.md`의 "What's Next"가 바뀌면 → Liam standup에서 언급
- PR 머지되면 → 다음 태스크로 Status 이동 → Liam이 "다음은 이거야"
- 시간 지나면 → `progress-check` 스킬 트리거 → "어떻게 돼가?"

---

## 11. 마이그레이션 계획

### Phase 1: Rules + agents.md 먼저
1. `.agents/agents.md` 작성 (위 내용)
2. `.agents/rules/voice.md` 작성
3. 기존 `.gemini/agents/*.md` 참조하되 대폭 축소
4. 테스트: agy 직접 호출해서 voice 확인

### Phase 2: Skills 이관
1. `slack-reply` 스킬 작성 + 테스트
2. `autonomous-work` 스킬 작성
3. `ai.py`에서 하드코딩 프롬프트 제거, 스킬 기반으로 전환

### Phase 3: Orchestrator 슬림화
1. `ai.py` → `call_agent()` 단일 함수로 축소
2. `router.py` → AI 라우팅 제거, 키워드만
3. `progress.md` 자동 갱신 로직 추가
4. 자기 행동 필터 추가

### Phase 4: 튜닝
1. 실제 돌려보고 voice 안 맞는 부분 rules 수정
2. 대화 발전 속도 조정 (autonomous work interval)
3. 잡담 빈도 조정

---

## 12. MCP Server — 에이전트 도구 설계

### 개요

에이전트가 필요한 정보를 **직접 가져가는** 구조.
Python이 미리 조합해서 넘기는 게 아니라, agy가 MCP 도구를 호출해서 알아서 조회.

```
.agents/mcp_config.json
{
  "mcpServers": {
    "virtual-office": {
      "command": "python3",
      "args": ["tools/mcp_server.py"],
      "env": {
        "DB_PATH": "data/memory.db",
        "GITHUB_REPO": "boipqiod/shout"
      }
    }
  }
}
```

### 도구 목록

| 도구 | 설명 | 주 사용자 |
|------|------|-----------|
| `get_progress` | 현재 스프린트, 태스크 상태, What's Next | 모두 |
| `get_my_actions` | 내가 최근에 한 행동 목록 (중복 방지용) | 모두 |
| `get_recent_messages` | 최근 Slack 메시지 N개 | 모두 |
| `get_open_issues` | GitHub 오픈 이슈 목록 (번호, 제목, assignee) | Liam, Aiden |
| `get_pr_diff` | 특정 PR의 diff (리뷰용) | Aiden |
| `get_wiki_list` | 현재 위키 문서 목록 (중복 작성 방지) | Aiden, Sarah, Chloe |
| `get_blocked_tasks` | 블로커 있는 태스크 목록 | Liam, Sarah |
| `get_team_activity` | 최근 N일간 누가 뭘 했는지 요약 | Liam |
| `get_simon_status` | Simon 마지막 메시지/PR 시점 + 현재 태스크 | Liam |
| `update_progress` | 태스크 상태 변경, 액션 기록 추가 | 모두 (작업 완료 시) |

### 도구 상세

#### get_progress
```
Input: (없음)
Output: {
  "sprint": "Sprint 1 — Foundation",
  "goal": "Monorepo setup, Express backend, Next.js frontend, basic Socket.io chat",
  "tasks": [
    {"id": 1, "title": "Monorepo setup", "assignee": "Simon", "status": "in-progress", "issue": "#10"},
    {"id": 2, "title": "Express TypeScript backend", "assignee": "Simon", "status": "todo", "issue": null},
    ...
  ],
  "whats_next": "Simon completes monorepo PR → Aiden reviews → Express backend",
  "blocked": []
}
```

#### get_my_actions
```
Input: {"agent": "aiden", "days": 7}
Output: {
  "actions": [
    {"date": "2026-06-02", "type": "wiki_write", "title": "Coding Standards"},
    {"date": "2026-06-02", "type": "wiki_write", "title": "WebSocket Resilience Guidelines"},
    {"date": "2026-06-03", "type": "slack", "summary": "Posted architecture notes for monorepo"}
  ]
}
```

#### get_recent_messages
```
Input: {"limit": 20}
Output: {
  "messages": [
    {"ts": "...", "username": "Simon", "text": "is it ok if i start this weekend?"},
    {"ts": "...", "username": "Liam (PM)", "text": "no dramas at all, mate."},
    ...
  ]
}
```

#### get_open_issues
```
Input: (없음)
Output: {
  "issues": [
    {"number": 10, "title": "Setup monorepo with Next.js...", "assignee": "Simon", "state": "open", "created": "2026-06-03"},
    {"number": 11, "title": "...", "state": "open", ...}
  ]
}
```

#### get_pr_diff
```
Input: {"pr_number": 12}
Output: {
  "title": "feat: monorepo setup with npm workspaces",
  "author": "boipqiod",
  "diff": "diff --git a/package.json ...",
  "files_changed": ["package.json", "packages/backend/tsconfig.json", ...]
}
```

#### get_wiki_list
```
Input: (없음)
Output: {
  "pages": [
    "Coding Standards",
    "WebSocket Resilience Guidelines",
    "Investor Demo Scenario",
    "Competitor Analysis"
  ]
}
```

#### get_blocked_tasks
```
Input: (없음)
Output: {
  "blocked": [
    {"task": "Express backend", "reason": "waiting for monorepo PR merge", "blocked_since": "2026-06-03"}
  ]
}
```

#### get_team_activity
```
Input: {"days": 3}
Output: {
  "activity": {
    "Simon": {"last_seen": "2026-06-03", "current_task": "Monorepo setup", "messages": 5},
    "Aiden": {"actions": ["wrote Coding Standards wiki", "wrote WebSocket guide"]},
    "Liam": {"actions": ["created issue #9", "confirmed Simon's weekend plan"]},
    "Sarah": {"actions": ["wrote Investor Demo Scenario"]},
    "Chloe": {"actions": ["casual chat"]}
  }
}
```

#### get_simon_status
```
Input: (없음)
Output: {
  "last_message": "2026-06-03T09:22:00",
  "last_message_text": "is it ok if i start this weekend?",
  "current_task": "Monorepo setup (npm workspaces)",
  "days_since_update": 1,
  "has_open_pr": false
}
```

#### update_progress
```
Input: {
  "action": "add_log",
  "agent": "aiden",
  "entry": "wrote wiki 'API Error Handling Patterns'"
}
또는:
Input: {
  "action": "update_task",
  "task_id": 1,
  "status": "done"
}
Output: {"ok": true}
```

### 에이전트별 도구 사용 패턴

**Liam (standup 할 때):**
```
1. get_progress() → 현재 스프린트 상태 확인
2. get_simon_status() → Simon 마지막 활동 확인
3. → "morning mate, how'd the monorepo go over the weekend?"
```

**Aiden (자율 작업 할 때):**
```
1. get_progress() → 뭐가 필요한지
2. get_my_actions("aiden") → 내가 뭘 이미 했는지
3. get_wiki_list() → 어떤 문서가 이미 있는지
4. → "coding standards 있고, error handling 없네. 그거 쓰자."
5. (작업 후) update_progress() → 기록
```

**Aiden (PR 리뷰 할 때):**
```
1. get_pr_diff(12) → diff 가져오기
2. → 리뷰 작성
```

**Sarah (데모 체크 할 때):**
```
1. get_progress() → 스프린트 진행률
2. get_blocked_tasks() → 막힌 거 있는지
3. → "where are we at with the demo flow? anything blocked?"
```

**Chloe (자율 작업 할 때):**
```
1. get_my_actions("chloe") → 최근에 뭐 했는지
2. get_wiki_list() → 경쟁사 분석 있나
3. → "competitor analysis 업데이트 해야겠다"
```

### 데이터 소스

MCP 서버가 읽는 곳:

| 도구 | 소스 |
|------|------|
| get_progress, get_blocked_tasks | `data/progress.json` (Python이 관리) |
| get_my_actions, update_progress | `data/memory.db` (actions 테이블) |
| get_recent_messages | `data/memory.db` (messages 테이블) |
| get_open_issues, get_pr_diff | GitHub API (gh CLI) |
| get_wiki_list | `shout_wiki/` 디렉토리 ls |
| get_simon_status | `data/memory.db` + GitHub API |
| get_team_activity | `data/memory.db` (actions + messages) |

### progress 저장: JSON

.md 대신 **JSON으로** 진행 상태 관리. MCP 서버가 구조화된 데이터로 읽고 쓰기 편함.

```json
// data/progress.json
{
  "sprint": {
    "name": "Sprint 1",
    "goal": "Monorepo setup, Express backend, Next.js frontend, basic Socket.io chat",
    "start_date": "2026-06-01",
    "end_date": "2026-06-14"
  },
  "tasks": [
    {"id": 1, "title": "Monorepo setup", "assignee": "Simon", "status": "in-progress", "issue": 10},
    {"id": 2, "title": "Express TypeScript backend", "assignee": "Simon", "status": "todo", "issue": null},
    {"id": 3, "title": "Next.js frontend shell", "assignee": "Simon", "status": "todo", "issue": null},
    {"id": 4, "title": "Basic Socket.io chat room", "assignee": "Simon", "status": "todo", "issue": null}
  ],
  "whats_next": "Simon completes monorepo PR → Aiden reviews",
  "blocked": []
}
```

Python orchestrator가 이벤트 발생 시 이 파일을 갱신:
- PR opened → 해당 task status를 "in-review"로
- PR merged → "done"으로 + whats_next 업데이트
- Issue created → tasks에 추가
- Bot action 완료 → actions 테이블에 기록

---

## 13. 기존 대비 개선 요약

| 문제 | v2 | v3 |
|------|-----|-----|
| 캐릭터 톤 무시 | 6000자 context에 묻힘 | rules/voice.md가 Always On으로 강제 |
| 중복 작업 | progress 인식 없음 | progress.md 필수 참조 |
| 자기 행동 모름 | GitHub event 재처리 | own-action 필터 + action log |
| 대화 정체 | 매번 즉흥 판단 | What's Next → 방향성 제공 |
| 프롬프트 수정 = 코드 수정 | ai.py 하드코딩 | .md 파일만 수정 |
| AI 라우팅 비용 | 매 메시지 AI 호출 | 키워드 only, 빠르고 무료 |
