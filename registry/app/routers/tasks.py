import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_agent
from ..database import get_db
from ..models import Agent, CBTTransaction, Task, TaskResult
from ..schemas import (
    TaskResultRequest,
    TaskSubmitRequest,
    TaskSubmitResponse,
    TaskVerifyRequest,
    TaskVerifyResponse,
)
from ..crypto import verify_result_signature

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Minimum quality score to trigger CBT minting
MIN_QUALITY_SCORE = 0.5

# Reputation gained per accepted task
REPUTATION_PER_TASK = 1


@router.post("", response_model=TaskSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_task(
    body: TaskSubmitRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    if current_agent.agent_id != body.orchestrator_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="orchestrator_id does not match token.")

    # --- Balance check: orchestrator must be able to cover the reward ---
    if current_agent.cbt_balance < body.reward_cbt:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient CBT balance. Required: {body.reward_cbt}, available: {current_agent.cbt_balance}",
        )

    # Auto-assign: find best available agent for the capability
    assigned_to = body.target_agent_id
    if not assigned_to:
        candidates = (
            db.query(Agent)
            .filter(
                Agent.status != "offline",
                Agent.available_slots > 0,
                Agent.agent_id != current_agent.agent_id,
            )
            .order_by(Agent.reputation.desc())
            .all()
        )
        for candidate in candidates:
            if body.type in candidate.capabilities:
                assigned_to = candidate.agent_id
                break

    task_status = "assigned" if assigned_to else "queued"

    task = Task(
        task_id=str(uuid.uuid4()),
        orchestrator_id=body.orchestrator_id,
        type=body.type,
        target_agent_id=body.target_agent_id,
        assigned_to=assigned_to,
        reward_cbt=body.reward_cbt,
        deadline_seconds=body.deadline_seconds,
        status=task_status,
    )
    task.input = body.input.model_dump()

    # --- Debit the orchestrator upfront ---
    current_agent.cbt_balance -= body.reward_cbt
    debit_tx = CBTTransaction(
        agent_id=current_agent.agent_id,
        amount=-body.reward_cbt,
        task_id=task.task_id,
        type="spent",
    )

    db.add(task)
    db.add(debit_tx)
    db.commit()
    db.refresh(task)

    return TaskSubmitResponse(
        task_id=task.task_id,
        status=task.status,
        assigned_to=task.assigned_to,
    )


@router.post("/{task_id}/accept", status_code=status.HTTP_200_OK)
def accept_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    task = _get_task(db, task_id)

    if task.assigned_to != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Task is not assigned to this agent.")

    if task.status not in ("assigned", "queued"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Task is already '{task.status}'.")

    task.status = "accepted"
    task.accepted_at = datetime.now(timezone.utc)

    # Reflect in agent availability
    current_agent.available_slots = max(0, current_agent.available_slots - 1)
    if current_agent.available_slots == 0:
        current_agent.status = "busy"

    db.commit()
    return {"ok": True}


@router.post("/{task_id}/result", status_code=status.HTTP_200_OK)
def submit_result(
    task_id: str,
    body: TaskResultRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    task = _get_task(db, task_id)

    if task.assigned_to != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Task is not assigned to this agent.")

    if task.status not in ("accepted", "assigned"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Task is already '{task.status}'.")

    # Verify signature
    output_dict = body.output.model_dump()
    if not verify_result_signature(current_agent.public_key, output_dict, body.signature):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid result signature.")

    result = TaskResult(
        task_id=task_id,
        agent_id=current_agent.agent_id,
        signature=body.signature,
    )
    result.output = output_dict

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)

    # Free up the slot
    current_agent.available_slots = min(
        current_agent.max_concurrent_tasks,
        current_agent.available_slots + 1,
    )
    if current_agent.available_slots > 0:
        current_agent.status = "idle"

    db.add(result)
    db.commit()
    return {"ok": True}


@router.post("/{task_id}/verify", response_model=TaskVerifyResponse)
def verify_task(
    task_id: str,
    body: TaskVerifyRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    task = _get_task(db, task_id)

    if task.orchestrator_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the orchestrator can verify this task.")

    if task.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Task is '{task.status}', expected 'completed'.")

    if not task.result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No result found for this task.")

    task.result.quality_score = body.quality_score
    task.status = "verified"
    task.verified_at = datetime.now(timezone.utc)

    # --- CBT settlement ---
    # The orchestrator was debited reward_cbt upfront at task submission.
    # Now we pay the agent and refund any remainder to the orchestrator.
    orchestrator = db.query(Agent).filter(Agent.agent_id == task.orchestrator_id).first()

    cbt_awarded = 0.0
    if body.verdict == "accepted" and body.quality_score >= MIN_QUALITY_SCORE:
        agent = db.query(Agent).filter(Agent.agent_id == task.assigned_to).first()
        if agent:
            reputation_multiplier = 1.0 + (agent.reputation / 1000)
            cbt_awarded = round(task.reward_cbt * body.quality_score * reputation_multiplier, 4)
            # Cap at the escrowed amount so we never overpay
            cbt_awarded = min(cbt_awarded, task.reward_cbt)

            agent.cbt_balance += cbt_awarded
            agent.cbt_earned_total += cbt_awarded
            agent.reputation += REPUTATION_PER_TASK

            tx = CBTTransaction(
                agent_id=agent.agent_id,
                amount=cbt_awarded,
                task_id=task_id,
                type="earned",
            )
            db.add(tx)

    # Refund the unused portion to the orchestrator
    refund = round(task.reward_cbt - cbt_awarded, 4)
    if refund > 0 and orchestrator:
        orchestrator.cbt_balance += refund
        refund_tx = CBTTransaction(
            agent_id=orchestrator.agent_id,
            amount=refund,
            task_id=task_id,
            type="refund",
        )
        db.add(refund_tx)

    db.commit()

    return TaskVerifyResponse(
        task_id=task_id,
        verdict=body.verdict,
        cbt_awarded=cbt_awarded,
    )


@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Cancel a task and refund the full reward to the orchestrator."""
    task = _get_task(db, task_id)

    if task.orchestrator_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the orchestrator can cancel this task.")

    if task.status in ("verified", "failed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Task is already '{task.status}', cannot cancel.")

    task.status = "failed"

    # Full refund
    current_agent.cbt_balance += task.reward_cbt
    refund_tx = CBTTransaction(
        agent_id=current_agent.agent_id,
        amount=task.reward_cbt,
        task_id=task_id,
        type="refund",
    )
    db.add(refund_tx)

    # Free agent slot if task was accepted
    if task.assigned_to:
        agent = db.query(Agent).filter(Agent.agent_id == task.assigned_to).first()
        if agent:
            agent.available_slots = min(agent.max_concurrent_tasks, agent.available_slots + 1)
            if agent.available_slots > 0:
                agent.status = "idle"

    db.commit()
    return {"ok": True, "refunded_cbt": task.reward_cbt}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_task(db: Session, task_id: str) -> Task:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found.")
    return task
