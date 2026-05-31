#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/protfolio}"
PROJECT_NAME="${PROJECT_NAME:-scorecraft}"
PROJECT_DIR="${DEPLOY_ROOT}/${PROJECT_NAME}"
LEGACY_PROJECT_DIR="${LEGACY_PROJECT_DIR:-/home/lsy/${PROJECT_NAME}}"

if [[ "${DOCKER_SUDO:-false}" == "true" ]]; then
  DOCKER_CMD=(sudo docker)
else
  DOCKER_CMD=(docker)
fi

run_predeploy_backup() {
  local backup_script="${PORTFOLIO_BACKUP_SCRIPT:-/home/lsy/bin/portfolio_backup.sh}"
  if [[ "${SKIP_PORTFOLIO_BACKUP:-false}" == "true" ]]; then
    echo "[deploy] skip portfolio backup"
    return 0
  fi
  if [[ ! -x "$backup_script" ]]; then
    echo "::error::Portfolio backup script is missing or not executable: $backup_script"
    echo "Set SKIP_PORTFOLIO_BACKUP=true only for non-production dry runs."
    exit 1
  fi
  echo "[deploy] pre-deploy backup: scorecraft"
  "$backup_script" scorecraft
}

run_predeploy_backup

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on the deployment server."
  exit 1
fi

mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/shared/data/uploads"
mkdir -p "$PROJECT_DIR/shared/data/jobs"

if [[ "$PROJECT_DIR" != "$LEGACY_PROJECT_DIR" && -d "$LEGACY_PROJECT_DIR" ]]; then
  if [[ -f "$LEGACY_PROJECT_DIR/.env" && ! -f "$PROJECT_DIR/.env" ]]; then
    echo "[deploy] migrate legacy env: $LEGACY_PROJECT_DIR/.env -> $PROJECT_DIR/.env"
    cp "$LEGACY_PROJECT_DIR/.env" "$PROJECT_DIR/.env"
  fi
  if [[ -d "$LEGACY_PROJECT_DIR/shared/data" ]]; then
    echo "[deploy] migrate legacy data: $LEGACY_PROJECT_DIR/shared/data -> $PROJECT_DIR/shared/data"
    rsync -a --ignore-existing "$LEGACY_PROJECT_DIR/shared/data/" "$PROJECT_DIR/shared/data/"
  fi
fi

rsync -a --delete --no-owner --no-group \
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

if [[ "$PROJECT_DIR" != "$LEGACY_PROJECT_DIR" && -f "$LEGACY_PROJECT_DIR/docker-compose.yml" ]]; then
  RUNNING_DIR="$("${DOCKER_CMD[@]}" inspect scorecraft-app --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' 2>/dev/null || true)"
  if [[ "$RUNNING_DIR" == "$LEGACY_PROJECT_DIR" ]]; then
    echo "[deploy] stop legacy scorecraft stack from $LEGACY_PROJECT_DIR"
    "${DOCKER_CMD[@]}" compose -f "$LEGACY_PROJECT_DIR/docker-compose.yml" down
  fi
fi

"${DOCKER_CMD[@]}" compose up -d --build
"${DOCKER_CMD[@]}" compose ps
