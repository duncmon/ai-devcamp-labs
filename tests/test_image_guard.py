from unittest.mock import MagicMock
from google.genai import types as genai_types
from google.adk.models.llm_response import LlmResponse
from backend.social_poster.agent import _catch_image_placeholder


def test_catch_image_placeholder_with_explicit_image_line():
    ctx = MagicMock()
    ctx.state = {}
    ctx.user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text="Draft a post about AI, with an illustration")]
    )
    resp = LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text="Here is a draft about AI.\n\nImage: A futuristic robot in a modern laboratory")]
        )
    )
    result = _catch_image_placeholder(ctx, resp)
    assert result is not None
    fc = result.content.parts[0].function_call
    assert fc.name == "generate_image"
    assert "futuristic robot" in fc.args["prompt"]


def test_catch_image_omission_when_illustration_requested():
    ctx = MagicMock()
    ctx.state = {}
    ctx.user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text="Draft a post about context drift, with an illustration")]
    )
    resp = LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text="Is your AI agent losing its way?\n\nContext drift is a serious issue.")]
        )
    )
    result = _catch_image_placeholder(ctx, resp)
    assert result is not None
    fc = result.content.parts[0].function_call
    assert fc.name == "generate_image"
    assert "illustration" in fc.args["prompt"].lower()


def test_catch_image_placeholder_skips_when_image_already_exists():
    ctx = MagicMock()
    ctx.state = {"current_image_path": "/path/to/existing.png"}
    ctx.user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text="Revise the draft")]
    )
    resp = LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text="Here is the revised draft.\n\nImage: Same robot")]
        )
    )
    result = _catch_image_placeholder(ctx, resp)
    assert result is None
