from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.metadata_resolver import MetadataResolver
from app.ingestion.pipeline import _purge_existing_document_data, ingest_file
from app.models.document import Document

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}


@dataclass
class SyncSummary:
    ingested: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


async def sync_folder(session: AsyncSession, root_dir: Path) -> SyncSummary:
    """Walks root_dir, ingesting new/changed files and soft-deleting registry
    rows whose source file has disappeared since the last run.

    Deletion-detection is scoped by `ingestion_root` (the resolved root_dir
    each row was ingested from), not by tenants discovered in this run's
    file listing — scoping by discovered tenants breaks the moment every
    file under a root is deleted, since then nothing is discovered at all
    and there'd be no tenant to scope by, even though the deletion is
    exactly what should be detected.
    """
    resolver = MetadataResolver(root_dir)
    summary = SyncSummary()
    resolved_root = str(root_dir.resolve())  # noqa: ASYNC240 -- one-shot CLI batch walk, not a server handler

    files = [
        p
        for p in root_dir.rglob("*")  # noqa: ASYNC240 -- one-shot CLI batch walk, not a server handler
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTENSIONS
        and p.name != MetadataResolver.MANIFEST_FILENAME
    ]

    discovered_paths: set[str] = set()
    for file_path in files:
        relative_path = file_path.relative_to(root_dir).as_posix()
        discovered_paths.add(relative_path)

        resolved = resolver.resolve(file_path)
        result = await ingest_file(session, root_dir, file_path, resolved)
        await session.commit()

        if result.status == "ingested":
            summary.ingested.append(result.source_path)
        elif result.status == "unchanged":
            summary.unchanged.append(result.source_path)
        else:
            summary.skipped.append(result.source_path)

    result = await session.execute(
        select(Document).where(
            Document.status != "deleted", Document.ingestion_root == resolved_root
        )
    )
    for document in result.scalars().all():
        if document.source_path not in discovered_paths:
            _purge_existing_document_data(str(document.id))
            document.status = "deleted"
            summary.deleted.append(document.source_path)
    await session.commit()

    return summary
