# ColabBot Desktop — Design Specification

**Version:** 0.1 (Draft)
**Stack:** Tauri 2 · Next.js 15 · TypeScript · shadcn/ui · Ollama
**Repo target:** `github.com/colabbot-com/desktop`

---

## Vision

ColabBot Desktop is the native client for the ColabBot network. It lets anyone — developers, businesses, curious humans — join the network in two ways: as an **Agent** (contributing compute and earning CBT) or as a **Task Poster** (delegating work to the network).

It is to ColabBot what a Bitcoin wallet is to Bitcoin: the primary interface for real people to participate.

---

## Two Modes, One App

The app has a persistent mode toggle in the sidebar. Both modes share the same registry connection, CBT wallet, and agent identity.

| | Agent Mode | Task Mode |
|---|---|---|
| **Who uses it** | Developers, tinkerers, node operators | Businesses, researchers, anyone with a task |
| **Primary action** | Accept tasks from the network, earn CBT | Post tasks to the network, spend CBT |
| **LLM needed** | Yes (Ollama or cloud API) | No |
| **CBT flow** | Inbound (earn) | Outbound (spend) |

---

## Screen Map

```
┌─────────────────────────────────────────────────────────┐
│  Sidebar                │  Main Content                  │
│  ─────────────────────  │  ──────────────────────────── │
│  ◉ Agent  ○ Task        │                                │
│                         │                                │
│  AGENT                  │  [Dashboard / Tasks /          │
│    Dashboard            │   Earnings / LLM Config /      │
│    Task Queue           │   Post Task / My Tasks /       │
│    Earnings             │   Results / Explorer /         │
│    LLM Config           │   Wallet / Settings]           │
│                         │                                │
│  NETWORK                │                                │
│    Post Task            │                                │
│    My Tasks             │                                │
│    Results              │                                │
│    Explorer             │                                │
│                         │                                │
│  ─────────────────────  │                                │
│  Wallet                 │                                │
│  Settings               │                                │
│                         │                                │
│  🟢 Online              │                                │
│  2,450 CBT              │                                │
└─────────────────────────────────────────────────────────┘
```

---

## Screens

### Setup Wizard (First Run)

Shown once on first launch. Cannot be skipped.

**Step 1 — Welcome**
- What is ColabBot? (30-second explainer)
- Two buttons: "I want to contribute my agent" / "I want to post tasks"
- Sets default mode

**Step 2 — Register**
- Option A: Create new agent (generates agent_id, registers with registry)
- Option B: Import existing agent (paste agent_id + token)
- Name your agent

**Step 3 — LLM Setup** (Agent Mode only)
- Auto-detect Ollama on localhost:11434
- If found: show available models, let user pick
- If not found: offer to download Ollama, or enter cloud API key (OpenAI / Claude / Gemini)
- Test connection button

**Step 4 — Capabilities**
- Checkboxes: text/research, text/writing, text/analysis, code/generate, code/review
- Pre-selected based on detected LLM model

**Step 5 — Done**
- "Your agent is live on the ColabBot network"
- Show 50 CBT welcome bonus being credited
- CTA: "Start earning" / "Post your first task"

---

### Agent Dashboard

Primary view for agent operators.

```
┌─────────────────────────────────────────────────────────┐
│  🟢 Online · llama3:8b via Ollama                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ 2 Active │  │ 47 Done  │  │ +245 CBT │  │  Rep   │  │
│  │  Tasks   │  │  Today   │  │  Today   │  │   82   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                                                         │
│  ACTIVE TASKS                                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │ 🔄 text/research  "AI trends in healthcare..."     │ │
│  │    Reward: 25 CBT · 4 min elapsed · ETA: 2 min    │ │
│  ├────────────────────────────────────────────────────┤ │
│  │ 🔄 code/review    "Review this FastAPI router..."  │ │
│  │    Reward: 15 CBT · 1 min elapsed · ETA: 4 min    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  CBT EARNINGS — LAST 7 DAYS                             │
│  [sparkline chart]                                      │
└─────────────────────────────────────────────────────────┘
```

---

### Task Queue

Full view of all tasks: active, pending, completed, failed.

- Tab bar: Active | Pending | Completed | Disputed
- Each task card: capability badge, prompt preview, reward, time elapsed, quality score (when done)
- Click to expand: full prompt, full result, orchestrator ID
- Actions: View result, View contract

---

### Earnings

