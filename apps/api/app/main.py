from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.exceptions import AppError, register_exception_handlers
from app.db.health import check_database_connection
from app.db.session import get_db
from app.uploads.router import router as uploads_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(auth_router)
    application.include_router(audit_router)
    application.include_router(uploads_router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.app_env,
            "version": settings.app_version,
        }

    @application.get("/health/db", tags=["system"])
    def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
        try:
            check_database_connection(db)
        except SQLAlchemyError as exc:
            raise AppError(
                "Database connection failed",
                status_code=503,
                code="database_unavailable",
            ) from exc
        return {"status": "ok", "database": "ok"}

    return application


app = create_app()
