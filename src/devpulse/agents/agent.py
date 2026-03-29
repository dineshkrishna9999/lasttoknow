"""DevPulse agent — the core AI brain."""

from __future__ import annotations

import logging

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from ._tools import DevPulseTools
from .instructions import BRIEFING_INSTRUCTION

logger = logging.getLogger(__name__)


class DevPulseAgent(LlmAgent):
    """AI-powered tech radar agent.

    Uses Google ADK with LiteLLM so any LLM provider works
    (Azure, OpenAI, Gemini, Claude, Ollama).
    """

    def __init__(self, llm: LiteLlm) -> None:
        self._devpulse_tools = DevPulseTools()

        super().__init__(
            name="devpulse_agent",
            description="AI-powered tech radar that tracks packages, releases, and trends.",
            model=llm,
            instruction=BRIEFING_INSTRUCTION,
            tools=self._devpulse_tools.get_tools(),  # type: ignore[arg-type]
        )


def run_agent(model: str, message: str) -> str:
    """Run the DevPulse agent and return its response.

    Args:
        model: LiteLLM model string (e.g. "azure/gpt-4.1", "gpt-4o").
        message: The user's message.

    Returns:
        The agent's text response.

    Raises:
        RuntimeError: If the agent fails (auth error, no response, etc).
    """
    llm = LiteLlm(model=model)
    agent = DevPulseAgent(llm=llm)

    session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name="devpulse",
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
