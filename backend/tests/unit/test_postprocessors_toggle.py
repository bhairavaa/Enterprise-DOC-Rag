from app.config import Settings
from app.core.retrieval import postprocessors as postprocessors_module


def test_reranker_excluded_when_disabled(monkeypatch):
    settings = Settings(_env_file=None, reranker_enabled=False, context_compression_enabled=False)
    monkeypatch.setattr(postprocessors_module, "get_settings", lambda: settings)

    result = postprocessors_module.build_postprocessors()

    assert [type(p).__name__ for p in result] == [
        "DeduplicateSentencesPostprocessor",
        "LongContextReorder",
    ]
