from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.dependencies import get_current_api_key
from app.db.session import get_db_session
from app.models.api_key import ApiKey
from app.models.document import Document
from app.schemas.filters import FacetsResponse

router = APIRouter(tags=["filters"])


def _restrict(values: list[str], allowed: list[str] | None) -> list[str]:
    if not allowed:
        return values
    allowed_set = set(allowed)
    return [v for v in values if v in allowed_set]


@router.get("/filters/facets", response_model=FacetsResponse)
async def get_facets(
    api_key: ApiKey = Depends(get_current_api_key), session: AsyncSession = Depends(get_db_session)
) -> FacetsResponse:
    """Distinct department/doc_type/tag values currently in the registry for
    the caller's tenant, restricted to whatever their key is scoped to —
    populates the frontend's filter checkboxes with real, authorized
    facets instead of free text."""
    tenant_id = api_key.tenant_id
    allowed = api_key.allowed_filters or {}
    base = Document.tenant_id == tenant_id, Document.status != "deleted"

    departments = await session.execute(
        select(distinct(Document.department)).where(*base, Document.department.isnot(None))
    )
    doc_types = await session.execute(
        select(distinct(Document.doc_type)).where(*base, Document.doc_type.isnot(None))
    )
    tags = await session.execute(
        select(distinct(func.unnest(Document.tags))).where(*base, Document.tags.isnot(None))
    )

    return FacetsResponse(
        department=_restrict(sorted(v for (v,) in departments.all()), allowed.get("department")),
        doc_type=_restrict(sorted(v for (v,) in doc_types.all()), allowed.get("doc_type")),
        tags=_restrict(sorted(v for (v,) in tags.all()), allowed.get("tags")),
    )
