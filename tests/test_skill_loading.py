import json
import pathlib
import pytest
from backend.social_poster.agent import draft_agent

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_draft_agent_has_mandatory_skill_loading_instruction():
    """Verifies Learning 31: draft_agent's instruction must explicitly mandate
    calling load_skill for brand-voice rather than relying on optional suggestions."""
    instructions = draft_agent.instruction
    assert "load_skill for brand-voice" in instructions
    assert "NEVER write draft text" in instructions
    assert "without calling load_skill for brand-voice" in instructions


def test_eval_config_has_brand_voice_skill_consulted_rubric():
    """Verifies Learning 31: evals/eval_config.json must have a rubric verifying
    that skills are actually consulted/loaded, closing the progressive disclosure blind spot."""
    cfg_file = REPO_ROOT / "evals" / "eval_config.json"
    assert cfg_file.exists()
    
    with open(cfg_file) as f:
        config = json.load(f)
    
    tool_rubrics = config["criteria"]["rubric_based_tool_use_quality_v1"]["rubrics"]
    rubric_ids = [r["rubric_id"] for r in tool_rubrics]
    assert "brand_voice_skill_consulted" in rubric_ids

    # Find the rubric and verify its text property
    rubric = next(r for r in tool_rubrics if r["rubric_id"] == "brand_voice_skill_consulted")
    assert "brand-voice" in rubric["rubric_content"]["text_property"].lower()


def test_eval_config_has_brand_voice_followed_final_response_rubric():
    """Verifies Step 2: evals/eval_config.json must have brand_voice_followed
    to catch corporate clichés in final text."""
    cfg_file = REPO_ROOT / "evals" / "eval_config.json"
    with open(cfg_file) as f:
        config = json.load(f)
    
    final_rubrics = config["criteria"]["rubric_based_final_response_quality_v1"]["rubrics"]
    rubric_ids = [r["rubric_id"] for r in final_rubrics]
    assert "brand_voice_followed" in rubric_ids


def test_brand_voice_skill_is_in_pristine_state():
    """Verifies that skills/brand-voice/SKILL.md is restored to pristine state,
    banning clichés rather than requiring them."""
    skill_file = REPO_ROOT / "skills" / "brand-voice" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text()
    
    assert "## Banned clichés" in content
    assert "Never use: \"game-changer\"" in content
    assert "## Required phrases" not in content
