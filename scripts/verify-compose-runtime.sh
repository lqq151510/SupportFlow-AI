#!/usr/bin/env zsh
set -euo pipefail

REPOSITORY_ROOT=${0:A:h:h}
cd "$REPOSITORY_ROOT"

require_service() {
  local service=$1
  if [[ -z "$(docker compose ps -q "$service")" ]]; then
    print -u2 "Compose service is not running: $service"
    exit 1
  fi
}

require_service backend
require_service frontend
require_service redis
require_service elasticsearch
require_service rocketmq-broker

curl --fail --silent http://localhost:8080/actuator/health | rg -q '"status":"UP"'
curl --fail --silent --output /dev/null http://localhost:5173/
curl --fail --silent 'http://localhost:9200/_cluster/health?wait_for_status=green&timeout=20s' | rg -q '"status":"green"'
docker compose exec -T redis redis-cli ping | rg -qx 'PONG'
docker compose exec -T rocketmq-broker sh mqadmin topicRoute \
  -n rocketmq-namesrv:9876 -t support-domain-events | rg -q 'support-domain-events'

echo "SupportFlow AI Compose runtime checks passed."
