"""Unit and integration tests for model fallback and deprecation resilience.

Validates that FallbackGemini and generate_image transparently handle 404 NOT_FOUND
and cascade to the next candidate model, and that role-based cost tiering is honored.
"""

from unittest.mock import patch
import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from google.genai.errors import ClientError

from backend.social_poster import guardrails, tools
from backend.social_poster.guardrails import FallbackGemini


# --- Unit Tests: FallbackGemini -----------------------------------------------


@pytest.mark.anyio
async def test_fallback_gemini_catches_404_and_cascades():
    """Verify that FallbackGemini catches 404 NOT_FOUND and falls back to candidate."""
    m = FallbackGemini(
        model="gemini-3.8-flash",
        fallback_models=["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"],
    )
    req = LlmRequest(
        model="gemini-3.8-flash",
        contents=[types.Content(role="user", parts=[types.Part.from_text(text="Test")])],
    )

    expected_resp = LlmResponse(
        content=types.Content(role="model", parts=[types.Part.from_text(text="Success from 2.5")])
    )

    call_history = []

    async def fake_super_generate(llm_request, stream=False):
        if False:
            yield None
        call_history.append(llm_request.model)
        if llm_request.model == "gemini-3.8-flash":
            raise ClientError(404, {"error": {"message": "Publisher model gemini-3.8-flash not found"}})
        if llm_request.model == "gemini-3.5-flash":
            raise ClientError(404, {"error": {"message": "Publisher model gemini-3.5-flash not found"}})
        if llm_request.model == "gemini-2.5-flash":
            yield expected_resp

    with patch("google.adk.models.Gemini.generate_content_async", side_effect=fake_super_generate):
        results = []
        async for resp in m.generate_content_async(req):
            results.append(resp)

        assert len(results) == 1
        assert results[0].content.parts[0].text == "Success from 2.5"
        assert call_history == ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]


@pytest.mark.anyio
async def test_fallback_gemini_raises_non_404_errors():
    """Verify that non-404 errors (such as 429 RESOURCE_EXHAUSTED) are raised immediately."""
    m = FallbackGemini(
        model="gemini-3.8-flash",
        fallback_models=["gemini-3.8-flash", "gemini-2.5-flash"],
    )
    req = LlmRequest(
        model="gemini-3.8-flash",
        contents=[types.Content(role="user", parts=[types.Part.from_text(text="Test")])],
    )

    async def fake_super_generate(llm_request, stream=False):
        if False:
            yield None
        raise ClientError(429, {"error": {"message": "429 RESOURCE_EXHAUSTED quota exceeded"}})

    with patch("google.adk.models.Gemini.generate_content_async", side_effect=fake_super_generate):
        with pytest.raises(ClientError) as exc_info:
            async for _ in m.generate_content_async(req):
                pass
        assert exc_info.value.code == 429


def test_guardrails_role_based_model_tiering():
    """Verify that model() returns appropriate fallback models per agent role."""
    research_m = guardrails.model("gemini-3.8-flash-lite")
    assert "gemini-2.5-flash-lite" in research_m.fallback_models
    assert "gemini-3.5-flash-lite" in research_m.fallback_models
    assert "gemini-3.8-flash-lite" in research_m.fallback_models

    draft_m = guardrails.model("gemini-3.8-flash")
    assert "gemini-2.5-flash" in draft_m.fallback_models
    assert "gemini-3.5-flash" in draft_m.fallback_models
    assert "gemini-3.8-flash" in draft_m.fallback_models

    pro_m = guardrails.model("gemini-3.8-pro")
    assert "gemini-2.5-pro" in pro_m.fallback_models
    assert "gemini-3.8-pro" in pro_m.fallback_models


# --- Unit Tests: Image Generation Cascading -----------------------------------


def test_generate_image_cascading_on_404(monkeypatch, tmp_path):
    """Verify that generate_image probes candidates in order on 404 until one succeeds."""
    attempted_models = []

    class _FakeInlineData:
        mime_type = "image/png"
        data = b"\x89PNG\r\n\x1a\nFakeImageData"

    class _FakePart:
        inline_data = _FakeInlineData()

    class _FakeContent:
        parts = [_FakePart()]

    class _FakeCandidate:
        content = _FakeContent()

    class _FakeSuccessResponse:
        candidates = [_FakeCandidate()]

    class _FakeClient:
        class models:
            @staticmethod
            def generate_content(model, contents, config):
                attempted_models.append(model)
                if model in ("gemini-3.8-flash-image", "gemini-3.5-flash-image", "gemini-3.1-flash-image"):
                    raise ClientError(404, {"error": {"message": f"Model {model} not found"}})
                if model == "imagen-3.0-generate-002":
                    raise ClientError(404, {"error": {"message": f"Model {model} not found"}})
                if model == "gemini-2.5-flash-image":
                    return _FakeSuccessResponse()
                raise ValueError("Unexpected model")

    monkeypatch.setattr(tools.genai, "Client", lambda **kwargs: _FakeClient())
    monkeypatch.setattr(tools, "OUTPUTS_DIR", tmp_path)

    res = tools.generate_image("a sleek social graphic")
    assert res["status"] == "success"
    assert res["model_used"] == "gemini-2.5-flash-image"
    assert "gemini-3.8-flash-image" in attempted_models
    assert attempted_models[-1] == "gemini-2.5-flash-image"
