#!/usr/bin/env bash
# Smoke-test MCP endpoints against a running glow-api server.
#
# Usage:
#   ./verify_mcp.sh                         # unauth checks only
#   MCP_JWT=eyJ... ./verify_mcp.sh          # full sweep with bearer token
#   MCP_BASE=http://localhost:8000 MCP_JWT=eyJ... ./verify_mcp.sh
#
# Exit 0 if every check that was possible given the supplied env passed.

set -u
BASE="${MCP_BASE:-http://localhost:8000}"
JWT="${MCP_JWT:-}"
FAILED=0

section() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
pass()    { printf '  \033[32m✓\033[0m %s\n' "$1"; }
fail()    { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED=1; }

rpc() {
  # $1: method   $2: params json   $3: require_auth (0|1)
  local method="$1" params="$2" need_auth="$3"
  local hdrs=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')
  if [[ "$need_auth" == "1" && -n "$JWT" ]]; then
    hdrs+=(-H "Authorization: Bearer $JWT")
  fi
  curl -sS -m 15 "${hdrs[@]}" \
    -X POST "$BASE/mcp/" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$method\",\"params\":$params}"
}

section "PRM metadata (no auth)"
prm=$(curl -sS -m 10 "$BASE/.well-known/oauth-protected-resource")
echo "  $prm" | head -c 400; echo
if echo "$prm" | grep -q '"resource"'; then pass "PRM returns resource"; else fail "PRM missing"; fi

section "Unauth tools/list should be 401"
unauth=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' -X POST "$BASE/mcp/" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}')
if [[ "$unauth" == "401" ]]; then pass "401 without bearer"; else fail "expected 401, got $unauth"; fi

if [[ -z "$JWT" ]]; then
  section "Authed checks skipped"
  echo "  Set MCP_JWT=<bearer token> to run tools/list, prompts/list, prompts/get."
  exit $FAILED
fi

_extract_json() {
  # Peel an MCP streamable-HTTP SSE response down to its JSON payload.
  /Users/ashoksaravanan/Coding/learnloopllc-glow-api/.venv/bin/python3 -c '
import sys
body = sys.stdin.read()
for line in body.splitlines():
    if line.startswith("data: "):
        print(line[6:])
        break
else:
    print(body)
'
}

section "tools/list (authed)"
tools=$(rpc tools/list '{}' 1 | _extract_json)
tool_count=$(echo "$tools" | /Users/ashoksaravanan/Coding/learnloopllc-glow-api/.venv/bin/python3 -c '
import json, sys
try:
  r = json.load(sys.stdin)
  t = r.get("result", {}).get("tools", [])
  print(len(t))
except Exception as e:
  print(f"ERR:{e}")
')
echo "  tool_count=$tool_count"
echo "  raw (first 500 chars): $(echo "$tools" | head -c 500)"
if [[ "$tool_count" =~ ^[0-9]+$ ]] && (( tool_count > 0 )); then
  pass "tools/list returned $tool_count tools (scoped to caller's agent)"
elif [[ "$tool_count" == "0" ]]; then
  pass "tools/list returned 0 tools (caller has no MCP agent configured, or agent has no tools)"
else
  fail "tools/list malformed"
fi

section "prompts/list (authed)"
prompts=$(rpc prompts/list '{}' 1 | _extract_json)
echo "  raw (first 400 chars): $(echo "$prompts" | head -c 400)"
if echo "$prompts" | grep -q '"agent_system_prompt"'; then
  pass "agent_system_prompt prompt is visible"
elif echo "$prompts" | grep -q '"result"'; then
  pass "prompts/list ok (agent_system_prompt hidden — caller has no agent)"
else
  fail "prompts/list malformed"
fi

section "prompts/get agent_system_prompt (authed)"
sp=$(rpc prompts/get '{"name":"agent_system_prompt","arguments":{}}' 1 | _extract_json)
echo "  raw (first 600 chars): $(echo "$sp" | head -c 600)"
if echo "$sp" | grep -q '"messages"'; then
  pass "prompts/get returned messages"
else
  fail "prompts/get malformed or missing messages"
fi

exit $FAILED
