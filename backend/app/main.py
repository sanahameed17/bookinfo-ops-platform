"""
FastAPI application entry point.

Run locally (from the backend folder):
    uvicorn app.main:app --reload --port 8000
OpenAPI docs: http://127.0.0.1:8000/docs
"""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import PlatformError
from app.routers.api import router


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(),
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    log = logging.getLogger("app")

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=("Read-only monitoring and AI operations API for the Istio Bookinfo application. "
                     "Data comes live from the Kubernetes API and Prometheus. CPU is in cores, memory "
                     "in MiB, timestamps in UTC ISO 8601. Unknown values are null, never 0."),
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid = uuid.uuid4().hex[:8]
        start = time.perf_counter()
        response = await call_next(request)
        log.info("%s %s %s -> %s (%.0f ms)", rid, request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(PlatformError)
    async def platform_error(_: Request, exc: PlatformError):
        log.warning("%s: %s", exc.code, exc.message)
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "VALIDATION_ERROR", "message": "Request validation failed",
            "details": {"errors": [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]}}})

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"error": {
            "code": "INTERNAL_ERROR", "message": f"{type(exc).__name__}: {exc}"[:300], "details": {}}})

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
