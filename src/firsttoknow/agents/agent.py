"""FirstToKnow agent — the core AI brain."""

from __future__ import annotations

import logging
import sys
import threading
import warnings
from contextlib import contextmanager
from typing import TYPE_CHECKING

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from ._tools import FirstToKnowTools
from .instructions import BRIEFING_INSTRUCTION

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


class FirstToKnowAgent(LlmAgent):
    """AI-powered tech radar agent.

    Uses Google ADK with LiteLLM so any LLM provider works
    (Azure, OpenAI, Gemini, Claude, Ollama).
    """

    def __init__(self, llm: LiteLlm) -> None:
        self._firsttoknow_tools = FirstToKnowTools()

        super().__init__(
            name="firsttoknow_agent",
            description="AI-powered tech radar that tracks packages, releases, and trends.",
            model=llm,
            instruction=BRIEFING_INSTRUCTION,
            tools=self._firsttoknow_tools.get_tools(),  # type: ignore[arg-type]
        )


@contextmanager
def _suppress_noisy_output() -> Generator[None]:
    """Temporarily suppress ADK/LiteLLM background noise, restoring everything on exit."""
    # Save previous state
    old_excepthook = threading.excepthook
    old_filters = warnings.filters[:]
    old_stderr = sys.stderr
    old_levels: dict[str, int] = {}
    noisy_loggers = ("LiteLLM", "google.adk", "litellm", "httpx")
    for name in noisy_loggers:
        lg = logging.getLogger(name)
        old_levels[name] = lg.level
        lg.setLevel(logging.CRITICAL)

    threading.excepthook = lambda _args: None
    warnings.filterwarnings("ignore")
    devnull = open("/dev/null", "w")  # noqa: PTH123, SIM115
    sys.stderr = devnull

    try:
        yield
    finally:
        # Restore everything
        sys.stderr = old_stderr
        devnull.close()
        threading.excepthook = old_excepthook
        warnings.filters[:] = old_filters  # type: ignore[index]
        for name in noisy_loggers:
            logging.getLogger(name).setLevel(old_levels[name])


def run_agent(model: str, message: str) -> str:
    """Run the FirstToKnow agent and return its response.

    Args:
        model: LiteLLM model string (e.g. "azure/gpt-4.1", "gpt-4o").
        message: The user's message.

    Returns:
        The agent's text response.

    Raises:
        RuntimeError: If the agent fails (auth error, no response, etc).
    """
    with _suppress_noisy_output():
        return _run_agent_inner(model, message)


def _run_agent_inner(model: str, message: str) -> str:
    """Inner agent runner (called with output suppressed)."""
    llm = LiteLlm(model=model)
    agent = FirstToKnowAgent(llm=llm)

    session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name="firsttoknow",
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
