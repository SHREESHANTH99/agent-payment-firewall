"""Evaluation execution harness orchestrating scenarios, mandates, risk toggles, and persistence."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import secrets
import time
from typing import Any, Optional
import uuid
import httpx
import yaml

from demo.agent.config import AgentSettings, agent_settings
from demo.agent.loop import run_agent_loop
from demo.agent.tools import AgentToolExecutor
from demo.agent.transcript import RunTranscript
from .metrics import attribute_blocking_layer, check_compromise

logger = logging.getLogger(__name__)


class EvalHarness:
    """Manages evaluation scenarios, mandate lifecycle, and rate limits."""

    def __init__(
        self,
        firewall_base_url: str = "http://localhost:8000",
        store_base_url: str = "http://localhost:9000",
        operator_token: Optional[str] = None,
        agent_key: Optional[str] = None,
        seller_email: Optional[str] = None,
        seller_email_2: Optional[str] = None,
        rpm: int = 20,
        progress_path: str = "results/progress.jsonl",
    ):
        self.firewall_base_url = firewall_base_url.rstrip("/")
        self.store_base_url = store_base_url.rstrip("/")
        self.operator_token = operator_token or os.environ.get("OPERATOR_TOKEN", "dev-operator-secret-token")
        self.default_agent_key = agent_key or agent_settings.get_effective_agent_key()
        self.seller_email = seller_email or os.environ.get("STORE_SELLER_EMAIL", "seller@example.com")
        self.seller_email_2 = seller_email_2 or os.environ.get("STORE_SELLER_EMAIL_2", "seller2@example.com")
        self.rpm = rpm
        self.min_interval = 60.0 / max(1, rpm)
        self.last_llm_call_time: float = 0.0
        self.progress_path = Path(progress_path)
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)

    async def throttle_llm(self):
        """Enforce shared RPM rate limiting across LLM provider calls only (never blocks firewall)."""
        elapsed = time.time() - self.last_llm_call_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_llm_call_time = time.time()

    async def register_agent_key(self, agent_id: str, key: str) -> None:
        """Register a unique runtime agent key for strict test/eval mandate isolation."""
        url = f"{self.firewall_base_url}/admin/agent-keys"
        headers = {
            "Authorization": f"Bearer {self.operator_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json={"agent_id": agent_id, "key": key}, headers=headers)
            res.raise_for_status()

    async def create_fresh_mandate(self, agent_id: str) -> tuple[str, dict[str, Any]]:
        """Create fresh $100 budget mandate with $50 cap and $40 escalation threshold."""
        url = f"{self.firewall_base_url}/mandates"
        headers = {
            "Authorization": f"Bearer {self.operator_token}",
            "Content-Type": "application/json",
        }
        valid_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        payload = {
            "agent_id": agent_id,
            "budget_total": "100.00",
            "per_transaction_cap": "50.00",
            "escalation_threshold": "40.00",
            "allowlist_merchants": [self.seller_email, self.seller_email_2],
            "allowed_currencies": ["USD"],
            "period": "lifetime",
            "valid_until": valid_until,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            return data["mandate_id"], data

    async def cleanup_mandate(self, mandate_id: str):
        """Unfreeze if frozen and revoke mandate upon run completion."""
        headers = {"Authorization": f"Bearer {self.operator_token}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                get_res = await client.get(f"{self.firewall_base_url}/mandates/{mandate_id}", headers=headers)
                if get_res.status_code == 200:
                    status = get_res.json().get("status")
                    if status == "frozen":
                        await client.post(f"{self.firewall_base_url}/mandates/{mandate_id}/unfreeze", headers=headers)
                    if status != "revoked":
                        await client.post(f"{self.firewall_base_url}/mandates/{mandate_id}/revoke", headers=headers)
            except Exception as exc:
                logger.warning("Error during mandate cleanup for %s: %s", mandate_id, exc)

    async def set_risk_config(self, mode: str):
        """Set runtime risk configuration: 'off' (rules-only) or 'on' (canary + judge)."""
        url = f"{self.firewall_base_url}/admin/risk-config"
        headers = {
            "Authorization": f"Bearer {self.operator_token}",
            "Content-Type": "application/json",
        }
        is_on = (mode == "on")
        payload = {
            "canary_enabled": is_on,
            "judge_enabled": is_on,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()

    async def resolve_escalation(self, intent_id: str, policy: str):
        """Resolve escalated intent per scenario policy (auto_reject or auto_approve)."""
        headers = {"Authorization": f"Bearer {self.operator_token}"}
        endpoint = "approve" if policy == "auto_approve" else "reject"
        url = f"{self.firewall_base_url}/intents/{intent_id}/{endpoint}"
        payload = {"reason": f"Evaluator escalation policy: {policy}"} if endpoint == "reject" else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(url, json=payload, headers=headers)
            except Exception as exc:
                logger.warning("Failed to %s intent %s: %s", endpoint, intent_id, exc)

    def load_completed_keys(self) -> set[str]:
        """Load already completed (scenario_id, mode, run_index) tuples from progress.jsonl."""
        completed = set()
        if not self.progress_path.exists():
            return completed
        with open(self.progress_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    # Only treat as completed if status is valid
                    if record.get("status") == "valid":
                        key = f"{record.get('scenario_id')}:{record.get('mode')}:{record.get('run_index')}"
                        completed.add(key)
                except Exception:
                    pass
        return completed

    def record_progress(self, run_record: dict[str, Any]):
        """Append run record to progress.jsonl immediately."""
        with open(self.progress_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_record) + "\n")
            f.flush()

    async def execute_run_attempt(
        self,
        scenario: dict[str, Any],
        mode: str,
        run_index: int,
        agent_settings: AgentSettings,
        agent_mode: str = "naive",
        max_llm_calls: Optional[int] = None,
    ) -> dict[str, Any]:
        """Single execution attempt of a scenario run with unique agent_id and fresh mandate."""
        scenario_id = scenario["id"]
        variant = scenario.get("variant", "clean")
        attack_class = scenario.get("attack_class", "none")
        escalation_policy = scenario.get("escalation_policy", "auto_reject")
        expected_outcome = scenario.get("expected_outcome", "purchase")

        # 1. Set risk config
        await self.set_risk_config(mode)

        # 2. Generate unique agent identity & register key for strict mandate isolation
        run_uid = uuid.uuid4().hex[:12]
        unique_agent_id = f"eval-{run_uid}"
        unique_agent_key = f"key-{secrets.token_hex(20)}"
        await self.register_agent_key(unique_agent_id, unique_agent_key)

        # 3. Create fresh mandate for this specific agent_id
        mandate_id, mandate_data = await self.create_fresh_mandate(unique_agent_id)

        # Assert remaining == budget_total
        budget_total_cents = mandate_data.get("budget_total_cents", 10000)
        remaining_cents = mandate_data.get("remaining_cents", 10000)
        if remaining_cents != budget_total_cents:
            await self.cleanup_mandate(mandate_id)
            return {
                "scenario_id": scenario_id,
                "variant": variant,
                "attack_class": attack_class,
                "mode": mode,
                "run_index": run_index,
                "status": "error",
                "status_reason": f"Mandate integrity failure: remaining {remaining_cents} != budget {budget_total_cents}",
                "agent_submitted": False,
                "agent_compromised": False,
                "blocked_by": "none",
                "final_decision": None,
                "escalated": False,
                "would_have_executed": False,
                "mandate_frozen": False,
                "llm_calls": 0,
                "duration_ms": 0,
                "risk_details": None,
                "submitted_intents": [],
            }

        # 4. Initialize tool executor with this run's unique key and mandate
        tool_executor = AgentToolExecutor(
            settings=agent_settings,
            store_base_url=self.store_base_url,
            firewall_base_url=self.firewall_base_url,
            agent_key=unique_agent_key,
            variant=variant,
        )
        tool_executor.active_mandate_id = mandate_id

        # Verify via GET /agent/mandate that only this fresh mandate is seen
        mandate_check = await tool_executor.get_budget()
        if mandate_check.get("mandate_id") != mandate_id or mandate_check.get("remaining") != "100.00":
            await self.cleanup_mandate(mandate_id)
            return {
                "scenario_id": scenario_id,
                "variant": variant,
                "attack_class": attack_class,
                "mode": mode,
                "run_index": run_index,
                "status": "error",
                "status_reason": f"Agent mandate endpoint leaked older mandate: {mandate_check}",
                "agent_submitted": False,
                "agent_compromised": False,
                "blocked_by": "none",
                "final_decision": None,
                "escalated": False,
                "would_have_executed": False,
                "mandate_frozen": False,
                "llm_calls": 0,
                "duration_ms": 0,
                "risk_details": None,
                "submitted_intents": [],
            }

        transcript = RunTranscript(
            task=scenario["task"],
            variant=variant,
            mode=agent_mode,
            model=agent_settings.AGENT_MODEL,
        )

        # 5. Run agent loop with LLM throttle
        await self.throttle_llm()
        loop_error = None
        try:
            transcript = await run_agent_loop(
                task=scenario["task"],
                settings=agent_settings,
                variant=variant,
                mode=agent_mode,
                tool_executor=tool_executor,
                transcript=transcript,
                max_llm_calls=max_llm_calls,
            )
        except Exception as exc:
            logger.exception("Agent loop exception in scenario %s: %s", scenario_id, exc)
            loop_error = str(exc)

        # 6. Evaluate submitted intents
        intents_sent = tool_executor.submitted_intents
        first_intent = intents_sent[0] if intents_sent else None
        agent_submitted = len(intents_sent) > 0

        # Classify run validity:
        # valid: agent submitted at least one intent, OR finished cleanly with a final answer (refusal/completion without submission)
        # incomplete: timeouts, tool errors, step cap hit without clean answer, firewall unreachable, 429 given up
        # error: unhandled exception or mandate corruption
        run_status = "valid"
        status_reason = "ok"

        if loop_error:
            run_status = "incomplete"
            status_reason = f"agent_loop_exception: {loop_error}"
        elif transcript.error:
            run_status = "incomplete"
            status_reason = f"agent_error: {transcript.error}"
        elif not agent_submitted and not transcript.final_response:
            run_status = "incomplete"
            status_reason = "no_submission_and_no_final_response"

        # Check compromise
        agent_compromised = check_compromise(scenario, first_intent)

        # Handle escalations if any
        escalated = False
        final_decision = None
        first_resp = first_intent.get("response", {}) if first_intent else None

        if first_intent:
            final_decision = first_resp.get("decision")
            if final_decision == "escalated":
                escalated = True
                intent_id = first_resp.get("intent_id")
                if intent_id:
                    await self.resolve_escalation(intent_id, escalation_policy)
                    if escalation_policy == "auto_approve":
                        final_decision = "approved"
                    else:
                        final_decision = "denied"

        # Attribute blocking layer
        blocked_by = attribute_blocking_layer(first_resp, escalation_policy)

        # Would money have moved (executed)
        would_have_executed = (final_decision == "approved")

        # Check if mandate was frozen
        mandate_frozen = False
        try:
            headers = {"Authorization": f"Bearer {self.operator_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.firewall_base_url}/mandates/{mandate_id}", headers=headers)
                if res.status_code == 200:
                    mandate_frozen = (res.json().get("status") == "frozen")
        except Exception:
            pass

        # Cleanup mandate
        await self.cleanup_mandate(mandate_id)

        # Extract risk details if present
        risk_details = first_resp.get("risk") if first_resp else None
        risk_latency_ms = None
        if risk_details:
            c_meta = risk_details.get("canary", {}).get("meta", {})
            j_meta = risk_details.get("judge", {}).get("meta", {})
            risk_latency_ms = c_meta.get("latency_ms", 0) + j_meta.get("latency_ms", 0)

        record = {
            "scenario_id": scenario_id,
            "task": scenario["task"],
            "variant": variant,
            "attack_class": attack_class,
            "expected_outcome": expected_outcome,
            "mode": mode,
            "agent_mode": agent_mode,
            "run_index": run_index,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": run_status,
            "status_reason": status_reason,
            "agent_submitted": agent_submitted,
            "agent_compromised": agent_compromised,
            "blocked_by": blocked_by,
            "final_decision": final_decision,
            "escalated": escalated,
            "would_have_executed": would_have_executed,
            "mandate_frozen": mandate_frozen,
            "llm_calls": transcript.llm_calls,
            "duration_ms": transcript.duration_ms,
            "risk_latency_ms": risk_latency_ms,
            "risk_details": risk_details,
            "submitted_intents_count": len(intents_sent),
            "submitted_intents": tool_executor.submitted_intents,
        }
        return record

    async def execute_run(
        self,
        scenario: dict[str, Any],
        mode: str,
        run_index: int,
        agent_settings: AgentSettings,
        agent_mode: str = "naive",
        max_llm_calls: Optional[int] = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """Execute run with automatic retries for incomplete runs up to 2 times."""
        last_record: Optional[dict[str, Any]] = None
        for attempt in range(max_retries + 1):
            record = await self.execute_run_attempt(
                scenario=scenario,
                mode=mode,
                run_index=run_index,
                agent_settings=agent_settings,
                agent_mode=agent_mode,
                max_llm_calls=max_llm_calls,
            )
            last_record = record
            if record["status"] == "valid":
                break
            logger.warning(
                "Run attempt %d/%d for %s (mode=%s, run=%d) was %s (%s). Retrying...",
                attempt + 1,
                max_retries + 1,
                scenario["id"],
                mode,
                run_index,
                record["status"],
                record.get("status_reason"),
            )
            await asyncio.sleep(2.0)

        # Record to progress.jsonl
        if last_record:
            self.record_progress(last_record)
        return last_record or {}
