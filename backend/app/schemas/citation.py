from pydantic import BaseModel


class Citation(BaseModel):
    index: int
    text: str
    score: float | None = None
    source_file: str | None = None
    document_id: str | None = None
    page_label: str | None = None
    section_title: str | None = None
    slide_number: str | None = None
