#!/usr/bin/env bash
# =============================================================================
# Virtual Office — Master Test Runner
# Runs all connectivity and integration tests sequentially.
# =============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

header() { 
    echo -e "\n${CYAN}==================================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}==================================================${NC}" 
}
passed() { echo -e "  ${GREEN}PASS${NC} $1"; }
failed() { echo -e "  ${RED}FAIL${NC} $1"; }
info() { echo -e "  ${YELLOW}INFO${NC} $1"; }

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"
cd "$WORKSPACE"

# Ensure Python dependencies are installed
info "Verifying Python dependencies..."
pip3 install -r requirements.txt > /dev/null 2>&1
if [ $? -eq 0 ]; then
    passed "Python dependencies installed"
else
    failed "Failed to verify python dependencies. Trying to proceed anyway..."
fi

# Initialize status flags
STATUS_SLACK=0
STATUS_GITHUB=0
STATUS_AGY=0
STATUS_INTEGRATION=0

# 1. Slack Smoke Test
header "Test 1: Slack Connectivity Smoke Test"
python3 test_slack.py
if [ $? -eq 0 ]; then
    STATUS_SLACK=1
else
    STATUS_SLACK=0
fi

# 2. GitHub Smoke Test (Read Connection)
header "Test 2: GitHub Connectivity Smoke Test"
python3 test_github.py
if [ $? -eq 0 ]; then
    STATUS_GITHUB=1
else
    STATUS_GITHUB=0
fi

# 3. agy CLI Integration Test
header "Test 3: agy CLI & Agent Loader Test"
bash test_agy.sh
if [ $? -eq 0 ]; then
    STATUS_AGY=1
else
    STATUS_AGY=0
fi

# 4. Pipeline Integration Test
header "Test 4: E2E Pipeline Mock Integration Test"
python3 test_integration.py
if [ $? -eq 0 ]; then
    STATUS_INTEGRATION=1
else
    STATUS_INTEGRATION=0
fi

# Final Report Summary
header "VIRTUAL OFFICE - TEST SUMMARY"
echo ""

if [ $STATUS_SLACK -eq 1 ]; then passed "Slack Smoke Test"; else failed "Slack Smoke Test"; fi
if [ $STATUS_GITHUB -eq 1 ]; then passed "GitHub Smoke Test"; else failed "GitHub Smoke Test"; fi
if [ $STATUS_AGY -eq 1 ]; then passed "agy CLI & Agent Loader Test"; else failed "agy CLI & Agent Loader Test"; fi
if [ $STATUS_INTEGRATION -eq 1 ]; then passed "Pipeline Integration Test"; else failed "Pipeline Integration Test"; fi

echo ""
TOTAL_PASSED=$((STATUS_SLACK + STATUS_GITHUB + STATUS_AGY + STATUS_INTEGRATION))

if [ $TOTAL_PASSED -eq 4 ]; then
    echo -e "${GREEN}🎉 All tests passed successfully! System is ready to run live.${NC}"
    exit 0
else
    echo -e "${RED}❌ $VERBOSE_ERRORS Some tests failed. Please check the logs above.${NC}"
    exit 1
fi
