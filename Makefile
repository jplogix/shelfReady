.PHONY: db api worker web test

db:
	docker compose up -d

api:
	cd services/api && .venv/bin/uvicorn app.main:app --reload --port 8000

worker:
	cd services/api && .venv/bin/python -m app.worker

web:
	cd apps/web && npm run dev

test:
	cd services/api && .venv/bin/pytest -q
