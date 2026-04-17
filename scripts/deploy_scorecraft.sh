#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/protfolio}"
PROJECT_NAME="${PROJECT_NAME:-scorecraft}"
PROJECT_DIR="${DEPLOY_ROOT}/${PROJECT_NAME}"

if [[ "${DOCKER_SUDO:-false}" == "true" ]]; then
  DOCKER_CMD=(sudo docker)
else
  DOCKER_CMD=(docker)
fi

mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/shared/data/uploads"
mkdir -p "$PROJECT_DIR/shared/data/jobs"

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on the deployment server."
  exit 1
fi

rsync -a --delete \
  --exclude ".git" \
  --exclude ".github" \
  --exclude ".env" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "shared" \
  ./ "$PROJECT_DIR"/

cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

"${DOCKER_CMD[@]}" compose up -d --build
"${DOCKER_CMD[@]}" compose ps
