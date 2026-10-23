"""AI Music Marketer API entrypoint.

Run the Next.js frontend separately from this API service.
"""
from __future__ import annotations
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from .config import settings
from .database import init_db
from .routers import songs, runs, stats, artist
from .routers import connections, v1
from .core.errors import ApiError, api_error_handler
from .core.rate_limiter import limiter, rate_limit_exception_handler
from .services import job_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    job_scheduler.start_scheduler()
    yield
    job_scheduler.stop_scheduler()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.state.limiter = limiter


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions and return safe 500 response."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "unhandled_exception",
        extra={"request_id": request_id, "path": request.url.path},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "request_id": request_id,
                "details": [],
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "").strip()
    if (
        not request_id
        or len(request_id) > 128
        or not request_id.isascii()
        or any(ord(char) < 32 for char in request_id)
    ):
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/v1/"):
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ()) if part != "body"),
                "message": error.get("msg", "Invalid value."),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        request_id = request.state.request_id
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request did not satisfy the API contract.",
                    "request_id": request_id,
                    "details": errors,
                }
            },
            headers={"X-Request-ID": request_id},
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/v1/"):
        request_id = request.state.request_id
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                    "request_id": request_id,
                    "details": [],
                }
            },
            headers={"X-Request-ID": request_id},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(songs.router)
app.include_router(runs.router)
app.include_router(stats.router)
app.include_router(artist.router)
app.include_router(v1.router)
app.include_router(connections.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name,
            "environment": settings.environment}


@app.get("/")
def index():
    return {"app": settings.app_name, "api": "/api/v1", "docs": "/docs"}