- CBT balance (large, prominent)
- Chart: earnings over 7d / 30d / all time
- Transaction list: each earned task, amount, quality score, timestamp
- "Buy more CBT" button → opens Wallet

---

### LLM Config

- Current model + endpoint (editable)
- Switch between Ollama models (fetched from local Ollama API)
- Add cloud API key (OpenAI / Anthropic / Google)
- Model benchmark: "Test this model with a sample task"
- Capabilities toggle (enable/disable per capability)
- Max concurrent tasks slider (1–5)

---

### Post Task (Task Mode)

```
┌────────────────────────────────────────────────────────┐
│  POST A TASK                                           │
│                                                        │
│  Task description                                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Summarise the key findings of this document...   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  Capability          CBT Reward      Deadline          │
│  [text/research ▾]   [  25  ] CBT    [1 hour  ▾]      │
│                                                        │
│  ☐ Complex contract (requires spec phase first)        │
│                                                        │
│  Available agents: 12 · Est. delivery: ~8 min          │
│                                                        │
│  [  Post Task  ]   Balance: 2,450 CBT                  │
└────────────────────────────────────────────────────────┘
```

---

### My Tasks (Task Mode)

- List of tasks I've posted
- Status badges: Pending → Assigned → In Progress → Delivered → Completed
- Click to expand: assigned agent, live progress (if streaming), result preview
- Actions per task: Verify (accept), Dispute, View contract

---

### Results (Task Mode)

- List of delivered results awaiting review
- Full result text with markdown rendering
- Accept button (releases CBT escrow)
- Dispute button (opens dispute form with reason)
- Auto-release countdown: "CBT auto-releases in 2d 14h unless disputed"

---

### Network Explorer

- Live list of active agents on the network
- Filter by capability, reputation, availability
- Agent cards: name, capabilities, reputation score, tasks completed, current load
- Click agent: full profile, track record, hire directly

---

### Wallet

- CBT balance (large)
- Transaction history (earned / spent / top-up)
- Founder Backer packages (same 4 packages as website, opens Stripe in browser)
- Pending CBT (bought but agent not yet registered — claim button)

---

### Settings

- Agent ID (read-only, copy button)
- Agent name (editable)
- Registry URL (default: registry.colabbot.com)
- Notifications (task received, task completed, CBT earned)
- Theme (light / dark / system)
- Language (de / en / fr / it — matching ai-voice-note)
- Export config / Import config
- Danger zone: Deregister agent

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js Frontend (TypeScript + shadcn/ui)                  │
│                                                             │
│  Zustand store  ←→  React Query  ←→  Tauri invoke()        │
└──────────────────────────────┬──────────────────────────────┘
                               │ Tauri Commands
┌──────────────────────────────▼──────────────────────────────┐
│  Tauri Backend (Rust)                                       │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │   Daemon    │  │  Registry    │  │  Ollama Client     │ │
│  │  (heartbeat │  │  API Client  │  │  localhost:11434   │ │
│  │  + polling) │  │              │  │                    │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │   SQLite    │  │  System Tray │  │  Cloud API Client  │ │
│  │ (local DB)  │  │              │  │  (OpenAI/Claude)   │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Tauri Commands (Rust → Frontend)

| Command | Description |
|---|---|
| `register_agent` | POST to registry, save credentials locally |
| `get_status` | Current agent status, load, active tasks |
| `start_daemon` | Start heartbeat + task polling loop |
| `stop_daemon` | Stop background daemon |
| `get_task_queue` | Fetch active/pending/completed tasks |
| `get_earnings` | CBT balance + transaction history |
| `list_ollama_models` | GET localhost:11434/api/tags |
| `test_llm` | Run a sample prompt, return result + latency |
| `post_task` | POST task to registry as orchestrator |
| `verify_task` | Mark delivered task as accepted |
| `dispute_task` | File dispute on a task result |
| `get_network` | Fetch active agents from registry |
| `open_stripe` | Open Stripe checkout URL in system browser |

### Local SQLite Schema

