# Tagent Architecture (Updated)

## Direction Applied

This project now follows the requested split:

- Backend: microservices
- Frontend: React with MVC
- Human-in-the-loop: handled in orchestrator workflow

## High-Level Architecture

```text
React Frontend (MVC)
  -> calls -> Orchestrator Service (FastAPI + LangGraph)
                -> calls -> MCP Tools Service
                -> calls -> Graph/Jira/etc adapters

Teams Adapter Service (Bot Framework)
  -> also calls -> Orchestrator Service
```

## Service Boundaries

### Orchestrator Service

Path: `backend/services/orchestrator-service`

Contains:
- `src/tagent/agents`: LangGraph orchestration nodes/graph/state
- `src/tagent/application`: use cases and app services
- `src/tagent/domain`: entities, value objects, ports
- `src/tagent/infrastructure`: adapter implementations
- `main.py`: HTTP API (`/health`, `/orchestrate`)

### Teams Adapter Service

Path: `backend/services/teams-adapter-service`

Contains:
- `src/tagent/bot`: Teams adapter, controllers, card views
- `main.py`: bot web server entrypoint

Important:
- This service no longer owns orchestration logic.
- It forwards user message payloads to orchestrator over HTTP.

### MCP Tools Service

Path: `backend/services/mcp-tools-service`

Contains:
- `src/tagent/mcp`: MCP server and tools
- `main.py`: runs MCP stdio server

## Frontend MVC

Path: `frontend`

MVC split:
- Model: `frontend/src/mvc/models/AgentModel.ts`
- View: `frontend/src/mvc/views/ChatView.tsx`
- Controller: `frontend/src/mvc/controllers/ChatController.ts`

The React controller sends messages to orchestrator and updates model state.
The view reads from model and renders chat + status.

## Human in the Loop

- Reviewer node determines approval requirement.
- Orchestrator response includes approval metadata.
- Channel-specific UX (Teams card or web UI) can ask for user confirmation.

## Next Build Steps

1. Add orchestrator endpoint to resume paused workflows after approval.
2. Add persistent checkpoint store (PostgreSQL/Redis).
3. Move mcp package ownership fully to mcp-tools-service and consume over transport.
4. Add API gateway and auth between frontend/teams adapter/orchestrator.

