import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.db.base import Base

# Import all model modules so Base.metadata is fully populated for autogenerate.
from app.models import api_key, conversation, document  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()


def get_url() -> str:
    return settings.database_url


def include_object(object, name, type_, reflected, compare_to):
    """Tables like `data_docstore` are created and owned by llama-index's
    own Postgres storage integrations (docstore, and later chat store), not
    by our SQLAlchemy models — they intentionally have no entry in
    target_metadata. Without this filter, autogenerate proposes dropping
    them on every run since they exist in the DB but not in our metadata."""
    if type_ == "table" and reflected and compare_to is None:
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, include_object=include_object
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(get_url(), pool_pre_ping=True)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
