from fastapi import APIRouter, Depends

from app.core.retrieval.citations import build_citations
from app.core.retrieval.search_service import run_search
from app.core.security.dependencies import get_current_api_key
from app.core.security.rate_limit import rate_limiter
from app.core.security.scoping import resolve_scoped_filters
from app.models.api_key import ApiKey
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse, dependencies=[Depends(rate_limiter("search"))])
def search(
    request: SearchRequest, api_key: ApiKey = Depends(get_current_api_key)
) -> SearchResponse:
    """Retrieval-only debug/tuning endpoint — no generation. Lets you
    inspect what the hybrid pipeline (dense + BM25 fusion, parent-child
    merge, rerank, compression, reorder) actually returns for a query
    before it ever reaches the LLM."""
    search_filters = resolve_scoped_filters(api_key, request.department, request.doc_type, request.tags)
    nodes = run_search(request.query, search_filters)
    return SearchResponse(citations=build_citations(nodes))
