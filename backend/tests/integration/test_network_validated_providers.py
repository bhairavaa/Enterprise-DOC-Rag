"""Providers whose constructor makes a live network call to validate
credentials, so they need a real API key and network access."""

import os

import pytest

from app.config import Settings
from app.core.providers.llm_factory import _build_llm

pytestmark = pytest.mark.integration


def test_gemini_llm_factory():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set")

    settings = Settings(_env_file=None, llm_provider="gemini", llm_model="gemini-2.0-flash", google_api_key=api_key)
    llm = _build_llm(settings)
    assert type(llm).__name__ == "GoogleGenAI"
