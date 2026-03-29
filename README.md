# 📡 DevPulse

> Your AI-powered tech radar. Track packages, releases, trends — and get briefed like a CTO.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

**You're always the last to know.**

LiteLLM shipped a breaking change — you found out from a colleague. Google ADK released the exact fix you needed — 2 weeks ago. A repo with 15K stars solves your exact problem — you never heard of it.

**DevPulse fixes this.** It's an AI agent that knows YOUR stack, tracks what matters, and briefs you like a personal tech analyst.

## How It Works

```bash
# Tell it what you care about
devpulse track litellm
devpulse track --github BerriAI/litellm
devpulse track --topic "AI agents"

# Or auto-detect from your project
devpulse scan                        # Reads pyproject.toml / requirements.txt

# Get your personalized briefing
devpulse brief --model gpt-4o
```

```
╭──────────────────────── 📡 DevPulse Briefing ────────────────────────╮
│                                                                       │
│  🔴 CRITICAL                                                         │
│  ├── litellm 1.41.0 → Breaking: Azure auth flow changed              │
│  └── google-adk 1.28.0 → New: Multi-agent orchestration              │
│                                                                       │
│  🟡 WORTH KNOWING                                                    │
│  ├── 🔥 Trending: "hermes-agent" (15K ⭐ this week)                   │
│  └── HN: "AI agent memory" discussion (342 points)                   │
│                                                                       │
│  🟢 FYI                                                              │
│  ├── pytest 9.0.2 — minor bugfixes                                   │
│  └── 3 new repos matching "AI agents" trending today                 │
│                                                                       │
╰───────────────────────────────── model: gpt-4o ──────────────────────╯
```

## Features

- **Track anything** — PyPI packages, GitHub repos, topics
- **Auto-detect dependencies** — scans pyproject.toml / requirements.txt
- **AI-powered briefings** — powered by Google ADK + LiteLLM
- **Smart prioritization** — 🔴 Critical / 🟡 Important / 🟢 FYI
- **Works with any LLM** — Azure OpenAI, OpenAI, Gemini, Claude, Ollama (local)
- **Beautiful terminal output** — powered by Rich + Typer

## Installation

```bash
# From source (recommended for now)
git clone https://github.com/dineshkrishna9999/devpulse.git
cd devpulse
uv sync

# Then run with
uv run devpulse --help
```

## Quick Start

```bash
# 1. Set your LLM model
devpulse config model gpt-4o
# or set DEVPULSE_MODEL env var
# or pass --model flag each time

# 2. Track your stack
devpulse track litellm                  # PyPI package
devpulse track --github BerriAI/litellm # GitHub repo
devpulse track --topic "AI agents"      # Topic
devpulse track litellm --version 1.40.0 # With current version
devpulse scan                           # Auto-detect from pyproject.toml

# 3. See what you're tracking
devpulse list

# 4. Get briefed
devpulse brief                          # Uses configured model
devpulse brief --model azure/gpt-4.1   # Override model
devpulse brief --raw                    # Raw text, no formatting

# 5. Manage
devpulse untrack litellm                # Stop tracking
devpulse status                         # Full overview
devpulse config show                    # Show settings
```

## Supported LLM Providers

DevPulse uses [LiteLLM](https://github.com/BerriAI/litellm) under the hood, so **any LLM works**:

| Provider | Model Example | Env Var |
|----------|---------------|---------|
| Azure OpenAI | `azure/gpt-4.1` | `AZURE_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Google Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Anthropic Claude | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| Ollama (local) | `ollama/llama3` | None needed! |

```bash
devpulse config model azure/gpt-4.1
devpulse config model ollama/llama3
```

## Data Sources

The agent fetches from:

- **PyPI** — package releases, versions, metadata
- **GitHub** — trending repositories by language
- **Hacker News** — top stories matching your tracked topics

## Architecture

```
┌──────────────────────────────────────────────┐
│              DevPulse CLI (Typer)             │
│          commands → renderer → terminal       │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│         ADK Orchestrator Agent                │
│        (Google ADK + LiteLLM)                 │
│                                               │
│  System prompt defines HOW the agent thinks   │
│  Tools define WHAT it can do:                 │
│    • fetch_pypi_releases()                    │
│    • fetch_github_trending()                  │
│    • fetch_hackernews_top()                   │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│           External APIs (httpx)               │
│    PyPI JSON · GitHub Search · HN Algolia     │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│         Local State (~/.devpulse/)            │
│    config.json · tracked.json                 │
└──────────────────────────────────────────────┘
```

## Development

```bash
# Clone & install
git clone https://github.com/dineshkrishna9999/devpulse.git
cd devpulse
uv sync

# Run checks
uv run poe fmt          # Format code
uv run poe lint         # Lint code
uv run poe typecheck    # Type check (mypy)
uv run poe test         # Run tests
uv run poe check        # Run ALL checks

# Run the CLI
uv run devpulse status
```

### Project Structure

```
src/devpulse/
├── cli.py              # CLI entry point (Typer)
├── config.py           # Config & tracked items (~/.devpulse/)
├── models.py           # Data models (dataclasses + StrEnum)
├── renderer.py         # Rich terminal output (panels, tables)
├── scanner.py          # Dependency scanner (pyproject.toml, requirements.txt)
└── agents/
    ├── agent.py        # ADK agent class + runner
    ├── _tools.py       # Tool functions (PyPI, GitHub, HN fetchers)
    └── instructions/
        └── briefing.py # System prompt for the briefing agent
```

## License

[MIT](LICENSE)
