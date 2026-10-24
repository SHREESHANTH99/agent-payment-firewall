"""Full smoke-test: create mandate, test 3 intents, verify audit chain."""
import asyncio
import json
import os
import httpx

BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
OPERATOR_TOKEN = os.getenv("OPERATOR_TOKEN", "test-operator-token")
AGENT_KEY      = os.getenv("AGENT_KEY", "test-agent-key")

OP_HEADERS    = {"Authorization": f"Bearer {OPERATOR_TOKEN}", "Content-Type": "application/json"}
AGENT_HEADERS = {"X-Agent-Key": AGENT_KEY, "Content-Type": "application/json"}


async def run():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:

        # 0. Health
        r = await c.get("/health")
        print(f"[health] {r.status_code} {r.text}")

        # 1. Create mandate
        import uuid, time
        mandate_id = f"smoke-{int(time.time())}"
        r = await c.post("/mandates", headers=OP_HEADERS, json={
            "mandate_id": mandate_id,
            "agent_id": "agent-007",
            "budget_total": "100.00",
            "per_transaction_cap": "50.00",
            "escalation_threshold": "20.00",
            "period": "lifetime",
            "allowed_currencies": ["USD"],
            "allowlist_merchants": ["vendor@paypal.com"],
        })
        print(f"\n[create mandate] {r.status_code}")
        if r.status_code not in (200, 201):
            print("  ERROR:", r.text); return
        mandate_data = r.json()
        mandate_id = mandate_data.get("mandate_id")
        print(f"  created actual mandate_id={mandate_id} status={mandate_data.get('status')}")

        # 2a. $5 intent -> should be APPROVED (below $20 threshold)
        r = await c.post("/intents", headers=AGENT_HEADERS, json={
            "idempotency_key": str(uuid.uuid4()),
            "mandate_id": mandate_id,
            "amount": "5.00",
            "currency": "USD",
            "merchant": "vendor@paypal.com",
            "description": "Smoke test auto-approve",
        })
        print(f"\n[intent $5 - expect approved/executing] {r.status_code}")
        d = r.json()
        print(f"  decision={d.get('decision')} status={d.get('status')}")
        print(f"  reasons={d.get('reasons')}")

        # 2b. $25 intent -> should be ESCALATED (above $20 threshold)
        r = await c.post("/intents", headers=AGENT_HEADERS, json={
            "idempotency_key": str(uuid.uuid4()),
            "mandate_id": mandate_id,
            "amount": "25.00",
            "currency": "USD",
            "merchant": "vendor@paypal.com",
            "description": "Smoke test escalation",
        })
        print(f"\n[intent $25 - expect escalated] {r.status_code}")
        d = r.json()
        print(f"  decision={d.get('decision')} status={d.get('status')}")
        escalated_id = d.get("intent_id")

        # 2c. $99 intent -> should be DENIED (exceeds $50 cap)
        r = await c.post("/intents", headers=AGENT_HEADERS, json={
            "idempotency_key": str(uuid.uuid4()),
            "mandate_id": mandate_id,
            "amount": "99.00",
            "currency": "USD",
            "merchant": "vendor@paypal.com",
            "description": "Smoke test deny",
        })
        print(f"\n[intent $99 - expect denied] {r.status_code}")
        d = r.json()
        print(f"  decision={d.get('decision')} status={d.get('status')}")
        print(f"  reasons={[x.get('code') for x in d.get('reasons', [])]}")

        # 3. Operator approve the escalated intent
        if escalated_id:
            r = await c.post(f"/intents/{escalated_id}/approve", headers=OP_HEADERS)
            print(f"\n[approve escalated intent] {r.status_code}")
            d = r.json()
            print(f"  status={d.get('status')} paypal_ref={d.get('paypal_ref')}")

        # 4. Check mandate remaining budget
        r = await c.get(f"/mandates/{mandate_id}", headers=OP_HEADERS)
        print(f"\n[mandate budget after] {r.status_code}")
        d = r.json()
        print(f"  remaining=${d.get('remaining_cents',0)/100:.2f}  reserved=${d.get('reserved_cents',0)/100:.2f}  spent=${d.get('spent_cents',0)/100:.2f}")

        # 5. Verify audit chain
        r = await c.get("/audit/verify", headers=OP_HEADERS)
        print(f"\n[audit/verify] {r.status_code}")
        d = r.json()
        print(f"  valid={d.get('valid')} checked={d.get('checked')} broken_index={d.get('first_broken_index')}")

        print("\n✅ Smoke test complete")

asyncio.run(run())
