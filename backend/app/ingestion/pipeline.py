from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client.http import models as qmodels
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.cache.semantic_cache import invalidate_for_document
from app.core.providers.embedding_factory import get_embed_model, get_embedding_dimension
from app.core.retrieval.docstore import get_docstore
from app.core.retrieval.qdrant_store import ensure_collection, get_qdrant_client, get_vector_store
from app.ingestion.file_hash import hash_file, stat_file
from app.ingestion.loaders.docx_loader import load_docx
from app.ingestion.loaders.pdf_loader import load_pdf
from app.ingestion.loaders.pptx_loader import load_pptx
from app.ingestion.metadata_resolver import ResolvedMetadata
from app.ingestion.node_parsers import build_hierarchical_nodes
from app.ingestion.versioning import finalize_document, get_or_create_document

LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".pptx": load_pptx,
}


@dataclass
class IngestResult:
    source_path: str
    status: str  # "unchanged" | "ingested" | "skipped_unsupported"
    num_leaf_chunks: int = 0
    document_id: str | None = None
    errors: list[str] = field(default_factory=list)


def _purge_existing_document_data(document_id: str) -> None:
    """Removes every node (leaf + parent) tied to a document's previous
    state before re-ingesting a changed file — otherwise stale chunks from
    the old version would linger in the docstore/vector store alongside the
    new ones. Also invalidates any cached chat answers that cited this
    document, since they may no longer be accurate."""
    docstore = get_docstore()
    docstore.delete_ref_doc(document_id, raise_error=False)

    settings = get_settings()
    client = get_qdrant_client()
    if client.collection_exists(settings.embedding_collection_name):
        client.delete(
            collection_name=settings.embedding_collection_name,
            points_selector=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id", match=qmodels.MatchValue(value=document_id)
                    )
                ]
            ),
        )

    invalidate_for_document(document_id)


async def ingest_file(
    session: AsyncSession,
    root_dir: Path,
    file_path: Path,
    resolved: ResolvedMetadata,
) -> IngestResult:
    ext = file_path.suffix.lower()
    loader = LOADERS.get(ext)
    relative_path = file_path.relative_to(root_dir).as_posix()

    if loader is None:
        return IngestResult(source_path=relative_path, status="skipped_unsupported")

    content_hash = hash_file(file_path)
    stat = stat_file(file_path)

    decision = await get_or_create_document(
        session,
        tenant_id=resolved.tenant_id,
        source_path=relative_path,
        ingestion_root=str(root_dir.resolve()),  # noqa: ASYNC240 -- CLI batch ingest, not a server handler
        file_name=file_path.name,
        file_type=ext.lstrip("."),
        department=resolved.department,
        doc_type=resolved.doc_type,
        tags=resolved.tags,
        content_hash=content_hash,
        size_bytes=stat.size_bytes,
    )

    if not decision.changed:
        return IngestResult(
            source_path=relative_path, status="unchanged", document_id=str(decision.document.id)
        )

    document = decision.document
    document_id = str(document.id)

    # Commit now so the "processing" status is visible to other DB
    # connections (e.g. the API server's GET /documents, which the frontend
    # polls) while the slow part -- parsing, embedding, Qdrant upsert --
    # runs below. Without this, "processing" only ever exists inside this
    # uncommitted transaction and is overwritten by "completed" before the
    # single end-of-function commit -- so a poller watching for a
    # "processing" row to know when to keep refreshing never sees one; the
    # row appears to jump straight from nonexistent to "completed", and the
    # frontend's list silently goes stale until a manual reload.
    # AsyncSessionLocal uses expire_on_commit=False, so `document`'s already
    # -loaded attributes stay usable after this commit without a reload.
    await session.commit()

    if not decision.is_new:
        _purge_existing_document_data(document_id)

    documents = loader(file_path)
    for doc in documents:
        doc.id_ = document_id  # shared ref_doc_id -> one delete_ref_doc() call purges the whole file
        doc.metadata.update(
            {
                "tenant_id": resolved.tenant_id,
                "department": resolved.department,
                "doc_type": resolved.doc_type,
                "tags": resolved.tags,
                "source_file": relative_path,
                "content_hash": content_hash,
                "document_id": document_id,
                "document_version": document.current_version,
            }
        )

    all_nodes, leaf_nodes = build_hierarchical_nodes(documents)

    docstore = get_docstore()
    docstore.add_documents(all_nodes)

    settings = get_settings()
    embed_model = get_embed_model()
    embed_model(leaf_nodes)  # sets node.embedding in place

    client = get_qdrant_client()
    ensure_collection(client, settings.embedding_collection_name, get_embedding_dimension())
    vector_store = get_vector_store(settings.embedding_collection_name)
    vector_store.add(leaf_nodes)

    await finalize_document(session, document, num_chunks=len(leaf_nodes))

    return IngestResult(
        source_path=relative_path,
        status="ingested",
        num_leaf_chunks=len(leaf_nodes),
        document_id=document_id,
    )
