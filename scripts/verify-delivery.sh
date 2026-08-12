#!/usr/bin/env zsh
set -euo pipefail

REPOSITORY_ROOT=${0:A:h:h}

cd "$REPOSITORY_ROOT"
git diff --check
mvn -B -f backend/pom.xml verify
npm --prefix frontend run test:unit
npm --prefix frontend run build
docker compose config --quiet
k6 inspect -e SUPPORTFLOW_ACCESS_TOKEN=inspect-only perf/k6/api-orders.js >/dev/null
k6 inspect -e SUPPORTFLOW_ACCESS_TOKEN=inspect-only -e SUPPORTFLOW_CONVERSATION_ID=1 perf/k6/sse-chat.js >/dev/null

echo "SupportFlow AI delivery checks passed."
