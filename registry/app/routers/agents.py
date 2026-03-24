import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth import get_current_agent
from ..database import get_db
from ..models import Agent, Task
from ..schemas import (
    AgentListResponse,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentSummary,
    HeartbeatRequest,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/register", response_model=AgentRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_agent(body: AgentRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Agent).filter(Agent.agent_id == body.agent_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent '{body.agent_id}' is already registered.",
        )

    agent = Agent(
        agent_id=body.agent_id,
        name=body.name,
        version=body.version,
        endpoint=body.endpoint,
        model=body.model,
        max_concurrent_tasks=body.max_concurrent_tasks,
        public_key=body.public_key,
        auth_token=str(uuid.uuid4()),
        available_slots=body.max_concurrent_tasks,
        last_heartbeat=datetime.now(timezone.utc),
    )
    agent.capabilities = body.capabilities

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return AgentRegisterResponse(
        agent_id=agent.agent_id,
        token=agent.auth_token,
        cbt_balance=agent.cbt_balance,
    )


@router.post("/{agent_id}/heartbeat", status_code=status.HTTP_200_OK)
def heartbeat(
    agent_id: str,
    body: HeartbeatRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    if current_agent.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match agent_id.")

    current_agent.status = body.status
    current_agent.current_load = body.current_load
    current_agent.available_slots = body.available_slots
    current_agent.last_heartbeat = datetime.now(timezone.utc)

    db.commit()
    return {"ok": True}


@router.get("", response_model=AgentListResponse)
def list_agents(
    capability: Optional[str] = Query(default=None),
    min_reputation: Optional[int] = Query(default=None, ge=0),
    max_load: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Agent).filter(Agent.status != "offline")

    if min_reputation is not None:
        query = query.filter(Agent.reputation >= min_reputation)

    if max_load is not None:
        query = query.filter(Agent.current_load <= max_load)

    agents = query.order_by(Agent.reputation.desc()).limit(limit).all()

    if capability:
        # Filter in Python — capabilities stored as JSON string
        agents = [a for a in agents if capability in a.capabilities]

    return AgentListResponse(
        agents=[
            AgentSummary(
                agent_id=a.agent_id,
                name=a.name,
                capabilities=a.capabilities,
                reputation=a.reputation,
                cbt_earned=a.cbt_earned_total,
                current_load=a.current_load,
                endpoint=a.endpoint,
            )
            for a in agents
        ]
    )


@router.get("/{agent_id}/tasks/pending", status_code=status.HTTP_200_OK)
def get_pending_tasks(
    agent_id: str,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Return tasks assigned to this agent that are waiting to be accepted or worked on."""
    if current_agent.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match agent_id.")

    tasks = (
        db.query(Task)
        .filter(Task.assigned_to == agent_id, Task.status.in_(["assigned", "queued"]))
        .order_by(Task.created_at.asc())
        .all()
    )
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "type": t.type,
                "input": t.input,
                "reward_cbt": t.reward_cbt,
                "deadline_seconds": t.deadline_seconds,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    }


@router.get("/{agent_id}/balance", status_code=status.HTTP_200_OK)
def get_balance(
    agent_id: str,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Return the current CBT balance and total earned for this agent."""
    if current_agent.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match agent_id.")

    return {
        "agent_id": agent_id,
        "cbt_balance": current_agent.cbt_balance,
        "cbt_earned_total": current_agent.cbt_earned_total,
        "reputation": current_agent.reputation,
    }
