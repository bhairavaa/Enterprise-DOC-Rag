import argparse
import asyncio
from pathlib import Path

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.ingestion.bm25_index import rebuild_bm25_index
from app.ingestion.registry_sync import sync_folder
from app.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def run_ingestion(root_dir: Path) -> None:
    async with AsyncSessionLocal() as session:
        summary = await sync_folder(session, root_dir)

    logger.info(
        "ingestion_complete",
        ingested=len(summary.ingested),
        unchanged=len(summary.unchanged),
        deleted=len(summary.deleted),
        skipped=len(summary.skipped),
    )
    print(f"Ingested:  {len(summary.ingested)} {summary.ingested}")
    print(f"Unchanged: {len(summary.unchanged)}")
    print(f"Deleted:   {len(summary.deleted)} {summary.deleted}")
    print(f"Skipped:   {len(summary.skipped)} {summary.skipped}")

    if summary.ingested or summary.deleted:
        num_indexed = rebuild_bm25_index()
        print(f"BM25 index rebuilt: {num_indexed} nodes")
    else:
        print("BM25 index unchanged (no ingested/deleted files)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a folder of documents (PDF/DOCX/PPTX) into the RAG index."
    )
    parser.add_argument("root", type=Path, help="Root folder to ingest, e.g. sample_docs/")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    asyncio.run(run_ingestion(args.root.resolve()))


if __name__ == "__main__":
    main()
