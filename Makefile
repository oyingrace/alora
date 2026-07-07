.PHONY: dev test snippet bench deploy migrate

# apps/api's venv, used explicitly everywhere below instead of a bare `python`/
# `uvicorn` — those resolve against whatever's first on PATH, which silently picks
# up a global interpreter with none of this project's dependencies installed if
# the venv isn't active in the calling shell.
API_PY := apps/api/.venv/bin/python

dev: snippet
	docker compose -f deploy/docker-compose.yml up -d postgres redis
	( cd apps/api && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 ) & \
	( cd apps/web && npm run dev )

test:
	cd apps/api && .venv/bin/python -m pytest -q

snippet:
	cd packages/snippet && npm run build
	cp packages/snippet/dist/agent.js apps/web/public/agent.js

bench:
	cd bench && ../$(API_PY) run_benchmark.py

migrate:
	cd apps/api && .venv/bin/alembic upgrade head

deploy:
	bash deploy/deploy.sh
