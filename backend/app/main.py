from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.middleware import RequestContextMiddleware
from app.observability.tracing import setup_tracing

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    logger.info("app_startup", env=settings.app_env, llm_provider=settings.llm_provider)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise Document RAG",
        version="0.1.0",
        description="Multi-tenant, hybrid-search document RAG API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
