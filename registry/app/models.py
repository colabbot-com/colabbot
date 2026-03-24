import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    _capabilities = Column("capabilities", Text, nullable=False)  # JSON array
    model = Column(String, nullable=True)
    max_concurrent_tasks = Column(Integer, default=1, nullable=False)
    public_key = Column(Text, nullable=False)
    auth_token = Column(String, unique=True, nullable=False, index=True)

    # Reputation & balance
    reputation = Column(Integer, default=0, nullable=False)
    cbt_balance = Column(Float, default=0.0, nullable=False)
    cbt_earned_total = Column(Float, default=0.0, nullable=False)

    # Availability
    status = Column(String, default="idle", nullable=False)   # idle | busy | draining | offline
    current_load = Column(Float, default=0.0, nullable=False)
    available_slots = Column(Integer, default=1, nullable=False)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    tasks_assigned = relationship("Task", back_populates="agent", foreign_keys="Task.assigned_to")

    @property
    def capabilities(self) -> list[str]:
        return json.loads(self._capabilities)

    @capabilities.setter
    def capabilities(self, value: list[str]):
        self._capabilities = json.dumps(value)


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)
    orchestrator_id = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    _input = Column("input", Text, nullable=False)       # JSON object
    target_agent_id = Column(String, nullable=True)
    assigned_to = Column(String, ForeignKey("agents.agent_id"), nullable=True, index=True)
    reward_cbt = Column(Float, nullable=False)
    deadline_seconds = Column(Integer, nullable=True)

    # Lifecycle
    status = Column(String, default="queued", nullable=False)
    # queued | assigned | accepted | working | completed | verified | failed

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="tasks_assigned", foreign_keys=[assigned_to])
    result = relationship("TaskResult", back_populates="task", uselist=False)

    @property
    def input(self) -> dict:
        return json.loads(self._input)

    @input.setter
    def input(self, value: dict):
        self._input = json.dumps(value)


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.task_id"), unique=True, nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    _output = Column("output", Text, nullable=False)     # JSON object
    signature = Column(Text, nullable=False)
    quality_score = Column(Float, nullable=True)         # set after verification
    submitted_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    task = relationship("Task", back_populates="result")

    @property
    def output(self) -> dict:
        return json.loads(self._output)

    @output.setter
    def output(self, value: dict):
        self._output = json.dumps(value)


class CBTTransaction(Base):
    __tablename__ = "cbt_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)               # positive = credit, negative = debit
    task_id = Column(String, ForeignKey("tasks.task_id"), nullable=True)
    type = Column(String, nullable=False)                # earned | spent | topup | transfer
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
