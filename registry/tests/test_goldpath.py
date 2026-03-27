"""
Integration tests for the ColabBot Registry golden path:

  Register → Heartbeat → Submit Task (balance check) → Accept → Result → Verify
  + Cancel/Refund + Topup Claim

These tests hit the real FastAPI app with an in-memory SQLite DB.
"""

import pytest
from tests.conftest import auth_header, register_agent, sign_output, PUBLIC_KEY_B64


# ---------------------------------------------------------------------------
# 1. Agent Registration
# ---------------------------------------------------------------------------

def test_register_agent(client):
    resp = client.post("/v1/agents/register", json={
        "agent_id": "alice",
        "name": "Alice",
        "version": "1.0.0",
        "endpoint": "https://example.com/alice",
        "capabilities": ["text/research"],
        "public_key": PUBLIC_KEY_B64,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_id"] == "alice"
    assert "token" in data
    assert data["cbt_balance"] == 0.0


def test_register_duplicate_fails(client):
    register_agent(client, agent_id="bob")
    resp = client.post("/v1/agents/register", json={
        "agent_id": "bob",
        "name": "Bob Again",
        "version": "1.0.0",
        "endpoint": "https://example.com/bob",
        "capabilities": ["text/research"],
        "public_key": PUBLIC_KEY_B64,
    })
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 2. Heartbeat
# ---------------------------------------------------------------------------

def test_heartbeat(client):
    agent = register_agent(client, agent_id="heartbeat-agent")
    resp = client.post(
        f"/v1/agents/{agent['agent_id']}/heartbeat",
        json={"status": "idle", "current_load": 0.0, "available_slots": 1},
        headers=auth_header(agent["token"]),
    )
    assert resp.status_code == 200


def test_heartbeat_wrong_token(client):
    register_agent(client, agent_id="agent-a")
    agent_b = register_agent(client, agent_id="agent-b")
    resp = client.post(
        "/v1/agents/agent-a/heartbeat",
        json={"status": "idle", "current_load": 0.0, "available_slots": 1},
        headers=auth_header(agent_b["token"]),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. Task Submit — Balance Check + Debit
# ---------------------------------------------------------------------------

def _give_cbt(client, agent_id: str, token: str, amount: float):
    """Directly top up an agent's balance via DB for testing."""
    from sqlalchemy.orm import Session
    from tests.conftest import TestSession
    from app.models import Agent
    db = TestSession()
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    agent.cbt_balance += amount
    db.commit()
    db.close()


def test_submit_task_insufficient_balance(client):
    orchestrator = register_agent(client, agent_id="poor-orch")
    resp = client.post(
        "/v1/tasks",
        json={
            "orchestrator_id": orchestrator["agent_id"],
            "type": "text/research",
            "input": {"prompt": "test"},
            "reward_cbt": 100.0,
        },
        headers=auth_header(orchestrator["token"]),
    )
    assert resp.status_code == 402
    assert "Insufficient" in resp.json()["detail"]


def test_submit_task_debits_orchestrator(client):
    # Register orchestrator + worker
    orch = register_agent(client, agent_id="rich-orch")
    register_agent(client, agent_id="worker-1", capabilities=["text/research"])

    # Give orchestrator some CBT
    _give_cbt(client, orch["agent_id"], orch["token"], 500.0)

    # Send heartbeat for worker so it's discoverable
    worker = register_agent(client, agent_id="worker-avail", capabilities=["text/research"])
    client.post(
        f"/v1/agents/{worker['agent_id']}/heartbeat",
        json={"status": "idle", "current_load": 0.0, "available_slots": 3},
        headers=auth_header(worker["token"]),
    )

    resp = client.post(
        "/v1/tasks",
        json={
            "orchestrator_id": orch["agent_id"],
            "type": "text/research",
            "input": {"prompt": "research something"},
            "reward_cbt": 50.0,
        },
        headers=auth_header(orch["token"]),
    )
    assert resp.status_code == 201

    # Check balance was debited
    balance_resp = client.get(
        f"/v1/agents/{orch['agent_id']}/balance",
        headers=auth_header(orch["token"]),
    )
    assert balance_resp.json()["cbt_balance"] == 450.0


# ---------------------------------------------------------------------------
# 4. Full Lifecycle: Submit → Accept → Result → Verify (with refund)
# ---------------------------------------------------------------------------

def test_full_task_lifecycle(client):
    # Setup: orchestrator with balance, worker agent
    orch = register_agent(client, agent_id="orch-lifecycle")
    worker = register_agent(client, agent_id="worker-lifecycle", capabilities=["code/generate"])
    _give_cbt(client, orch["agent_id"], orch["token"], 100.0)

    # Worker sends heartbeat to be discoverable
    client.post(
        f"/v1/agents/{worker['agent_id']}/heartbeat",
        json={"status": "idle", "current_load": 0.0, "available_slots": 3},
        headers=auth_header(worker["token"]),
    )

    # Submit task
    submit_resp = client.post(
        "/v1/tasks",
        json={
            "orchestrator_id": orch["agent_id"],
            "type": "code/generate",
            "input": {"prompt": "write hello world"},
            "reward_cbt": 20.0,
        },
        headers=auth_header(orch["token"]),
    )
    assert submit_resp.status_code == 201
    task_id = submit_resp.json()["task_id"]
    assert submit_resp.json()["assigned_to"] == worker["agent_id"]

    # Orchestrator balance debited
    bal = client.get(f"/v1/agents/{orch['agent_id']}/balance", headers=auth_header(orch["token"])).json()
    assert bal["cbt_balance"] == 80.0

    # Accept
    accept_resp = client.post(
        f"/v1/tasks/{task_id}/accept",
        headers=auth_header(worker["token"]),
    )
    assert accept_resp.status_code == 200

    # Submit result
    output = {"content": "print('hello world')", "format": "text", "tokens_used": 10}
    sig = sign_output(output)
    result_resp = client.post(
        f"/v1/tasks/{task_id}/result",
        json={"agent_id": worker["agent_id"], "output": output, "signature": sig},
        headers=auth_header(worker["token"]),
    )
    assert result_resp.status_code == 200

    # Verify with quality_score 0.8
    verify_resp = client.post(
        f"/v1/tasks/{task_id}/verify",
        json={
            "orchestrator_id": orch["agent_id"],
            "verdict": "accepted",
            "quality_score": 0.8,
        },
        headers=auth_header(orch["token"]),
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["verdict"] == "accepted"

    # Worker earned: 20 * 0.8 * 1.0 (rep=0 → multiplier=1.0) = 16.0
    cbt_awarded = verify_data["cbt_awarded"]
    assert cbt_awarded == 16.0

    # Worker balance updated
    worker_bal = client.get(
        f"/v1/agents/{worker['agent_id']}/balance",
        headers=auth_header(worker["token"]),
    ).json()
    assert worker_bal["cbt_balance"] == 16.0
    assert worker_bal["reputation"] == 1

    # Orchestrator got refund of unused portion: 20 - 16 = 4
    orch_bal = client.get(
        f"/v1/agents/{orch['agent_id']}/balance",
        headers=auth_header(orch["token"]),
    ).json()
    assert orch_bal["cbt_balance"] == 84.0  # 80 + 4 refund


def test_verify_rejected_full_refund(client):
    """When verdict=rejected, orchestrator gets full refund."""
    orch = register_agent(client, agent_id="orch-reject")
    worker = register_agent(client, agent_id="worker-reject", capabilities=["text/research"])
    _give_cbt(client, orch["agent_id"], orch["token"], 50.0)

    client.post(
        f"/v1/agents/{worker['agent_id']}/heartbeat",
        json={"status": "idle", "current_load": 0.0, "available_slots": 3},
        headers=auth_header(worker["token"]),
    )

    submit = client.post("/v1/tasks", json={
        "orchestrator_id": orch["agent_id"],
        "type": "text/research",
        "input": {"prompt": "test"},
        "reward_cbt": 30.0,
    }, headers=auth_header(orch["token"]))
    task_id = submit.json()["task_id"]

    # Accept + result
    client.post(f"/v1/tasks/{task_id}/accept", headers=auth_header(worker["token"]))
    output = {"content": "bad result", "format": "text", "tokens_used": 5}
    client.post(f"/v1/tasks/{task_id}/result", json={
        "agent_id": worker["agent_id"], "output": output, "signature": sign_output(output),
    }, headers=auth_header(worker["token"]))

    # Verify: rejected
    verify = client.post(f"/v1/tasks/{task_id}/verify", json={
        "orchestrator_id": orch["agent_id"], "verdict": "rejected", "quality_score": 0.2,
    }, headers=auth_header(orch["token"]))
    assert verify.status_code == 200
    assert verify.json()["cbt_awarded"] == 0.0

    # Orchestrator gets full 30 CBT back
    bal = client.get(f"/v1/agents/{orch['agent_id']}/balance", headers=auth_header(orch["token"])).json()
    assert bal["cbt_balance"] == 50.0  # 20 remaining + 30 refund


# ---------------------------------------------------------------------------
# 5. Task Cancel — Full Refund
# ---------------------------------------------------------------------------

def test_cancel_task_refunds(client):
    orch = register_agent(client, agent_id="orch-cancel")
    _give_cbt(client, orch["agent_id"], orch["token"], 100.0)

    submit = client.post("/v1/tasks", json={
        "orchestrator_id": orch["agent_id"],
        "type": "text/research",
        "input": {"prompt": "cancel me"},
        "reward_cbt": 25.0,
    }, headers=auth_header(orch["token"]))
    task_id = submit.json()["task_id"]

    # Balance should be 75 after debit
    bal = client.get(f"/v1/agents/{orch['agent_id']}/balance", headers=auth_header(orch["token"])).json()
    assert bal["cbt_balance"] == 75.0

    # Cancel
    cancel = client.post(f"/v1/tasks/{task_id}/cancel", headers=auth_header(orch["token"]))
    assert cancel.status_code == 200
    assert cancel.json()["refunded_cbt"] == 25.0

    # Balance restored
    bal = client.get(f"/v1/agents/{orch['agent_id']}/balance", headers=auth_header(orch["token"])).json()
    assert bal["cbt_balance"] == 100.0


def test_cancel_already_verified_fails(client):
    """Cannot cancel a verified task."""
    orch = register_agent(client, agent_id="orch-cancel-fail")
    worker = register_agent(client, agent_id="worker-cancel-fail", capabilities=["text/research"])
    _give_cbt(client, orch["agent_id"], orch["token"], 100.0)

    client.post(f"/v1/agents/{worker['agent_id']}/heartbeat",
                json={"status": "idle", "current_load": 0.0, "available_slots": 3},
                headers=auth_header(worker["token"]))

    submit = client.post("/v1/tasks", json={
        "orchestrator_id": orch["agent_id"], "type": "text/research",
        "input": {"prompt": "do work"}, "reward_cbt": 10.0,
    }, headers=auth_header(orch["token"]))
    task_id = submit.json()["task_id"]

    client.post(f"/v1/tasks/{task_id}/accept", headers=auth_header(worker["token"]))
    output = {"content": "done", "format": "text", "tokens_used": 5}
    client.post(f"/v1/tasks/{task_id}/result", json={
        "agent_id": worker["agent_id"], "output": output, "signature": sign_output(output),
    }, headers=auth_header(worker["token"]))
    client.post(f"/v1/tasks/{task_id}/verify", json={
        "orchestrator_id": orch["agent_id"], "verdict": "accepted", "quality_score": 1.0,
    }, headers=auth_header(orch["token"]))

    # Try to cancel — should fail
    cancel = client.post(f"/v1/tasks/{task_id}/cancel", headers=auth_header(orch["token"]))
    assert cancel.status_code == 409


# ---------------------------------------------------------------------------
# 6. Topup Claim
# ---------------------------------------------------------------------------

def test_claim_pending_topup(client):
    """Claim pending CBT after registering an agent."""
    from tests.conftest import TestSession
    from app.models import CBTTransaction

    # Simulate a pending topup (as if Stripe webhook fired before agent existed)
    db = TestSession()
    tx = CBTTransaction(
        agent_id="pending",
        amount=500.0,
        task_id=None,
        type="topup_pending",
        stripe_session_id="cs_test_abc123",
    )
    db.add(tx)
    db.commit()
    db.close()

    # Register agent
    agent = register_agent(client, agent_id="backer-agent")
    assert agent["cbt_balance"] == 0.0

    # Claim
    claim = client.post("/v1/topup/claim", json={
        "stripe_session_id": "cs_test_abc123",
    }, headers=auth_header(agent["token"]))
    assert claim.status_code == 200
    data = claim.json()
    assert data["claimed_cbt"] == 500.0
    assert data["new_balance"] == 500.0

    # Second claim should fail (already claimed)
    claim2 = client.post("/v1/topup/claim", json={
        "stripe_session_id": "cs_test_abc123",
    }, headers=auth_header(agent["token"]))
    assert claim2.status_code == 404


def test_claim_nonexistent_session(client):
    agent = register_agent(client, agent_id="claim-fail")
    resp = client.post("/v1/topup/claim", json={
        "stripe_session_id": "cs_does_not_exist",
    }, headers=auth_header(agent["token"]))
    assert resp.status_code == 404
