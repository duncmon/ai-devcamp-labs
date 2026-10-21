"""Guardrails: Model Armor on every model call, DLP before posting.

Layers (LAYERS, not alternatives: different layers catch different attacks):

  content_config()   Model Armor, applied INLINE by Agent Platform on each Gemini call
                     (GenerateContentConfig.model_armor_config), both directions
  friendly_block     after_model_callback: turns a Model Armor block into a
                     readable refusal instead of an empty turn
  redact_before_post DLP de-identify on create_post text (before_tool_callback)

All no-op if MODEL_ARMOR_TEMPLATE_ID is unset or "off", so ungoverned behaviour
is reproducible by flipping one var.

WHY INLINE, NOT A SANITIZE API CALL (verified 2026-09-21, LEARNINGS.md): calling
the Model Armor sanitize API from agent code works locally (your user ADC) and
returns 401 inside Agent Runtime, with plain REST AND with the client library,
because the agent runs as its own Agent Identity. Google's guidance for that case
is inline enforcement, which Agent Platform performs with ITS OWN service agent.
Constraints, each learnt by hitting it:
  * the Gemini call must use a REGIONAL location (GOOGLE_CLOUD_LOCATION=us-central1).
    Against `global` the template is "not found", whichever template you use;
  * STREAMING calls are not screened at all: an injection sails through with no
    block and no error. main.py therefore turns streaming off when this is on;
  * `global` templates cannot be created; use us-central1, the gateway's region;
  * Agent Platform's own service agent needs roles/modelarmor.user (gcp-setup.sh step 7);
  * Agent Platform's template lookup fails at random ("The template named ... was not
    found"). Fixed by retry options on the ADK model object (model() below): 15 of
    15 deployed checks passed with it, most failed without. The same options in
    the request config are ignored inside the deployed agent.
Why not call the sanitize API from a callback after all? It CAN work: the 401 is
google-auth's "prevent agent token sharing" default, and setting
GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=False lets both REST and
the client library through (verified). But Google warns against relaxing it in
production, so this repo uses inline enforcement instead. See LEARNINGS.md.
DLP is called with the DLP client library on the global endpoint.
"""

import logging
import os
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.adk.models import Gemini
from google.cloud import dlp_v2
from google.genai import types as genai_types

log = logging.getLogger(__name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
# DLP wants the project ID *string* and rejects the project NUMBER ("Malformed
# parent field"), but inside Agent Runtime GOOGLE_CLOUD_PROJECT is the number.
# Set PROJECT_ID on the deployment (gcp-setup.sh prints the flag).
DLP_PROJECT = os.environ.get("PROJECT_ID") or PROJECT  # also used for the Model Armor template path
if not DLP_PROJECT or DLP_PROJECT.isdigit():
    try:
        import google.auth
        _, adc_project = google.auth.default()
        if adc_project and not adc_project.isdigit():
            DLP_PROJECT = adc_project
    except Exception:
        pass
# Where the TEMPLATE lives. Use the same region as the Agent Gateway and Gemini
# (us-central1); `global` templates cannot be created.
MA_REGION = os.environ.get("MODEL_ARMOR_REGION", "us-central1")
# "off" (or blank) disables the Model Armor layers. A deployed engine cannot take
# an empty env var (the API rejects it), so "off" is the switch there.
MA_TEMPLATE = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "")
if MA_TEMPLATE.strip().lower() in ("off", "none", "disabled"):
    MA_TEMPLATE = ""

# Model Armor requires the Gemini call to target the REGIONAL endpoint matching the
# template (us-central1). If GOOGLE_CLOUD_LOCATION is "global" (which agents-cli deploy
# injects by default), Vertex AI rejects the call with 400 TEMPLATE_NOT_FOUND.
# Defensive self-healing: enforce regional location whenever Model Armor is active.
if MA_TEMPLATE and os.environ.get("GOOGLE_CLOUD_LOCATION", "").strip() in ("global", ""):
    log.warning(
        "Model Armor requires a regional location matching the template (%s). "
        "Overriding GOOGLE_CLOUD_LOCATION from %r to %r to prevent 400 TEMPLATE_NOT_FOUND.",
        MA_REGION,
        os.environ.get("GOOGLE_CLOUD_LOCATION"),
        MA_REGION,
    )
    os.environ["GOOGLE_CLOUD_LOCATION"] = MA_REGION
    os.environ["VERTEX_LOCATION"] = MA_REGION

