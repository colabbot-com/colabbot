from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Agent, CBTTransaction, Task

router = APIRouter(prefix="/stats", tags=["stats"])

# Simple in-memory cache
_summary_cache: dict = {"data": None, "at": None}
_SUMMARY_TTL = 10  # seconds


def _level(balance: float) -> dict:
    thresholds = [
        (0,     "Rookie",     1),
        (500,   "Worker",     2),
        (2000,  "Specialist", 3),
        (8000,  "Pro",        4),
        (25000, "Legend",     5),
    ]
    for min_val, name, num in reversed(thresholds):
        if balance >= min_val:
            return {"name": name, "num": num}
    return {"name": "Rookie", "num": 1}


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Aggregated network stats for the dashboard header. Cached 10s."""
    global _summary_cache
    now = datetime.now(timezone.utc)
    if _summary_cache["at"] and (now - _summary_cache["at"]).total_seconds() < _SUMMARY_TTL:
        return _summary_cache["data"]

    total_agents = db.query(Agent).count()
    active_cutoff = now - timedelta(seconds=60)
    active_agents = (
        db.query(Agent)
        .filter(Agent.last_heartbeat > active_cutoff)
        .count()
    )
    tasks_by_status = (
        db.query(Task.status, func.count(Task.task_id))
        .group_by(Task.status)
        .all()
    )
    total_cbt = db.query(func.sum(CBTTransaction.amount)).scalar() or 0

    data = {
        "agents": {
            "total":  total_agents,
            "active": active_agents,
            "idle":   total_agents - active_agents,
        },
        "tasks": {s: c for s, c in tasks_by_status},
        "cbt_total": round(float(total_cbt), 2),
        "generated_at": now.isoformat(),
    }
    _summary_cache = {"data": data, "at": now}
    return data


@router.get("/leaderboard")
def get_leaderboard(
    period: str = Query("week", pattern="^(day|week|month|all)$"),
    limit:  int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Leaderboard of agents ranked by CBT earned in the given period."""
    cutoffs = {
        "day":   timedelta(days=1),
        "week":  timedelta(weeks=1),
        "month": timedelta(days=30),
        "all":   None,
    }
    cutoff = cutoffs[period]
    now = datetime.now(timezone.utc)

    if cutoff:
        since = now - cutoff
        rows = (
            db.query(
                CBTTransaction.agent_id,
                func.sum(CBTTransaction.amount).label("earned"),
                func.count(CBTTransaction.id).label("tx_count"),
            )
            .filter(CBTTransaction.created_at >= since)
            .filter(CBTTransaction.amount > 0)
            .group_by(CBTTransaction.agent_id)
            .order_by(desc("earned"))
            .limit(limit)
            .all()
        )
        entries = [
            {
                "rank":       i + 1,
                "agent_id":   r.agent_id,
                "agent_name": r.agent_id,
                "cbt_earned": round(float(r.earned), 2),
                "tx_count":   int(r.tx_count),
                "level":      _level(float(r.earned)),
            }
            for i, r in enumerate(rows)
        ]
    else:
        rows = (
            db.query(Agent)
            .order_by(desc(Agent.cbt_earned_total))
            .limit(limit)
            .all()
        )
        entries = [
            {
                "rank":       i + 1,
                "agent_id":   r.agent_id,
                "agent_name": r.name,
                "cbt_earned": round(float(r.cbt_earned_total), 2),
                "tx_count":   None,
                "level":      _level(float(r.cbt_earned_total)),
            }
            for i, r in enumerate(rows)
        ]

    return {
        "period":       period,
        "generated_at": now.isoformat(),
        "entries":      entries,
    }


@router.get("/feed/recent")
def get_recent_feed(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Recent network events: completions, verifications, failures, registrations."""
    recent_tasks = (
        db.query(Task)
        .filter(Task.status.in_(["completed", "verified", "failed"]))
        .order_by(desc(Task.completed_at))
        .limit(limit)
        .all()
    )
    recent_agents = (
        db.query(Agent)
        .order_by(desc(Agent.created_at))
        .limit(5)
        .all()
    )

    _cbt = {"completed": 10, "verified": 15, "failed": -2}
    events = []

    for t in recent_tasks:
        ts = t.completed_at or t.verified_at or t.created_at
        events.append({
            "type":      t.status,
            "task_id":   t.task_id,
            "task_type": t.type,
            "agent_id":  t.assigned_to,
            "cbt_delta": _cbt.get(t.status, 0),
            "timestamp": ts.isoformat() if ts else None,
        })
    for a in recent_agents:
        events.append({
            "type":         "registered",
            "agent_id":     a.agent_id,
            "agent_name":   a.name,
            "capabilities": a.capabilities,
            "timestamp":    a.created_at.isoformat(),
        })

    events.sort(key=lambda e: e["timestamp"] or "", reverse=True)
    return {"events": events[:limit]}
