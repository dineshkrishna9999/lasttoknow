# 🔔 FirstToKnow

### Because being the first to know isn't luck — it's a system.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

You've been here:

- 😤 LiteLLM shipped a **breaking change** — you found out when your prod pipeline crashed
- 🤦 Google ADK released the exact fix you needed — **2 weeks ago**
- 😶 A repo with **15K stars** solves your exact problem — you never heard of it
- 🫠 Your colleague casually drops *"oh yeah, that was deprecated last month"*

You're not lazy. You're not out of touch. **There's just too much happening and no one tool that watches YOUR stack.**

Dependabot bumps versions but doesn't explain why it matters. daily.dev shows generic news, not YOUR news. GitHub Watch drowns you in noise.

## The Fix

**FirstToKnow** is an AI agent that knows your stack, tracks what matters to YOU, and briefs you like a personal tech analyst.

```bash
# 30 seconds to set up
uv run firsttoknow scan                          # Auto-detects deps from your project
uv run firsttoknow track --topic "AI agents"     # Add topics you care about
uv run firsttoknow brief --model gpt-4o          # Get your personalized briefing
```

```
╭───────────────────────── 🔔 FirstToKnow Briefing ──────────────────────────╮
│                                                                            │
│  🔴 CRITICAL — action needed                                              │
│  ├── litellm 1.41.0 → Breaking: Azure auth flow changed                   │
│  └── google-adk 1.28.0 → New: Multi-agent orchestration                   │
│                                                                            │
│  🟡 WORTH KNOWING                                                         │
│  ├── 🔥 Trending: "hermes-agent" (15K ⭐ this week)                        │
│  └── HN: "AI agent memory" discussion (342 points)                        │
│                                                                            │
│  🟢 FYI                                                                   │
│  ├── pytest 9.0.2 — minor bugfixes                                        │
│  └── 3 new repos matching "AI agents" trending today                      │
│                                                                            │
╰──────────────────────────────── model: gpt-4o ─────────────────────────────╯
```

**No dashboards.** No browser tabs. No newsletters you'll never read. Just one command and you're the **first** to know.

### Real output — tracking an npm package

```bash
$ uv run firsttoknow track --npm express
✓ Now tracking express (npm)

$ uv run firsttoknow brief
```

```
╭───────────────────────────────────── 🔔 FirstToKnow Briefing ──────────────────────────────────────╮
│                                                                                                    │
│  ## 📦 Package Updates                                                                             │
│                                                                                                    │
│  **express 5.2.1** — The latest version of Express is 5.2.1. This release includes ongoing         │
│  enhancements beneath the major 5.x line, which previously introduced long-awaited improvements    │
│  like async route handling and upgraded error middleware. 🟢                                        │
│  [Read more](https://expressjs.com/)                                                               │
│                                                                                                    │
│  ## 🔥 Trending Repos                                                                              │
│                                                                                                    │
│  **instructkr/clawd-code** (31,349★) — A toolkit for the leaked Claude Code base, with             │
│  automation scripts. Reflects the ongoing momentum in open AI exploitation — especially             │
│  noteworthy for teams monitoring IP leaks and "shadow LLMs."                                       │
│  [Read more](https://github.com/instructkr/clawd-code)                                             │
│                                                                                                    │
│  ## 📰 News & Discussions                                                                          │
│                                                                                                    │
│  **axios 1.14.1 and 0.30.4 on npm are compromised** (331 pts, 48 comments) — Two versions of      │
│  Axios were compromised through a stolen maintainer's account, with malicious dependency            │
│  injection found in published packages. Supply chain attacks remain rampant, highlighting the       │
│  importance of strict CI/CD, dependency auditing, and package pinning for all JS projects.          │
│  [Read more](https://reddit.com/r/programming/comments/1s8ct9i/)                                   │
│                                                                                                    │
│  ## 💡 TL;DR                                                                                       │
│                                                                                                    │
│  - axios (npm) suffered a supply chain compromise — dependency hygiene and ongoing vigilance        │
│    for all open-source projects (especially in Node.js) is essential.                               │
│  - Express is stable at 5.2.1; no urgent actions required.                                         │
│                                                                                                    │
╰──────────────────────────────────────── model: azure/gpt-4.1 ──────────────────────────────────────╯
```

*Actual output from `firsttoknow brief` — not mocked, not edited.*

## Why FirstToKnow > Everything Else

| Tool | What it does | What it doesn't do |
|------|-------------|-------------------|
| **Dependabot** | Bumps versions | Doesn't explain what changed or why it matters to YOU |
| **daily.dev** | Generic news feed | Not personalized to your stack |
| **GitHub Watch** | Notifications | Drowns you in noise, zero intelligence |
| **Newsletters** | Curated by someone else | Not YOUR stack, stale by the time you read |
| **🔔 FirstToKnow** | **Knows YOUR stack, fetches real-time data, AI synthesizes and prioritizes** | — |

