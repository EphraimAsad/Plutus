# Plutus

[![CI](https://github.com/yourusername/plutus/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/plutus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)

**Production-Grade Financial Reconciliation Platform**

Plutus is a full-stack internal operations platform for financial data reconciliation, exception management, and operational reporting. It enables operations teams to ingest, validate, match, and reconcile records from multiple source systems with powerful matching algorithms and AI-powered explanations.

---

## Features

### Data Ingestion
- Multi-format file support (CSV, XLSX, XLS)
- Configurable schema mappings per source
- Automatic duplicate detection via file hashing
- Background processing with real-time job tracking

### Reconciliation Engine
- **Cross-Source Reconciliation**: Compare records between two different sources (e.g., Bank vs Ledger)
- **Duplicate Detection**: Find potential duplicates within a single source
- **Exact Matching**: ID + Amount + Date
- **Tolerance Matching**: Configurable date (±N days) and amount (±N%) tolerances
- **Fuzzy Matching**: Description and reference similarity using rapidfuzz
- **Scored Matching**: Weighted combination with confidence scores
- Automatic exception creation for candidates requiring review

### Exception Management
- Priority-based exception queue
- Side-by-side record comparison
- Manual resolution workflow with full audit trail
- Assignee management and escalation paths

### Reporting & Export
- **Report Types**: Reconciliation summary, unmatched items, exception backlog, anomaly report, ingestion health
- **Export Formats**: CSV, Excel (XLSX), PDF, JSON
- Background generation with progress tracking

### AI Explanations (Optional)
- Natural language explanations for exceptions and anomalies
- **Ollama** (default): Local AI - data stays in your infrastructure
- **Anthropic Claude** & **OpenAI GPT**: Cloud providers available
- Read-only mode with safety guardrails

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- 8GB RAM recommended
- *Optional*: [Ollama](https://ollama.ai/) for local AI explanations

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/plutus.git
cd plutus

# Create environment file
cp .env.example .env

# Build and start all services
docker-compose up -d --build

# Wait for services to start (30-60 seconds)
docker-compose ps

# Run database migrations
docker-compose exec backend alembic upgrade head

# Create admin user
docker-compose exec backend python -m scripts.seed_demo_data
```

### Access the Application

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:5173 |
| **API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

### Default Admin Credentials

| Email | Password |
|-------|----------|
| `admin@plutus-app.com` | `admin123!` |

> **Note**: Change the admin password after first login.

### Quick Test with Sample Data

Sample CSV files are included in the `test/` directory for testing the reconciliation workflow:

```bash
# Navigate to Sources page and create two sources:
# - Bank Statement (map: transaction_id, date, amount, description, reference)
# - Internal Ledger (map: entry_id, posting_date, amount, memo, ref_number)

# Upload test files via Ingestion page:
# - test/bank_statement.csv (12 records)
# - test/internal_ledger.csv (13 records)

# Run reconciliation and verify:
# - ~8 confirmed matches
# - ~3 candidates needing review (creates exceptions)
# - ~3 unmatched records
```

See `test/README.txt` for detailed step-by-step testing instructions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│                    http://localhost:5173                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/REST
┌─────────────────────────────▼───────────────────────────────────┐
│                      Backend (FastAPI)                          │
│                    http://localhost:8000                        │
└───────┬─────────────────────────────────────────────┬───────────┘
        │                                             │
        │ Async Tasks                                 │ SQL
        ▼                                             ▼
┌───────────────┐                           ┌─────────────────┐
│    Celery     │                           │   PostgreSQL    │
│   Workers     │                           │                 │
└───────┬───────┘                           └─────────────────┘
        │
        ▼
┌───────────────┐
│     Redis     │
└───────────────┘
```

### Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic 2 |
| **Database** | PostgreSQL 16 |
| **Queue** | Celery 5, Redis 7 |
| **AI** | Ollama, Anthropic, OpenAI |

---

## Project Structure

```
plutus/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # REST API endpoints
│   │   ├── core/             # Config, security, database
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── workers/          # Celery tasks
│   ├── alembic/              # Database migrations
│   └── tests/                # Test suite
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable UI components
│   │   ├── features/         # Feature modules
│   │   ├── pages/            # Page components
│   │   └── lib/              # Utilities
│   └── package.json
├── infra/docker/             # Dockerfiles
├── docker-compose.yml
└── .env.example
```

---

## Development

### Common Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run database migrations
docker-compose exec backend alembic upgrade head

# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Run tests
docker-compose exec backend pytest -v

# Code formatting
docker-compose exec backend ruff format .
docker-compose exec backend ruff check .

# Access shell
docker-compose exec backend /bin/sh
```

### Reset Database

```bash
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
docker-compose exec backend python -m scripts.seed_demo_data
```

### CI/CD

The project includes GitHub Actions workflows for continuous integration:

**Workflow:** `.github/workflows/ci.yml`

| Job | Description |
|-----|-------------|
| **Backend CI** | Ruff linting, MyPy type checking, pytest with PostgreSQL/Redis |
| **Frontend CI** | ESLint, TypeScript checking, Vitest tests, production build |
| **Docker Build** | Validates all Dockerfiles build successfully |

**Triggers:** Push to `main`, pull requests, manual dispatch

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | *Required* |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `AI_PROVIDER` | AI provider (`ollama`/`anthropic`/`openai`) | `ollama` |
| `OLLAMA_MODEL` | Ollama model name | `gemma:7b` |
| `DEBUG` | Enable debug mode | `true` |

See `.env.example` for full configuration options.

### AI Setup (Optional)

Plutus supports AI-powered explanations for exceptions and anomalies. By default, it uses **Ollama** for local inference.

**Using Ollama (Recommended):**
```bash
# Install Ollama from https://ollama.ai
# Pull the default model
ollama pull gemma:7b

# Ollama runs on http://localhost:11434 by default
# The backend connects via host.docker.internal
```

**Using Cloud Providers:**
```bash
# In .env file:
AI_PROVIDER=anthropic  # or openai
ANTHROPIC_API_KEY=your-api-key
# or
OPENAI_API_KEY=your-api-key
```

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Get JWT token |
| `GET` | `/auth/me` | Current user info |

### Sources
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sources` | List sources |
| `POST` | `/sources` | Create source (Admin) |
| `POST` | `/sources/{id}/schema-mapping` | Add schema mapping |
| `DELETE` | `/sources/{id}` | Delete source and related data (Admin) |

### Ingestion
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ingestion/upload` | Upload file |
| `GET` | `/ingestion/jobs` | List jobs |
| `GET` | `/ingestion/jobs/{id}` | Job details |
| `DELETE` | `/ingestion/jobs/{id}` | Delete job and related records (Admin) |

### Reconciliation
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/reconciliation/runs` | Start run |
| `GET` | `/reconciliation/runs/{id}/summary` | Run summary |
| `GET` | `/reconciliation/runs/{id}/matches` | Match candidates |
| `DELETE` | `/reconciliation/runs/{id}` | Delete run and related data (Admin) |

### Exceptions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/exceptions` | List exceptions |
| `POST` | `/exceptions/{id}/resolve` | Resolve exception |
| `POST` | `/exceptions/{id}/escalate` | Escalate exception |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/reports` | Generate report |
| `GET` | `/reports/{id}/download` | Download report |

### Audit
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/audit` | List audit logs (Admin) |
| `GET` | `/audit/{entity_type}/{entity_id}` | Entity audit history |

Full API documentation available at `/docs` when running.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow existing code style
- Add tests for new features
- Update documentation as needed
- Use conventional commit messages

---

## Troubleshooting

### Services Won't Start

```bash
docker-compose logs backend
docker-compose logs postgres
```

### Database Connection Issues

```bash
docker-compose down -v
docker-compose up -d
```

### Migration Errors

```bash
docker-compose exec backend alembic current
docker-compose exec backend alembic upgrade head
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Documentation

- [System Architecture](SystemArchitecture.md) - Detailed technical architecture
- [API Docs](http://localhost:8000/docs) - Interactive API documentation (when running)

---

**Built with FastAPI, React, and PostgreSQL**
