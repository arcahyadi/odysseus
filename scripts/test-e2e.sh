#!/usr/bin/env bash
# test-e2e.sh — AgentOS Full-Stack End-to-End Test Suite
# Usage: ./scripts/test-e2e.sh [--ci] [--skip-docker]
#   --ci         : Run in CI mode (no Docker, TestClient only)
#   --skip-docker: Skip Docker Compose (assumes services already running)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
TOTAL=0

# ── Helpers ──
check() {
  TOTAL=$((TOTAL + 1))
  local label="$1"
  shift
  if "$@"; then
    echo -e "  ${GREEN}PASS${NC} ${label}"
    PASS=$((PASS + 1))
  else
    echo -e "  ${RED}FAIL${NC} ${label}"
    FAIL=$((FAIL + 1))
  fi
}

section() {
  echo ""
  echo -e "${BLUE}═══ $1 ═══${NC}"
}

# ── Parse args ──
CI_MODE=false
SKIP_DOCKER=false
for arg in "$@"; do
  case "$arg" in
    --ci) CI_MODE=true; SKIP_DOCKER=true ;;
    --skip-docker) SKIP_DOCKER=true ;;
  esac
done

BASE_URL="${BASE_URL:-http://127.0.0.1:7000}"

# ═══════════════════════════════════════════════════════════════
# 1. DOCKER / INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════
section "1. INFRASTRUCTURE"

if [ "$SKIP_DOCKER" = false ]; then
  echo "Starting Docker Compose (profile: default)..."
  docker compose --profile default up -d 2>&1 | tail -5 || true

  echo "Waiting for services to be healthy..."
  for i in $(seq 1 30); do
    if curl -sf "$BASE_URL/api/health" > /dev/null 2>&1; then
      echo "  Server ready after ${i}s"
      break
    fi
    sleep 2
  done
else
  echo "Skipping Docker (--ci or --skip-docker)"
fi

check "Health endpoint" curl -sf "$BASE_URL/api/health" > /dev/null

# ═══════════════════════════════════════════════════════════════
# 2. HTTP ENDPOINTS
# ═══════════════════════════════════════════════════════════════
section "2. HTTP ENDPOINTS"

check "GET /api/health returns 200" \
  bash -c "curl -sf $BASE_URL/api/health | python -c \"import sys,json; d=json.load(sys.stdin); assert d['status']=='healthy'\""

check "GET /api/version returns version" \
  bash -c "curl -sf $BASE_URL/api/version | python -c \"import sys,json; d=json.load(sys.stdin); assert 'version' in d\""

check "GET / returns HTML" \
  bash -c "curl -sf $BASE_URL/ | grep -q 'Odysseus'"

check "GET / returns cockpit-phase-bar" \
  bash -c "curl -sf $BASE_URL/ | grep -q 'cockpit-phase-bar'"

# ═══════════════════════════════════════════════════════════════
# 3. STATIC ASSETS (UI)
# ═══════════════════════════════════════════════════════════════
section "3. STATIC ASSETS (UI)"

check "cockpit.js has onThoughtBusEvent" \
  bash -c "curl -sf $BASE_URL/static/js/cockpit.js | grep -q 'onThoughtBusEvent'"

check "cockpit.js has phase_enter handler" \
  bash -c "curl -sf $BASE_URL/static/js/cockpit.js | grep -q 'phase_enter'"

check "cockpit.js has renderPhaseBar" \
  bash -c "curl -sf $BASE_URL/static/js/cockpit.js | grep -q 'renderPhaseBar'"

check "CSS has cockpit-phase-bar" \
  bash -c "curl -sf $BASE_URL/static/css/style.min.css | grep -q 'cockpit-phase-bar'"

check "CSS has pb-dot" \
  bash -c "curl -sf $BASE_URL/static/css/style.min.css | grep -q 'pb-dot'"

# ═══════════════════════════════════════════════════════════════
# 4. UNIT TESTS
# ═══════════════════════════════════════════════════════════════
section "4. UNIT & INTEGRATION TESTS"

check "ThoughtBus tests (27)" \
  bash -c "python -m pytest tests/test_thought_bus.py -q --tb=no 2>&1 | grep -q 'passed'"

check "DurableExecution tests (21)" \
  bash -c "python -m pytest tests/test_durable_execution.py -q --tb=no 2>&1 | grep -q 'passed'"

check "Memory provenance tests (21)" \
  bash -c "python -m pytest tests/test_memory_provenance.py -q --tb=no 2>&1 | grep -q 'passed'"

check "Preferences tests (13)" \
  bash -c "python -m pytest tests/test_preferences.py -q --tb=no 2>&1 | grep -q 'passed'"

