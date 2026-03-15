# Plutus Backend

FastAPI-based backend for the Plutus reconciliation and reporting platform.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload

# Run tests
pytest

# Lint and format
ruff check .
ruff format .
mypy .
```

## Project Structure

```
app/
├── main.py              # FastAPI application entry
├── core/                # Core configuration and utilities
├── api/                 # API routes and dependencies
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── services/            # Business logic
├── repositories/        # Database operations
├── workers/             # Celery tasks
├── utils/               # Utility functions
└── tests/               # Test suite
```