# Responses get a second template WITHOUT the prompt-injection filter: that
# filter fires on a model reply that merely DISCUSSES injection (this user's
# signature topic), so outputs are screened on the responsible-AI filters only.
MA_OUTPUT_TEMPLATE = os.environ.get(
    "MODEL_ARMOR_OUTPUT_TEMPLATE_ID", f"{MA_TEMPLATE}-output" if MA_TEMPLATE else ""
)

# PII redaction has its OWN switch, independent of Model Armor: "on" turns on DLP at
# the request boundary (main.py) and before a post is sent. Off by default so Labs 1-2
# need no DLP setup. (It used to ride on the Model Armor switch, so turning guardrails
# off silently stopped the outgoing post being redacted too.)
PII_REDACTION = os.environ.get("PII_REDACTION", "off").strip().lower() in ("on", "true", "1")

REFUSAL = (
    "I can't help with that request — it was flagged by our content safety "
    "checks. Happy to help with your next post idea instead."
)

_dlp_client = None


def _dlp() -> "dlp_v2.DlpServiceClient":
    global _dlp_client
    if _dlp_client is None:
        _dlp_client = dlp_v2.DlpServiceClient()
    return _dlp_client


def _template(template_id: str) -> str:
    # The project ID, not the number Agent Runtime provides: in testing the deployed
    # agent (number in the path) hit "template not found" far more often than a
    # local run (ID in the path).
    return f"projects/{DLP_PROJECT}/locations/{MA_REGION}/templates/{template_id}"


# Shared exponential backoff and jitter configuration for Gemini models.
# Handles transient Vertex AI shared capacity limits (429 RESOURCE_EXHAUSTED),
# random Model Armor template lookup glitches (400), request timeouts (408),
# and transient gateway/service unavailable errors (500, 502, 503, 504).
# Based on official Google ADK resilience recommendations:
# https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted
RETRY_CONFIG = genai_types.HttpRetryOptions(
    attempts=6,
    initial_delay=1.5,
    max_delay=32.0,
    exp_base=2.0,
    jitter=0.5,
    http_status_codes=[400, 408, 429, 500, 502, 503, 504],
)


def content_config(screen_input: bool = True) -> Optional[genai_types.GenerateContentConfig]:
    """GenerateContentConfig that configures Model Armor screening and ADK retries.

    screen_input=False for the internal sub-agents: their input is text the
    orchestrator wrote, not the user's, so only the reply is screened.
    If GOOGLE_CLOUD_LOCATION is `global` the calls will fail with "template not found":
    deliberately left loud (fail closed) rather than silently dropping the guardrail.
    """
    model_armor = None
    if MA_TEMPLATE:
        if os.environ.get("GOOGLE_CLOUD_LOCATION", "global") == "global":
            log.error(
                "Model Armor is on but GOOGLE_CLOUD_LOCATION is global: Gemini calls "
                "will be rejected (template not found). Use a regional location."
            )
        model_armor = genai_types.ModelArmorConfig(
            prompt_template_name=_template(MA_TEMPLATE) if screen_input else None,
            response_template_name=_template(MA_OUTPUT_TEMPLATE),
        )

    return genai_types.GenerateContentConfig(
        model_armor_config=model_armor,
        http_options=genai_types.HttpOptions(retry_options=RETRY_CONFIG),
    )


class FallbackGemini(Gemini):
  """Gemini model adapter with automatic cascading fallback for retired or unreleased models.

  Prefers Gemini 3.5 / 3.0 models; falls back gracefully to Gemini 2.5 GA models
  if 404 NOT_FOUND is returned by the Vertex AI publisher endpoint."""
  fallback_models: list[str] = []

  async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
    models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
    last_err = None
    for candidate in models_to_try:
      try:
        llm_request.model = candidate
        async for resp in super().generate_content_async(llm_request, stream=stream):
          yield resp
        return
      except Exception as e:
        err_str = str(e)
        if "404" in err_str or "not found" in err_str.lower():
          log.warning(
              "Model %s returned 404 NOT_FOUND; falling back to next candidate in cascade...",
              candidate,
          )
          last_err = e
          continue
        raise e
    if last_err:
      raise last_err


