import uuid
from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Document(Base):
    """Current-state registry row for a source file. Historical versions of
    a changed file live in DocumentVersion; this row always reflects the
    latest ingested state (see app/ingestion/versioning.py)."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("tenant_id", "source_path", name="uq_documents_tenant_source_path"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    ingestion_root: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    """Absolute path of the root folder this file was ingested from. Scopes
    registry_sync's deletion-detection to files that came from the same
    root — otherwise a root with zero discovered files (e.g. every file in
    it was deleted) has no way to distinguish "nothing changed here" from
    "everything here was removed"."""
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    department: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    doc_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    num_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version"
    )


class DocumentVersion(Base):
    """Audit trail entry for one ingested state of a document. Inserted every
    time incremental indexing detects a content_hash change for an existing
    source_path; the previous row's superseded_at is stamped at the same time."""

    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    num_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="versions")