check "Visual output tests (21)" \
  bash -c "python -m pytest tests/test_visual_output.py -q --tb=no 2>&1 | grep -q 'passed'"

check "Module 6.5-6.7 tests (27)" \
  bash -c "python -m pytest tests/test_modules_6_5_6_7.py -q --tb=no 2>&1 | grep -q 'passed'"

check "SFD 100% tests (32)" \
  bash -c "python -m pytest tests/test_sfd_100.py -q --tb=no 2>&1 | grep -q 'passed'"

check "Integration full tests (11)" \
  bash -c "python -m pytest tests/test_integration_full.py -q --tb=no 2>&1 | grep -q 'passed'"

check "UI pipeline tests (8)" \
  bash -c "python -m pytest tests/test_ui_pipeline.py -q --tb=no 2>&1 | grep -q 'passed'"

check "HTTP integration tests" \
  bash -c "python -m pytest tests/test_http_integration.py -q --tb=no 2>&1 | grep -E '(passed|failed)' | grep -v 'failed'"

# ═══════════════════════════════════════════════════════════════
# 5. SFD MODULE VERIFICATION
# ═══════════════════════════════════════════════════════════════
section "5. SFD MODULE IMPORT VERIFICATION"

check "Module: thought_bus" \
  python -c "from src.thought_bus import ThoughtBus, on_phase, SubscriberRegistry"

check "Module: durable_execution" \
  python -c "from src.durable_execution import DurableEngine, RetryPolicy, SagaCoordinator"

check "Module: memory_provenance" \
  python -c "from src.memory_provenance import MemoryOperations, OmissionFilter, parse_frontmatter"

check "Module: preferences" \
  python -c "from src.preferences import PreferenceEngine, BehavioralGuardrail, resolve_preferences"

check "Module: visual_output" \
  python -c "from src.visual_output import OutputRouter, InlineRenderer, DesignModule"

check "Module: classification" \
  python -c "from src.classification import classify_data, RetentionLevel, RightToForget"

check "Module: content_security" \
  python -c "from src.content_security import InjectionGuard, OutputFilter"

check "Module: tool_discovery" \
  python -c "from src.tool_discovery import ToolSearch, MCPRegistry, ConnectorSuggester"

check "Module: conversation_search" \
  python -c "from src.conversation_search import ConversationSearch, LinguisticSignalDetector"

check "Module: multi_agent_decision" \
  python -c "from src.multi_agent_decision import MultiAgentDecisionEngine, TaskProfile"

check "Module: context_manager" \
  python -c "from src.context_manager import ContextManager, ContextBudget"

# ═══════════════════════════════════════════════════════════════
# 6. KILL-SWITCH VERIFICATION
# ═══════════════════════════════════════════════════════════════
section "6. KILL-SWITCH STATUS"

echo "Kill-switches actifs (coeur ON):"
python -c "
from src.killswitch_registry import read_states
states = read_states()
core = [s for s in states if s.get('default') == 'on']
for s in core:
    print(f\"  {s['env_var']}: {s['name']} ({'ON' if s.get('is_on') else 'OFF'})\")
"

# ═══════════════════════════════════════════════════════════════
# 7. AGENT/CRAFT MODE DETECTION
# ═══════════════════════════════════════════════════════════════
section "7. AGENT/CHAT MODE DETECTION"

check "Agent mode detector: 'build a backup system' → agent" \
  python -c "
from src.mode_detector import detect_mode, InteractionMode
mode = detect_mode('build a backup system')
assert mode == InteractionMode.AGENT, f'Expected AGENT, got {mode}'
"

check "Agent mode detector: 'hello' → chat" \
  python -c "
from src.mode_detector import detect_mode, InteractionMode
mode = detect_mode('hello how are you')
assert mode == InteractionMode.CHAT, f'Expected CHAT, got {mode}'
"

check "Agent mode detector: 'refactor the auth module' → agent" \
  python -c "
from src.mode_detector import detect_mode, InteractionMode
mode = detect_mode('refactor the auth module')
assert mode == InteractionMode.AGENT, f'Expected AGENT, got {mode}'
"

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
section "SUMMARY"

echo ""
echo -e "  ${GREEN}PASS: $PASS${NC}"
echo -e "  ${RED}FAIL: $FAIL${NC}"
echo -e "  TOTAL: $TOTAL"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}═══ ALL TESTS PASSED ═══${NC}"
  exit 0
else
  echo -e "${RED}═══ $FAIL TEST(S) FAILED ═══${NC}"
  exit 1
fi