def model(name: str):
    """The model for an agent, wrapped in FallbackGemini with cascading model support and retries.
    
    Protects against model deprecation/removal (Gemini 2.5) and premature model unavailability
    (Gemini 3.8/3.5), with role-based fallbacks to reduce execution costs."""
    custom_fallbacks = os.environ.get("MODEL_FALLBACKS")
    if custom_fallbacks and custom_fallbacks.strip():
        fallbacks = [m.strip() for m in custom_fallbacks.split(",") if m.strip()]
    elif "flash-lite" in name.lower():
        # Research role: keep costs lowest
        fallbacks = ["gemini-3.8-flash-lite", "gemini-3.5-flash-lite", "gemini-3.0-flash-lite", "gemini-2.5-flash-lite"]
    elif "pro" in name.lower():
        # High reasoning role
        fallbacks = ["gemini-3.8-pro", "gemini-3.5-pro", "gemini-3.1-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash"]
    else:
        # Default/Orchestrator/Draft role
        fallbacks = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.0-flash", "gemini-2.5-flash"]

    return FallbackGemini(
        model=name,
        fallback_models=fallbacks,
        retry_options=RETRY_CONFIG,
    )


def friendly_block(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """after_model_callback: a Model Armor block arrives as error_code MODEL_ARMOR
    with no content. Replace it with a readable refusal."""
    if llm_response.error_code == "MODEL_ARMOR":
        log.warning("Model Armor blocked a call: %s", llm_response.error_message)
        return LlmResponse(
            content=genai_types.Content(
                role="model", parts=[genai_types.Part.from_text(text=REFUSAL)]
            )
        )
    return None


def _latest_user_text(llm_request: LlmRequest) -> str:  # kept for tests/tools
    for content in reversed(llm_request.contents or []):
        if content.role == "user" and content.parts:
            texts = [p.text for p in content.parts if p.text]
            if texts:
                return "\n".join(texts)
    return ""


# --- DLP ----------------------------------------------------------------------

# Two thresholds, because the two families fail in opposite ways. Names and
# locations are fuzzy: at DLP's default POSSIBLE tier a capitalized product or
# project noun (e.g. "Agent Substrate") reads as PERSON_NAME, so they need
# LIKELY. Phones and emails are structured, and DLP rates a phone number
# POSSIBLE whenever it sits inside a sentence ("...or +44 7911 123456 if you
# want the slides"), so a blanket LIKELY silently leaked it (LEARNINGS.md,
# 2026-09-21). Structured types therefore run at POSSIBLE.
_DLP_PASSES = [
    (["EMAIL_ADDRESS", "PHONE_NUMBER"], "POSSIBLE"),
    (["PERSON_NAME", "LOCATION"], "LIKELY"),
]


# Multi-country domestic & international phone regex:
# - International prefix: optional (+44, +33, +86, +54, +1, etc.)
# - UK: 10-11 digits starting with 0 (01x, 02x, 03x, 07x)
# - France: 10 digits starting with 0 (01-09)
# - China: 11-digit mobile (13-19) or landline (010, 02x, etc.)
# - Argentina: Buenos Aires (011 / 11) or domestic mobile (15)
_PHONE_REGEX = (
    r"(?:"
    r"(?:\+\d{1,3}[\s-]?)?"
    r"(?:"
    r"0[1-9](?:[\s.-]?\d{2}){4}"                      # France (0356486930 / 03 56 48 69 30)
    r"|"
    r"0[1-9]\d{1,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}"      # UK (020 7946 0000)
    r"|"
    r"1[3-9]\d{9}"                                    # China mobile (13812345678)
    r"|"
    r"0\d{2,3}[\s.-]?\d{7,8}"                         # China landline (010-85001234)
    r"|"
    r"(?:0?11|15)[\s.-]?\d{4}[\s.-]?\d{4}"            # Argentina (011 4321 0000)
    r")"
    r")"
)

_CUSTOM_PHONE_INFO_TYPE = [
    {
        "info_type": {"name": "PHONE_NUMBER"},
        "regex": {"pattern": _PHONE_REGEX},
        "likelihood": "LIKELY",
    }
]


def _deidentify(text: str, info_types: list[str], min_likelihood: str) -> str:
    inspect_config = {
        "info_types": [{"name": t} for t in info_types],
        "min_likelihood": min_likelihood,
    }
    if "PHONE_NUMBER" in info_types:
        inspect_config["custom_info_types"] = _CUSTOM_PHONE_INFO_TYPE

    resp = _dlp().deidentify_content(
        request={
            "parent": f"projects/{DLP_PROJECT}/locations/global",
            "inspect_config": inspect_config,
            "deidentify_config": {
                "info_type_transformations": {
                    "transformations": [
                        {"primitive_transformation": {"replace_with_info_type_config": {}}}
                    ]
                }
            },
            "item": {"value": text},
        },
        timeout=15,
    )
    return resp.item.value or text


def redact_pii(text: str) -> str:
    """De-identifies PII via Cloud DLP, replacing each finding with its type
    (e.g. "[PERSON_NAME]"). Used on final drafts before they leave the app."""
    for info_types, likelihood in _DLP_PASSES:
        text = _deidentify(text, info_types, likelihood)
    return text


# At the boundary we redact the identifiers that make a message personal data:
# emails, phone numbers, person names. NOT locations: DLP reads any city as a
# LOCATION, so "a post about our London event" would lose the one word that matters,
# for little privacy gain. (The pre-post pass above still uses the full set.)
_BOUNDARY_PASSES = [
    (["EMAIL_ADDRESS", "PHONE_NUMBER"], "POSSIBLE"),
    (["PERSON_NAME"], "LIKELY"),
]
_boundary_cache: dict[str, str] = {}


def redact_boundary(text: str) -> str:
    """De-identify a user's message BEFORE it reaches the agent, the model, the session
    store or Memory Bank. Raises if DLP fails: the caller must fail closed."""
    if not text or not text.strip():
        return text
    hit = _boundary_cache.get(text)
    if hit is not None:
        return hit
    out = text
    for info_types, likelihood in _BOUNDARY_PASSES:
        out = _deidentify(out, info_types, likelihood)
    if len(_boundary_cache) > 512:
        _boundary_cache.clear()
    _boundary_cache[text] = out
    return out


def redact_pii_text(text: str) -> dict:
    """Removes personal information from text before it is used in a post.

    Use whenever the user pastes or uploads source material that may contain
    real people's names, email addresses, phone numbers, or locations.

    Args:
        text: The text to clean.

    Returns:
        dict with 'status' and 'redacted_text' (PII replaced by placeholders
        like [PERSON_NAME]).
    """
    # A tool that raises kills the whole turn (DynamicNodeFailError), so a DLP
    # failure (e.g. the 401 a plain-HTTP call gets inside Agent Runtime) is
    # reported back to the model instead.
    try:
        return {"status": "success", "redacted_text": redact_pii(text)}
    except Exception as e:  # noqa: BLE001
        log.warning("redact_pii_text: DLP unavailable, text left unredacted: %s", e)
        return {
            "status": "error",
            "error": f"PII redaction is unavailable ({type(e).__name__}); the text was NOT redacted.",
            "redacted_text": text,
        }


def redact_before_post(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    """before_tool_callback: final drafts get a DLP pass on their way out.
    Mutating args in place changes what the tool actually receives (the same
    dict is passed on to the call); returning None lets the call proceed."""
    if not PII_REDACTION:
        return None
    if tool.name in ("create_post", "linkedin_create_post") and isinstance(args.get("text"), str):
        redacted = redact_pii(args["text"])
        if redacted != args["text"]:
            log.warning("DLP redacted PII from outgoing post")
            args["text"] = redacted
    return None
