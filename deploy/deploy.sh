#!/usr/bin/env bash
# Rsync the repo to the ECS host and bring the compose stack up.
# Usage: ECS_HOST=user@1.2.3.4 ECS_PATH=/opt/memora ./deploy/deploy.sh
set -euo pipefail

: "${ECS_HOST:?Set ECS_HOST=user@host}"
ECS_PATH="${ECS_PATH:-/opt/memora}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rsync -az --delete \
	--exclude ".git" \
	--exclude "node_modules" \
	--exclude "__pycache__" \
	--exclude ".next" \
	"$REPO_ROOT/" "$ECS_HOST:$ECS_PATH/"

ssh "$ECS_HOST" "cd $ECS_PATH && docker compose -f deploy/docker-compose.yml up -d --build"
