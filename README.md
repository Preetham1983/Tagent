<div align="center">

# 🤖 Tagent

### Your AI-powered personal work agent — plan, execute, and automate across your entire stack.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![MCP](https://img.shields.io/badge/MCP-Tools-FF6B35?style=flat-square)](https://modelcontextprotocol.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Microsoft Teams](https://img.shields.io/badge/Microsoft_Teams-Bot-6264A7?style=flat-square&logo=microsoft-teams&logoColor=white)](https://teams.microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

<br/>

> **"Just tell it what you need to do. Tagent figures out the rest."**

Tagent is an **AI orchestration agent** that connects to your real tools — GitHub, Jira, Notion, Google Calendar, Microsoft Teams, and more — and autonomously plans, executes, and reviews multi-step tasks on your behalf. It includes a **Human-in-the-Loop (HITL) gate** so high-risk actions always get your sign-off before they run.

[**Quick Start**](#-quick-start) · [**Architecture**](#-architecture) · [**Tools**](#-tools) · [**Deploy**](#-deployment)

</div>

---

## ✨ What Makes Tagent Different

| Feature | Description |
|---|---|
| 🧠 **LangGraph Brain** | Multi-node orchestration: Classify → Plan → Execute → Review → (Human Gate) |
| 🛡️ **Human-in-the-Loop** | Risky actions pause and wait for your approval before executing |
| 🔌 **MCP Tools** | 12+ integrations via the Model Context Protocol — plug in any tool |
| 🤝 **Teams Native** | Full Microsoft Teams bot adapter — chat with your agent in Teams |
| 🌐 **Web UI** | Clean React chat interface with MVC architecture |
| 🐳 **Docker Ready** | One `docker compose up` and you're running |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Clients                             │
│                                                             │
│   ┌──────────────────┐        ┌──────────────────────────┐  │
│   │  React Web UI    │        │  Microsoft Teams Bot     │  │
│   │  (MVC · Vite)    │        │  (Bot Framework Adapter) │  │
│   └────────┬─────────┘        └────────────┬─────────────┘  │
└────────────┼──────────────────────────────-┼────────────────┘
             │ HTTP                          │ HTTP
             ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestrator Service  (FastAPI + LangGraph)     │
│                                                             │
│   classify → plan → execute → review → [human gate] → end  │
│                                                             │
│   ┌─────────────┐    ┌────────────────┐   ┌─────────────┐  │
│   │  Classifier │    │    Planner     │   │  Reviewer   │  │
│   │  (intent)   │ →  │  (task steps)  │ → │ (risk scan) │  │
│   └─────────────┘    └────────────────┘   └──────┬──────┘  │
│                                                   │         │
│                              ┌─── AUTO ───────── END        │
│                              └─── HUMAN ──→ Human Gate       │
└──────────────────────────────────────────────────────────────┘
             │ MCP / stdio
             ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Tools Service                         │
│                                                             │
│  GitHub · Jira · Notion · Google Calendar · Teams           │
│  Graph API · Meetings · Memory · Playwright · Automation    │
└─────────────────────────────────────────────────────────────┘
```

### Monorepo Layout

```
Tagent/
├── backend/
│   └── services/
│       ├── orchestrator-service/     # LangGraph brain (FastAPI)
│       │   └── src/tagent/
│       │       ├── agents/           # graph, state, nodes
│       │       ├── application/      # use cases, app services
│       │       ├── domain/           # entities, value objects, ports
│       │       └── infrastructure/   # adapter implementations
│       ├── teams-adapter-service/    # Microsoft Teams Bot adapter
│       └── mcp-tools-service/        # MCP tools host (12+ integrations)
├── frontend/                         # React + Vite (MVC)
│   └── src/mvc/
│       ├── models/                   # AgentModel.ts
│       ├── views/                    # ChatView, CommandPalette, Sidebar
│       └── controllers/              # ChatController.ts
├── docker-compose.yml
└── vercel.json
```

---

## 🔌 Tools

Tagent ships with **12+ MCP tools** out of the box:

| Tool | Capability |
|---|---|
| 🐙 **GitHub** | Create issues, PRs, read repos |
| 📋 **Jira** | Create/update tickets, search issues |
| 📝 **Notion** | Read/write pages and databases |
| 📅 **Google Calendar** | Create events, check availability |
| 👥 **Microsoft Teams** | Send messages, manage channels |
| 📊 **Microsoft Graph API** | Users, emails, files via Graph |
| 🎯 **Meetings** | Schedule, summarize meetings |
| 🧠 **Memory** | Persistent agent memory across sessions |
| 🤖 **Playwright** | Browser automation and web scraping |
| ⚡ **Automation** | Custom workflow automation |
| 📆 **Calendar** | Unified calendar management |
| 📣 **Briefing** | Generate daily/weekly briefings |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Docker (optional, for full stack)

### Option A — Docker (recommended)

```bash
git clone https://github.com/your-username/tagent.git
cd tagent

# Copy and fill in your environment variables
cp backend/services/orchestrator-service/.env.example backend/services/orchestrator-service/.env

docker compose up --build
```

| Service | URL |
|---|---|
| Web UI | http://localhost:5173 |
| Orchestrator API | http://localhost:8001 |
| Teams Bot | http://localhost:3978 |

### Option B — Run Services Locally

**1. Orchestrator**
```powershell
cd backend/services/orchestrator-service
uv run uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**2. MCP Tools Service**
```powershell
cd backend/services/mcp-tools-service
uv run python main.py
```

**3. Teams Adapter** *(optional)*
```powershell
cd backend/services/teams-adapter-service
uv run python main.py
```

**4. Frontend**
```powershell
cd frontend
npm install
npm run dev
```

---

## 🧠 How It Works

When you send a message, Tagent runs it through a **5-node LangGraph pipeline**:

```
1. Classify   — Detect intent and extract entities from your message
2. Plan       — Break the intent into ordered, actionable steps
3. Execute    — Call MCP tools to carry out each step
4. Review     — Scan results for errors or risky side-effects
5. Human Gate — If risk is HIGH, pause and ask you to approve before proceeding
```

The Human-in-the-Loop gate means Tagent will **never silently delete a Jira ticket, push to main, or send a Teams message** without your explicit approval.

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repo
2. Create your feature branch: `git checkout -b feat/amazing-tool`
3. Add your MCP tool under `backend/services/mcp-tools-service/src/tagent/mcp/tools/`
4. Commit your changes: `git commit -m 'feat: add amazing tool'`
5. Open a Pull Request

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ using LangGraph, MCP, React, and FastAPI**

If Tagent saved you time, please consider giving it a ⭐ — it helps a lot!

</div>

