"""add ingestion_root to documents

Revision ID: 313f11a56b5a
Revises: 334ca3b490bf
Create Date: 2026-08-03 14:57:45.163846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '313f11a56b5a'
down_revision: Union[str, None] = '334ca3b490bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Note: autogenerate also proposed dropping `data_docstore` — that table is
# created and owned by llama-index's PostgresDocumentStore (app/core/retrieval/
# docstore.py), not by our SQLAlchemy models, so it's intentionally outside
# target_metadata and must NOT be touched by our migrations.


def upgrade() -> None:
    op.add_column('documents', sa.Column('ingestion_root', sa.String(length=1024), nullable=False))
    op.create_index(op.f('ix_documents_ingestion_root'), 'documents', ['ingestion_root'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_documents_ingestion_root'), table_name='documents')
    op.drop_column('documents', 'ingestion_root')
