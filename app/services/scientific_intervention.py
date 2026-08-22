"""Pure builders and endpoint evaluation for scientific interventions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.contracts.scientific_intervention import (
    CampaignEndpointSpec,
    EndpointAttainmentAssessment,
    EndpointAttainmentStatus,
    EndpointComparison,
    EndpointCriterion,
    EndpointCriterionAssessment,
    ExecutionPlanRef,
    InterventionConstraint,
    InterventionFeasibilityAssessment,
    InterventionUtilityBreakdown,
    MaterialSpec,
    MeasurementProtocolSpec,
    ScientificIntervention,
    SynthesisRouteSpec,
)


def build_intervention_utility(
    *,
    scientific_value: float,
    information_value: float,
    failure_penalty: float,
    execution_cost_penalty: float,
    execution_time_penalty: float,
    expected_endpoint_impact: float | None = None,
    expected_information_gain: float | None = None,
    weights: Mapping[str, float] | None = None,
    rationale: str,
) -> InterventionUtilityBreakdown:
    """Build an auditable execution-aware utility decomposition."""
    utility_weights = {
        "scientific": 1.0,
        "information": 1.0,
        "failure": 1.0,
        "execution_cost": 1.0,
        "execution_time": 1.0,
        **dict(weights or {}),
    }
    total = (
        utility_weights["scientific"] * float(scientific_value)
        + utility_weights["information"] * float(information_value)
        - utility_weights["failure"] * float(failure_penalty)
        - utility_weights["execution_cost"] * float(execution_cost_penalty)
        - utility_weights["execution_time"] * float(execution_time_penalty)
    )
    return InterventionUtilityBreakdown(
        scientific_value=scientific_value,
        information_value=information_value,
        failure_penalty=failure_penalty,
        execution_cost_penalty=execution_cost_penalty,
        execution_time_penalty=execution_time_penalty,
        total_utility=total,
        expected_endpoint_impact=expected_endpoint_impact,
        expected_information_gain=expected_information_gain,
        weights=dict(weights or {}),
        rationale=rationale,
    )


def build_scientific_intervention(
    *,
    campaign_id: str,
    round_index: int,
    candidate_index: int,
    endpoint: CampaignEndpointSpec,
    scientific_target: str,
    design_parameters: Mapping[str, Any],
    synthesis_route: SynthesisRouteSpec,
    measurement_protocol: MeasurementProtocolSpec,
    required_instruments: tuple[str, ...],
    feasibility: InterventionFeasibilityAssessment,
    utility: InterventionUtilityBreakdown,
    material: MaterialSpec | None = None,
    decision_trace_id: str | None = None,
    execution_plan: ExecutionPlanRef | None = None,
    safety_constraints: tuple[InterventionConstraint, ...] = (),
    provenance: Mapping[str, Any] | None = None,
    created_at: datetime | None = None,
) -> ScientificIntervention:
    """Bind a candidate to endpoint, route, measurement, and execution evidence."""
    identity_payload = {
        "campaign_id": campaign_id,
        "round_index": round_index,
        "candidate_index": candidate_index,
        "endpoint": endpoint.model_dump(mode="json"),
        "scientific_target": scientific_target,
        "material": material.model_dump(mode="json") if material else None,
        "design_parameters": dict(design_parameters),
        "synthesis_route": synthesis_route.model_dump(mode="json"),
        "measurement_protocol": measurement_protocol.model_dump(mode="json"),
        "required_instruments": list(required_instruments),
        "execution_plan": execution_plan.model_dump(mode="json") if execution_plan else None,
        "safety_constraints": [item.model_dump(mode="json") for item in safety_constraints],
        "feasibility": feasibility.model_dump(mode="json"),
        "utility": utility.model_dump(mode="json"),
        "provenance": dict(provenance or {}),
    }
    canonical = json.dumps(
        identity_payload,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    intervention_id = f"si-{hashlib.sha256(canonical).hexdigest()[:24]}"
    return ScientificIntervention(
        intervention_id=intervention_id,
        campaign_id=campaign_id,
        round_index=round_index,
        candidate_index=candidate_index,
        decision_trace_id=decision_trace_id,
        endpoint=endpoint.model_copy(deep=True),
        scientific_target=scientific_target,
        material=material.model_copy(deep=True) if material else None,
        design_parameters=dict(design_parameters),
        synthesis_route=synthesis_route.model_copy(deep=True),
        measurement_protocol=measurement_protocol.model_copy(deep=True),
        required_instruments=tuple(required_instruments),
        execution_plan=execution_plan.model_copy(deep=True) if execution_plan else None,
        safety_constraints=tuple(item.model_copy(deep=True) for item in safety_constraints),
        feasibility=feasibility.model_copy(deep=True),
        utility=utility.model_copy(deep=True),
        provenance=dict(provenance or {}),
        shadow_only=True,
        created_at=created_at or datetime.now(UTC),
    )


def evaluate_endpoint_attainment(
    endpoint: CampaignEndpointSpec,
    *,
    measurements: Mapping[str, float],
    replicate_counts: Mapping[str, int] | None = None,
    confidences: Mapping[str, float] | None = None,
    experiments_used: int = 0,
    elapsed_wall_clock_s: float = 0.0,
    resource_cost: float = 0.0,
    now: datetime | None = None,
) -> EndpointAttainmentAssessment:
    """Evaluate campaign success against endpoint evidence, not a proxy score."""
    replicates = dict(replicate_counts or {})
    confidence_by_metric = dict(confidences or {})
    assessments = tuple(
        _evaluate_criterion(
            criterion,
            measurements=measurements,
            replicate_count=int(replicates.get(criterion.metric_name, 0)),
            confidence=confidence_by_metric.get(criterion.metric_name),
        )
        for criterion in endpoint.criteria
    )
    required = [
        assessment for criterion, assessment in zip(endpoint.criteria, assessments, strict=True) if criterion.required
    ]
    attained = bool(required) and all(item.passed is True for item in required)
    exhausted = _exhausted_budgets(
        endpoint,
        experiments_used=experiments_used,
        elapsed_wall_clock_s=elapsed_wall_clock_s,
        resource_cost=resource_cost,
    )
    if attained:
        status = EndpointAttainmentStatus.ATTAINED
        rationale = "All required scientific endpoint criteria were satisfied."
    elif exhausted:
        status = EndpointAttainmentStatus.BUDGET_EXHAUSTED
        rationale = "The scientific endpoint was not attained before a campaign budget was exhausted."
    elif any(item.passed is None for item in required):
        status = EndpointAttainmentStatus.INSUFFICIENT_EVIDENCE
        rationale = "Required endpoint evidence is missing or lacks replication/confidence."
    else:
        status = EndpointAttainmentStatus.NOT_ATTAINED
        rationale = "At least one required scientific endpoint criterion was not satisfied."
    return EndpointAttainmentAssessment(
        endpoint_id=endpoint.endpoint_id,
        status=status,
        attained=attained,
        criteria=assessments,
        experiments_used=experiments_used,
        elapsed_wall_clock_s=elapsed_wall_clock_s,
        resource_cost=resource_cost,
        exhausted_budgets=exhausted,
        assessed_at=now or datetime.now(UTC),
        rationale=rationale,
    )


def _evaluate_criterion(
    criterion: EndpointCriterion,
    *,
    measurements: Mapping[str, float],
    replicate_count: int,
    confidence: float | None,
) -> EndpointCriterionAssessment:
    observed = measurements.get(criterion.metric_name)
    if observed is None:
        return EndpointCriterionAssessment(
            criterion_id=criterion.criterion_id,
            metric_name=criterion.metric_name,
            replicate_count=replicate_count,
            confidence=confidence,
            passed=None,
            reason="No measurement was recorded for this endpoint metric.",
        )
    if replicate_count < criterion.minimum_replicates:
        return EndpointCriterionAssessment(
            criterion_id=criterion.criterion_id,
            metric_name=criterion.metric_name,
            observed_value=observed,
            replicate_count=replicate_count,
            confidence=confidence,
            passed=None,
            reason=(f"Replicate count {replicate_count} is below required {criterion.minimum_replicates}."),
        )
    if criterion.minimum_confidence is not None and (confidence is None or confidence < criterion.minimum_confidence):
        return EndpointCriterionAssessment(
            criterion_id=criterion.criterion_id,
            metric_name=criterion.metric_name,
            observed_value=observed,
            replicate_count=replicate_count,
            confidence=confidence,
            passed=None,
            reason="Measurement confidence is below the endpoint requirement.",
        )

    value = float(observed)
    if criterion.comparison == EndpointComparison.AT_LEAST:
        passed = value >= float(criterion.threshold)
    elif criterion.comparison == EndpointComparison.AT_MOST:
        passed = value <= float(criterion.threshold)
    elif criterion.comparison == EndpointComparison.BETWEEN:
        passed = float(criterion.lower_bound) <= value <= float(criterion.upper_bound)
    else:
        passed = abs(value - float(criterion.threshold)) <= float(criterion.tolerance)
    return EndpointCriterionAssessment(
        criterion_id=criterion.criterion_id,
        metric_name=criterion.metric_name,
        observed_value=value,
        replicate_count=replicate_count,
        confidence=confidence,
        passed=passed,
        reason="Endpoint criterion satisfied." if passed else "Endpoint criterion not satisfied.",
    )


def _exhausted_budgets(
    endpoint: CampaignEndpointSpec,
    *,
    experiments_used: int,
    elapsed_wall_clock_s: float,
    resource_cost: float,
) -> tuple[str, ...]:
    exhausted: list[str] = []
    if endpoint.max_experiments is not None and experiments_used >= endpoint.max_experiments:
        exhausted.append("max_experiments")
    if endpoint.max_wall_clock_s is not None and elapsed_wall_clock_s >= endpoint.max_wall_clock_s:
        exhausted.append("max_wall_clock_s")
    if endpoint.max_resource_cost is not None and resource_cost >= endpoint.max_resource_cost:
        exhausted.append("max_resource_cost")
    return tuple(exhausted)


__all__ = [
    "build_intervention_utility",
    "build_scientific_intervention",
    "evaluate_endpoint_attainment",
]
