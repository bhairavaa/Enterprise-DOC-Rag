"""RAGAS evaluation harness: runs the golden Q&A set through the real
retrieval pipeline (app/core/retrieval) and the app's configured generation
LLM, then scores each answer for faithfulness, context precision/recall,
and answer relevancy.

Requires a configured, working LLM_PROVIDER API key — same requirement as
real chat generation (see Phase 3). Usage:

    cd backend
    ./.venv/Scripts/python.exe -m eval.run_eval
"""

import asyncio
import json
from pathlib import Path

from eval import _ragas_compat

_ragas_compat.apply()

from llama_index.core.llms import ChatMessage, MessageRole  # noqa: E402
from llama_index.core.schema import QueryBundle  # noqa: E402
from ragas.metrics.collections import (  # noqa: E402
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)

from app.config import get_settings  # noqa: E402
from app.core.providers.llm_factory import get_llm  # noqa: E402
from app.core.retrieval.filters import SearchFilters  # noqa: E402
from app.core.retrieval.hybrid_retriever import build_hybrid_retriever  # noqa: E402
from app.core.retrieval.postprocessors import build_postprocessors  # noqa: E402
from eval.metrics_report import print_report  # noqa: E402
from eval.providers import build_ragas_embeddings, build_ragas_llm  # noqa: E402

GOLDEN_SET_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "golden_qa" / "golden_set.jsonl"

EVAL_SYSTEM_PROMPT = "Answer the question using only the context provided."


def load_golden_set(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def run_pipeline(question: str, search_filters: SearchFilters) -> tuple[str, list[str]]:
    """Same retrieval + generation shape as app/core/chat/engine.py, minus
    semantic cache and conversation persistence (not relevant for eval —
    every question should hit the real pipeline fresh)."""
    retriever = build_hybrid_retriever(search_filters)
    query_bundle = QueryBundle(query_str=question)

    nodes = retriever.retrieve(query_bundle)
    for postprocessor in build_postprocessors():
        nodes = postprocessor.postprocess_nodes(nodes, query_bundle=query_bundle)

    contexts = [n.node.get_content(metadata_mode="none") for n in nodes]

    llm = get_llm()
    context_block = "\n\n".join(contexts)
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=EVAL_SYSTEM_PROMPT),
        ChatMessage(
            role=MessageRole.USER, content=f"Context:\n{context_block}\n\nQuestion: {question}"
        ),
    ]
    response = await llm.achat(messages)
    return str(response.message.content), contexts


async def main() -> None:
    settings = get_settings()
    golden_set = load_golden_set(GOLDEN_SET_PATH)

    ragas_llm = build_ragas_llm(settings)
    ragas_embeddings = build_ragas_embeddings(settings)

    faithfulness = Faithfulness(llm=ragas_llm)
    context_precision = ContextPrecision(llm=ragas_llm)
    context_recall = ContextRecall(llm=ragas_llm)
    answer_relevancy = AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings)

    results = []
    for item in golden_set:
        question = item["question"]
        reference = item["ground_truth"]
        search_filters = SearchFilters(tenant_id=item["tenant_id"])

        answer, contexts = await run_pipeline(question, search_filters)

        results.append(
            {
                "question": question,
                "faithfulness": (
                    await faithfulness.ascore(
                        user_input=question, response=answer, retrieved_contexts=contexts
                    )
                ).value,
                "context_precision": (
                    await context_precision.ascore(
                        user_input=question, reference=reference, retrieved_contexts=contexts
                    )
                ).value,
                "context_recall": (
                    await context_recall.ascore(
                        user_input=question, retrieved_contexts=contexts, reference=reference
                    )
                ).value,
                "answer_relevancy": (
                    await answer_relevancy.ascore(user_input=question, response=answer)
                ).value,
            }
        )

    print_report(results)


if __name__ == "__main__":
    asyncio.run(main())
