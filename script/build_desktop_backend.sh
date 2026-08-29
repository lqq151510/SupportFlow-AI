#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
OUTPUT_DIR="$BACKEND_DIR/target/desktop"
INPUT_DIR="$BACKEND_DIR/target/desktop-input"
APP_NAME="SupportFlowBackend"
JAR_NAME="supportflow-backend-0.0.1-SNAPSHOT.jar"

cd "$BACKEND_DIR"
mvn -B -DskipTests package
rm -rf "$INPUT_DIR"
mkdir -p "$INPUT_DIR"
cp "$BACKEND_DIR/target/$JAR_NAME" "$INPUT_DIR/$JAR_NAME"
rm -rf "$OUTPUT_DIR/$APP_NAME.app"
jpackage \
  --type app-image \
  --name "$APP_NAME" \
  --input "$INPUT_DIR" \
  --main-jar "$JAR_NAME" \
  --dest "$OUTPUT_DIR" \
  --app-version 1.0.0
