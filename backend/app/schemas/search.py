from pydantic import BaseModel

from app.schemas.citation import Citation


class SearchRequest(BaseModel):
    query: str
    department: list[str] | None = None
    doc_type: list[str] | None = None
    tags: list[str] | None = None


class SearchResponse(BaseModel):
    citations: list[Citation]
