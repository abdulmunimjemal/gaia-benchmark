from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RouteType = Literal["direct", "web", "code", "artifact"]
RiskLevel = Literal["low", "medium", "high"]


class TaskRecord(BaseModel):
    task_id: str
    question: str
    expected_answer: str | None = None
    attachment_name: str | None = None
    attachment_path: str | None = None
    dataset_root: str | None = None
    level: int | None = None
    split: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str


class PlannerDecision(BaseModel):
    route: RouteType = "web"
    risk: RiskLevel = "medium"
    use_verifier: bool = True
    needs_web: bool = False
    needs_code: bool = False
    needs_artifact: bool = False
    research_queries: list[str] = Field(default_factory=list)
    working_plan: list[str] = Field(default_factory=list)
    answer_shape: str = "short"


class ToolTrace(BaseModel):
    name: str
    category: str = "generic"
    arguments: dict[str, Any] = Field(default_factory=dict)
    summary: str
    success: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArtifactObservation(BaseModel):
    name: str
    source_type: Literal["task_attachment", "web_fetch", "local_file", "generated"]
    source_uri: str
    kind: str
    stored_path: str
    excerpt: str = ""


class SandboxExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    results: list[str] = Field(default_factory=list)
    error_name: str | None = None
    error_value: str | None = None
    traceback: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_name is None


class SolverOutput(BaseModel):
    answer: str
    confidence: Literal["low", "medium", "high"] = "medium"
    citations: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""


class JudgeOutput(BaseModel):
    is_sufficient: bool = True
    issues: list[str] = Field(default_factory=list)
    revised_answer: str | None = None


class TaskRunResult(BaseModel):
    run_id: str
    task_id: str
    question: str
    answer: str
    raw_answer: str | None = None
    scorer_answer: str | None = None
    expected_answer: str | None = None
    score: float | None = None
    passed: bool | None = None
    route: RouteType = "web"
    risk: RiskLevel = "medium"
    retry_count: int = 0
    error_taxonomy: str | None = None
    planner: PlannerDecision
    solver: SolverOutput
    judge: JudgeOutput
    tool_calls: list[ToolTrace] = Field(default_factory=list)
    artifacts_used: list[ArtifactObservation] = Field(default_factory=list)
    duration_seconds: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubmissionRow(BaseModel):
    task_id: str
    model_answer: str
    reasoning_trace: str | None = None
