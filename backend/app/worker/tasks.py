import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.ingestion.bm25_index import rebuild_bm25_index
from app.ingestion.metadata_resolver import ResolvedMetadata
from app.ingestion.pipeline import ingest_file
from app.ingestion.versioning import mark_document_failed
from app.logging import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="ingest_document")
def ingest_document_task(
    file_path: str,
    root_dir: str,
    tenant_id: str,
    department: str | None,
    doc_type: str | None,
    tags: list[str],
) -> dict:
    """Runs one file through the same ingestion pipeline as CLI folder
    ingestion (app/ingestion/runner.py), off the request thread — a Celery
    worker is its own process, so it gets its own fresh instances of the
    module-level singletons (Qdrant client, embed model, ...) rather than
    sharing the API process's. The DB engine is NOT one of those shared
    singletons, deliberately -- see _ingest()."""
    return asyncio.run(_ingest(file_path, root_dir, tenant_id, department, doc_type, tags))


async def _ingest(
    file_path: str,
    root_dir: str,
    tenant_id: str,
    department: str | None,
    doc_type: str | None,
    tags: list[str],
) -> dict:
    resolved = ResolvedMetadata(
        tenant_id=tenant_id, department=department, doc_type=doc_type, tags=tags
    )
    source_path = Path(file_path).relative_to(Path(root_dir)).as_posix()

    # A fresh engine per task, NOT app.db.session's shared module-level
    # singleton. ingest_document_task runs each task via asyncio.run(),
    # which creates and later closes a brand-new event loop per call (the
    # --pool=solo worker processes tasks one at a time, sequentially, in
    # the same OS thread/process). A shared engine's asyncpg connection
    # pool binds to whichever loop first used it; the *next* task's new
    # loop then crashes reusing those connections -- pool_pre_ping's own
    # health-check needs to run on the connection's original loop, so even
    # that safety net can't save it (RuntimeError: ... attached to a
    # different loop). Same bug class as KNOWN_ISSUES.md #3 (the API's
    # chat path sharing a loop-bound async Qdrant client across throwaway
    # loops) -- different subsystem, same root cause: never share a
    # resource whose lifecycle is tied to one event loop across others.
    # Disposed in `finally` so nothing outlives this task's loop.
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            try:
                result = await ingest_file(session, Path(root_dir), Path(file_path), resolved)
                await session.commit()
            except Exception:
                await session.rollback()
                await mark_document_failed(session, tenant_id=tenant_id, source_path=source_path)
                await session.commit()
                raise
    finally:
        await engine.dispose()

    if result.status == "ingested":
        rebuild_bm25_index()

    logger.info(
        "async_ingestion_complete",
        status=result.status,
        source_path=result.source_path,
        num_leaf_chunks=result.num_leaf_chunks,
    )
    return {
        "status": result.status,
        "document_id": result.document_id,
        "source_path": result.source_path,
        "num_leaf_chunks": result.num_leaf_chunks,
    }
