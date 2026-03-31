"""LastToKnow agent — the core AI brain."""

from __future__ import annotations

import logging
import sys
import threading
import warnings

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from ._tools import LastToKnowTools
from .instructions import BRIEFING_INSTRUCTION

logger = logging.getLogger(__name__)


class LastToKnowAgent(LlmAgent):
    """AI-powered tech radar agent.

    Uses Google ADK with LiteLLM so any LLM provider works
    (Azure, OpenAI, Gemini, Claude, Ollama).
    """

    def __init__(self, llm: LiteLlm) -> None:
        self._lasttoknow_tools = LastToKnowTools()

        super().__init__(
            name="lasttoknow_agent",
            description="AI-powered tech radar that tracks packages, releases, and trends.",
            model=llm,
            instruction=BRIEFING_INSTRUCTION,
            tools=self._lasttoknow_tools.get_tools(),  # type: ignore[arg-type]
        )


def _suppress_noisy_output() -> None:
    """Suppress ADK/LiteLLM background thread tracebacks and warnings."""
    # Silence loggers
    for name in ("LiteLLM", "google.adk", "litellm", "httpx"):
        logging.getLogger(name).setLevel(logging.CRITICAL)

    # Suppress background thread exception tracebacks
    threading.excepthook = lambda _args: None

    # Suppress warnings (e.g. "App name mismatch detected")
    warnings.filterwarnings("ignore")

    # Redirect stderr to suppress any remaining noise during the run
    sys.stderr = open("/dev/null", "w")  # noqa: PTH123, SIM115


def _restore_output() -> None:
    """Restore stderr after suppression."""
    sys.stderr = sys.__stderr__


def run_agent(model: str, message: str) -> str:
    """Run the LastToKnow agent and return its response.

    Args:
        model: LiteLLM model string (e.g. "azure/gpt-4.1", "gpt-4o").
        message: The user's message.

    Returns:
        The agent's text response.

    Raises:
        RuntimeError: If the agent fails (auth error, no response, etc).
    """
    _suppress_noisy_output()

    try:
        return _run_agent_inner(model, message)
    finally:
        _restore_output()


def _run_agent_inner(model: str, message: str) -> str:
    """Inner agent runner (called with output suppressed)."""
    llm = LiteLlm(model=model)
    agent = LastToKnowAgent(llm=llm)

    session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name="lasttoknow",
        auto_create_session=True,
    )

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    response = ""
    try:
        for event in runner.run(new_message=content, session_id="session", user_id="user"):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response = part.text
    except Exception as exc:
        msg = str(exc)
        if "api_key" in msg.lower() or "authentication" in msg.lower():
            msg = f"Authentication failed for model '{model}'. Check your API key."
        raise RuntimeError(msg) from exc

    if not response:
        msg = f"No response from model '{model}'. Check your API key and model name."
        raise RuntimeError(msg)

    return response
