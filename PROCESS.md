# Virtual Office v2 — Project Documentation

## Overview

Virtual Office는 AI 에이전트 4명(Liam/PM, Aiden/Tech Lead, Sarah/CEO, Chloe/Sales)이 Slack에서 실제 호주 스타트업 원격 팀처럼 행동하는 시뮬레이션이다. 영어 연습 + 개발 학습 + 이민 준비를 위한 프로젝트.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  main.py (Entry Point)                                       │
│  - dotenv 로딩                                               │
│  - graceful shutdown (flag 기반, 1초 단위 sleep)              │
│  - LOOP_INTERVAL env 지원                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  orchestrator.py (Main Loop — Single Process)                │
│                                                              │
│  tick() 순서:                                                │
│  1. scheduler.dispatch_ready()  — 딜레이 만료된 메시지 전송    │
│  2. agent.update_state()        — 시간 기반 상태 갱신         │
│  3. _check_slack()              — 새 메시지 fetch + 처리      │
│  4. _check_github()             — 이벤트 폴링 (5분마다)       │
│  5. _sync_wiki()                — git pull (10분마다)         │
│  6. _check_skill_triggers()     — 스탠드업/스프린트 플랜       │
│  7. autonomous work             — 에이전트별 자율 작업         │
│  8. _maybe_ambient_chat()       — 잡담 (매우 드물게)          │
│  9. _maybe_daily_compress()     — 자정 요약                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│  slack.py    │ │  ai.py   │ │  github.py   │
│  - 읽기(Bot) │ │  - agy   │ │  - gh CLI    │
│  - 쓰기(Hook)│ │  - Gemini│ │  - REST API  │
│  - enrich    │ │  - CB    │ │  - 캐싱      │
│  - decode    │ │  - parse │ │  - backoff   │
└──────────────┘ └──────────┘ └──────────────┘
```

---

## File Structure

```
~/dev/virtual-office/
├── main.py                          # 진입점 (dotenv, graceful shutdown)
├── .env                             # 실제 credentials (gitignore됨)
├── .env.template                    # 템플릿
├── .gitignore
├── requirements.txt                 # python-dotenv, google-generativeai
│
├── .gemini/
│   ├── GEMINI.md                    # 전역 규칙 (agy 자동 로드)
│   ├── agents/
│   │   ├── liam.md                  # PM 페르소나 (temp 0.7)
│   │   ├── aiden.md                 # Tech Lead (temp 0.3)
│   │   ├── sarah.md                 # CEO (temp 0.5)
│   │   └── chloe.md                 # Sales (temp 0.8)
│   └── skills/                      # Dead code — agy 자율모드용 예비
│       ├── standup.md
│       ├── review.md
│       ├── plan.md
│       ├── chat.md
│       └── compress.md
│
├── agents/
│   ├── orchestrator.py              # 메인 루프
│   ├── agent.py                     # Agent 클래스 (상태, 스케줄, frontmatter 파싱)
│   ├── scheduler.py                 # 딜레이 큐 (SQLite persist, 멱등 dispatch)
│   └── router.py                    # 키워드 + AI 라우팅
│
├── integrations/
│   ├── ai.py                        # agy 서브에이전트 + Gemini fallback + circuit breaker
│   ├── slack.py                     # 읽기/쓰기 + 페이지네이션 + user resolve + decode
│   └── github.py                    # 이슈/PR/위키 + 캐싱 + exponential backoff
│
├── memory/
│   ├── store.py                     # SQLite (messages, events, kv, scheduled_messages)
│   ├── retrieval.py                 # 컨텍스트 검색
│   └── compression.py              # 일일 요약 (토큰 제한)
│
├── config/
│   ├── daily_patterns.json          # 에이전트 일과 + engagement level
│   ├── project_context.md           # Shout 프로젝트 정보
│   └── prompts/router.txt           # AI 라우터 프롬프트
│
├── data/
│   └── memory.db                    # SQLite (자동 생성)
│
├── test_agy.sh                      # Level 1-5 agy CLI 테스트
├── test_integration.py              # 전체 파이프라인 통합 테스트
└── test_slack.py                    # Slack 연결 smoke test
```

---

## AI Backend: agy (Antigravity CLI)

### 호출 방식

```python
# 서브에이전트 호출 (페르소나 적용)
agy --add-dir {workspace} -p "@{agent_name}\n\n{prompt}"

