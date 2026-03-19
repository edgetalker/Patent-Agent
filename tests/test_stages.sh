#!/usr/bin/env bash
# ============================================================
# Patent Agent 分阶段测试脚本
# 用法：bash tests/test_stages.sh
# 前提：服务已在 localhost:8000 运行
# ============================================================

set -e
BASE_URL="http://localhost:8000"
DISCLOSURE=$(cat tests/sample_data/disclosure.txt)
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}  ✓ PASS${NC} $1"; }
fail() { echo -e "${RED}  ✗ FAIL${NC} $1"; }
info() { echo -e "${YELLOW}  ▶ $1${NC}"; }

# ─── 阶段一：基础连通性 ───────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  阶段一：基础连通性测试"
echo "══════════════════════════════════════════"

info "健康检查..."
HEALTH=$(curl -s "${BASE_URL}/api/v1/health")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  pass "Health check OK: $HEALTH"
else
  fail "Health check failed: $HEALTH"
  exit 1
fi

info "404 测试（不存在的 session）..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v1/patent/sessions/invalid-id/state")
if [ "$STATUS" = "404" ]; then
  pass "404 correctly returned for invalid session"
else
  fail "Expected 404, got $STATUS"
fi

info "422 测试（交底书过短）..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${BASE_URL}/api/v1/patent/sessions/start" \
  -H "Content-Type: application/json" \
  -d '{"disclosure":"短","mirror_types":"方法"}')
if [ "$STATUS" = "422" ]; then
  pass "422 correctly returned for short disclosure"
else
  fail "Expected 422, got $STATUS"
fi

# ─── 阶段二：Step 1 SSE 流式输出 ─────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  阶段二：Step 1 SSE 流式输出测试"
echo "══════════════════════════════════════════"

info "启动 Step 1，流式接收输出（最多等待120秒）..."

PAYLOAD=$(jq -n --arg d "$DISCLOSURE" --arg m "方法" \
  '{"disclosure": $d, "mirror_types": $m}')

# 收集 SSE 事件到临时文件
TMP_SSE=$(mktemp)
timeout 120 curl -s -N -X POST "${BASE_URL}/api/v1/patent/sessions/start" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" > "$TMP_SSE" 2>&1 || true

# 提取 thread_id
THREAD_ID=$(grep '"session_created"' "$TMP_SSE" | head -1 | \
  python3 -c "import sys,json; line=sys.stdin.read(); \
  data=[l for l in line.split('\n') if 'data:' in l]; \
  print(json.loads(data[0].replace('data:','').strip())['thread_id'])" 2>/dev/null || echo "")

if [ -n "$THREAD_ID" ]; then
  pass "Session created | thread_id=${THREAD_ID:0:8}..."
else
  fail "Failed to get thread_id from SSE stream"
  echo "  SSE output:"
  cat "$TMP_SSE" | head -20
  exit 1
fi

# 检查是否有 token 事件
TOKEN_COUNT=$(grep -c '"type":"token"' "$TMP_SSE" || echo "0")
if [ "$TOKEN_COUNT" -gt "0" ]; then
  pass "Received $TOKEN_COUNT token events (streaming OK)"
else
  fail "No token events received"
fi

# 检查 step_complete 事件
if grep -q '"type":"step_complete"' "$TMP_SSE"; then
  STEP_NUM=$(grep '"step_complete"' "$TMP_SSE" | python3 -c \
    "import sys,json; \
    data=[l for l in sys.stdin.read().split('\n') if 'data:' in l]; \
    print(json.loads(data[-1].replace('data:','').strip()).get('step','?'))" 2>/dev/null || echo "?")
  pass "Step $STEP_NUM complete event received"
else
  fail "No step_complete event received"
  cat "$TMP_SSE" | tail -5
fi

rm -f "$TMP_SSE"

# ─── 阶段三：State 查询 ───────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  阶段三：State 查询测试"
echo "══════════════════════════════════════════"

info "查询 Session 状态..."
STATE=$(curl -s "${BASE_URL}/api/v1/patent/sessions/${THREAD_ID}/state")
STATUS_VAL=$(echo "$STATE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")

if [ "$STATUS_VAL" = "awaiting_review" ]; then
  pass "Session status = awaiting_review (HITL interrupt working)"
else
  fail "Expected awaiting_review, got $STATUS_VAL"
  echo "  State: $STATE"
fi

# ─── 阶段四：Submit Review（Step 1 → Step 2）────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  阶段四：提交审核（Step 1 → Step 2）"
echo "══════════════════════════════════════════"

info "提取 Step 1 输出内容..."
STEP1_OUTPUT=$(curl -s "${BASE_URL}/api/v1/patent/sessions/${THREAD_ID}/state" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  pr=d.get('pending_review',{}); print(pr.get('output','') if pr else '')" 2>/dev/null || echo "")

if [ -z "$STEP1_OUTPUT" ]; then
  fail "Could not extract Step 1 output"
  exit 1
fi
pass "Step 1 output extracted (len=${#STEP1_OUTPUT})"

info "提交 Step 1 审核结果，流式接收 Step 2 输出..."
TMP_SSE2=$(mktemp)

REVIEW_PAYLOAD=$(jq -n --arg c "$STEP1_OUTPUT" '{"content": $c}')
timeout 120 curl -s -N -X POST "${BASE_URL}/api/v1/patent/sessions/${THREAD_ID}/review" \
  -H "Content-Type: application/json" \
  -d "$REVIEW_PAYLOAD" > "$TMP_SSE2" 2>&1 || true

if grep -q '"step_complete"' "$TMP_SSE2"; then
  pass "Step 2 complete event received"
else
  fail "Step 2 did not complete"
  cat "$TMP_SSE2" | tail -10
fi

rm -f "$TMP_SSE2"

# ─── 总结 ─────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  测试完成"
echo "  THREAD_ID=${THREAD_ID}"
echo "  保留此 thread_id 继续手动测试后续步骤"
echo "══════════════════════════════════════════"
echo ""
echo "  后续手动测试命令："
echo "  curl -s '${BASE_URL}/api/v1/patent/sessions/${THREAD_ID}/state' | python3 -m json.tool"
echo "  curl -s '${BASE_URL}/api/v1/patent/sessions/${THREAD_ID}/export' | python3 -m json.tool"