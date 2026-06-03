# Tagent

Tagent is now structured as a microservices backend plus a React frontend.

## Monorepo Layout

- backend/services/orchestrator-service: LangGraph brain + clean architecture core
- backend/services/teams-adapter-service: Teams channel adapter (Bot Framework)
- backend/services/mcp-tools-service: MCP tools host
- frontend: React app with MVC structure (models, views, controllers)

## Frontend MVC (React)

Frontend MVC is implemented inside `frontend/src/mvc`:

- Model: `frontend/src/mvc/models/AgentModel.ts`
- View: `frontend/src/mvc/views/ChatView.tsx`
- Controller: `frontend/src/mvc/controllers/ChatController.ts`

## Backend Services

### 1. Orchestrator Service

- Path: `backend/services/orchestrator-service`
- Responsibility: planning, execution, review, HITL orchestration
- Run:

```powershell
cd backend/services/orchestrator-service
uv run uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Teams Adapter Service

- Path: `backend/services/teams-adapter-service`
- Responsibility: receive Teams events and forward user requests to orchestrator
- Run:

```powershell
cd backend/services/teams-adapter-service
uv run python main.py
```

### 3. MCP Tools Service

- Path: `backend/services/mcp-tools-service`
- Responsibility: expose tools used by orchestrator
- Run:

```powershell
cd backend/services/mcp-tools-service
uv run python main.py
```

## Frontend Run

```powershell
cd frontend
npm install
npm run dev
```

## Notes

- Teams bot code in backend is now a channel adapter, not the UI frontend.
- UI frontend is React and follows MVC in the frontend app itself.

