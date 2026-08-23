"""Versioned contracts for endpoint-driven scientific interventions.

These models are additive and shadow-only. Candidate providers may continue to
return parameter dictionaries; a candidate becomes a scientific intervention
only after HELIOS binds it to an endpoint, route, measurement protocol,
feasibility assessment, and auditable utility decomposition.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENDPOINT_CONTRACT_VERSION = "campaign_endpoint.v1"
INTERVENTION_CONTRACT_VERSION = "scientific_intervention.v1"
INTERVENTION_PORTFOLIO_CONTRACT_VERSION = "scientific_intervention_portfolio.v1"


class _FrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )


class EndpointComparison(StrEnum):
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    BETWEEN = "between"
    TARGET = "target"


class EndpointAttainmentStatus(StrEnum):
    ATTAINED = "attained"
    NOT_ATTAINED = "not_attained"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BUDGET_EXHAUSTED = "budget_exhausted"


class EndpointCriterion(_FrozenContract):
    """One measurable, evaluable condition of a scientific endpoint."""

    criterion_id: str = Field(min_length=1, max_length=160)
    metric_name: str = Field(min_length=1, max_length=160)
    comparison: EndpointComparison
    threshold: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    tolerance: float | None = Field(default=None, ge=0.0)
    required: bool = True
    minimum_replicates: int = Field(default=1, ge=1)
    minimum_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    measurement_protocol_id: str | None = Field(default=None, max_length=160)
    rationale: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _comparison_has_required_bounds(self) -> EndpointCriterion:
        if self.comparison == EndpointComparison.BETWEEN:
            if self.lower_bound is None or self.upper_bound is None:
                raise ValueError("between criteria require lower_bound and upper_bound")
            if self.lower_bound > self.upper_bound:
                raise ValueError("lower_bound must not exceed upper_bound")
        elif self.threshold is None:
            raise ValueError(f"{self.comparison.value} criteria require threshold")
        if self.comparison == EndpointComparison.TARGET and self.tolerance is None:
            raise ValueError("target criteria require tolerance")
        return self


class CampaignEndpointSpec(_FrozenContract):
    """Campaign-level scientific endpoint and its evidence/budget contract."""

    contract_version: Literal["campaign_endpoint.v1"] = ENDPOINT_CONTRACT_VERSION
    endpoint_id: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1, max_length=4000)
    criteria: tuple[EndpointCriterion, ...] = Field(min_length=1)
    max_experiments: int | None = Field(default=None, ge=1)
    max_wall_clock_s: float | None = Field(default=None, gt=0.0)
    max_resource_cost: float | None = Field(default=None, ge=0.0)
    validation_protocol_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _metadata_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_json(value)
        return value

    @model_validator(mode="after")
    def _criterion_ids_are_unique(self) -> CampaignEndpointSpec:
        criterion_ids = [criterion.criterion_id for criterion in self.criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("endpoint criterion_id values must be unique")
        if not any(criterion.required for criterion in self.criteria):
            raise ValueError("endpoint requires at least one required criterion")
        if len(self.validation_protocol_ids) != len(set(self.validation_protocol_ids)):
            raise ValueError("validation_protocol_ids must be unique")
        return self


class EndpointCriterionAssessment(_FrozenContract):
    criterion_id: str
    metric_name: str
    observed_value: float | None = None
    replicate_count: int = Field(default=0, ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool | None = None
    reason: str = Field(min_length=1, max_length=2000)


class EndpointAttainmentAssessment(_FrozenContract):
    endpoint_id: str
    status: EndpointAttainmentStatus
    attained: bool
    criteria: tuple[EndpointCriterionAssessment, ...]
    experiments_used: int = Field(default=0, ge=0)
    elapsed_wall_clock_s: float = Field(default=0.0, ge=0.0)
    resource_cost: float = Field(default=0.0, ge=0.0)
    exhausted_budgets: tuple[str, ...] = ()
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rationale: str = Field(min_length=1, max_length=4000)

    @field_validator("assessed_at")
    @classmethod
    def _assessed_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("assessed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _status_matches_attainment(self) -> EndpointAttainmentAssessment:
        if self.attained != (self.status == EndpointAttainmentStatus.ATTAINED):
            raise ValueError("attained must match endpoint attainment status")
        if len(self.exhausted_budgets) != len(set(self.exhausted_budgets)):
            raise ValueError("exhausted_budgets must be unique")
        return self


class InterventionConstraintType(StrEnum):
    PHYSICAL = "physical"
    OPERATIONAL = "operational"
    SAFETY = "safety"
    EPISTEMIC = "epistemic"
    GOVERNANCE = "governance"


class InterventionConstraint(_FrozenContract):
    constraint_id: str = Field(min_length=1, max_length=160)
    constraint_type: InterventionConstraintType
    statement: str = Field(min_length=1, max_length=2000)
    hard: bool = True
    source: str = Field(default="campaign", min_length=1, max_length=160)


class MaterialSpec(_FrozenContract):
    material_id: str | None = Field(default=None, max_length=160)
    composition: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("composition", "attributes")
    @classmethod
    def _mappings_are_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_json(value)
        return value


class SynthesisRouteSpec(_FrozenContract):
    route_id: str = Field(min_length=1, max_length=160)
    route_name: str = Field(min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    process_parameters: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()

    @field_validator("process_parameters")
    @classmethod
    def _process_parameters_are_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_json(value)
        return value


class MeasurementProtocolSpec(_FrozenContract):
    protocol_id: str = Field(min_length=1, max_length=160)
    metric_names: tuple[str, ...] = Field(min_length=1)
    instrument_ids: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    replicates: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _metadata_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_json(value)
        return value

    @model_validator(mode="after")
    def _protocol_references_are_unique(self) -> MeasurementProtocolSpec:
        for field_name, values in (
            ("metric_names", self.metric_names),
            ("instrument_ids", self.instrument_ids),
            ("controls", self.controls),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must be unique")
        return self


class ExecutionPlanRef(_FrozenContract):
    graph_id: str = Field(min_length=1, max_length=200)
    graph_hash: str = Field(min_length=1, max_length=256)
    backend: str = Field(min_length=1, max_length=160)
    resource_ids: tuple[str, ...] = ()
    compiled: bool = True


class InterventionFeasibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class InterventionFeasibilityAssessment(_FrozenContract):
    status: InterventionFeasibilityStatus
    expected_failure_risk: float = Field(ge=0.0, le=1.0)
    expected_cost: float = Field(default=0.0, ge=0.0)
    expected_duration_s: float = Field(default=0.0, ge=0.0)
    missing_capabilities: tuple[str, ...] = ()
    hard_gate_reasons: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _status_matches_gate_evidence(self) -> InterventionFeasibilityAssessment:
        if self.status == InterventionFeasibilityStatus.ELIGIBLE and (
            self.missing_capabilities or self.hard_gate_reasons
        ):
            raise ValueError("eligible interventions cannot carry hard-gate failures")
        if self.status == InterventionFeasibilityStatus.BLOCKED and not (
            self.missing_capabilities or self.hard_gate_reasons
        ):
            raise ValueError("blocked interventions require an explicit gate reason")
        return self


class InterventionUtilityBreakdown(_FrozenContract):
    scientific_value: float
    information_value: float
    failure_penalty: float = Field(ge=0.0)
    execution_cost_penalty: float = Field(ge=0.0)
    execution_time_penalty: float = Field(ge=0.0)
    total_utility: float
    expected_endpoint_impact: float | None = None
    expected_information_gain: float | None = None
    weights: dict[str, float] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=2000)

    @field_validator("weights")
    @classmethod
    def _weights_are_finite(cls, value: dict[str, float]) -> dict[str, float]:
        _validate_bounded_json(value)
        allowed = {
            "scientific",
            "information",
            "failure",
            "execution_cost",
            "execution_time",
        }
        unsupported = sorted(set(value) - allowed)
        if unsupported:
            raise ValueError(f"unsupported utility weight keys: {unsupported}")
        if any(weight < 0.0 for weight in value.values()):
            raise ValueError("utility weights must be non-negative")
        return value

    @model_validator(mode="after")
    def _total_matches_components(self) -> InterventionUtilityBreakdown:
        weights = {
            "scientific": 1.0,
            "information": 1.0,
            "failure": 1.0,
            "execution_cost": 1.0,
            "execution_time": 1.0,
            **self.weights,
        }
        expected_total = (
            weights["scientific"] * self.scientific_value
            + weights["information"] * self.information_value
            - weights["failure"] * self.failure_penalty
            - weights["execution_cost"] * self.execution_cost_penalty
            - weights["execution_time"] * self.execution_time_penalty
        )
        if not math.isclose(self.total_utility, expected_total, abs_tol=1e-9):
            raise ValueError("total_utility must equal the recorded component sum")
        return self


class ScientificIntervention(_FrozenContract):
    """One endpoint-conditioned, auditable, shadow-only scientific action."""

    contract_version: Literal["scientific_intervention.v1"] = INTERVENTION_CONTRACT_VERSION
    intervention_id: str = Field(min_length=1, max_length=200)
    campaign_id: str = Field(min_length=1, max_length=200)
    round_index: int = Field(ge=0)
    candidate_index: int = Field(ge=0)
    decision_trace_id: str | None = Field(default=None, max_length=200)
    endpoint: CampaignEndpointSpec
    scientific_target: str = Field(min_length=1, max_length=4000)
    material: MaterialSpec | None = None
    design_parameters: dict[str, Any] = Field(default_factory=dict)
    synthesis_route: SynthesisRouteSpec
    measurement_protocol: MeasurementProtocolSpec
    required_instruments: tuple[str, ...] = ()
    execution_plan: ExecutionPlanRef | None = None
    safety_constraints: tuple[InterventionConstraint, ...] = ()
    feasibility: InterventionFeasibilityAssessment
    utility: InterventionUtilityBreakdown
    provenance: dict[str, Any] = Field(default_factory=dict)
    shadow_only: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("design_parameters", "provenance")
    @classmethod
    def _mappings_are_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_json(value)
        return value

    @field_validator("created_at")
    @classmethod
    def _created_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_intervention_boundary(self) -> ScientificIntervention:
        if not self.shadow_only:
            raise ValueError("scientific_intervention.v1 is shadow-only")
        if len(self.required_instruments) != len(set(self.required_instruments)):
            raise ValueError("required_instruments must be unique")
        measurement_instruments = set(self.measurement_protocol.instrument_ids)
        if not measurement_instruments.issubset(self.required_instruments):
            raise ValueError("measurement instruments must be included in required_instruments")
        endpoint_metrics = {criterion.metric_name for criterion in self.endpoint.criteria if criterion.required}
        if not endpoint_metrics.issubset(self.measurement_protocol.metric_names):
            raise ValueError("measurement protocol must cover all required endpoint metrics")
        constraint_ids = [item.constraint_id for item in self.safety_constraints]
        if len(constraint_ids) != len(set(constraint_ids)):
            raise ValueError("safety constraint ids must be unique")
        return self


class ScientificInterventionPortfolio(_FrozenContract):
    """Shadow ranking manifest for a batch of scientific interventions."""

    contract_version: Literal["scientific_intervention_portfolio.v1"] = INTERVENTION_PORTFOLIO_CONTRACT_VERSION
    portfolio_id: str = Field(min_length=1, max_length=200)
    campaign_id: str = Field(min_length=1, max_length=200)
    round_index: int = Field(ge=0)
    decision_trace_id: str | None = Field(default=None, max_length=200)
    endpoint_id: str = Field(min_length=1, max_length=160)
    intervention_ids: tuple[str, ...] = Field(min_length=1)
    ranked_intervention_ids: tuple[str, ...] = Field(min_length=1)
    recommended_intervention_ids: tuple[str, ...] = ()
    would_change_order: bool = False
    rationale: str = Field(min_length=1, max_length=4000)
    provenance: dict[str, Any] = Field(default_factory=dict)
    shadow_only: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("provenance")
    @classmethod
    def _provenance_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_json(value)
        return value

    @field_validator("created_at")
    @classmethod
    def _created_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _ranking_is_complete_and_shadow_only(self) -> ScientificInterventionPortfolio:
        intervention_ids = self.intervention_ids
        ranked_ids = self.ranked_intervention_ids
        if not self.shadow_only:
            raise ValueError("scientific_intervention_portfolio.v1 is shadow-only")
        if len(intervention_ids) != len(set(intervention_ids)):
            raise ValueError("portfolio intervention_ids must be unique")
        if len(ranked_ids) != len(set(ranked_ids)):
            raise ValueError("ranked_intervention_ids must be unique")
        if set(ranked_ids) != set(intervention_ids):
            raise ValueError("ranked_intervention_ids must contain every intervention")
        if len(self.recommended_intervention_ids) != len(set(self.recommended_intervention_ids)):
            raise ValueError("recommended_intervention_ids must be unique")
        if not set(self.recommended_intervention_ids).issubset(intervention_ids):
            raise ValueError("recommended interventions must belong to the portfolio")
        if self.would_change_order != (ranked_ids != intervention_ids):
            raise ValueError("would_change_order must match the recorded ranking")
        return self


def _validate_bounded_json(value: Any, *, depth: int = 0) -> None:
    if depth > 6:
        raise ValueError("mapping exceeds depth limit 6")
    if isinstance(value, dict):
        if len(value) > 64:
            raise ValueError("mapping exceeds 64 items")
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 160:
                raise ValueError("mapping keys must be non-empty strings <=160 chars")
            _validate_bounded_json(item, depth=depth + 1)
        return
    if isinstance(value, list | tuple):
        if len(value) > 64:
            raise ValueError("sequence exceeds 64 items")
        for item in value:
            _validate_bounded_json(item, depth=depth + 1)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("mapping numbers must be finite")
    if isinstance(value, str) and len(value) > 4000:
        raise ValueError("mapping strings must be <=4000 characters")
    if value is not None and not isinstance(value, str | int | float | bool):
        raise ValueError(f"unsupported mapping type {type(value).__name__}")


__all__ = [
    "CampaignEndpointSpec",
    "ENDPOINT_CONTRACT_VERSION",
    "EndpointAttainmentAssessment",
    "EndpointAttainmentStatus",
    "EndpointComparison",
    "EndpointCriterion",
    "EndpointCriterionAssessment",
    "ExecutionPlanRef",
    "INTERVENTION_CONTRACT_VERSION",
    "INTERVENTION_PORTFOLIO_CONTRACT_VERSION",
    "InterventionConstraint",
    "InterventionConstraintType",
    "InterventionFeasibilityAssessment",
    "InterventionFeasibilityStatus",
    "InterventionUtilityBreakdown",
    "MaterialSpec",
    "MeasurementProtocolSpec",
    "ScientificIntervention",
    "ScientificInterventionPortfolio",
    "SynthesisRouteSpec",
]