## Get Started in 60 Seconds

```bash
# Install
git clone https://github.com/dineshkrishna9999/firsttoknow.git
cd firsttoknow && uv sync

# Point it at any LLM (Azure, OpenAI, Gemini, Claude, Ollama)
echo "OPENAI_API_KEY=sk-..." > .env
uv run firsttoknow config model gpt-4o

# Tell it what you care about
uv run firsttoknow track litellm                  # PyPI package
uv run firsttoknow track --npm express            # npm package
uv run firsttoknow track --github BerriAI/litellm # GitHub repo
uv run firsttoknow track --topic "AI agents"      # Broad topic
uv run firsttoknow scan                           # Or just auto-detect everything

# Get briefed
uv run firsttoknow brief
```

That's it. You're the first to know.

## All Commands

```bash
# Track / Untrack
uv run firsttoknow track <name>                 # Track a PyPI package
uv run firsttoknow track --npm <name>           # Track an npm package
uv run firsttoknow track --github owner/repo    # Track a GitHub repo
uv run firsttoknow track --topic "AI agents"    # Track a topic
uv run firsttoknow track litellm --version 1.40 # Track with current version
uv run firsttoknow scan                         # Auto-detect from pyproject.toml / package.json
uv run firsttoknow untrack <name>               # Stop tracking

# Briefings
uv run firsttoknow brief                        # Get your AI briefing
uv run firsttoknow brief --model azure/gpt-4.1  # Use a specific model
uv run firsttoknow brief --raw                  # Raw text, no formatting

# Manage
uv run firsttoknow list                         # See what you're tracking
uv run firsttoknow status                       # Full overview
uv run firsttoknow config model <model>         # Set default LLM
uv run firsttoknow config show                  # Show settings
```

## Works With Any LLM

Powered by [LiteLLM](https://github.com/BerriAI/litellm) — so you're not locked in:

| Provider | Model | Env Var |
|----------|-------|---------|
| **Azure OpenAI** | `azure/gpt-4.1` | `AZURE_API_KEY` |
| **OpenAI** | `gpt-4o` | `OPENAI_API_KEY` |
| **Google Gemini** | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| **Anthropic Claude** | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| **Ollama (free!)** | `ollama/llama3` | None needed |

## How It Works Under the Hood

```
You run: firsttoknow brief
              │
              ▼
   ┌─────────────────────┐
   │   FirstToKnow CLI   │  Reads your tracked items from ~/.firsttoknow/
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │    ADK Agent +      │  AI decides which tools to call based on
   │    LiteLLM          │  what you're tracking
   └──────────┬──────────┘
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
  ┌──────┐ ┌──────┐ ┌──────┐
  │ PyPI │ │GitHub│ │  HN  │   Real API calls — not hallucinated data
  │  API │ │  API │ │ API  │
  └──────┘ └──────┘ └──────┘
  ┌──────┐ ┌──────┐ ┌──────┐
  │ npm  │ │Dev.to│ │Reddit│
  │  API │ │  API │ │ API  │
  └──────┘ └──────┘ └──────┘
              │
              ▼
   ┌─────────────────────┐
   │  AI synthesizes     │  Prioritizes: 🔴 Critical → 🟡 Important → 🟢 FYI
   │  and prioritizes    │  Thinks like a senior dev briefing a CTO
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Rich terminal      │  Beautiful panels, tables, colored output
   │  output             │
   └─────────────────────┘
```

The AI **decides** which tools to call — you don't hardcode the flow. You just say "brief me" and it figures out what to check.

## Development

```bash
git clone https://github.com/dineshkrishna9999/firsttoknow.git
cd firsttoknow && uv sync

uv run poe check        # Run ALL checks (format, lint, typecheck, test)
uv run poe test         # Just tests
uv run poe fmt          # Format code
```

### Project Structure

```
src/firsttoknow/
├── cli.py              # CLI commands (Typer)
├── config.py           # Config & persistence (~/.firsttoknow/)
├── models.py           # Data models
├── renderer.py         # Rich terminal output
├── scanner.py          # Dependency scanner (pyproject.toml, requirements.txt, package.json)
└── agents/
    ├── agent.py        # ADK agent + runner
    ├── _tools.py       # API fetchers (PyPI, npm, GitHub, HN, Dev.to, Reddit)
    └── instructions/
        └── briefing.py # System prompt
```

## License

[MIT](LICENSE) — do whatever you want with it.

---

<p align="center">
  <b>Stop being the last to know. Start being the first.</b><br>
  <a href="https://github.com/dineshkrishna9999/firsttoknow">⭐ Star this repo</a> if you've ever found out about a breaking change from a colleague.
</p>
