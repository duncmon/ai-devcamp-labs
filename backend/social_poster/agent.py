import os
import pathlib
import sys
from typing import Any, Optional
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.skills import load_skill_from_dir
from google.adk.tools import google_search, load_memory
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.tools.tool_context import ToolContext
from mcp import StdioServerParameters
from .tools import generate_image

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = PROJECT_ROOT / "skills"
MCP_SERVER = PROJECT_ROOT / "mcp" / "linkedin_server.py"

skill_toolset = SkillToolset(
    skills=[
        load_skill_from_dir(SKILLS_DIR / "post-formatter"),
        load_skill_from_dir(SKILLS_DIR / "platform-style"),
        load_skill_from_dir(SKILLS_DIR / "brand-voice"),
        load_skill_from_dir(SKILLS_DIR / "poster-style"),
    ],
)

BUFFER_API_KEY = os.environ.get("BUFFER_API_KEY", "")

buffer_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp.buffer.com/mcp",
        headers={"Authorization": f"Bearer {BUFFER_API_KEY}"},
    ),
    require_confirmation=True,
)

linkedin_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[str(MCP_SERVER)],
            env={
                "DRY_RUN": os.environ.get("DRY_RUN", "true"),
                "LINKEDIN_ACCESS_TOKEN": os.environ.get("LINKEDIN_ACCESS_TOKEN", ""),
            },
        ),
    ),
    tool_filter=["get_profile", "create_post"],
    tool_name_prefix="linkedin",
    require_confirmation=True,
)

POST_VIA = os.environ.get("POST_VIA", "").strip().lower()
use_linkedin = POST_VIA != "buffer"
use_buffer = bool(BUFFER_API_KEY) and POST_VIA != "linkedin"
use_memory_bank = bool(os.environ.get("APP_URL") or os.environ.get("AGENT_ENGINE_ID"))

RESEARCH_MODEL = os.environ.get("RESEARCH_MODEL", "gemini-3.5-flash-lite")
ORCHESTRATOR_MODEL = os.environ.get("ORCHESTRATOR_MODEL", "gemini-3.8-flash")

search_agent = Agent(
    name="web_researcher",
    model=RESEARCH_MODEL,
    description="Researches facts, dates, and context on the web.",
    instruction="Research the given query and return a concise summary of relevant facts.",
    tools=[google_search],
)

tools = [
    *([load_memory] if use_memory_bank else []),
    AgentTool(agent=search_agent),
    generate_image,
    skill_toolset,
]

if use_buffer:
    tools.append(buffer_toolset)
if use_linkedin:
    tools.append(linkedin_toolset)

# idea -> consulting_memory -> researching -> drafting -> awaiting_approval -> posted
_TOOL_STAGES = {
    "web_researcher": "researching",
    "load_skill": "drafting",
    "generate_image": "drafting",
    "load_memory": "consulting_memory",
}


def _init_stage(callback_context: CallbackContext) -> None:
    if "pipeline_stage" not in callback_context.state:
        callback_context.state["pipeline_stage"] = "idea"


def _track_stage(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: dict
) -> Optional[dict]:
    if tool.name in _TOOL_STAGES:
        tool_context.state["pipeline_stage"] = _TOOL_STAGES[tool.name]
    elif tool.name in ("create_post", "linkedin_create_post") and tool_response.get("isError") is False:
        tool_context.state["pipeline_stage"] = "posted"  # only a completed MCP call
    return None  # never modify the tool result


async def _stage_after_agent(callback_context: CallbackContext) -> None:
    # A turn that ends mid-pipeline is waiting on the user (draft approval).
    if callback_context.state.get("pipeline_stage") in ("researching", "drafting"):
        callback_context.state["pipeline_stage"] = "awaiting_approval"
        return

    if use_memory_bank and callback_context.state.get("pipeline_stage") == "posted":
        if callback_context.state.get("memory_ingested"):
            return
        try:
            await callback_context.add_session_to_memory()
            callback_context.state["memory_ingested"] = True
        except Exception:
            pass


_MEMORY_ROUTING = """
0. FIRST, before researching or drafting, call load_memory to find out
   what the user has posted about before, how they phrase things, and any
   preferences they have stated (preferred platform, tone, topics to avoid).
   Weave that into the draft brief so the new post sounds like them and
   doesn't repeat old topics. If nothing comes back, say so briefly and carry
   on — an empty memory is normal on a first conversation.
""" if use_memory_bank else ""

root_agent = Agent(
    name="social_poster",
    model=ORCHESTRATOR_MODEL,
    description="Helps the user turn an idea into a polished social media post.",
    instruction=f"""You help the user turn an idea into a social media post.

Workflow:{_MEMORY_ROUTING}
1. If the idea needs facts, dates, or context, research it with the
   web_researcher tool first.
2. When drafting, load and follow the relevant skills: post-formatter
   (structure), platform-style (rules for the target platform), and
   brand-voice (tone).
3. If the user asks for an image, load and follow the poster-style skill,
   then call generate_image with a detailed visual description and tell
   them where the file was saved.
4. ALWAYS show the finished draft to the user and ask for their approval
   before any posting action.
5. Routing for publishing:
   - Use LinkedIn (linkedin_create_post) for an immediate post with an image attached.
   - Use Buffer for scheduling or for posting to other platforms (for an immediate Buffer post, ask Buffer to publish now rather than schedule).

Posting rules (strict):
- Only post AFTER the user has explicitly approved the exact draft shown to
  them. "Yes", "post it" counts; enthusiasm about the idea does not.
- After posting, share the returned confirmation with the user.""",
    tools=tools,
    before_agent_callback=_init_stage,
    after_tool_callback=_track_stage,
    after_agent_callback=_stage_after_agent,
)