# Raw 호출 (라우팅, 압축 등 — 서브에이전트 미로딩)
agy -p "{system_prompt}\n\n---\n\n{user_prompt}"
```

### 동작 원리
- `--add-dir`로 workspace 지정 → agy가 `.gemini/GEMINI.md` + `.gemini/agents/*.md` 자동 로드
- `@liam` 멘션 → 해당 `.md` 파일을 system instruction으로 사용
- stdout = AI 응답 (XML 태그 포함)
- stderr = agy 내부 로그 (분리됨)

### Circuit Breaker
- 연속 3회 실패 (타임아웃/에러) → 5분 cooldown
- cooldown 중 Gemini API fallback 사용
- cooldown 후 자동 리셋

### stdout 처리
- `_strip_preamble()`: 첫 번째 XML 태그 이전의 모든 텍스트 제거
- 실제 관찰: agy가 `"Answering the request in character as Aiden."` 같은 preamble 출력 → strip됨

---

## Message Flow (상세)

### 1. 메시지 수신

```
Slack API (conversations.history)
  → 페이지네이션 (cursor 기반, max 5페이지 = 50개)
  → oldest 파라미터로 마지막 처리 이후만
  → 틱당 MAX_PER_TICK=3 처리, 나머지는 DB 저장만
```

### 2. 메시지 전처리 (enrich)

```
enrich_message(msg):
  1. user ID (U0ABC123) → display name (resolve_user_id, 캐시)
  2. Slack 인코딩 디코딩:
     - <@U123> → @display_name
     - <#C123|channel> → #channel
     - <http://url|label> → label
     - &amp; &lt; &gt; → & < >
```

### 3. 라우팅

```
route(msg):
  1. @멘션 직접 확인 → 해당 에이전트
  2. 키워드 매칭 (tech/pm/biz/mkt 점수)
  3. AI fallback (_call_ai_raw → JSON 배열)
  4. 최종 fallback: Liam (PM이 모든 걸 받음)
```

### 4. 응답 생성

```
generate_response(agent, msg, context):
  프롬프트 구조:
    "You are {agent.name}. Stay in character.
     Your engagement level: {engagement}. Speed: {delay_default}.
     Default to silence unless relevant.
     
     ## Context (최근 50개 메시지 + GitHub state)
     ## New Message
     ## Other Responses Already Scheduled
     ## Task + Output format"
  
  출력 파싱:
    <decision>reply|silence</decision>  → exact match
    <delay>immediate|short|medium|long</delay>
    <response>메시지 텍스트</response>  → 미닫힘 fallback 있음
    <actions>[JSON]</actions>           → trailing comma 허용
```

### 5. 스케줄링

```
scheduler.schedule(agent_name, text, delay_seconds):
  1. ScheduledMessage 생성
  2. SQLite persist (scheduled_messages 테이블)
  3. pending 리스트에 추가
```

### 6. 디스패치

```
scheduler.dispatch_ready():
  1. is_ready() 확인 (send_at <= now)
  2. DB에 dispatched=1 마킹 (멱등성)
  3. slack.send_message() → bool 반환
  4. 실패 시: unmark + retry (max 3회, 60초 간격)
  5. 성공 시: actions 실행 → DB에서 삭제
```

### 7. 후처리 (send_message 내부)

```
_clean_message(text):
  1. wiki 링크 교정 (file:/// → GitHub URL)
  2. prompt leakage 감지 → 폐기
```

---

## Persona System

### 구조 (각 .gemini/agents/*.md)

```yaml
---
name: agent_name
description: 라우팅 설명
tools: [read_file, ...]
max_turns: N
temperature: 0.3-0.8
---

# Name — Role

LANGUAGE RULE: Always respond in English only.

## 3 Core Principles (CORE VALUE / DEFENSE / SECRET)
## Voice (톤, 길이, 슬랭)
## Knowledge Scope (talks about / ignores)
## Autonomous Work (할 수 있는 작업 유형)
## Few-Shot Examples (4-5개)
```

### 페르소나 차별화 메커니즘

| 레이어 | 방법 |
|--------|------|
| System instruction | agy가 .md 파일을 system prompt로 로드 |
| User prompt identity | `"You are {name}. Stay in character."` |
| Engagement level | daily_patterns.json → 프롬프트에 주입 |
| Temperature | frontmatter에서 파싱 → Gemini API fallback에 적용 |
| Silence guidance | 에이전트별 "ignores" 목록 + engagement level |
| Vocabulary ceiling | Liam: max "backend, frontend, PR" |

### Temperature 설정

| Agent | Temp | 효과 |
|-------|------|------|
| Aiden | 0.3 | 예측 가능, 간결, 일관적 |
| Sarah | 0.5 | 결단력 있되 약간의 변화 |
| Liam | 0.7 | 자연스러운 대화, 적당한 다양성 |
| Chloe | 0.8 | 에너지 있고 창의적, 가장 다양 |

---

## Safety & Resilience

### Fault Tolerance

| 장애 시나리오 | 대응 |
|--------------|------|
| Slack 읽기 실패 | 빈 배열 반환, 다음 틱에 재시도 |
| Slack 쓰기 실패 | bool 반환 → scheduler retry (max 3) |
| agy 타임아웃 (120s) | circuit breaker → Gemini fallback |
| agy 연속 실패 | 3회 후 5분 cooldown |
| GitHub rate limit | exponential backoff (60s→900s) |
| SQLite 에러 | try/except per method, connection 정리 |
| 프로세스 재시작 | scheduled_messages DB에서 복원 |
| 메시지 폭주 | 틱당 3개 cap, 나머지 DB 저장만 |

### Bot-to-Bot Loop Prevention

```
1. count_recent_bot_messages(10분) + scheduler.pending 합산
2. 합계 >= 3 → 봇 응답 차단
3. 봇 메시지는 @멘션 있을 때만 응답
```

### Dispatch Idempotency

```
1. schedule → DB에 dispatched=0으로 저장
2. dispatch 시작 → dispatched=1 마킹
3. 전송 성공 → DB에서 삭제
4. 전송 실패 → dispatched=0 복원 + retry
5. 프로세스 크래시 → 재시작 시 dispatched=0만 로드
```

### Graceful Shutdown

```
1. SIGINT/SIGTERM → _shutting_down = True
2. 현재 틱 완료 대기 (1초 단위 체크)
3. 두 번째 Ctrl+C → os._exit(1) 강제 종료
4. agy subprocess: start_new_session=True (프로세스 그룹 분리)
```

---

## Data Storage (SQLite)

### Tables

```sql
messages          — Slack 메시지 히스토리 (ts UNIQUE, is_bot, created_at UTC)
events            — GitHub 이벤트 (event_id UNIQUE)
agent_state       — 에이전트 상태 (미사용, 향후 확장)
daily_summaries   — 일일 요약 (date PRIMARY KEY)
kv                — key-value (last_slack_ts, last_github_event_id, last_ambient_chat)
scheduled_messages — 스케줄된 메시지 (dispatched flag, retry_count)
```

### Indexes

```sql
idx_messages_bot_time ON messages(is_bot, created_at)
```

### 시간 규칙
- DB: `datetime('now')` = UTC
- 쿼리: `datetime.utcnow()` 사용
- 에이전트 스케줄: `datetime.now()` (로컬 시간 — 호주 시간대 기준)

---

## Configuration

### daily_patterns.json

```json
{
  "Liam": {
    "wake_hour": 8,
    "sleep_hour": 18,
    "work_blocks": [[9, 12], [13, 17]],
    "slack_check_interval_minutes": [30, 60],
    "response_delay_default": "short",
    "autonomous_work_interval_hours": [8, 14],
    "engagement": "high — responds to most messages, coordinates the team"
  }
}
```

### Delay Ranges

| Hint | 초 (min-max) |
|------|-------------|
| immediate | 15-60 |
| short | 60-300 |
| medium | 600-1800 |
| long | 3600-7200 |

추가 responder는 position × 120-600초 추가.

---

## Testing

### test_agy.sh — CLI 동작 확인

```
Level 1: agy 플래그 존재 + 기본 호출
Level 2: @agent 서브에이전트 멘션 + stderr 분리
Level 3: XML 태그 출력 + silence 결정
Level 4: --add-dir 없이 라우팅 JSON
Level 5: Python AIClient/Agent/DB/Scheduler 초기화
```

### test_slack.py — Slack 연결 확인

```
1. 환경변수 존재 확인
2. Bot Token auth.test
3. conversations.history 읽기
4. users.info scope 확인
5. Webhook 전송 (--send 플래그)
```

### test_integration.py — 전체 파이프라인

```
Test 1: Human → Route → AI → Parse (XML 태그, 영어, delay)
Test 2: Silence 결정 (무관한 메시지)
Test 3: Autonomous Work Planning (plan_work JSON)
Test 4: Casual Chat Generation
Test 5: Router AI Fallback (JSON 배열)
Test 6: Scheduler + Dispatch (dry run)
Test 7: Circuit Breaker (시뮬레이션)
Test 8: Persona Differentiation (같은 질문, 다른 답)
```

---

## Modification History

### Round 1: Logic Bugs (14건)

| ID | 파일 | 수정 |
|----|------|------|
| C1 | ai.py | `_strip_preamble()` — agy stdout 오염 방어 |
| C2 | ai.py | `_call_ai_raw`에서 `--add-dir` 제거 — @멘션 오발동 차단 |
| C3 | ai.py | `plan_work` 프롬프트에 `issue_number` 추가 + 파싱 검증 |
| C4 | orchestrator.py | 봇 카운트에 scheduler.pending 합산 |
| M1 | store.py | `datetime.utcnow()` 통일 |
| M2 | store.py | 봇 감지에 username 체크 추가 |
| M3 | orchestrator.py | `set_last_ts` 루프 밖으로 이동 |
| M4 | orchestrator.py | `execute_work` 실패 시 1-2시간 후 재시도 |
| M5 | github.py | `get_project_state()` 5분 TTL 캐시 |
| M6 | scheduler.py | action 실패 시 3회 retry 후 drop |
| M7 | ai.py | `<response>` 태그 미닫힘 fallback |
| M8 | ai.py | `route_message` JSON 추출 강화 |
| L3 | store.py | bare `except:` → `except (ValueError, TypeError):` |
| L6 | ai.py | Gemini fallback에서 YAML frontmatter strip |

### Round 2: Data Flow + Fault Tolerance (10건)

| ID | 파일 | 수정 |
|----|------|------|
| F1 | slack.py + scheduler.py | `send_message` → bool 반환 + retry 연동 |
| F2 | ai.py | circuit breaker (3회 실패 → 5분 cooldown) |
| F3 | orchestrator.py | 틱당 메시지 처리 cap (MAX_PER_TICK=3) |
| D1 | slack.py | 페이지네이션 (cursor 기반, max 5페이지) |
| D2 | slack.py | `resolve_user_id()` + 캐시 |
| D3 | slack.py | `_decode_slack_text()` — Slack 인코딩 정리 |
| D4 | scheduler.py + store.py | SQLite persist (scheduled_messages 테이블) |
| D6 | compression.py | limit 200→100, 30000자 하드캡 |
| F4 | github.py | exponential backoff (60s→900s) |
| F6 | store.py | `idx_messages_bot_time` 인덱스 |

### Round 3: Prompt Reliability + Persona Isolation (8건)

| ID | 파일 | 수정 |
|----|------|------|
| P3 | ai.py | silence 판정 exact match (`in` → `==`) |
| P5 | ai.py | `_parse_work_result` 태그 미닫힘 fallback |
| B-1 | ai.py | user prompt에 `"You are {agent.name}"` 추가 |
| B-2 | daily_patterns.json | engagement level 필드 추가 |
| B-3 | agent.py + ai.py | frontmatter temperature 파싱 → Gemini API 적용 |
| B-4 | ai.py | 행동 패턴 (delay, engagement) 모델에 노출 |
| A-4 | ai.py | JSON 파싱 관대화 (trailing comma, fence strip) |
| C-1 | ai.py | Think: 섹션 제거 (토큰 절약) |

### Round 4: Shutdown Safety + Idempotency (4건)

| ID | 파일 | 수정 |
|----|------|------|
| S1 | main.py | flag 기반 graceful shutdown + 1초 sleep 분할 |
| S1 | ai.py | `start_new_session=True` (프로세스 그룹 분리) |
| S3 | scheduler.py + store.py | dispatch 멱등성 (dispatched 컬럼) |
| S2 | — | skills/*.md 유지 결정 (삭제 안 함) |

### Round 6: Logic Bugs — Data Loss & Stability (8건)

| ID | 파일 | 수정 |
|----|------|------|
| R6-1 | orchestrator.py | overflow 메시지 ts를 latest_ts에 반영하지 않도록 변경 (메시지 유실 방지) |
| R6-2 | scheduler.py | 6개 DB 접근 메서드에 try/finally 커넥션 정리 |
| R6-3 | orchestrator.py + agent.py | autonomous work 실패 카운터 (3회 초과 시 정상 간격 복귀) |
| R6-4 | orchestrator.py | `_build_rich_context` 결과 6000자 하드캡 |
| R6-5 | orchestrator.py | Liam PR 하드코딩 응답 → AI 생성으로 교체 |
| R6-6 | router.py | 키워드 매칭에 `\b` 단어 경계 체크 (false positive 방지) |
| R6-7 | orchestrator.py | `_handle_human_message` responder 중복 제거 |
| R6-8 | agent.py | `_work_fail_count` / `_max_work_failures` 필드 추가 |

### Round 7: Deep Review — Resilience, Fallback, UX (13건)

| ID | 파일 | 수정 |
|----|------|------|
| R7-1 | ai.py | `_call_ai`에 Gemini fallback 추가 (circuit open 시 Gemini로 전환) |
| R7-2 | orchestrator.py | GitHub event_id를 루프 후에만 저장 + `_handle_github_event` try/except |
| R7-3 | ai.py | subprocess Popen + os.killpg로 orphan 프로세스 방지 |
| R7-4 | orchestrator.py | `_do_autonomous_work` 전체 try/except (예외 시 정상 간격 복귀) |
| R7-5 | store.py | 읽기 메서드 6개에 try/finally 커넥션 정리 |
| R7-6 | orchestrator.py | `latest_ts`를 max()로 계산 (순서 의존성 제거) |
| R7-7 | orchestrator.py | `_handle_bot_message` break를 available 체크 안쪽으로 이동 |
| R7-8 | orchestrator.py | responder 루프에 per-agent try/except |
| R7-9 | ai.py | Gemini API 전용 circuit breaker 추가 |
| R7-10 | ai.py | `_extract_json_array` greedy regex → non-greedy |
| R7-11 | orchestrator.py | `_build_rich_context` 틱 단위 캐싱 |
| R7-12 | orchestrator.py | daily compress window 5분 → 30분 |
| R7-13 | orchestrator.py | IssuesEvent Liam 하드코딩 → AI 생성 |

### Round 7.5: Infra Fixes (5건)

| ID | 파일 | 수정 |
|----|------|------|
| R7.5-1 | slack.py | channel mention 신형식 `<#C123>` 지원 |
| R7.5-2 | github.py | wiki title sanitize (`/\:*?<>\|` 제거) |
| R7.5-3 | router.py | 오분류 키워드 제거 (type, class, when, user) |
| R7.5-4 | ai.py | `_fix_json` single quote → double quote 변환 추가 |
| R7.5-5 | ai.py | dead import `signal` 제거 |

### Round 8: Language Fix — LANG Environment (1건)

| ID | 파일 | 수정 |
|----|------|------|
| R8-1 | ai.py | subprocess 호출 시 `env={"LANG":"en_US.UTF-8","LC_ALL":"en_US.UTF-8"}` 강제 |

### Round 8.5: Overflow 중복 처리 방지 + plan_work 중복 제거 (2건)

| ID | 파일 | 수정 |
|----|------|------|
| R8.5-1 | orchestrator.py | overflow 메시지 save_message 제거 (다음 틱에서 자연스럽게 재fetch) |
| R8.5-2 | ai.py | `plan_work` project_state 파라미터 optional화 + 빈 문자열 시 섹션 미표시 |

---

## Future Improvements (Backlog)

### 대화 자연스러움

| 항목 | 구현 방식 |
|------|-----------|
| 이모지 리액션 (👍👀✅) | Slack reactions API 연동 — 코드에서 확률 제어 |
| 오타/실수 | `random.random() < 0.1` 시 프롬프트에 "실수해라" 지시 주입 |
| 메시지 분할 | 확률 기반으로 `<response>` 여러 개 허용 |
| 무드 변동 | 매일 아침 랜덤 mood 생성, 프롬프트에 삽입 |
| AFK/일상 표현 | "brb", "back", "internet's weird" 등 패턴 |
| 답장 지연 사과 | "oh sorry just saw this" 패턴 |
| 대화 포크 | 동시에 2개 토픽 진행 가능하도록 |

### 운영 안정성

| 항목 | 설명 |
|------|------|
| 프로세스 감시 | launchd plist 또는 supervisord |
| DB retention | 30일 이상 된 messages/events 정리 |
| 로그 로테이션 | Python logging + RotatingFileHandler |
| health check | 주기적 Slack ping 또는 파일 touch |
| 모니터링 | circuit breaker 상태, 큐 크기 외부 노출 |

### 보안

| 항목 | 설명 |
|------|------|
| 프롬프트 인젝션 방어 | 사용자 텍스트 sanitize (XML 태그 strip, 500자 제한) |
| 컨텍스트 노출 제한 | 민감 정보 마스킹 |
| webhook URL 로그 마스킹 | 에러 메시지에서 URL 제거 |
| 일일 AI 호출 budget cap | 하루 100회 초과 시 차단 |

---

## Known Limitations

1. **users:read scope 없음** — user ID가 이름으로 안 바뀜 (Slack App 설정에서 추가 필요)
2. **GitHub App 미지원** — 현재 코드는 PAT/gh CLI 기반. PEM 기반 App 인증 미구현
3. **skills/*.md dead code** — orchestrator가 직접 프롬프트 구성. agy 자율모드 지원 시 활용 가능
4. **Wiki push 미구현** — `github.py:push_wiki`가 로컬 파일만 쓰고 git commit+push 안 함
5. **Temperature agy 미적용** — agy가 frontmatter temperature를 읽는지 미확인. Gemini fallback에서만 적용됨
6. **Anti-convergence 없음** — 장기 운영 시 에이전트 voice가 수렴할 수 있음. few-shot 로테이션 미구현
7. **이모지 리액션 미구현** — Slack reactions API 연동 없음. 실제 팀 대비 가장 부자연스러운 부분
8. **프로세스 감시 없음** — launchd/systemd 미설정. 크래시 시 수동 재시작 필요
9. **SQLite retention 없음** — messages/events 테이블 무한 성장. 30일 이상 운영 시 정리 필요
10. **프롬프트 인젝션 방어 없음** — Slack 메시지 텍스트가 무가공으로 AI 프롬프트에 삽입됨

---

## Deployment Checklist

```bash
# 1. 코드 복사
cp -r ~/dev/virtual-office/ /target/path/

# 2. 의존성
pip3 install python-dotenv google-generativeai

# 3. 환경 설정
cp .env.template .env
# .env 편집: Slack tokens, webhooks, GitHub repo

# 4. 위키 클론
git clone https://github.com/boipqiod/shout.wiki.git shout_wiki/

# 5. agy 확인
agy --version

# 6. 테스트 순서
bash test_agy.sh              # agy CLI 동작
python3 test_slack.py         # Slack 연결 (읽기)
python3 test_slack.py --send  # Slack 웹훅 (쓰기)
python3 test_integration.py   # 전체 파이프라인

# 7. 실행
python3 main.py
```

---

## Design Decisions (Why)

| 결정 | 이유 |
|------|------|
| Single process | Race condition 방지, 디버깅 용이 |
| agy native subagent | System instruction 레벨 페르소나 (user prompt보다 강함) |
| 에이전트 도구 제한 | Aiden만 grep_search, 나머지는 read_file만. 안전성 |
| 쓰기는 orchestrator가 | 에이전트가 직접 파일/이슈 못 만듦. 코드가 통제 |
| AI가 silence 결정 | 침묵도 유효한 행동. 모든 메시지에 답할 필요 없음 |
| Keyword router 우선 | AI 호출 절약. 명확한 토픽은 키워드로 충분 |
| SQLite | 외부 의존성 없음. 단일 프로세스에 적합 |
| Webhook per character | 각 에이전트가 다른 이름/아이콘으로 표시 |
| Bot token for reading | 하나의 토큰으로 채널 전체 읽기 |
