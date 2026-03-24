# ColabBot — API Payload Schemas

JSON Schema (Draft 2020-12) definitions for all ColabBot v1 REST API payloads.

| Schema file | Endpoint | Direction |
|---|---|---|
| [agent-register-request.json](agent-register-request.json) | `POST /agents/register` | Client → Registry |
| [agent-register-response.json](agent-register-response.json) | `POST /agents/register` | Registry → Client |
| [heartbeat-request.json](heartbeat-request.json) | `POST /agents/{agent_id}/heartbeat` | Agent → Registry |
| [agent-list-response.json](agent-list-response.json) | `GET /agents` | Registry → Client |
| [task-submit-request.json](task-submit-request.json) | `POST /tasks` | Orchestrator → Registry |
| [task-submit-response.json](task-submit-response.json) | `POST /tasks` | Registry → Orchestrator |
| [task-result-request.json](task-result-request.json) | `POST /tasks/{task_id}/result` | Agent → Registry |
| [task-verify-request.json](task-verify-request.json) | `POST /tasks/{task_id}/verify` | Orchestrator → Registry |

See [PROTOCOL.md](../PROTOCOL.md) for the full protocol specification.
