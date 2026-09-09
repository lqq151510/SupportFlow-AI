#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
OUTPUT_DIR="$BACKEND_DIR/target/desktop"
INPUT_DIR="$BACKEND_DIR/target/desktop-input"
RUNTIME_DIR="$BACKEND_DIR/target/desktop-runtime"
APP_NAME="SupportFlowBackend"
JAR_NAME="supportflow-backend-0.0.1-SNAPSHOT.jar"

JLINK_BIN="${JAVA_HOME:+$JAVA_HOME/bin/jlink}"
if [[ -z "$JLINK_BIN" || ! -x "$JLINK_BIN" ]]; then
  JLINK_BIN="$(command -v jlink)"
fi
JAVA_BIN="${JLINK_BIN%/jlink}/java"
if [[ ! -x "$JAVA_BIN" ]]; then
  JAVA_BIN="$(command -v java)"
fi
JAVA_MODULES="$("$JAVA_BIN" --list-modules | cut -d@ -f1 | paste -sd, -)"

cd "$BACKEND_DIR"
mvn -B -DskipTests package
rm -rf "$INPUT_DIR"
mkdir -p "$INPUT_DIR"
cp "$BACKEND_DIR/target/$JAR_NAME" "$INPUT_DIR/$JAR_NAME"
rm -rf "$OUTPUT_DIR/$APP_NAME.app"
rm -rf "$RUNTIME_DIR"
# Keep a complete, self-contained runtime: Tauri copies native Java libraries
# from this app image, including libattach.dylib used by the JDK launcher.
"$JLINK_BIN" \
  --add-modules "$JAVA_MODULES" \
  --strip-debug \
  --no-header-files \
  --no-man-pages \
  --compress=zip-6 \
  --output "$RUNTIME_DIR"
# jpackage 要求版本号首段 >= 1，无法写 0.1.0；辅助进程版本仅供内部标识，
# 用户可见的产品版本以 tauri.conf.json 的 version（0.1.0）为准。
jpackage \
  --type app-image \
  --name "$APP_NAME" \
  --input "$INPUT_DIR" \
  --main-jar "$JAR_NAME" \
  --runtime-image "$RUNTIME_DIR" \
  --dest "$OUTPUT_DIR" \
  --app-version 1.0.0
