# Plutus System Architecture

## Overview

Plutus is a production-grade financial reconciliation platform built with a modern, microservices-inspired architecture. The system enables operations teams to ingest, validate, reconcile, and report on financial data from multiple source systems.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PLUTUS PLATFORM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐    HTTP/REST    ┌─────────────────────────────────────┐   │
│   │   Frontend  │◄──────────────►│           Backend (API)              │   │
│   │   (React)   │                 │           (FastAPI)                  │   │
│   └─────────────┘                 └──────────────┬──────────────────────┘   │
│                                                  │                          │
│                          ┌───────────────────────┼───────────────────────┐  │
│                          │                       │                       │  │
│                          ▼                       ▼                       ▼  │
│                   ┌─────────────┐        ┌─────────────┐         ┌────────┐ │
│                   │  PostgreSQL │        │    Redis    │         │ Celery │ │
│                   │  (Primary)  │        │   (Queue)   │         │Workers │ │
│                   └─────────────┘        └─────────────┘         └────────┘ │
│                                                                              │
│                                    ┌─────────────┐                          │
│                                    │   Ollama    │                          │
│                                    │ (Local AI)  │                          │
│                                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React 18, TypeScript, Vite | Single-page application |
| **UI Components** | Tailwind CSS, shadcn/ui | Styling and component library |
| **State Management** | TanStack Query | Server state and caching |
| **Backend** | FastAPI, Python 3.12 | REST API server |
| **ORM** | SQLAlchemy 2.0 (async) | Database abstraction |
| **Database** | PostgreSQL 16 | Primary data store |
| **Task Queue** | Celery, Redis | Background job processing |
| **AI Provider** | Ollama (default) | Local AI explanations |
| **Containerization** | Docker, Docker Compose | Development and deployment |

---

## Backend Architecture

### Directory Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── routes/           # REST endpoint handlers
│   │   └── deps.py           # Dependency injection
│   ├── core/
│   │   ├── config.py         # Application settings
│   │   ├── database.py       # Database connection
│   │   ├── security.py       # Authentication/JWT
│   │   ├── logging.py        # Structured logging
│   │   └── ai_providers/     # AI provider abstraction
│   ├── models/               # SQLAlchemy ORM models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic layer
│   ├── workers/              # Celery task definitions
│   └── utils/                # Shared utilities
├── alembic/                  # Database migrations
├── scripts/                  # CLI scripts
└── tests/                    # Test suite
```

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (routes/)                     │
│  Handles HTTP requests, authentication, input validation     │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    Service Layer (services/)                 │
│  Business logic, orchestration, transaction management       │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    Model Layer (models/)                     │
│  SQLAlchemy ORM models, database schema definition           │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                      Database (PostgreSQL)                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Services

| Service | Responsibility |
|---------|----------------|
| `IngestionService` | File parsing, raw record creation, job management |
| `ValidationService` | Schema validation, data quality checks |
| `NormalizationService` | Field mapping, data standardization |
| `MatchingService` | Exact, tolerance, fuzzy, and scored matching |
| `ReconciliationService` | Orchestrates matching across sources |
| `ExceptionService` | Exception creation and workflow management |
| `AnomalyService` | Rule-based anomaly detection |
| `ReportingService` | Report data aggregation |
| `ExportService` | File generation (CSV, XLSX, PDF, JSON) |
| `AIExplanationService` | AI-powered analysis and explanations |

---

## Database Schema

### Entity Relationship Overview

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│    users     │     │  source_systems  │     │ ingestion_jobs  │
└──────────────┘     └──────────────────┘     └─────────────────┘
       │                     │                        │
       │                     │                        │
       ▼                     ▼                        ▼
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  audit_logs  │     │ schema_mappings  │     │   raw_records   │
└──────────────┘     └──────────────────┘     └─────────────────┘
                                                      │
                                                      ▼
                     ┌──────────────────┐     ┌─────────────────┐
                     │ validation_results│◄────│canonical_records│
                     └──────────────────┘     └─────────────────┘
                                                      │
                     ┌────────────────────────────────┼────────────────────────┐
                     │                                │                        │
                     ▼                                ▼                        ▼
              ┌─────────────┐              ┌─────────────────┐        ┌────────────┐
              │  anomalies  │              │ reconciliation  │        │ exceptions │
              └─────────────┘              │     _runs       │        └────────────┘
                                           └─────────────────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              │                    │                    │
                              ▼                    ▼                    ▼
                     ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐
                     │match_candidates│  │reconciled_matches│  │unmatched_records│
                     └────────────────┘  └─────────────────┘  └─────────────────┘
```

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts and authentication |
| `source_systems` | External data source definitions |
| `source_schema_mappings` | Field mapping configurations |
| `ingestion_jobs` | File upload job tracking |
| `raw_records` | Unprocessed records from source files |
| `validation_results` | Validation status per raw record |
| `canonical_records` | Normalized, canonical format records |
| `reconciliation_runs` | Reconciliation job metadata |
| `match_candidates` | Potential matches with scores |
| `reconciled_matches` | Confirmed matches |
| `unmatched_records` | Records without matches |
| `exceptions` | Items requiring manual review |
| `anomalies` | Detected data anomalies |
| `reports` | Generated report metadata |
| `report_snapshots` | Point-in-time report data |
| `ai_explanations` | AI-generated analysis |
| `audit_logs` | System activity tracking |

