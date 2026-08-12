#!/bin/zsh
set -euo pipefail

project_root=${0:a:h:h}
results_dir="$project_root/docs/reports"
runtime_dir=$(mktemp -d)
backend_pid=""

cleanup() {
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid"
    wait "$backend_pid" 2>/dev/null || true
  fi
  rm -rf "$runtime_dir"
}
trap cleanup EXIT INT TERM

if lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
  print -u2 "Port 8080 is already in use; stop the existing process before running the isolated load test."
  exit 1
fi

mkdir -p "$results_dir"
(
  cd "$project_root/backend"
  mvn -q spring-boot:run -Dspring-boot.run.arguments=--supportflow.model.mock.enabled=true
) >"$runtime_dir/backend.log" 2>&1 &
backend_pid=$!

for attempt in {1..60}; do
  if curl -fsS http://127.0.0.1:8080/actuator/health >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    tail -n 80 "$runtime_dir/backend.log" >&2
    exit 1
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8080/actuator/health >/dev/null

node "$project_root/perf/prepare-load-test.mjs" >"$runtime_dir/environment.json"
chmod 600 "$runtime_dir/environment.json"
access_token=$(node -e 'const fs=require("fs"); process.stdout.write(JSON.parse(fs.readFileSync(process.argv[1])).accessToken)' "$runtime_dir/environment.json")
conversation_id=$(node -e 'const fs=require("fs"); process.stdout.write(String(JSON.parse(fs.readFileSync(process.argv[1])).conversationId))' "$runtime_dir/environment.json")

SUPPORTFLOW_BASE_URL=http://127.0.0.1:8080 \
SUPPORTFLOW_ACCESS_TOKEN="$access_token" \
k6 run --summary-export "$results_dir/k6-api-orders.json" "$project_root/perf/k6/api-orders.js"

SUPPORTFLOW_BASE_URL=http://127.0.0.1:8080 \
SUPPORTFLOW_ACCESS_TOKEN="$access_token" \
SUPPORTFLOW_CONVERSATION_ID="$conversation_id" \
k6 run --summary-export "$results_dir/k6-sse-chat.json" "$project_root/perf/k6/sse-chat.js"
