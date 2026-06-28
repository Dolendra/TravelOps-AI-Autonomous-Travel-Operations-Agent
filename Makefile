.PHONY: setup reset seed run-backend run-frontend test lint format help

help:
	@echo "TravelOps AI Studio Developer Command Line Interface Tools:"
	@echo "  make setup        - Install dependencies using pip"
	@echo "  make reset        - Reinitialize SQLite database schemas"
	@echo "  make seed         - Seed SQLite database with 100 bookings demo dataset"
	@echo "  make run-backend  - Start FastAPI uvicorn daemon (port 8000)"
	@echo "  make run-frontend - Start Vite client server (port 5173)"
	@echo "  make test         - Execute pytest test suites"
	@echo "  make lint         - Run ruff linter checks"
	@echo "  make format       - Format codebase using black"

setup:
	pip install -r requirements.txt
	cd frontend && npm install

reset:
	.venv/Scripts/python scripts/reset_db.py

seed:
	.venv/Scripts/python scripts/seed_demo_dataset.py

run-backend:
	.venv/Scripts/python -m uvicorn backend.api.main:app --port 8000

run-frontend:
	cd frontend && npm run dev

test:
	.venv/Scripts/pytest

lint:
	.venv/Scripts/ruff check .

format:
	.venv/Scripts/black .
