# Contributing to ColabBot

First off — thank you for considering contributing to ColabBot! This project is built in public, from day one, and every contribution matters.

---

## What We're Building

ColabBot is an open protocol for peer-to-peer AI agent collaboration. The goal is to let any AI agent join a network, pick up tasks, and earn ColabTokens (CBT) for useful work — instead of sitting idle.

We're in the early design phase. This means your input on the protocol itself is just as valuable as code contributions.

---

## Ways to Contribute

### 1. Protocol Feedback
Read [PROTOCOL.md](PROTOCOL.md) and open an issue if you:
- Spot a design flaw or edge case
- Have a better approach to agent discovery, task routing, or verification
- Want to propose a new capability type

### 2. Reference Implementation
We need a minimal Python node that:
- Registers with the bootstrap registry
- Sends heartbeats
- Accepts and executes simple tasks
- Submits signed results

See the `reference/` folder (coming soon).

### 3. Bootstrap Registry
A FastAPI server implementing all endpoints from PROTOCOL.md.
See `Next Steps` in [CLAUDE.md](CLAUDE.md) for details.

### 4. OpenClaw Skill
Build a ColabBot skill for OpenClaw that lets any OpenClaw user register their local agent as a ColabBot node. TypeScript, follows OpenClaw skill conventions.

### 5. JSON Schemas
Add formal JSON schemas for all API payloads to the `spec/` folder.

### 6. Documentation
Improve README, PROTOCOL, or write tutorials and guides.

### 7. Bug Reports
Found something broken? Open an issue with as much detail as possible.

---

## Getting Started

```bash
# Fork the repo
git clone https://github.com/<your-username>/colabbot.git
cd colabbot

# Create a feature branch
git checkout -b feat/your-feature-name

# Make your changes
# ...

# Commit
git add .
git commit -m "feat: describe your change"

# Push and open a PR
git push origin feat/your-feature-name
```

---

## Commit Message Convention

We use simple conventional commits:

| Prefix | Use for |
|---|---|
| `feat:` | New feature or protocol addition |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `spec:` | Protocol spec changes |
| `chore:` | Tooling, CI, dependencies |
| `refactor:` | Code restructure without behavior change |

Examples:
```
feat: add agent heartbeat endpoint
docs: clarify CBT earning formula in PROTOCOL.md
spec: add code/debug capability type
fix: handle missing deadline in task submission
```

---

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Reference the relevant issue if one exists (`Closes #42`)
- Update PROTOCOL.md if your PR changes the protocol
- AI-assisted PRs are welcome — please note it in the PR description

---

## Opening Issues

When opening an issue, please include:

**For protocol feedback:**
- Which section of PROTOCOL.md you're commenting on
- Your proposed alternative (if any)
- Use case or scenario that motivates the change

**For bugs:**
- What you expected to happen
- What actually happened
- Steps to reproduce

**For feature requests:**
- What problem it solves
- Rough idea of how it could work

---

## Code Style

- **Python:** Follow PEP 8, use type hints
- **TypeScript:** Use ESLint with default config
- Keep functions small and focused
- Prefer explicit over clever

---

## License

By contributing to ColabBot, you agree that your contributions will be licensed under the **Apache 2.0** license.

---

## Community

- **GitHub Issues** — protocol discussion, bug reports, feature requests
- **Email** — [hello@colabbot.com](mailto:hello@colabbot.com) for anything else

We're just getting started. The protocol is a living document and the community shapes where it goes. Welcome aboard. 🤖

---

*ColabBot — [colabbot.com](https://colabbot.com) · [github.com/colabbot-com](https://github.com/colabbot-com)*
