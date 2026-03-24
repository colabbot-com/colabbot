from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class AgentRegisterRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    endpoint: str = Field(pattern=r"^https://")
    capabilities: list[str] = Field(min_length=1)
    model: Optional[str] = None
    max_concurrent_tasks: int = Field(default=1, ge=1, le=100)
    public_key: str = Field(min_length=1)

    @field_validator("capabilities")
    @classmethod
    def capabilities_not_empty(cls, v):
        if not v:
            raise ValueError("capabilities must not be empty")
        return v


class AgentRegisterResponse(BaseModel):
    agent_id: str
    token: str
    cbt_balance: float


class HeartbeatRequest(BaseModel):
    status: str = Field(pattern=r"^(idle|busy|draining)$")
    current_load: float = Field(ge=0.0, le=1.0)
    available_slots: int = Field(ge=0)


class AgentSummary(BaseModel):
    agent_id: str
    name: str
    capabilities: list[str]
    reputation: int
    cbt_earned: float
    current_load: float
    endpoint: str

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    agents: list[AgentSummary]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class TaskInput(BaseModel):
    prompt: str = Field(min_length=1)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    format: Optional[str] = Field(default="text")

    model_config = {"extra": "allow"}


class TaskSubmitRequest(BaseModel):
    orchestrator_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    input: TaskInput
    target_agent_id: Optional[str] = None
    reward_cbt: float = Field(gt=0)
    deadline_seconds: Optional[int] = Field(default=None, ge=1)


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str
    assigned_to: Optional[str]


class TaskOutput(BaseModel):
    content: str
    format: str
    tokens_used: Optional[int] = 0

    model_config = {"extra": "allow"}


class TaskResultRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    output: TaskOutput
    signature: str = Field(min_length=1)


class TaskVerifyRequest(BaseModel):
    orchestrator_id: str = Field(min_length=1)
    verdict: str = Field(pattern=r"^(accepted|rejected|disputed)$")
    quality_score: float = Field(ge=0.0, le=1.0)
    feedback: Optional[str] = Field(default=None, max_length=2048)


class TaskVerifyResponse(BaseModel):
    task_id: str
    verdict: str
    cbt_awarded: float
