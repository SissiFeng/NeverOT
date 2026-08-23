"""Outcome accounting for contextual shadow campaign decisions.

This module binds a shadow ``CampaignDecisionTrace`` to observed post-decision
outcomes and computes deterministic reward summaries. It is pure DTO and
scoring logic: no database writes, external calls, promotion gates, or policy
updates happen here.
"""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.contracts.scientific_intervention import (
    ScientificIntervention,
    ScientificInterventionPortfolio,
)
from app.services.decision_trace import CampaignDecisionTrace
from app.services.verifiable_reward import (
    RUBRIC_VERSION_DEFAULT,
    RewardVerification,
    split_reward,
    verify_context,
    verify_execution,
    verify_failure,
    verify_objective,
    verify_proxy_gap,
    verify_recovery,
    verify_safety,
    verify_validation,
)
from app.services.verifiable_reward import (
    clamp as _shared_clamp,
)
from app.services.verifiable_reward import (
    execution_score as _shared_execution,
)
from app.services.verifiable_reward import (
    objective_score as _shared_objective,
)
from app.services.verifiable_reward import (
    proxy_gap_score as _shared_proxy_gap,
)
from app.services.verifiable_reward import (
    round_component as _shared_round_component,
)
from app.services.verifiable_reward import (
    validation_score as _shared_validation,
)

__all__ = [
    "CampaignDecisionAccounting",
    "CampaignDecisionAccountingBuilder",
    "CampaignDecisionOutcome",
    "CampaignDecisionOutcomeBuilder",
    "CampaignDecisionReward",
    "CampaignDecisionRewardCalculator",
    "build_campaign_decision_accounting",
    "build_campaign_decision_outcome",
    "calculate_campaign_decision_reward",
]


class CampaignDecisionOutcome(BaseModel):
    """Observed post-decision outcome linked to a shadow decision trace."""

    trace_id: str
    campaign_id: str
    round_index: int = Field(ge=0)
    observed_action: str | None = None
    observed_backend: str | None = None
    candidate_count: int | None = None
    execution_success: bool | None = None
    failure_count: int = 0
    safety_incident_count: int = 0
    objective_delta: float | None = None
    proxy_gap_delta: float | None = None
    validation_success: bool | None = None
    recovery_attempted: bool = False
    recovery_success: bool | None = None
    context_request_fulfilled: bool | None = None
    human_override: bool | None = None
    intervention_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @field_validator("intervention_ids")
    @classmethod
    def _intervention_ids_are_unique(cls, value: list[str]) -> list[str]:
        if any(not item for item in value):
            raise ValueError("intervention_ids must be non-empty")
        if len(value) != len(set(value)):
            raise ValueError("intervention_ids must be unique")
        return value


class CampaignDecisionReward(BaseModel):
    """Deterministic reward/regret summary for a decision outcome."""

    trace_id: str
    reward: float = Field(ge=-1.0, le=1.0)
    regret: float | None = None
    safety_penalty: float = 0.0
    failure_penalty: float = 0.0
    objective_reward: float = 0.0
    proxy_gap_reward: float = 0.0
    validation_reward: float = 0.0
    recovery_reward: float = 0.0
    context_reward: float = 0.0
    # Phase A (RLVR wedge): version the rubric, split process vs outcome credit,
    # and carry the per-signal verifiable records. Defaults keep older callers
    # and persisted rows loading unchanged.
    rubric_version: str = RUBRIC_VERSION_DEFAULT
    process_reward: float = 0.0
    outcome_reward: float = 0.0
    verifications: list[RewardVerification] = Field(default_factory=list)
    rationale: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CampaignDecisionAccounting(BaseModel):
    """Trace, observed outcome, and reward summary bundled for replay."""

    trace: CampaignDecisionTrace
    outcome: CampaignDecisionOutcome
    reward: CampaignDecisionReward
    interventions: list[ScientificIntervention] = Field(default_factory=list)
    intervention_portfolio: ScientificInterventionPortfolio | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _intervention_references_are_aligned(self) -> CampaignDecisionAccounting:
        trace_ids = self.trace.intervention_ids
        outcome_ids = self.outcome.intervention_ids
        intervention_ids = [item.intervention_id for item in self.interventions]
        if trace_ids != outcome_ids or trace_ids != intervention_ids:
            raise ValueError(
                "trace, outcome, and accounting intervention ids must align"
            )
        if len(intervention_ids) != len(set(intervention_ids)):
            raise ValueError("accounting interventions must be unique")
        for intervention in self.interventions:
            if intervention.campaign_id != self.trace.campaign_id:
                raise ValueError("intervention campaign_id must match accounting trace")
            if intervention.round_index != self.trace.round_index:
                raise ValueError("intervention round_index must match accounting trace")
            if intervention.decision_trace_id != self.trace.trace_id:
                raise ValueError("intervention decision_trace_id must match accounting trace")
        portfolio = self.intervention_portfolio
        if portfolio is not None:
            if portfolio.campaign_id != self.trace.campaign_id:
                raise ValueError("portfolio campaign_id must match accounting trace")
            if portfolio.round_index != self.trace.round_index:
                raise ValueError("portfolio round_index must match accounting trace")
            if portfolio.decision_trace_id != self.trace.trace_id:
                raise ValueError("portfolio decision_trace_id must match accounting trace")
            if list(portfolio.intervention_ids) != intervention_ids:
                raise ValueError("portfolio intervention ids must match accounting")
            endpoint_ids = {item.endpoint.endpoint_id for item in self.interventions}
            if endpoint_ids != {portfolio.endpoint_id}:
                raise ValueError("portfolio endpoint_id must match every intervention")
        return self


