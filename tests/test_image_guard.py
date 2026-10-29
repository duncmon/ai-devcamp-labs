from unittest.mock import MagicMock
from google.genai import types as genai_types
from google.adk.models.llm_response import LlmResponse
from backend.social_poster.agent import (
    _catch_image_placeholder,
    _sanitize_draft_response,
    _sanitize_and_fix_image_markdown,
)


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
    # Per Learning 30, _catch_image_placeholder strictly matches explicit placeholder syntax
    # (_IMAGE_PLACEHOLDER_RE) rather than eager substring scanning, protecting negative constraints ("no image").
    assert result is None


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


def test_sanitize_draft_response_strips_raw_paths_and_signed_urls():
    ctx = MagicMock()
    raw_text = (
        "Draft text about AI.\n\n#AI\n"
        "/Users/duncanmoncrieff/projects/gdg-london-ai-devcamp-sept26/ai-devcamp-labs/gallery/post-image-123.png\n"
        "https://storage.googleapis.com/lab2-bucket/post-images/123.png?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Signature=secret123"
    )
    resp = LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=raw_text)]
        )
    )
    result = _sanitize_draft_response(ctx, resp)
    assert result is not None
    cleaned = result.content.parts[0].text
    assert "/Users/duncanmoncrieff" not in cleaned
    assert "X-Goog-Signature" not in cleaned
    assert "Draft text about AI.\n\n#AI" in cleaned


def test_sanitize_and_fix_image_markdown_replaces_empty_tag():
    ctx = MagicMock()
    ctx.state = {"current_image_display_url": "/outputs/post-image-123.png"}
    text_with_empty_tag = (
        "Here is the draft.\n#AI\n![post image]()\nLooks good? If so, I can post it via Buffer."
    )
    resp = LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=text_with_empty_tag)]
        )
    )
    result = _sanitize_and_fix_image_markdown(ctx, resp)
    assert result is not None
    fixed = result.content.parts[0].text
    assert "![post image](/outputs/post-image-123.png)" in fixed
    assert "![post image]()" not in fixed


def test_sanitize_and_fix_image_markdown_removes_empty_tag_if_no_image():
    ctx = MagicMock()
    ctx.state = {}
    text_with_empty_tag = (
        "Here is the draft.\n#AI\n![post image]()\nLooks good?"
    )
    resp = LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=text_with_empty_tag)]
        )
    )
    result = _sanitize_and_fix_image_markdown(ctx, resp)
    assert result is not None
    fixed = result.content.parts[0].text
    assert "![post image]()" not in fixed
    assert "Here is the draft.\n#AI\nLooks good?" in fixed

