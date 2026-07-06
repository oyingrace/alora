.PHONY: dev test snippet bench deploy migrate

dev: snippet
	docker compose -f deploy/docker-compose.yml up -d postgres redis
	( cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 ) & \
	( cd apps/web && npm run dev )

test:
	cd apps/api && python -m pytest -q

snippet:
	cd packages/snippet && npm run build
	cp packages/snippet/dist/agent.js apps/web/public/agent.js

bench:
	cd bench && python run_benchmark.py

migrate:
	cd apps/api && alembic upgrade head

deploy:
	bash deploy/deploy.sh
