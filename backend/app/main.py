from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import accounts, cards, categories, health, installment_plans, movements, summary
from app.config import get_settings
from app.domain.errors import DomainError
from app.services.errors import ConflictError, NotFoundError

API_PREFIX = "/api/v1"


ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _error_handler(status_code: int) -> ExceptionHandler:
    async def handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Digital Budget API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Business rule violations and missing resources become clean JSON errors
    app.add_exception_handler(DomainError, _error_handler(status.HTTP_422_UNPROCESSABLE_CONTENT))
    app.add_exception_handler(NotFoundError, _error_handler(status.HTTP_404_NOT_FOUND))
    app.add_exception_handler(ConflictError, _error_handler(status.HTTP_409_CONFLICT))

    for router in (
        health.router,
        accounts.router,
        categories.router,
        movements.router,
        installment_plans.router,
        cards.router,
        summary.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
