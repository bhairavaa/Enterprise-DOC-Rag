from pydantic import BaseModel


class FacetsResponse(BaseModel):
    department: list[str]
    doc_type: list[str]
    tags: list[str]
