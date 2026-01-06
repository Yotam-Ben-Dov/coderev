"""FastAPI application factory for CodeRev."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import health, reviews, webhooks
from src.core.config import settings
from src.core.exceptions import CodeRevError
from src.db.session import close_db, init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown."""
    logger.info(
        "Starting CodeRev",
        version=settings.app_version,
        environment=settings.environment,
    )
    
    # Initialize database (creates tables if they don't exist)
    # In production, rely on Alembic migrations instead
    if settings.environment == "development":
        await init_db()
    
    yield
    
    # Cleanup
    await close_db()
    logger.info("Shutting down CodeRev")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered code review assistant",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(CodeRevError)
    async def coderev_exception_handler(request: Request, exc: CodeRevError) -> JSONResponse:
        logger.error("Application error", error=exc.message, details=exc.details)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": exc.message, "details": exc.details},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error"},
        )

    # Routes
    app.include_router(health.router, tags=["Health"])
    app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
    app.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])

    return app


app = create_app()