---

## Authentication & Authorization

### JWT-Based Authentication

```
┌─────────┐    POST /auth/login     ┌─────────┐
│ Client  │ ────────────────────►   │   API   │
│         │    {email, password}    │         │
└─────────┘                         └────┬────┘
                                         │
                                         ▼
                                    ┌─────────┐
                                    │Validate │
                                    │Password │
                                    └────┬────┘
                                         │
                                         ▼
┌─────────┐    {access_token}       ┌─────────┐
│ Client  │ ◄────────────────────   │   API   │
│         │    JWT (HS256)          │         │
└─────────┘                         └─────────┘
```

### Role-Based Access Control (RBAC)

| Role | Capabilities |
|------|--------------|
| `ADMIN` | Full system access, user management, configuration |
| `OPERATIONS_ANALYST` | Upload files, run reconciliation, resolve exceptions |
| `OPERATIONS_MANAGER` | View dashboards, generate reports, review trends |
| `READ_ONLY` | View dashboards and completed reports only |

### Security Implementation

```python
# Dependency injection for authentication
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
AnalystUser = Annotated[User, Depends(require_analyst_or_higher)]
```

---

## Background Job Processing

### Celery Architecture

```
┌─────────────┐     Publish      ┌─────────────┐
│   FastAPI   │ ───────────────► │    Redis    │
│   (API)     │                  │   (Broker)  │
└─────────────┘                  └──────┬──────┘
                                        │
                                        │ Subscribe
                                        ▼
                    ┌─────────────────────────────────────┐
                    │           Celery Workers            │
                    ├─────────────┬─────────────┬─────────┤
                    │ ingestion   │ reconcile   │ report  │
                    │   tasks     │   tasks     │  tasks  │
                    └─────────────┴─────────────┴─────────┘
                                        │
                                        │ Store Results
                                        ▼
                                 ┌─────────────┐
                                 │    Redis    │
                                 │  (Results)  │
                                 └─────────────┘
```

### Task Categories

| Task | Description |
|------|-------------|
| `process_ingestion_job` | Parse files, validate records, create canonical records |
| `run_reconciliation` | Execute matching algorithms across sources |
| `run_duplicate_detection` | Find duplicates within single source |
| `generate_report_task` | Generate report data and export files |
| `generate_ai_explanation` | Request AI analysis for exceptions/anomalies |

---

## Reconciliation Engine

### Matching Pipeline

