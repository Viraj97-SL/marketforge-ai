.PHONY: install test lint db-init ingest dashboard api docker-up docker-down clean

# ── Setup ────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"
	python -m spacy download en_core_web_sm

db-init:
	python -c "from marketforge.memory.postgres import init_database; init_database(); print('Database initialised.')"

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-fast:
	pytest tests/ -v --tb=short -x -q --no-cov

coverage:
	pytest tests/ --cov=src/marketforge --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# ── Code quality ───────────────────────────────────────────────────────────────
lint:
	ruff check src/ tests/ --fix
	mypy src/marketforge --ignore-missing-imports

# ── Services ──────────────────────────────────────────────────────────────────
docker-up:
	docker-compose up -d postgres redis mlflow

docker-down:
	docker-compose down

# ── Running the platform ───────────────────────────────────────────────────────
ingest:
	python -c "\
import asyncio, sys; sys.path.insert(0, 'src'); \
from marketforge.agents.data_collection.lead_agent import run_data_collection; \
from marketforge.utils.logger import setup_logging; \
setup_logging(); \
result = asyncio.run(run_data_collection('manual_run')); \
print(result)"

dashboard:
	cd dashboard && streamlit run app.py --server.port 8501

api:
	uvicorn api.main:app --reload --port 8000

# ── Airflow (local) ────────────────────────────────────────────────────────────
airflow-init:
	docker-compose up -d airflow-init

airflow-up:
	docker-compose up -d airflow-webserver airflow-scheduler

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -f test_marketforge.db
