"""Workaround for a ragas 0.4.3 packaging bug, not anything in our own code:
ragas unconditionally imports `langchain_community.chat_models.vertexai.
ChatVertexAI` at import time — even though this project never uses Vertex
AI — and that submodule was removed from langchain-community as part of its
ongoing provider-package restructuring (langchain-community is being
"sunset" in favor of standalone integration packages; see
https://github.com/langchain-ai/langchain-community/issues/674). Pinning an
older langchain-community that still has the module isn't viable either: it
requires an old langchain-core that conflicts with the rest of this
project's (langchain 1.x-based) dependency tree.

Registering a stub module before ragas is ever imported lets that single
import line succeed without touching any real package version. The stub is
never instantiated — this project's LLM_PROVIDER options are OpenAI/
Anthropic/Gemini/Groq/OpenRouter, never Vertex AI. Remove this once ragas
ships a fix upstream.
"""

import sys
import types


def apply() -> None:
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return

    stub = types.ModuleType(module_name)

    class ChatVertexAI:  # import-only stub, deliberately never usable
        def __init__(self, *args, **kwargs):
            raise NotImplementedError(
                "ChatVertexAI is an import-compat stub (see eval/_ragas_compat.py) "
                "— this project does not support Vertex AI as a provider."
            )

    stub.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = stub
