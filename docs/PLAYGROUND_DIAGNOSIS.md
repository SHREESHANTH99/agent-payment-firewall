# Judge Playground: Full Diagnosis Report

This document records the exact read-only diagnosis of the deployed sandbox Judge Playground (`https://payment-firewall-dashboard.onrender.com/playground`) and maps the concrete findings to our follow-up tasks.

---

## 1. Registered `/demo` Backend Routes

All `/demo` routes are registered in [`backend/app/api/demo.py`](../backend/app/api/demo.py) and mounted onto the FastAPI application in [`backend/app/main.py`](../backend/app/main.py#L265) via `register_demo(app)`:
- `DEMO_ENABLED` gate: Checked at runtime by `_ensure_enabled()`. When `DEMO_ENABLED` is false (or `0`), all routes raise HTTP `404` (`demo_disabled`).

| Method | Path | Request Model | Response Model / Shape | Auth |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/demo/sessions` | `CreateSessionRequest` (`display_name`, `scenario`) | `{"session": Session, "session_secret": str}` | Public |
| `GET` | `/demo/sessions/{id}/state` | None | `{"session": Session}` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `PATCH` | `/demo/sessions/{id}/config` | `DemoConfigPatch` (`canary_enabled`, `judge_enabled`, limits) | `{"config": DemoConfig}` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `POST` | `/demo/sessions/{id}/intents` | `IntentRequest` (`agent`, `amount`, `currency`, `merchant`, `target_mandate`, etc.) | `IntentResult` (`intent_id`, `decision`, `status`, `reasons`, `risk`, `operatorView`) | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `GET` | `/demo/sessions/{id}/escalations` | None | `{"items": List[EscalationView]}` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `POST` | `/demo/sessions/{id}/escalations/{id}/approve` | None | `IntentResult` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `POST` | `/demo/sessions/{id}/escalations/{id}/reject` | `RejectRequest` (`reason`) | `IntentResult` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `POST` | `/demo/sessions/{id}/mandates/{id}/freeze` | None | `{"mandate": MandateView}` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `POST` | `/demo/sessions/{id}/mandates/{id}/unfreeze` | None | `{"mandate": MandateView}` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `GET` | `/demo/attacks` | None | `{"items": List[AttackPreset]}` | Public |
| `POST` | `/demo/sessions/{id}/agent-runs` | `AgentRunRequest` (`task`, `variant`, `custom_page_text`, `agent`) | `{"run_id": str, "status": "running", "dry_run": true, "events_url": str}` | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `GET` | `/demo/sessions/{id}/agent-runs/{id}/events`| None | SSE stream `text/event-stream` (`AgentRunEvent`) | `X-Demo-Session-Id`, `X-Demo-Session-Secret` |
| `GET` | `/demo/sessions/{id}/store/catalog` | None | HTML custom catalog | Public session scoped |
| `GET` | `/demo/recorded-runs` | None | `{"items": List[RecordedRun]}` | Public |

Missing route required by specification:
- `GET /demo/health`: Returns `{ "enabled": bool, "quota_remaining": int, "version": str }` (or `503` when disabled).

---

## 2. Dashboard Call Audit & Contract Mismatches

Comparison between `dashboard/src/lib/demoClient.ts`, `docs/demo-api.md`, and `backend/app/api/demo.py`:

| Operation | Dashboard Call | Backend Expected | Mismatch & Status |
| :--- | :--- | :--- | :--- |
| **Create Session** | `POST /demo/sessions` with `{scenario}` | `CreateSessionRequest(scenario)` | Match |
| **Get State** | `GET /demo/sessions/{id}/state` | Headers `X-Demo-Session-Id`, `X-Demo-Session-Secret` | Match |
| **Update Config** | `PATCH /demo/sessions/{id}/config` | `DemoConfigPatch` | Match |
| **Submit Intent** | `POST /demo/sessions/{id}/intents` | `IntentRequest` (`agent`, `amount`, `currency`, `merchant`, `target_mandate`) | Previously mismatched (`agent_id`, `mandate_id` sent instead of `agent`). Now normalized in `demoClient.ts`. |
| **Agent Run** | `POST /demo/sessions/{id}/agent-runs` | `AgentRunRequest` (`task`, `variant`, `custom_page_text`, `agent`) | Previously mismatched (`user_task`, `attack_id` sent instead of `task`, `variant`). Now normalized. |
| **Agent Events** | `GET /demo/.../agent-runs/{id}/events` | SSE chunks `data: {...}` | Match |
| **Escalations** | `POST /demo/.../escalations/{id}/approve` | Empty body, 200 OK with `IntentResult` | Match |
| **Escalations** | `POST /demo/.../escalations/{id}/reject` | Body `{ "reason": str }`, 200 OK | Match |
| **Freeze / Unfreeze** | `POST /demo/.../mandates/{agent_id}/freeze` | 200 OK with `{"mandate": MandateView}` | Match |

---

## 3. Why Failures Were Silent

1. **Unconfigured Cloud LLM Provider (HTTP 429 `demo_quota`)**:
   - In the deployed production backend on Render, when `canary_enabled=true` and `judge_enabled=true`, the pipeline runs LLM canary/judge checks. Because no external LLM key is set in production, the LLM call triggers fail-closed error handling (`_llm_failed`), which raises:
     ```json
     HTTP 429: {"code": "demo_quota", "message": "The demo risk provider is unavailable", "fallback": true}
     ```
   - In earlier versions of `useJudgePlayground.ts`, any error in `submit()` fell into a generic `fallback(error)` without setting an active result or informing the user, leaving the UI completely static with buttons disabled.
2. **Missing `demo` Python package in Backend Docker Container**:
   - The backend `Dockerfile` only copies `./backend` into `/app`. When `start_agent_run` was called on Render, Python threw `ImportError: No module named 'demo'` when executing `from demo.agent.loop import ...`. The backend emitted a 3-event stream with a fallback notice and finished without executing live tool calls.
3. **Hard-disabled buttons in recorded mode**:
   - Buttons had `disabled={!session || mode === 'RECORDED'}`, which blocked user interaction without any visual error prompt explaining why.

---

## 4. API Base URL and Proxy Configuration

1. **Dashboard Origin vs API Origin**:
   - Dashboard: `https://payment-firewall-dashboard.onrender.com`
   - Backend API: `https://payment-firewall-api.onrender.com`
   - The dashboard calls the API directly using `NEXT_PUBLIC_API_URL` (with fallback to `https://payment-firewall-api.onrender.com`).
2. **CORS Headers**:
   - CORS is configured in `backend/app/main.py` allowing `DASHBOARD_ORIGIN` with `allow_headers=["*"]`. Browser preflight `OPTIONS` requests now succeed with `200 OK`.
3. **Streaming & POST Bodies**:
   - Direct requests to `payment-firewall-api.onrender.com` support `POST` JSON bodies and `text/event-stream` without intermediate proxy truncation.

---

## 5. Hard-Coded Snippets

In [`dashboard/src/lib/demoClient.ts`](../dashboard/src/lib/demoClient.ts#L195), `generateApiSnippets`:
- **Current Issue**: The cURL and Python code snippets previously used hard-coded values:
  - `agent_id: "A"`
  - `mandate_id: "mnd-demo-a"`
  - `idempotency_key: "playground-001"`
- **Required Fix**: Dynamic snippet generation that accepts the active session's real session ID, real active agent, real mandate ID, and dynamically masks the `X-Demo-Session-Secret` with a reveal/copy toggle.

---

## 6. Cause of "NOT RECORDED" and "WAITING"

In [`dashboard/src/app/playground/page.tsx`](../dashboard/src/app/playground/page.tsx#L64), `CheckpointStrip` displays 6 pipeline checkpoints:
- **`Idempotency`**: Hardcoded to `'NOT RECORDED'`.
- **`Canary scan`**: Displays `'NOT RECORDED'` until an intent result contains `result.risk.canary`.
- **`Risk judge`**: Displays `'NOT RECORDED'` until `result.risk.judge` is present.
- **`Mandate & rules`**, **`Atomic budget`**, **`Decision & payout`**: Displays `'WAITING'` before an intent is submitted.
- **Required Fix**: Rename `'NOT RECORDED'` to `"Not reached (stopped earlier)"` or `"Disabled"`, and `'WAITING'` to `"Not run yet"`.

---

## 7. Prioritized Implementation Plan

1. **Task 2: Fix Navigation Loop**:
   - Landing page CTA: "Try the Playground" (`/playground`), "View sample console" (`/console?demo=1`).
   - Console Login: "Explore the sample console" links directly to `/console?demo=1`.
   - Playground header: "Home" (`/`) and "Sample console" (`/console?demo=1`). Remove "Operator Console".
   - Persist demo flag in `sessionStorage` and prevent auth guard redirect when active.
2. **Task 3: OpenAPI Contract Alignment**:
   - Add `GET /demo/health`.
   - Export schema to `docs/openapi-demo.json` and generate TypeScript client types.
   - Comprehensive ASGI contract test suite.
3. **Task 4: Core Actions Wiring**:
   - Dynamic snippets, full error toast/announcement, pipeline animated replay, and escalation approve/reject.
4. **Task 5: Live Agent Tab & Recorded Fallback**:
   - Stream timeline with clean fallback playback from `/data/recorded_runs.json`.
5. **Task 6: UI Polish & Cold Start**:
   - Minimum text 13px, responsive 360px layout, cold start waking indicator.
6. **Task 7: Automated Tests & QA Checklist**:
   - Full Playwright & Vitest suite plus `docs/PLAYGROUND_QA.md`.
7. **Task 8: Security Audit**:
   - Complete verification of demo isolation and dry-run boundaries.
