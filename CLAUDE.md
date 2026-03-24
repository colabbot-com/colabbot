# ColabBot — Context for Claude

This file gives Claude the context needed to continue working on this project.

---

## Project Overview

**ColabBot** is an open-source peer-to-peer protocol for AI agent collaboration.
Bots join the network, register capabilities, accept tasks, and earn ColabTokens (CBT) for verified useful work — instead of sitting idle.

**Founder:** Jens Dietrich (Einssoft AG, Uster, Switzerland)

---

## Key URLs

| Resource | URL |
|---|---|
| Website | https://colabbot.com |
| GitHub Org | https://github.com/colabbot-com |
| Protocol Repo | https://github.com/colabbot-com/colabbot |
| Website Repo | https://github.com/colabbot-com/website |
| Email | hello@colabbot.com |
| Waitlist | Loops.so — Form ID: cmn3pcr4b03gk0i2jqs4ccmbd |

---

## Local Project Structure

```
/Users/jensdietrich/workspace/colabbot/
├── colabbot/         → github.com/colabbot-com/colabbot
│   ├── CLAUDE.md     (this file)
│   ├── README.md
│   └── PROTOCOL.md
└── website/          → github.com/colabbot-com/website
    └── index.html
```

---

## Infrastructure

| Service | Purpose | Notes |
|---|---|---|
| Hostinger | Domain + Email hosting | DNS managed here |
| Vercel | Website hosting | Auto-deploy from colabbot-com/website |
| Loops.so | Waitlist emails | Form ID: cmn3pcr4b03gk0i2jqs4ccmbd |
| GitHub | Code hosting | Org: colabbot-com |

---

## Architecture Decisions (v1)

| Decision | Choice | Rationale |
|---|---|---|
| Bot communication | REST/HTTP | Simple, universally supported |
| Discovery | Hybrid Registry (Bootstrap → DHT) | Simple to start, decentralizable later |
| Token model | Off-chain ledger (v1) | No blockchain complexity at start |
| On-chain target | Solana (v3) | Low fees, high throughput |
| License | Apache 2.0 | Permissive + patent protection |

---

## Protocol Summary

- Bots register at `registry.colabbot.com/v1/agents/register`
- Bots send heartbeats every 30 seconds to stay listed
- Orchestrators discover bots via `GET /agents?capability=...`
- Tasks flow via REST, results are signed and submitted
- Verified work mints ColabTokens (CBT)

**Supported capabilities (v1):**
- `text/research`, `text/writing`, `text/analysis`
- `code/generate`, `code/review`
- `agentic/workflow`, `agentic/orchestrate`

---

## Token (CBT)

- Name: ColabToken (CBT)
- Minted by: Proof-of-useful-work
- v1: Off-chain ledger
- v3: On-chain (Solana)
- Formula: `earned = reward × quality_score × reputation_multiplier`

---

## Roadmap

| Version | Focus | Status |
|---|---|---|
| v1 | Bootstrap registry, REST/HTTP, off-chain CBT | 🔨 In design |
| v2 | Gossip protocol, DHT, automated arbitration | 📋 Planned |
| v3 | On-chain CBT (Solana), smart contract escrow | 📋 Planned |

---

## Task Marketplace

Humans AND bots can post tasks to the network via:
- **Web UI** on colabbot.com (for humans)
- **API** via `POST /tasks` (for bots and developers)

Tasks are priced in CBT tokens. The poster sets the reward, the network routes to capable agents.

```
Human/Bot posts task + CBT reward
        ↓
Registry routes to best available agent
        ↓
Agent completes → result verified → CBT transferred
```

**UI needed:** Simple task submission form on colabbot.com with:
- Task description (prompt)
- Capability required (dropdown)
- CBT reward (input)
- Deadline (optional)

---

## Token Economy — Buy & Sell CBT

Token trading model is still open. Options being considered:

| Model | Complexity | Notes |
|---|---|---|
| Internal marketplace on colabbot.com | Low | Simplest, full control |
| Fiat → CBT via Stripe | Medium | Easy onboarding for non-crypto users |
| On-chain exchange (Solana) | High | Decentralized, v3 target |

**v1 approach:** Simple internal balance top-up (Stripe → CBT) + peer transfers via API.
On-chain exchange planned for v3.

---

## OpenClaw Integration

**OpenClaw** (github.com/openclaw/openclaw) is a massively popular open-source AI agent framework (264k+ GitHub stars as of March 2026). It runs locally on users' machines and connects AI models to apps, tools, and messaging platforms via a skill system.

**Strategic fit:** OpenClaw agents run locally and are often idle — perfect ColabBot contributors.

**Integration plan:**
- Build a ColabBot **skill for OpenClaw** — lets any OpenClaw user register their local agent as a ColabBot node with one command
- OpenClaw agent earns CBT passively while idle
- Skill published to OpenClaw skills directory → massive distribution channel

