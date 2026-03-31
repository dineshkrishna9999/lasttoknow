# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-03-31

### Added

- CLI with Typer: `track`, `untrack`, `list`, `brief`, `scan`, `status`, `config`
- ADK agent with LiteLLM backbone for AI-powered briefings
- 3 tool functions: PyPI releases, GitHub trending, Hacker News top stories
- Dependency scanner: auto-detect from `pyproject.toml` / `requirements.txt`
- Rich terminal output: panels, tables, colored text
- Config management with JSON persistence (`~/.lasttoknow/`)
- `.env` support via python-dotenv for API keys
- Works with any LLM provider: Azure OpenAI, OpenAI, Gemini, Claude, Ollama
- System prompt with priority levels: 🔴 Critical / 🟡 Important / 🟢 FYI
- 81 tests with full coverage across CLI, agents, config, scanner, and models
