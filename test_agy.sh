#!/usr/bin/env bash
# =============================================================================
# Virtual Office — agy Integration Test Script
# Run this on the machine where agy is installed.
# Usage: bash test_agy.sh
# =============================================================================

# set -o pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"

pass() { echo -e "  ${GREEN}PASS${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}FAIL${NC} $1"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}WARN${NC} $1"; ((WARN++)); }
header() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

# =============================================================================
header "Level 1: agy CLI 기본 동작"
# =============================================================================

# 1.1 agy 설치 확인
echo -n "  1.1 agy --version: "
AGY_VERSION=$(agy --version 2>&1)
if [ $? -eq 0 ]; then
    pass "$AGY_VERSION"
else
    fail "agy not found or error: $AGY_VERSION"
fi

# 1.2 --add-dir 플래그
echo -n "  1.2 --add-dir flag: "
if agy --help 2>&1 | grep -q "add-dir"; then
    pass "exists"
else
    fail "not found in --help"
fi

# 1.3 --dangerously-skip-permissions 플래그
echo -n "  1.3 --dangerously-skip-permissions: "
if agy --help 2>&1 | grep -q "dangerously"; then
    pass "exists"
else
    fail "not found in --help"
fi

# 1.4 -p 플래그
echo -n "  1.4 -p (prompt) flag: "
if agy --help 2>&1 | grep -qE "\-p[, ]|--prompt"; then
    pass "exists"
else
    warn "not found in --help (might use different name)"
fi

