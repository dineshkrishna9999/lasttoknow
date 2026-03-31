# Roadmap

> Features planned for FirstToKnow. Pick one, build it, ship it.

## v0.4.0 — Multi-Ecosystem

- [x] **npm support** — `firsttoknow track --npm express` (registry.npmjs.org API)
- [ ] **cargo support** — `firsttoknow track --cargo serde` (crates.io API)
- [ ] **maven/gradle support** — `firsttoknow track --maven org.springframework:spring-boot` (search.maven.org API)
- [ ] **go support** — `firsttoknow track --go github.com/gin-gonic/gin` (proxy.golang.org API)
- [x] Expand `scan` to detect `package.json` ~~, `Cargo.toml`, `build.gradle`, `go.mod`~~ (npm done; others TBD)

## v0.5.0 — Security

- [x] **CVE/OSV vulnerability alerts** — integrate with [osv.dev](https://osv.dev) API to check tracked packages for known vulnerabilities. Flag as 🔴 CRITICAL automatically.
- [ ] **License change detection** — compare license field across versions. Catch cases like Redis moving from BSD to BSL. Flag license changes as 🔴 CRITICAL (legal implications for commercial use).

## v0.6.0 — Smarter AI

- [ ] **Version diff analytics** — `firsttoknow explain <package> --from 1.40 --to 1.41`. Parse changelogs, release notes, commit history. AI generates plain-English summary of what changed and why it matters to YOU.
- [ ] **Breaking change detection** — semver major bumps, changelog keyword scanning ("BREAKING", "deprecated", "removed"), migration guide extraction.

## v0.7.0 — More Sources

- [ ] **Discord as a source** — many OSS projects (LangChain, Vercel, etc.) post announcements on Discord first. Monitor public channels via Discord bot API.
- [ ] **Slack as a source** — same for Slack-first communities. Public Slack workspace RSS/webhook integration.

## v0.8.0 — Push & Scheduled

- [ ] **Scheduled briefings** — `firsttoknow schedule daily 9am` runs briefings automatically via cron/daemon.
- [ ] **Slack/Discord webhook push** — send briefings to a channel when critical updates are detected.
- [ ] **Email alerts** — optional email notifications for 🔴 CRITICAL items.
- [ ] **GitHub Actions workflow** — run FirstToKnow as a scheduled GitHub Action, post results as PR comments or Slack messages.

---

## Ideas (not yet planned)

- [ ] Web dashboard (FastAPI + HTMX?)
- [ ] `pip install firsttoknow` — publish to PyPI
- [ ] Team mode — shared tracking across a team
- [ ] Content ideas generator — blog/LinkedIn post suggestions based on trends
- [ ] RSS/Atom feed output
- [ ] JSON/Markdown export for briefings