class CampaignDecisionOutcomeBuilder:
    """Build outcomes from decision traces and observed execution summaries."""

    def build(
        self,
        *,
        trace: CampaignDecisionTrace,
        observed_action: str | None = None,
        observed_backend: str | None = None,
        candidate_count: int | None = None,
        execution_success: bool | None = None,
        failure_count: int = 0,
        safety_incident_count: int = 0,
        objective_delta: float | None = None,
        proxy_gap_delta: float | None = None,
        validation_success: bool | None = None,
        recovery_attempted: bool = False,
        recovery_success: bool | None = None,
        context_request_fulfilled: bool | None = None,
        human_override: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CampaignDecisionOutcome:
        return CampaignDecisionOutcome(
            trace_id=trace.trace_id,
            campaign_id=trace.campaign_id,
            round_index=trace.round_index,
            observed_action=observed_action,
            observed_backend=observed_backend,
            candidate_count=candidate_count,
            execution_success=execution_success,
            failure_count=failure_count,
            safety_incident_count=safety_incident_count,
            objective_delta=objective_delta,
            proxy_gap_delta=proxy_gap_delta,
            validation_success=validation_success,
            recovery_attempted=recovery_attempted,
            recovery_success=recovery_success,
            context_request_fulfilled=context_request_fulfilled,
            human_override=human_override,
            intervention_ids=list(trace.intervention_ids),
            metadata=deepcopy(dict(metadata or {})),
        )


class CampaignDecisionRewardCalculator:
    """Calculate deterministic reward components from observed outcomes."""

    def calculate(self, outcome: CampaignDecisionOutcome) -> CampaignDecisionReward:
        # Build the per-signal verifications once; every scalar component and the
        # process/outcome split derive from them, so there is a single source of
        # truth and the numbers stay bit-identical to the pre-wedge calculator.
        verifications = [
            verify_execution(outcome.execution_success),
            verify_failure(outcome.failure_count),
            verify_safety(outcome.safety_incident_count),
            verify_objective(outcome.objective_delta),
            verify_proxy_gap(outcome.proxy_gap_delta),
            verify_validation(outcome.validation_success),
            verify_recovery(
                attempted=outcome.recovery_attempted,
                success=outcome.recovery_success,
            ),
            verify_context(outcome.context_request_fulfilled),
        ]
        scores = {v.name: v.score for v in verifications}
        execution_reward = scores["execution"]
        failure_penalty = scores["failure"]
        safety_penalty = scores["safety"]
        objective_reward = scores["objective"]
        proxy_gap_reward = scores["proxy_gap"]
        validation_reward = scores["validation"]
        recovery_reward = scores["recovery"]
        context_reward = scores["context"]
        raw_reward = sum(v.score for v in verifications)
        reward = _clamp(raw_reward)
        regret = max(0.0, -reward)
        process_reward, outcome_reward = split_reward(verifications)
        return CampaignDecisionReward(
            trace_id=outcome.trace_id,
            reward=reward,
            regret=regret,
            safety_penalty=safety_penalty,
            failure_penalty=failure_penalty,
            objective_reward=objective_reward,
            proxy_gap_reward=proxy_gap_reward,
            validation_reward=validation_reward,
            recovery_reward=recovery_reward,
            context_reward=context_reward,
            rubric_version=RUBRIC_VERSION_DEFAULT,
            process_reward=process_reward,
            outcome_reward=outcome_reward,
            verifications=verifications,
            rationale=_reward_rationale(
                execution_reward=execution_reward,
                failure_penalty=failure_penalty,
                safety_penalty=safety_penalty,
                objective_reward=objective_reward,
                proxy_gap_reward=proxy_gap_reward,
                validation_reward=validation_reward,
                recovery_reward=recovery_reward,
                context_reward=context_reward,
                raw_reward=raw_reward,
                reward=reward,
            ),
            metadata={
                "execution_reward": execution_reward,
                "raw_reward": raw_reward,
                "clamped": raw_reward != reward,
            },
        )


class CampaignDecisionAccountingBuilder:
    """Bind a trace and outcome with calculated reward accounting."""

    def build(
        self,
        *,
        trace: CampaignDecisionTrace,
        outcome: CampaignDecisionOutcome,
        interventions: Sequence[ScientificIntervention] = (),
        intervention_portfolio: ScientificInterventionPortfolio | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CampaignDecisionAccounting:
        reward = CampaignDecisionRewardCalculator().calculate(outcome)
        return CampaignDecisionAccounting(
            trace=trace.model_copy(deep=True),
            outcome=outcome.model_copy(deep=True),
            reward=reward,
            interventions=[item.model_copy(deep=True) for item in interventions],
            intervention_portfolio=(
                intervention_portfolio.model_copy(deep=True)
                if intervention_portfolio is not None
                else None
            ),
            metadata=deepcopy(dict(metadata or {})),
        )


def build_campaign_decision_outcome(**kwargs: Any) -> CampaignDecisionOutcome:
    """Build a CampaignDecisionOutcome with the default builder."""
    return CampaignDecisionOutcomeBuilder().build(**kwargs)


def calculate_campaign_decision_reward(
    outcome: CampaignDecisionOutcome,
) -> CampaignDecisionReward:
    """Calculate a CampaignDecisionReward with the default calculator."""
    return CampaignDecisionRewardCalculator().calculate(outcome)


def build_campaign_decision_accounting(**kwargs: Any) -> CampaignDecisionAccounting:
    """Build CampaignDecisionAccounting with the default builder."""
    return CampaignDecisionAccountingBuilder().build(**kwargs)


# Reward components delegate to the shared verifiable-reward core so the two
# calculators (here and loop_engineering) share one source of truth. Values are
# bit-for-bit identical to the former local copies (regression IRON RULE).
def _execution_reward(execution_success: bool | None) -> float:
    return _shared_execution(execution_success)


def _objective_reward(objective_delta: float | None) -> float:
    return _shared_objective(objective_delta)


def _proxy_gap_reward(proxy_gap_delta: float | None) -> float:
    return _shared_proxy_gap(proxy_gap_delta)


def _validation_reward(validation_success: bool | None) -> float:
    return _shared_validation(validation_success)


def _reward_rationale(
    *,
    execution_reward: float,
    failure_penalty: float,
    safety_penalty: float,
    objective_reward: float,
    proxy_gap_reward: float,
    validation_reward: float,
    recovery_reward: float,
    context_reward: float,
    raw_reward: float,
    reward: float,
) -> str:
    components = {
        "execution": execution_reward,
        "failure": failure_penalty,
        "safety": safety_penalty,
        "objective": objective_reward,
        "proxy_gap": proxy_gap_reward,
        "validation": validation_reward,
        "recovery": recovery_reward,
        "context": context_reward,
    }
    nonzero = [
        f"{name}={value:.3g}"
        for name, value in components.items()
        if value != 0.0
    ]
    if not nonzero:
        nonzero = ["no nonzero outcome components"]
    suffix = " Reward was clamped." if raw_reward != reward else ""
    return f"Reward components: {', '.join(nonzero)}.{suffix}"


def _clamp(value: float) -> float:
    return _shared_clamp(value)


def _round_component(value: float) -> float:
    return _shared_round_component(value)
