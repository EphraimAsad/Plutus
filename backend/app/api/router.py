"""Main API router that combines all route modules."""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    users,
    sources,
    ingestion,
    reconciliation,
    exceptions,
    anomalies,
    reports,
    audit,
    ai_explanations,
)

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(sources.router, prefix="/sources", tags=["Sources"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Ingestion"])
api_router.include_router(reconciliation.router, prefix="/reconciliation", tags=["Reconciliation"])
api_router.include_router(exceptions.router, prefix="/exceptions", tags=["Exceptions"])
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["Anomalies"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(ai_explanations.router, prefix="/ai-explanations", tags=["AI Explanations"])
