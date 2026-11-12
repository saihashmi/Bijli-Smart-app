# DataDoctor AI developer commands. Run from datadoctor/.
.PHONY: setup backend frontend test test-backend test-frontend e2e lint audit

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm ci

backend:          ## API on http://127.0.0.1:8000 (auto-reload)
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:         ## Web app on http://localhost:3000
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && .venv/bin/python -m pytest

test-frontend:
	cd frontend && npm test

e2e:              ## needs backend + frontend running
	cd frontend && npm run e2e

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint && npm run typecheck

audit:
	cd backend && .venv/bin/pip-audit -r requirements.txt
	cd frontend && npm audit
