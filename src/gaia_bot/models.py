"""Compatibility re-export for structured benchmark models.

Prefer importing from :mod:`gaia_bot.basemodels` in new code.
"""

from gaia_bot.basemodels import (
    ArtifactObservation,
    JudgeOutput,
    PlannerDecision,
    RiskLevel,
    RouteType,
    SandboxExecutionResult,
    SearchHit,
    SolverOutput,
    SubmissionRow,
    TaskRecord,
    TaskRunResult,
    ToolTrace,
)

__all__ = [
    "ArtifactObservation",
    "JudgeOutput",
    "PlannerDecision",
    "RiskLevel",
    "RouteType",
    "SandboxExecutionResult",
    "SearchHit",
    "SolverOutput",
    "SubmissionRow",
    "TaskRecord",
    "TaskRunResult",
    "ToolTrace",
]
