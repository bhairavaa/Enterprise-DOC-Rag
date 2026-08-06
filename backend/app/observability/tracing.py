from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)

_PROJECT_NAME = "enterprise-doc-rag"


def setup_tracing() -> None:
    """Auto-instruments every LlamaIndex call (retrieval, embedding, LLM,
    reranking) so each request's full pipeline shows up as a trace in
    Phoenix — retrieval latency, which nodes were retrieved, prompt/
    completion tokens, etc. — without hand-instrumenting every call site."""
    settings = get_settings()
    if not settings.phoenix_enabled:
        logger.info("tracing_disabled")
        return

    tracer_provider = register(
        endpoint=f"{settings.phoenix_collector_endpoint}/v1/traces",
        project_name=_PROJECT_NAME,
        auto_instrument=False,
        verbose=False,
        # Batched async export — the default (batch=False) exports each span
        # synchronously, which would add latency to every request (or risk
        # blocking on retries) if Phoenix is ever slow/unreachable.
        batch=True,
    )
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
    logger.info("tracing_enabled", endpoint=settings.phoenix_collector_endpoint)
