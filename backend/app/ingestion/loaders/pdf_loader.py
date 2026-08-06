import statistics
from pathlib import Path

import pymupdf
from llama_index.core import Document

HEADING_SIZE_RATIO = 1.15
HEADING_MAX_CHARS = 150


def load_pdf(file_path: Path) -> list[Document]:
    """One Document per page. section_title tracks the last heading seen so
    far in the document (carried across pages), detected via a font-size
    heuristic: a line is a heading candidate if its max span size is
    meaningfully larger than the document's median body-text size."""
    pdf = pymupdf.open(file_path)
    try:
        pages_raw = [page.get_text("dict")["blocks"] for page in pdf]
        heading_threshold = _heading_threshold(pages_raw)

        documents: list[Document] = []
        current_section: str | None = None
        for page_num, blocks in enumerate(pages_raw, start=1):
            lines_text, current_section = _extract_lines(
                blocks, heading_threshold, current_section
            )
            page_text = "\n".join(lines_text).strip()
            if not page_text:
                continue
            documents.append(
                Document(
                    text=page_text,
                    metadata={
                        "page_label": str(page_num),
                        "section_title": current_section,
                    },
                )
            )
        return documents
    finally:
        pdf.close()


def _heading_threshold(pages_raw: list[list[dict]]) -> float:
    sizes = [
        span["size"]
        for blocks in pages_raw
        for block in blocks
        if block.get("type") == 0
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span["text"].strip()
    ]
    body_size = statistics.median(sizes) if sizes else 10.0
    return body_size * HEADING_SIZE_RATIO


def _extract_lines(
    blocks: list[dict], heading_threshold: float, current_section: str | None
) -> tuple[list[str], str | None]:
    lines_text: list[str] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            line_text = "".join(span["text"] for span in spans).strip()
            if not line_text:
                continue
            max_size = max((span["size"] for span in spans), default=0.0)
            if max_size >= heading_threshold and len(line_text) < HEADING_MAX_CHARS:
                current_section = line_text
            lines_text.append(line_text)
    return lines_text, current_section