```
┌───────────────────────────────────────────────────────────────────┐
│                     Reconciliation Pipeline                        │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │ Left Source │    │ Right Source│    │  Parameters │            │
│  │  Records    │    │   Records   │    │ (tolerances)│            │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘            │
│         │                  │                   │                   │
│         └──────────────────┼───────────────────┘                   │
│                            │                                       │
│                            ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                     1. EXACT MATCH                           │  │
│  │     amount + date + reference + external_id = 100% match    │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                            │                                       │
│                            ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   2. TOLERANCE MATCH                         │  │
│  │     date ±N days, amount ±X% = high confidence match        │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                            │                                       │
│                            ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                     3. FUZZY MATCH                           │  │
│  │     rapidfuzz similarity on description/reference           │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                            │                                       │
│                            ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    4. SCORED MATCH                           │  │
│  │     weighted combination → match score 0.0 - 1.0            │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                            │                                       │
│         ┌──────────────────┼──────────────────┐                   │
│         ▼                  ▼                  ▼                   │
│    ┌─────────┐       ┌──────────┐       ┌──────────┐              │
│    │ Matched │       │ Candidate│       │Unmatched │              │
│    │(≥0.95)  │       │(0.7-0.95)│       │ (<0.7)   │              │
│    └─────────┘       └──────────┘       └──────────┘              │
│                            │                                       │
│                            ▼                                       │
│                     ┌──────────────┐                               │
│                     │  Exception   │                               │
│                     │    Queue     │                               │
│                     └──────────────┘                               │
└───────────────────────────────────────────────────────────────────┘
```

### Match Scoring Weights

| Factor | Weight | Description |
|--------|--------|-------------|
| Amount | 0.35 | Exact or within tolerance |
| Date | 0.25 | Record date proximity |
| Reference | 0.20 | Reference code similarity |
| Description | 0.15 | Text similarity score |
| Counterparty | 0.05 | Counterparty name match |

---

## AI Explanation Layer

### Provider Abstraction

```python
class BaseAIProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AIResponse:
        pass
```

### Supported Providers

| Provider | Model | Use Case |
|----------|-------|----------|
| **Ollama** (default) | gemma:7b | Local AI, no data leaves infrastructure |
| Anthropic | claude-3-sonnet | Enterprise-grade analysis |
| OpenAI | gpt-4-turbo | Alternative cloud provider |

### Safety Guardrails

1. **Read-Only Mode**: AI never modifies business data
2. **Safety Flags**: All responses include safety analysis
3. **Token Limits**: Enforced maximum token usage
4. **Content Filtering**: Provider-specific safety filters applied

---

## Frontend Architecture

### Directory Structure

```
frontend/src/
├── app/
│   ├── router.tsx        # React Router configuration
│   └── providers.tsx     # Context providers
├── components/
│   ├── ui/               # shadcn/ui components
│   └── charts/           # Recharts visualizations
├── features/
│   ├── auth/             # Authentication
│   ├── sources/          # Source management
│   ├── ingestion/        # File upload
│   ├── reconciliation/   # Matching UI
│   ├── exceptions/       # Exception queue
│   └── reports/          # Report generation
├── lib/
│   ├── api.ts            # API client
│   └── queryClient.ts    # TanStack Query config
└── pages/                # Route components
```

### State Management

```
┌──────────────────────────────────────────────────────────────────┐
│                    TanStack Query Architecture                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐                         ┌─────────────────────┐ │
│  │  Component  │◄── useQuery/useMutation─│   Query Cache       │ │
│  └─────────────┘                         │   (in-memory)       │ │
│                                          └──────────┬──────────┘ │
│                                                     │            │
│                                          ┌──────────▼──────────┐ │
│                                          │    API Client       │ │
│                                          │    (fetch/axios)    │ │
│                                          └──────────┬──────────┘ │
│                                                     │            │
│                                          ┌──────────▼──────────┐ │
│                                          │   Backend API       │ │
│                                          └─────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Ingestion to Reconciliation

```
                    File Upload (CSV/XLSX)
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│               Ingestion Pipeline                     │
│                                                     │
│  1. Parse file → RawRecord[]                        │
│  2. Validate against schema → ValidationResult[]    │
│  3. Normalize fields → CanonicalRecord[]            │
│  4. Detect duplicates                               │
│  5. Flag anomalies                                  │
│                                                     │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│            Reconciliation Pipeline                   │
│                                                     │
│  1. Load left/right source records                  │
│  2. Apply matching algorithms                       │
│  3. Generate match candidates with scores           │
│  4. Auto-confirm high-confidence matches            │
│  5. Create exceptions for manual review             │
│  6. Record unmatched items                          │
│                                                     │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              Exception Resolution                    │
│                                                     │
│  1. Analyst reviews exception queue                 │
│  2. Views side-by-side comparison                   │
│  3. Resolves, dismisses, or escalates              │
│  4. Optional: Request AI explanation                │
│  5. Audit trail recorded                            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Deployment

### Docker Compose Services

