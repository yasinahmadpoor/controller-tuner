#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.dev.yml)
PROJECT=controller-tuner-dev

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is not installed or not on PATH" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "error: Docker Compose v2 is required" >&2
  exit 1
fi

if [ ! -f engines/gaTunerPID/app.py ] || [ ! -f engines/tunerPID/README.md ]; then
  echo "==> Initializing engine submodules"
  git submodule update --init --recursive
fi

if ! docker image inspect node:20-alpine >/dev/null 2>&1 || \
  ! docker run --rm node:20-alpine sh -c 'command -v npm >/dev/null 2>&1' >/dev/null 2>&1; then
  echo "==> Refreshing node:20-alpine (npm was missing)"
  docker pull node:20-alpine
fi

port_in_use() {
  local port="$1"
  (exec 3<>"/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1
}

pick_port() {
  local preferred="$1"
  local fallback_start="$2"
  local port

  if ! port_in_use "$preferred"; then
    printf '%s\n' "$preferred"
    return
  fi

  for port in $(seq "$fallback_start" $((fallback_start + 50))); do
    if ! port_in_use "$port"; then
      printf '%s\n' "$port"
      return
    fi
  done

  echo "error: no free host port found near $fallback_start" >&2
  exit 1
}

echo "==> Recreating the dev stack (volumes are preserved)"
docker compose -p "$PROJECT" "${COMPOSE_FILES[@]}" down --remove-orphans

API_PORT="${API_PORT:-$(pick_port 8000 8010)}"
UI_PORT="${UI_PORT:-$(pick_port 5173 5183)}"
export API_PORT UI_PORT

docker compose -p "$PROJECT" "${COMPOSE_FILES[@]}" up --build --wait --wait-timeout 300

echo
echo "Controller Tuner (development) is up:"
echo "  UI:       http://localhost:${UI_PORT}"
echo "  API:      http://localhost:${API_PORT}/api/v1"
echo "  API docs: http://localhost:${API_PORT}/docs"
