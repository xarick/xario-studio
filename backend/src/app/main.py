import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.exceptions import AppError
from app.api.v1.router import api_router

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    # NOTE: stuck-job reconciliation runs on Celery worker startup (see
    # app.workers.tasks._reconcile_on_start), not here — only the worker
    # processes jobs, so a web-only restart must not touch in-flight work.
    # Disk hygiene is safe to run here: it only removes aged, unreferenced
    # files, never anything an active job depends on. Off the event loop so a
    # large storage scan can't delay startup. Keep a reference so the task
    # isn't garbage-collected before it finishes.
    cleanup_task = None
    if settings.CLEANUP_ON_STARTUP:
        from app.workers.cleanup import sweep_orphans
        cleanup_task = asyncio.create_task(asyncio.to_thread(sweep_orphans))
    logger.info("xario-studio backend started")
    yield
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
    logger.info("xario-studio backend stopped")


app = FastAPI(
    title="xario-studio API",
    description="Video to Shorts AI processing service",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# The dev servers are only trusted in development: with allow_credentials a
# production deployment that keeps localhost in the list lets anything a user
# happens to run locally call the API with their cookies.
_DEV_ORIGINS = ["http://localhost:3000", "http://localhost:5173"]
_cors_origins = sorted({settings.FRONTEND_URL, *(_DEV_ORIGINS if settings.DEBUG else [])})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s → %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(api_router, prefix="/api/v1")


@app.get("/healthz", tags=["health"])
def health():
    return {"status": "ok", "version": "0.1.0"}
