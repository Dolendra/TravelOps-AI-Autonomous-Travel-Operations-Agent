from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskDetails(BaseModel):
    task_id: str
    name: str
    status: str
    dependencies: List[str] = Field(default_factory=list)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(BaseModel):
    sender: str
    message: str
    timestamp: str
    payload: Optional[Dict[str, Any]] = None


class SessionDetails(BaseModel):
    session_id: str
    created_at: str
    workflow_state: str
    tasks: List[TaskDetails] = Field(default_factory=list)
    conversation: List[ConversationMessage] = Field(default_factory=list)


class ObservabilityMetrics(BaseModel):
    llm_calls: List[Dict[str, Any]] = Field(default_factory=list)
    total_cost_usd: float
    registered_tools_count: int


class EvaluationMetrics(BaseModel):
    intent_accuracy: float
    entity_accuracy: float
    hallucination_rate: float
    recovery_success_rate: float
    total_sessions: int
    success_rate: float
    avg_latency_sec: float
    avg_cost_usd: float
    total_tokens: int
    succeeded: int
    failed: int
    recovered: int
    intent_passed: int
    intent_total: int
    entity_passed: int
    entity_total: int
    recovered_total: int
    disruptions_total: int
