.PHONY: db db-stop migrate seed api worker web test build install

install:
	cd backend && uv sync
	cd frontend && npm install

db:
	cd backend && uv run python scripts/db.py start

db-stop:
	cd backend && uv run python scripts/db.py stop

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python scripts/seed.py

api:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

worker:
	cd backend && uv run python -m app.worker

web:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -q
	cd frontend && npx tsc --noEmit

build:
	cd frontend && npm run build

refresh:
	cd backend && uv run python scripts/refresh.py

backfill:
	cd backend && uv run python scripts/backfill_entities.py