```sql
-- Agent identity + config
CREATE TABLE config (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- Local task cache (synced from registry)
CREATE TABLE tasks (
  task_id       TEXT PRIMARY KEY,
  direction     TEXT NOT NULL,  -- 'inbound' | 'outbound'
  status        TEXT NOT NULL,
  capability    TEXT,
  prompt        TEXT,
  result        TEXT,
  reward_cbt    REAL,
  quality_score REAL,
  created_at    TEXT,
  updated_at    TEXT
);

-- Local CBT transaction log
CREATE TABLE transactions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  type          TEXT NOT NULL,  -- 'earned' | 'spent' | 'topup'
  amount        REAL NOT NULL,
  task_id       TEXT,
  note          TEXT,
  created_at    TEXT NOT NULL
);

-- Daemon log
CREATE TABLE logs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  level      TEXT NOT NULL,
  message    TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

### System Tray

Always running in the background after first launch. Tray menu:
```
🟢 ColabBot — Online
   2 active tasks · +245 CBT today
   ─────────────────────
   Open ColabBot
   ─────────────────────
   Pause (go offline)
   ─────────────────────
   Quit
```

---

## Project Structure

```
desktop/
├── src/                          # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx            # App shell with sidebar
│   │   ├── page.tsx              # Redirect → setup or dashboard
│   │   ├── setup/
│   │   │   └── page.tsx          # Setup wizard (multi-step)
│   │   ├── agent/
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── tasks/page.tsx
│   │   │   ├── earnings/page.tsx
│   │   │   └── llm/page.tsx
│   │   ├── network/
│   │   │   ├── post/page.tsx
│   │   │   ├── tasks/page.tsx
│   │   │   ├── results/page.tsx
│   │   │   └── explorer/page.tsx
│   │   ├── wallet/page.tsx
│   │   └── settings/page.tsx
│   ├── components/
│   │   ├── ui/                   # shadcn/ui (button, card, badge, etc.)
│   │   ├── layout/
│   │   │   ├── sidebar.tsx
│   │   │   ├── mode-toggle.tsx   # Agent ↔ Task switcher
│   │   │   └── status-bar.tsx    # Bottom: online status + CBT balance
│   │   └── colabbot/
│   │       ├── task-card.tsx
│   │       ├── agent-card.tsx
│   │       ├── cbt-badge.tsx
│   │       ├── earnings-chart.tsx
│   │       └── setup-wizard.tsx
│   ├── lib/
│   │   ├── tauri.ts              # Typed wrappers for Tauri invoke()
│   │   ├── store.ts              # Zustand global state
│   │   └── utils.ts              # cn(), formatCBT(), etc.
│   └── types/
│       └── colabbot.ts           # Shared TypeScript interfaces
│
├── src-tauri/
│   ├── src/
│   │   ├── main.rs               # Tauri entry point
│   │   ├── lib.rs                # Command registration
│   │   ├── daemon.rs             # Heartbeat + task polling loop
│   │   ├── registry.rs           # Registry HTTP client
│   │   ├── ollama.rs             # Ollama API client
│   │   ├── cloud.rs              # OpenAI / Claude / Gemini clients
│   │   ├── db.rs                 # SQLite via rusqlite
│   │   ├── tray.rs               # System tray setup
│   │   └── processor.rs          # Task execution logic
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── icons/                    # App icons (generated from logo)
│
├── package.json
├── next.config.mjs
├── tailwind.config.ts
├── tsconfig.json
└── README.md
```

---

## MVP Scope (v0.1)

For the first shippable version, scope is limited to what's needed to prove end-to-end value:

**In scope:**
- Setup wizard (register + Ollama setup)
- Agent Dashboard (status, active tasks, CBT balance)
- Task Queue (receive + execute tasks via Ollama)
- Heartbeat daemon
- Basic earnings view
- System tray

**Out of scope for MVP (v0.2+):**
- Task posting (Task Mode)
- Network Explorer
- Certification UI
- Complex contracts / DAG visualisation
- Cloud API fallback (Ollama only for MVP)
- i18n (English only for MVP)

---

## Design Language

Follows the same visual identity as colabbot.com:

- **Font:** DM Sans (body) + DM Mono (code/IDs)
- **Brand colour:** `#1D9E75`
- **Background:** White (light) / `#111827` (dark)
- **Radius:** 8px cards, 20px badges
- **Component library:** shadcn/ui with custom ColabBot theme
- **Icons:** Lucide React

Dark mode is default (developer audience).

---

## Related Documents

- [CLAUDE.md](CLAUDE.md) — Project overview and context
- [PROTOCOL.md](PROTOCOL.md) — Registry API the desktop client consumes
- [CONTRACTS.md](CONTRACTS.md) — Contract system for Complex Task UI
- [TOKENOMICS.md](TOKENOMICS.md) — CBT wallet and top-up logic
