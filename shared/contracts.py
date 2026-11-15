from typing import Any, Literal
from pydantic import BaseModel

Tier = Literal["read_only", "reversible", "money_moving", "sensitive", "protective", "platform"]
ToolStatus = Literal["ok", "blocked", "needs_approval", "error"]
CaseStatus = Literal["open", "need_info", "resolved", "awaiting_approval", "escalated", "rejected"]

class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = {}
    policy_ref: str | None = None        # required by gateway for money_moving tools

class CallContext(BaseModel):
    case_id: str
    session_id: str
    customer_id: str
    verified: bool = True
    step_up_passed: bool = False
    approved_by: str | None = None        # set only when a human approves

class ToolResult(BaseModel):
    status: ToolStatus
    data: dict[str, Any] = {}
    reason: str | None = None
    audit_id: int | None = None
    approval_id: int | None = None

class PolicyResult(BaseModel):
    rule_text: str
    source: str
    section: str
    score: float
    low_confidence: bool

class ActionTaken(BaseModel):
    tool: str
    status: ToolStatus
    summary: str

class AgentResponse(BaseModel):
    reply: str
    status: CaseStatus
    actions: list[ActionTaken] = []
    citations: list[PolicyResult] = []
    case_summary: str | None = None

class ChatRequest(BaseModel):
    session_id: str
    customer_id: str
    token: str
    message: str

class ChatResponse(AgentResponse):
    case_id: str