| Service | Port | Purpose |
|---------|------|---------|
| `frontend` | 5173 | React development server |
| `backend` | 8000 | FastAPI application |
| `worker` | - | Celery background workers |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Message broker and cache |

### Environment Configuration

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Security
SECRET_KEY=<random-32-byte-hex>
JWT_EXPIRE_MINUTES=1440

# Redis
REDIS_URL=redis://redis:6379/0

# AI
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma:7b
```

---

## API Design Patterns

### RESTful Conventions

| Method | Endpoint Pattern | Purpose |
|--------|------------------|---------|
| GET | `/resources` | List resources |
| POST | `/resources` | Create resource |
| GET | `/resources/{id}` | Get single resource |
| PUT | `/resources/{id}` | Update resource |
| DELETE | `/resources/{id}` | Delete resource |
| POST | `/resources/{id}/action` | Perform action |

### Response Format

```json
{
  "items": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### Error Handling

```json
{
  "detail": "Resource not found",
  "status_code": 404
}
```

---

## Performance Considerations

### Database Optimization

- **Indexes**: All foreign keys and frequently queried columns indexed
- **Connection Pooling**: SQLAlchemy async connection pool
- **Pagination**: All list endpoints support limit/offset

### Caching Strategy

- **Query Cache**: TanStack Query handles client-side caching
- **Redis**: Used for Celery task results and session data

### Background Processing

- Long-running operations (ingestion, reconciliation, reports) run in Celery workers
- Progress tracking via database status fields
- Polling endpoints for status updates

---

## Security Measures

1. **Password Hashing**: Argon2id algorithm
2. **JWT Tokens**: HS256 signed, configurable expiration
3. **CORS**: Configurable allowed origins
4. **Input Validation**: Pydantic schema enforcement
5. **SQL Injection Prevention**: SQLAlchemy parameterized queries
6. **XSS Prevention**: React's built-in escaping
7. **File Upload Validation**: Type and size limits enforced

---

## Monitoring & Observability

### Logging

- Structured JSON logging via Python `logging` module
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request/response logging middleware

### Health Checks

- `GET /health` - Basic liveness check
- Database connectivity validation
- Redis connectivity validation

---

## CI/CD Pipeline

### GitHub Actions Workflow

Located at `.github/workflows/ci.yml`, the CI pipeline runs on push/PR to `main`.

```
┌─────────────────────────────────────────────────────────────────┐
│                        CI Pipeline                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐         ┌─────────────────┐               │
│   │   Backend CI    │         │   Frontend CI   │               │
│   ├─────────────────┤         ├─────────────────┤               │
│   │ • Ruff lint     │         │ • ESLint        │               │
│   │ • Ruff format   │         │ • TypeScript    │               │
│   │ • MyPy types    │         │ • Vitest tests  │               │
│   │ • Alembic       │         │ • Vite build    │               │
│   │ • Pytest + cov  │         │                 │               │
│   └────────┬────────┘         └────────┬────────┘               │
│            │                           │                         │
│            └───────────┬───────────────┘                         │
│                        ▼                                         │
│              ┌─────────────────┐                                 │
│              │  Docker Build   │                                 │
│              ├─────────────────┤                                 │
│              │ • backend image │                                 │
│              │ • frontend image│                                 │
│              │ • worker image  │                                 │
│              └─────────────────┘                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### CI Services

| Service | Purpose |
|---------|---------|
| **PostgreSQL 16** | Test database for backend tests |
| **Redis 7** | Test broker for Celery tests |

### Quality Gates

| Check | Tool | Configuration |
|-------|------|---------------|
| Python Linting | Ruff | `pyproject.toml` |
| Python Types | MyPy | `pyproject.toml` |
| Python Tests | Pytest | `pytest.ini` options in `pyproject.toml` |
| JS/TS Linting | ESLint | `package.json` scripts |
| TypeScript | tsc | `tsconfig.json` |
| JS Tests | Vitest | `vite.config.ts` |

---

## Future Considerations

1. **Horizontal Scaling**: Celery workers can scale independently
2. **Read Replicas**: PostgreSQL read replicas for reporting
3. **API Versioning**: `/api/v1/` prefix for breaking changes
4. **Webhook Support**: Event-driven notifications
5. **SSO Integration**: SAML/OIDC authentication support
