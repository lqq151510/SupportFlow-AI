#!/usr/bin/env zsh
set -euo pipefail

REPOSITORY_ROOT=${0:A:h:h}
SCENARIO=${1:-}

if [[ "${SUPPORTFLOW_CONFIRM_FAULT_DRILL:-}" != "yes" ]]; then
  echo "Refusing to stop infrastructure without SUPPORTFLOW_CONFIRM_FAULT_DRILL=yes." >&2
  exit 2
fi

case "$SCENARIO" in
  redis|elasticsearch|rocketmq-broker) SERVICE=$SCENARIO ;;
  *)
    echo "Usage: SUPPORTFLOW_CONFIRM_FAULT_DRILL=yes $0 {redis|elasticsearch|rocketmq-broker}" >&2
    exit 2
    ;;
esac

cd "$REPOSITORY_ROOT"
CONTAINER_ID=$(docker compose ps -q "$SERVICE")
if [[ -z "$CONTAINER_ID" ]]; then
  echo "$SERVICE is not running under this Compose project." >&2
  exit 1
fi

restore_service() {
  docker compose start "$SERVICE" >/dev/null
  for attempt in {1..60}; do
    HEALTH=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER_ID")
    if [[ "$HEALTH" == "healthy" || "$HEALTH" == "running" ]]; then
      echo "$SERVICE recovered with state: $HEALTH"
      return
    fi
    sleep 2
  done
  echo "$SERVICE did not recover within 120 seconds." >&2
  return 1
}
trap restore_service EXIT INT TERM

echo "Stopping $SERVICE to exercise the documented outage path..."
docker compose stop "$SERVICE" >/dev/null
STATE=$(docker inspect --format '{{.State.Status}}' "$CONTAINER_ID")
if [[ "$STATE" != "exited" ]]; then
  echo "Expected $SERVICE to be exited, got $STATE." >&2
  exit 1
fi
echo "$SERVICE outage confirmed. Inspect application behavior using docs/demo-runbook.md; automatic recovery starts now."