# 1.5 기본 호출
echo -n "  1.5 basic call: "
BASIC=$(agy --dangerously-skip-permissions -p "Reply with exactly: HELLO_TEST" 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$BASIC" ]; then
    pass "got response (${#BASIC} chars)"
else
    fail "no response or error"
fi

# 1.6 --add-dir 동작
echo -n "  1.6 --add-dir workspace: "
ADDDIR=$(agy --add-dir "$WORKSPACE" --dangerously-skip-permissions -p "List the Python files you can see. Reply briefly." 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$ADDDIR" ]; then
    pass "got response (${#ADDDIR} chars)"
else
    fail "no response or error"
fi

# =============================================================================
header "Level 2: 서브에이전트 @멘션"
# =============================================================================

# 2.1 @liam 멘션
echo -n "  2.1 @liam mention: "
LIAM=$(agy --add-dir "$WORKSPACE" --dangerously-skip-permissions -p "@liam What's the sprint looking like?" 2>/dev/null)
LIAM_RC=$?
if [ $LIAM_RC -eq 0 ] && [ -n "$LIAM" ]; then
    pass "got response (${#LIAM} chars)"
    echo -e "       ${YELLOW}Preview:${NC} ${LIAM:0:120}..."
else
    fail "rc=$LIAM_RC, empty=$([[ -z "$LIAM" ]] && echo yes || echo no)"
fi

# 2.2 @aiden 멘션
echo -n "  2.2 @aiden mention: "
AIDEN=$(agy --add-dir "$WORKSPACE" --dangerously-skip-permissions -p "@aiden Should we use WebSocket or SSE for real-time?" 2>/dev/null)
AIDEN_RC=$?
if [ $AIDEN_RC -eq 0 ] && [ -n "$AIDEN" ]; then
    pass "got response (${#AIDEN} chars)"
    echo -e "       ${YELLOW}Preview:${NC} ${AIDEN:0:120}..."
else
    fail "rc=$AIDEN_RC"
fi

# 2.3 stderr 분리 확인
echo -n "  2.3 stderr separation: "
STDOUT=$(agy --add-dir "$WORKSPACE" --dangerously-skip-permissions -p "@liam say ok" 2>/tmp/agy_stderr_test)
STDERR=$(cat /tmp/agy_stderr_test 2>/dev/null)
if [ -n "$STDERR" ]; then
    warn "stderr has content (${#STDERR} chars): ${STDERR:0:80}"
else
    pass "stderr is clean"
fi

# =============================================================================
header "Level 3: 프롬프트 포맷 준수 (XML 태그)"
# =============================================================================

# 3.1 generate_response 포맷
echo -n "  3.1 XML tag output: "
XMLTEST=$(agy --add-dir "$WORKSPACE" --dangerously-skip-permissions -p '@liam

You are Liam. Stay in character.
Your engagement level: high. Your typical response speed: short.
Default to silence unless this message is clearly relevant to your role.

## New Message
From: Kong
Text: hey team, how are we tracking on the auth feature?

## Task
Decide whether to respond and what to say.

Output format:
<decision>reply OR silence</decision>
<delay>immediate OR short OR medium OR long</delay>
<response>your message here</response>
<actions>[]</actions>' 2>/dev/null)

HAS_DECISION=$(echo "$XMLTEST" | grep -c "<decision>")
HAS_RESPONSE=$(echo "$XMLTEST" | grep -c "<response>")
HAS_DELAY=$(echo "$XMLTEST" | grep -c "<delay>")

if [ "$HAS_RESPONSE" -gt 0 ]; then
    pass "has <response> tag"
else
    fail "no <response> tag found"
fi
echo -n "  3.1b tags found: "
echo -e "decision=$HAS_DECISION delay=$HAS_DELAY response=$HAS_RESPONSE"
echo -e "       ${YELLOW}Full output:${NC}"
echo "$XMLTEST" | head -20 | sed 's/^/       /'

# 3.2 silence 결정
echo -n "  3.2 silence decision: "
SILENCE_TEST=$(agy --add-dir "$WORKSPACE" --dangerously-skip-permissions -p '@aiden

You are Aiden. Stay in character.
Your engagement level: low. Your typical response speed: medium.
Default to silence unless this message is clearly relevant to your role.

## New Message
From: Kong
Text: anyone want to grab lunch?

## Task
Decide whether to respond and what to say.

Output format:
<decision>reply OR silence</decision>
<delay>immediate OR short OR medium OR long</delay>
<response>your message here</response>
<actions>[]</actions>' 2>/dev/null)

if echo "$SILENCE_TEST" | grep -qi "silence"; then
    pass "silence detected (good — Aiden ignoring lunch chat)"
else
    warn "Aiden replied to lunch chat (engagement too high?)"
fi
echo -e "       ${YELLOW}Decision:${NC} $(echo "$SILENCE_TEST" | grep -o '<decision>[^<]*</decision>' | head -1)"

# =============================================================================
header "Level 4: _call_ai_raw 시뮬레이션 (--add-dir 없이)"
# =============================================================================

# 4.1 라우팅 JSON
echo -n "  4.1 routing JSON: "
ROUTE=$(agy --dangerously-skip-permissions -p 'You are a routing assistant. Output only JSON.

---

Given this Slack message in a startup team channel:
"the API endpoint is returning 500 errors"

Who should respond? Pick 0-2 from: Liam, Aiden, Sarah, Chloe

Output JSON array only:
[{"name": "Name", "delay": "short"}]
Or: []' 2>/dev/null)

if echo "$ROUTE" | grep -q '\['; then
    pass "got JSON array"
    echo -e "       ${YELLOW}Output:${NC} $ROUTE"
else
    fail "no JSON array found"
    echo -e "       ${YELLOW}Got:${NC} ${ROUTE:0:200}"
fi

# 4.2 서브에이전트 미로딩 확인
echo -n "  4.2 no subagent without --add-dir: "
NO_SUB=$(agy --dangerously-skip-permissions -p "What agents do you have access to? Reply briefly." 2>/dev/null)
if echo "$NO_SUB" | grep -qi "liam\|aiden\|sarah\|chloe"; then
    warn "agents mentioned (might be from prompt context, not loaded)"
else
    pass "no agent names in response"
fi

# =============================================================================
header "Level 5: Python dry run"
# =============================================================================

# 5.1 AIClient 초기화
echo -n "  5.1 AIClient init: "
PY_AI=$(cd "$WORKSPACE" && python3 -c "
from integrations.ai import AIClient
ai = AIClient()
print(f'use_agy={ai.use_agy} circuit_open={ai._circuit_open}')
" 2>&1)
if echo "$PY_AI" | grep -q "use_agy=True"; then
    pass "agy detected: $PY_AI"
elif echo "$PY_AI" | grep -q "use_agy=False"; then
    warn "agy NOT detected by Python: $PY_AI"
else
    fail "error: $PY_AI"
fi

# 5.2 Agent frontmatter 파싱
echo -n "  5.2 Agent temperature parsing: "
PY_AGENT=$(cd "$WORKSPACE" && python3 -c "
from agents.agent import Agent
a = Agent('Liam', '.gemini/agents/liam.md')
print(f'name={a.name} temp={a.temperature}')
a2 = Agent('Aiden', '.gemini/agents/aiden.md')
print(f'name={a2.name} temp={a2.temperature}')
" 2>&1)
if echo "$PY_AGENT" | grep -q "temp=0"; then
    pass "$PY_AGENT"
else
    fail "$PY_AGENT"
fi

# 5.3 DB 초기화
echo -n "  5.3 DB init (scheduled_messages table): "
PY_DB=$(cd "$WORKSPACE" && python3 -c "
from memory.store import MemoryStore, get_connection
m = MemoryStore()
conn = get_connection()
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
conn.close()
print([t['name'] for t in tables])
" 2>&1)
if echo "$PY_DB" | grep -q "scheduled_messages"; then
    pass "table exists: $PY_DB"
else
    fail "missing table: $PY_DB"
fi

# 5.4 Scheduler DB persist
echo -n "  5.4 Scheduler persist: "
PY_SCHED=$(cd "$WORKSPACE" && python3 -c "
from integrations.slack import SlackClient
from integrations.github import GitHubClient
from agents.scheduler import Scheduler
slack = SlackClient()
github = GitHubClient()
s = Scheduler(slack, github)
s.schedule('Liam', 'test message', 5)
print(f'pending={s.pending_count()}')
# Clean up
from memory.store import get_connection
conn = get_connection()
conn.execute('DELETE FROM scheduled_messages')
conn.commit()
conn.close()
s.pending.clear()
print('cleaned up')
" 2>&1)
if echo "$PY_SCHED" | grep -q "pending=1"; then
    pass "$PY_SCHED"
else
    fail "$PY_SCHED"
fi

# =============================================================================
header "결과 요약"
# =============================================================================

echo ""
echo -e "  ${GREEN}PASS: $PASS${NC}  ${RED}FAIL: $FAIL${NC}  ${YELLOW}WARN: $WARN${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "  ${GREEN}All critical tests passed. Ready for live test.${NC}"
else
    echo -e "  ${RED}$FAIL test(s) failed. Fix before running live.${NC}"
fi

# Cleanup
rm -f /tmp/agy_stderr_test