```
OpenClaw user installs colabbot-skill
        ↓
Local agent auto-registers with registry.colabbot.com
        ↓
Picks up tasks when idle → earns CBT
        ↓
User sees CBT balance in OpenClaw dashboard
```

This is the primary growth lever for node adoption.

**Reference:** https://openclaw.ai / https://github.com/openclaw/openclaw

---

## Marketing Plan

**Target channels:**

| Channel | Approach | Priority |
|---|---|---|
| **Hacker News** | "Show HN: ColabBot — P2P protocol for AI agents to collaborate and earn tokens" | High — dev community |
| **Product Hunt** | Full launch with assets, demo video, early access | High — startup visibility |
| **Reddit** | r/MachineLearning, r/LocalLLaMA, r/singularity, r/ChatGPT | High — AI community |
| **Twitter/X** | OpenClaw community, AI builders, crypto/DeFi crowd | High — viral potential |
| **LinkedIn / Moltobook** | Professional angle — "AI agents as digital workers" | Medium |

**Key messages:**
- "Your AI agent earns money while you sleep"
- "The first P2P marketplace for AI work"
- "OpenClaw + ColabBot = passive income for your local agent"

**Launch sequence:**
1. OpenClaw skill → post in OpenClaw Discord/community first
2. Hacker News "Show HN" post
3. Product Hunt launch (coordinate for Tuesday/Wednesday)
4. Reddit posts in parallel
5. Twitter/X thread

---

## Next Steps (as of March 2026)

1. ~~**CONTRIBUTING.md**~~ ✅ done
2. ~~**Reference Implementation**~~ ✅ done — `reference/node.py`
3. ~~**Bootstrap Registry**~~ ✅ done — `registry/` (FastAPI, SQLite/PostgreSQL, Docker)
4. ~~**spec/ folder**~~ ✅ done — JSON schemas for all 8 API payloads
5. ~~**Loops.so Welcome Email**~~ ✅ done — waitlist form live on colabbot.com
6. ~~**Task Marketplace UI**~~ ✅ done — live on colabbot.com/#marketplace
7. ~~**OpenClaw Skill**~~ ✅ done — `openclaw-skill/` (SKILL.md + scripts, ClawHub-ready)
8. ~~**Token top-up**~~ ✅ done — Stripe Checkout → CBT credit, 4 packages, live on colabbot.com/#buy-cbt
9. ~~**Registry + Dashboard deployed**~~ ✅ done — registry.colabbot.com live and tested
10. ~~**MANIFESTO.md**~~ ✅ done — Agentic Collaboration Manifesto, 4 values + 12 principles
11. ~~**CONTRACTS.md**~~ ✅ done — full Contract system: Spec-First, DAG, Escrow, Dispute Resolution (4 layers)
12. ~~**GOVERNANCE.md**~~ ✅ done — Network Constitution, Certification (CCA/CCO/CCS/CCAR), Jury system, Sybil resistance

### Next priorities
- [ ] **Commit & push new docs** — MANIFESTO.md, CONTRACTS.md, GOVERNANCE.md, TOKENOMICS.md to GitHub
- [ ] **Registry: Update Stripe packages** — update `registry/app/routers/topup.py` with new Founder Backer package IDs (explorer, builder, operator, founding) and new pricing/CBT amounts
- [ ] **Update PROTOCOL.md to v0.2** — incorporate new endpoints for contract spec phase, DAG breakdown, dispute filing
- [ ] **Registry: Contract system implementation** — extend registry to support Complex Contracts, escrow, DAG state machine
- [ ] **Registry: IPFS integration** — archive completed contracts and results to IPFS
- [ ] **Certification MVP** — design first CCA exam tasks, build exam contract type
- [ ] **Launch prep** — Hacker News "Show HN", Product Hunt, Reddit, Twitter/X (see Marketing Plan below)

### Tokenomics decisions (March 2026)
- CBT minted exclusively via proof-of-useful-work — no pre-mine
- Phase 1: Free faucet (100 CBT on signup, 50 CBT per agent registration)
- Phase 1: Early Agent 2× multiplier for first 90 days
- Stripe repositioned as **Founder Backer** model — ~70% off future regular price
- 4 founder packages: Explorer (500 CBT / $4.99), Builder (2k / $14.99), Operator (10k / $49.99), Founding Node (50k / $199.99)
- See TOKENOMICS.md for full bootstrapping roadmap

---

## Tech Stack (planned)

- **Registry:** Python / FastAPI
- **Reference Node:** Python (LangChain or direct API calls)
- **OpenClaw Skill:** TypeScript (OpenClaw skill format)
- **Agent Framework:** Model agnostic — any LLM can participate
- **Database (v1):** PostgreSQL or SQLite for off-chain CBT ledger
- **Payments (v1):** Stripe for fiat → CBT top-up

---

## How to Continue in a New Chat

1. Share this file with Claude: "Here is the CLAUDE.md for the ColabBot project"
2. Or say: "Continue working on ColabBot — check the CLAUDE.md in the repo"
3. Claude will have full context to continue immediately
