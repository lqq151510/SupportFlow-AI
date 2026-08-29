#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_DATA_DIR="${SUPPORTFLOW_DESKTOP_DATA_DIR:-$HOME/Library/Application Support/SupportFlow AI}"
BACKEND_LOG="$DESKTOP_DATA_DIR/logs/backend.log"
BACKEND_PID=""
KEYCHAIN_SERVICE="com.lqq.supportflow.model-secret.v1"
KEYCHAIN_ACCOUNT="MODEL_SECRET_MASTER_KEY"

stop_project_app() {
  while IFS= read -r pid; do
    test -n "$pid" && kill "$pid" 2>/dev/null || true
  done < <(pgrep -f "$ROOT_DIR/frontend/src-tauri/target/.*/app" || true)
}

cleanup() {
  if test -n "$BACKEND_PID"; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

resolve_model_secret() {
  if test -n "${MODEL_SECRET_MASTER_KEY:-}"; then
    printf '%s' "$MODEL_SECRET_MASTER_KEY"
    return
  fi

  local existing_key
  if existing_key="$(security find-generic-password -a "$KEYCHAIN_ACCOUNT" -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)"; then
    printf '%s' "$existing_key"
    return
  fi

  local generated_key
  generated_key="$(openssl rand -base64 32)"
  security add-generic-password -U -a "$KEYCHAIN_ACCOUNT" -s "$KEYCHAIN_SERVICE" -w "$generated_key" >/dev/null
  echo "Created a local encryption key in the macOS Keychain." >&2
  printf '%s' "$generated_key"
}

start_backend() {
  if curl --fail --silent http://localhost:8080/actuator/health >/dev/null 2>&1; then
    echo "Reusing the SupportFlow backend already running on port 8080."
    return
  fi

  mkdir -p "$DESKTOP_DATA_DIR/data" "$DESKTOP_DATA_DIR/logs"
  echo "Starting the persistent local H2 backend in cloud-model API mode..."
  echo "Local data directory: $DESKTOP_DATA_DIR/data"
  local model_secret_master_key
  model_secret_master_key="$(resolve_model_secret)"
  (
    cd "$ROOT_DIR/backend"
    MODEL_SECRET_MASTER_KEY="$model_secret_master_key" \
      SUPPORTFLOW_DESKTOP_DATA_DIR="$DESKTOP_DATA_DIR/data" \
      SUPPORTFLOW_MODEL_MOCK_ENABLED="${SUPPORTFLOW_MODEL_MOCK_ENABLED:-false}" \
      mvn -B spring-boot:run -Dspring-boot.run.profiles=desktop
  ) >"$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!

  for _ in $(seq 1 60); do
    if curl --fail --silent http://localhost:8080/actuator/health >/dev/null 2>&1; then
      echo "Backend is ready."
      return
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      tail -80 "$BACKEND_LOG" >&2
      return 1
    fi
    sleep 1
  done

  tail -80 "$BACKEND_LOG" >&2
  echo "Backend did not become healthy within 60 seconds." >&2
  return 1
}

stop_project_app

case "$MODE" in
  run)
    start_backend
    cd "$ROOT_DIR/frontend"
    npm run tauri -- dev
    ;;
  --debug|debug)
    start_backend
    cd "$ROOT_DIR/frontend"
    RUST_BACKTRACE=1 RUST_LOG=info npm run tauri -- dev
    ;;
  --logs|logs|--telemetry|telemetry)
    start_backend
    echo "Backend log: $BACKEND_LOG"
    cd "$ROOT_DIR/frontend"
    RUST_LOG=info npm run tauri -- dev
    ;;
  --verify|verify)
    start_backend
    cd "$ROOT_DIR/frontend"
    npm run test:unit
    npm run build:dmg
    hdiutil verify src-tauri/target/release/bundle/dmg/*.dmg
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
