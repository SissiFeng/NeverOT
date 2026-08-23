"""Shadow assembly and ranking of endpoint-driven intervention portfolios."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.contracts.scientific_intervention import (
    CampaignEndpointSpec,
    EndpointComparison,
    EndpointCriterion,
    ExecutionPlanRef,
    InterventionConstraint,
    InterventionConstraintType,
    InterventionFeasibilityAssessment,
    InterventionFeasibilityStatus,
    MaterialSpec,
    MeasurementProtocolSpec,
    ScientificIntervention,
    ScientificInterventionPortfolio,
    SynthesisRouteSpec,
)
from app.services.adaptive_campaign_substrate import AdaptiveCampaignSubstrateSnapshot
from app.services.dynamic_action_space import (
    ActionAssessment,
    ActionShadowLabel,
    DynamicActionSpaceSnapshot,
)
from app.services.scientific_intervention import (
    build_intervention_utility,
    build_scientific_intervention,
)


@dataclass(frozen=True)
class ScientificInterventionPortfolioBuild:
    """Typed portfolio manifest plus its candidate-order intervention records."""

    portfolio: ScientificInterventionPortfolio
    interventions: tuple[ScientificIntervention, ...]


def derive_campaign_endpoint(
    *,
    objective_kpi: str,
    direction: str,
    target_value: float | None,
    max_rounds: int,
    batch_size: int,
    explicit_endpoint: CampaignEndpointSpec | None = None,
) -> CampaignEndpointSpec | None:
    """Return the explicit endpoint or a bounded legacy-target projection."""
    if explicit_endpoint is not None:
        return explicit_endpoint.model_copy(deep=True)
    if target_value is None:
        return None
    if direction not in {"maximize", "minimize"}:
        raise ValueError("direction must be 'maximize' or 'minimize'")
    comparison = EndpointComparison.AT_LEAST if direction == "maximize" else EndpointComparison.AT_MOST
    fingerprint = _hash_payload(
        {
            "objective_kpi": objective_kpi,
            "direction": direction,
            "target_value": target_value,
        }
    )[:16]
    return CampaignEndpointSpec(
        endpoint_id=f"legacy-target-{fingerprint}",
        statement=(
            f"Reach {objective_kpi} {comparison.value.replace('_', ' ')} "
            f"{target_value} within the declared campaign experiment budget."
        ),
        criteria=(
            EndpointCriterion(
                criterion_id=f"target-{fingerprint}",
                metric_name=objective_kpi,
                comparison=comparison,
                threshold=target_value,
                minimum_replicates=1,
                rationale="Projected from the legacy orchestrator target_value field.",
            ),
        ),
        max_experiments=max(1, int(max_rounds) * int(batch_size)),
        metadata={"source": "orchestrator_legacy_target"},
    )


def synthesis_route_from_campaign(
    *,
    route_graph: Mapping[str, Any] | None,
    active_node_id: str | None,
    protocol_pattern_id: str,
) -> tuple[SynthesisRouteSpec, dict[str, Any]]:
    """Resolve the active HELIOS-owned route into a typed route record."""
    graph = dict(route_graph or {})
    node = next(
        (
            dict(item)
            for item in graph.get("nodes", []) or []
            if isinstance(item, dict) and str(item.get("node_id")) == str(active_node_id)
        ),
        {},
    )
    route_id = str(active_node_id or node.get("node_id") or "campaign-default")
    route_name = str(node.get("label") or node.get("name") or route_id)
    raw_process = node.get("process_parameters")
    process_parameters = dict(raw_process) if isinstance(raw_process, dict) else {}
    if protocol_pattern_id:
        process_parameters.setdefault("protocol_pattern_id", protocol_pattern_id)
    required_capabilities = tuple(
        sorted(
            {str(value) for value in node.get("required_capabilities", []) or [] if value is not None and str(value)}
        )
    )
    route = SynthesisRouteSpec(
        route_id=route_id,
        route_name=route_name,
        location=_optional_text(node.get("location")),
        process_parameters=process_parameters,
        required_capabilities=required_capabilities,
    )
    evidence = {
        key: node[key]
        for key in (
            "expected_cost",
            "expected_duration_s",
            "safety_risk",
            "node_id",
            "label",
        )
        if key in node
    }
    return route, evidence


def measurement_protocol_for_endpoint(
    endpoint: CampaignEndpointSpec,
    *,
    protocol_id: str | None = None,
    instrument_ids: Sequence[str] = (),
    replicates: int | None = None,
) -> MeasurementProtocolSpec:
    """Build the measurement binding that covers every endpoint metric."""
    metric_names = tuple(dict.fromkeys(item.metric_name for item in endpoint.criteria))
    required_replicates = max(item.minimum_replicates for item in endpoint.criteria)
    chosen_protocol = (
        protocol_id
        or (endpoint.validation_protocol_ids[0] if endpoint.validation_protocol_ids else None)
        or f"{endpoint.endpoint_id}-measurement"
    )
    return MeasurementProtocolSpec(
        protocol_id=chosen_protocol,
        metric_names=metric_names,
        instrument_ids=tuple(dict.fromkeys(str(item) for item in instrument_ids)),
        replicates=max(required_replicates, int(replicates or 1)),
        metadata={"endpoint_id": endpoint.endpoint_id},
    )


def constraints_from_policy(
    policy_snapshot: Mapping[str, Any] | None,
) -> tuple[InterventionConstraint, ...]:
    """Parse only the explicit intervention-constraint list from policy."""
    constraints: list[InterventionConstraint] = []
    raw_constraints = dict(policy_snapshot or {}).get("scientific_intervention_constraints", [])
    if not isinstance(raw_constraints, list):
        raise ValueError("scientific_intervention_constraints must be a list")
    for raw in raw_constraints:
        if not isinstance(raw, dict):
            raise ValueError("scientific intervention constraints must be objects")
        constraints.append(
            InterventionConstraint(
                constraint_id=str(raw.get("constraint_id") or ""),
                constraint_type=InterventionConstraintType(raw.get("constraint_type", "safety")),
                statement=str(raw.get("statement") or ""),
                hard=bool(raw.get("hard", True)),
                source=str(raw.get("source") or "campaign_policy"),
            )
        )
    return tuple(constraints)


def build_campaign_intervention_portfolio(
    *,
    campaign_id: str,
    round_index: int,
    decision_trace_id: str,
    objective_kpi: str,
    direction: str,
    target_value: float | None,
    max_rounds: int,
    batch_size: int,
    explicit_endpoint: CampaignEndpointSpec | None,
    candidates: Sequence[Mapping[str, Any]],
    route_graph: Mapping[str, Any] | None,
    active_experimental_node_id: str | None,
    experimental_route_decision: Mapping[str, Any] | None,
    protocol_template: Mapping[str, Any],
    protocol_pattern_id: str,
    adaptive_campaign_snapshot: AdaptiveCampaignSubstrateSnapshot | None,
    candidate_evidence: Sequence[Mapping[str, Any]],
    available_capabilities: Sequence[str] | None,
    policy_snapshot: Mapping[str, Any] | None,
    created_at: datetime | None = None,
) -> ScientificInterventionPortfolioBuild | None:
    """Adapt one orchestrator round into the pure portfolio builder."""
    endpoint = derive_campaign_endpoint(
        objective_kpi=objective_kpi,
        direction=direction,
        target_value=target_value,
        max_rounds=max_rounds,
        batch_size=batch_size,
        explicit_endpoint=explicit_endpoint,
    )
    if endpoint is None:
        return None

    policy = dict(policy_snapshot or {})
    route, route_evidence = synthesis_route_from_campaign(
        route_graph=route_graph,
        active_node_id=active_experimental_node_id,
        protocol_pattern_id=protocol_pattern_id,
    )
    route_decision = dict(experimental_route_decision or {})
    route_evidence.update(
        {
            key: route_decision[key]
            for key in (
                "active_node_id",
                "selected_node_id",
                "execution_allowed",
                "applied",
                "changed",
                "reason",
            )
            if key in route_decision
        }
    )
    measurement_protocol = measurement_protocol_for_endpoint(
        endpoint,
        protocol_id=_optional_policy_text(policy, "measurement_protocol_id"),
        instrument_ids=_policy_string_list(policy, "measurement_instrument_ids"),
        replicates=_optional_policy_int(policy, "measurement_replicates"),
    )
    action_space = (
        adaptive_campaign_snapshot.dynamic_action_space_snapshot if adaptive_campaign_snapshot is not None else None
    )
    snapshot_metadata = dict(adaptive_campaign_snapshot.metadata) if adaptive_campaign_snapshot is not None else {}
    capabilities_source = snapshot_metadata.get("available_capabilities_source")
    capability_inventory_known = bool(available_capabilities is not None or capabilities_source == "campaign_deck")
    capabilities = (
        list(available_capabilities)
        if available_capabilities is not None
        else (list(action_space.available_capabilities) if action_space is not None else None)
    )
    raw_weights = policy.get("scientific_intervention_utility_weights")
    if raw_weights is not None and not isinstance(raw_weights, dict):
        raise ValueError("scientific_intervention_utility_weights must be an object")
    return build_scientific_intervention_portfolio(
        campaign_id=campaign_id,
        round_index=round_index,
        decision_trace_id=decision_trace_id,
        endpoint=endpoint,
        candidates=candidates,
        synthesis_route=route,
        measurement_protocol=measurement_protocol,
        protocol_template=protocol_template,
        protocol_pattern_id=protocol_pattern_id,
        action_space=action_space,
        available_capabilities=capabilities,
        capability_inventory_known=capability_inventory_known,
        candidate_evidence=candidate_evidence,
        route_evidence=route_evidence,
        safety_constraints=constraints_from_policy(policy),
        material_composition_keys=_policy_string_list(
            policy,
            "material_composition_keys",
        ),
        material_id=_optional_policy_text(policy, "material_id"),
        utility_weights=dict(raw_weights or {}),
        recommendation_count=_optional_policy_int(
            policy,
            "scientific_intervention_recommendation_count",
        ),
        created_at=created_at,
    )


def build_scientific_intervention_portfolio(
    *,
    campaign_id: str,
    round_index: int,
    decision_trace_id: str,
    endpoint: CampaignEndpointSpec,
    candidates: Sequence[Mapping[str, Any]],
    synthesis_route: SynthesisRouteSpec,
    measurement_protocol: MeasurementProtocolSpec,
    protocol_template: Mapping[str, Any],
    protocol_pattern_id: str = "",
    action_space: DynamicActionSpaceSnapshot | None = None,
    available_capabilities: Sequence[str] | None = None,
    capability_inventory_known: bool = True,
    candidate_evidence: Sequence[Mapping[str, Any]] = (),
    route_evidence: Mapping[str, Any] | None = None,
    safety_constraints: Sequence[InterventionConstraint] = (),
    material_composition_keys: Sequence[str] = (),
    material_id: str | None = None,
    utility_weights: Mapping[str, float] | None = None,
    recommendation_count: int | None = None,
    created_at: datetime | None = None,
) -> ScientificInterventionPortfolioBuild:
    """Assemble and rank interventions without mutating the live candidate order."""
    if not candidates:
        raise ValueError("an intervention portfolio requires at least one candidate")
    timestamp = created_at or datetime.now(UTC)
    action_names = _protocol_action_names(protocol_template)
    matched_actions = _matched_action_assessments(action_space, action_names)
    route_context = dict(route_evidence or {})
    required_instruments = _required_instruments(
        synthesis_route=synthesis_route,
        measurement_protocol=measurement_protocol,
        matched_actions=matched_actions,
    )
    evidence_by_candidate = _candidate_evidence_index(candidate_evidence)

    interventions: list[ScientificIntervention] = []
    for candidate_index, raw_candidate in enumerate(candidates):
        candidate = dict(raw_candidate)
        evidence = evidence_by_candidate.get(_canonical(candidate), {})
        feasibility = _assess_feasibility(
            action_space=action_space,
            available_capabilities=available_capabilities,
            capability_inventory_known=capability_inventory_known,
            matched_actions=matched_actions,
            synthesis_route=synthesis_route,
            route_evidence=route_context,
            candidate_evidence=evidence,
        )
        expected_cost = feasibility.expected_cost
        expected_duration_s = feasibility.expected_duration_s
        scientific_value = _first_finite(
            evidence,
            "utility",
            "expected_improvement",
            "objective_opportunity",
            default=0.0,
        )
        information_value = _first_finite(
            evidence,
            "info_gain",
            "uncertainty",
            "novelty",
            default=0.0,
        )
        expected_endpoint_impact = _optional_first_finite(
            evidence,
            "objective_opportunity",
            "expected_improvement",
        )
        expected_information_gain = _optional_first_finite(
            evidence,
            "info_gain",
            "uncertainty",
        )
        utility = build_intervention_utility(
            scientific_value=scientific_value,
            information_value=information_value,
            failure_penalty=feasibility.expected_failure_risk,
            execution_cost_penalty=_bounded_cost(expected_cost),
            execution_time_penalty=_bounded_cost(expected_duration_s / 3600.0),
            expected_endpoint_impact=expected_endpoint_impact,
            expected_information_gain=expected_information_gain,
            weights=utility_weights,
            rationale=(
                "Execution-aware shadow utility combines candidate evidence with "
                "failure risk, route cost, and route duration."
            ),
        )
        material = _material_from_candidate(
            candidate,
            composition_keys=material_composition_keys,
            material_id=material_id,
        )
        execution_plan = _planned_execution_ref(
            campaign_id=campaign_id,
            round_index=round_index,
            candidate_index=candidate_index,
            candidate=candidate,
            synthesis_route=synthesis_route,
            protocol_template=protocol_template,
            protocol_pattern_id=protocol_pattern_id,
            required_instruments=required_instruments,
        )
        interventions.append(
            build_scientific_intervention(
                campaign_id=campaign_id,
                round_index=round_index,
                candidate_index=candidate_index,
                decision_trace_id=decision_trace_id,
                endpoint=endpoint,
                scientific_target=endpoint.statement,
                material=material,
                design_parameters=candidate,
                synthesis_route=synthesis_route,
                measurement_protocol=measurement_protocol,
                required_instruments=required_instruments,
                execution_plan=execution_plan,
                safety_constraints=tuple(safety_constraints),
                feasibility=feasibility,
                utility=utility,
                provenance={
                    "assembler": "scientific_intervention_portfolio.v1",
                    "candidate_evidence": _bounded_candidate_evidence(evidence),
                    "matched_actions": [
                        {
                            "name": action.name,
                            "label": action.label.value,
                            "risk": action.risk,
                            "missing_capabilities": list(action.missing_capabilities),
                        }
                        for action in matched_actions
                    ],
                    "live_candidate_position": candidate_index,
                },
                created_at=timestamp,
            )
        )

    status_priority = {
        InterventionFeasibilityStatus.ELIGIBLE: 0,
        InterventionFeasibilityStatus.UNKNOWN: 1,
        InterventionFeasibilityStatus.BLOCKED: 2,
    }
    ranked = sorted(
        interventions,
        key=lambda item: (
            status_priority[item.feasibility.status],
            -item.utility.total_utility,
            item.candidate_index,
            item.intervention_id,
        ),
    )
    eligible = [item for item in ranked if item.feasibility.status == InterventionFeasibilityStatus.ELIGIBLE]
    count = len(eligible) if recommendation_count is None else max(0, recommendation_count)
    intervention_ids = tuple(item.intervention_id for item in interventions)
    ranked_ids = tuple(item.intervention_id for item in ranked)
    recommended_ids = tuple(item.intervention_id for item in eligible[:count])
    portfolio_payload = {
        "campaign_id": campaign_id,
        "round_index": round_index,
        "decision_trace_id": decision_trace_id,
        "endpoint_id": endpoint.endpoint_id,
        "intervention_ids": intervention_ids,
        "ranked_intervention_ids": ranked_ids,
        "recommended_intervention_ids": recommended_ids,
    }
    portfolio = ScientificInterventionPortfolio(
        portfolio_id=f"sip-{_hash_payload(portfolio_payload)[:24]}",
        campaign_id=campaign_id,
        round_index=round_index,
        decision_trace_id=decision_trace_id,
        endpoint_id=endpoint.endpoint_id,
        intervention_ids=intervention_ids,
        ranked_intervention_ids=ranked_ids,
        recommended_intervention_ids=recommended_ids,
        would_change_order=ranked_ids != intervention_ids,
        rationale=(
            f"Ranked {len(interventions)} intervention(s); {len(eligible)} passed "
            "execution-feasibility gates. Live candidate order remains unchanged."
        ),
        provenance={
            "ranking_policy": "feasibility_then_execution_aware_utility.v1",
            "live_order_preserved": True,
            "action_space_available": action_space is not None,
            "capability_inventory_known": capability_inventory_known,
            "action_names": list(action_names),
            "utility_weights": dict(utility_weights or {}),
        },
        shadow_only=True,
        created_at=timestamp,
    )
    return ScientificInterventionPortfolioBuild(
        portfolio=portfolio,
        interventions=tuple(interventions),
    )


def _assess_feasibility(
    *,
    action_space: DynamicActionSpaceSnapshot | None,
    available_capabilities: Sequence[str] | None,
    capability_inventory_known: bool,
    matched_actions: Sequence[ActionAssessment],
    synthesis_route: SynthesisRouteSpec,
    route_evidence: Mapping[str, Any],
    candidate_evidence: Mapping[str, Any],
) -> InterventionFeasibilityAssessment:
    missing = {capability for action in matched_actions for capability in action.missing_capabilities}
    capability_inventory = (
        set(available_capabilities)
        if available_capabilities is not None
        else set(action_space.available_capabilities if action_space is not None else ())
    )
    if capability_inventory_known and (available_capabilities is not None or action_space is not None):
        missing.update(set(synthesis_route.required_capabilities) - capability_inventory)
    hard_gate_reasons = {
        f"dynamic_action_disabled:{action.name}"
        for action in matched_actions
        if action.label == ActionShadowLabel.PROPOSED_DISABLED
    }
    if route_evidence.get("execution_allowed") is False:
        hard_gate_reasons.add("experimental_route_execution_not_allowed")
    if missing or hard_gate_reasons:
        status = InterventionFeasibilityStatus.BLOCKED
    elif not capability_inventory_known or action_space is None or not matched_actions:
        status = InterventionFeasibilityStatus.UNKNOWN
    else:
        status = InterventionFeasibilityStatus.ELIGIBLE

    risk_values = [action.risk for action in matched_actions]
    route_risk = _optional_first_finite(
        route_evidence,
        "failure_risk",
        "safety_risk",
    )
    candidate_risk = _candidate_failure_risk(candidate_evidence)
    for risk in (route_risk, candidate_risk):
        if risk is not None:
            risk_values.append(max(0.0, min(1.0, risk)))
    if status == InterventionFeasibilityStatus.UNKNOWN:
        risk_values.append(0.5)
    expected_failure_risk = max(risk_values, default=0.0)
    route_cost = _optional_first_finite(route_evidence, "expected_cost")
    action_cost = sum(action.cost or 0.0 for action in matched_actions)
    route_duration = _optional_first_finite(route_evidence, "expected_duration_s")
    action_duration = sum(action.latency or 0.0 for action in matched_actions)
    expected_cost = max(0.0, route_cost if route_cost is not None else action_cost)
    expected_duration_s = max(
        0.0,
        route_duration if route_duration is not None else action_duration,
    )
    evidence = [f"dynamic_action:{action.name}:{action.label.value}" for action in matched_actions]
    if action_space is None:
        evidence.append("dynamic_action_space:unavailable")
    elif not matched_actions:
        evidence.append("dynamic_action_space:no_protocol_action_match")
    if not capability_inventory_known:
        evidence.append("capability_inventory:unknown")
    return InterventionFeasibilityAssessment(
        status=status,
        expected_failure_risk=expected_failure_risk,
        expected_cost=expected_cost,
        expected_duration_s=expected_duration_s,
        missing_capabilities=tuple(sorted(missing)),
        hard_gate_reasons=tuple(sorted(hard_gate_reasons)),
        evidence=tuple(evidence),
    )


def _required_instruments(
    *,
    synthesis_route: SynthesisRouteSpec,
    measurement_protocol: MeasurementProtocolSpec,
    matched_actions: Sequence[ActionAssessment],
) -> tuple[str, ...]:
    values = set(synthesis_route.required_capabilities)
    values.update(measurement_protocol.instrument_ids)
    for action in matched_actions:
        values.update(action.required_capabilities)
    return tuple(sorted(values))


def _protocol_action_names(protocol_template: Mapping[str, Any]) -> tuple[str, ...]:
    steps = protocol_template.get("steps", [])
    if not isinstance(steps, list):
        return ()
    return tuple(
        dict.fromkeys(str(step.get("primitive")) for step in steps if isinstance(step, dict) and step.get("primitive"))
    )


def _matched_action_assessments(
    action_space: DynamicActionSpaceSnapshot | None,
    action_names: Sequence[str],
) -> tuple[ActionAssessment, ...]:
    if action_space is None:
        return ()
    by_name = {item.name: item for item in action_space.assessments}
    return tuple(by_name[name] for name in action_names if name in by_name)


def _candidate_evidence_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        params = row.get("params")
        if isinstance(params, dict):
            result.setdefault(_canonical(params), dict(row))
    return result


def _bounded_candidate_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "source",
        "source_action",
        "generator_backend",
        "expected_improvement",
        "objective_opportunity",
        "uncertainty",
        "novelty",
        "constraint_margin",
        "info_gain",
        "base_utility",
        "delta",
        "redundancy",
        "utility",
        "selected",
        "failure_risk",
        "predicted_failure_risk",
    )
    bounded = {key: value[key] for key in allowed if key in value and _is_json_scalar(value[key])}
    failure_risk = _candidate_failure_risk(value)
    if failure_risk is not None:
        bounded["failure_risk"] = failure_risk
    return bounded


def _candidate_failure_risk(value: Mapping[str, Any]) -> float | None:
    risk = _optional_first_finite(
        value,
        "failure_risk",
        "predicted_failure_risk",
    )
    if risk is not None:
        return risk
    diagnostics = value.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    return _optional_first_finite(
        diagnostics,
        "failure_risk",
        "predicted_failure_risk",
        "failure_probability",
    )


def _material_from_candidate(
    candidate: Mapping[str, Any],
    *,
    composition_keys: Sequence[str],
    material_id: str | None,
) -> MaterialSpec | None:
    composition = {
        key: candidate[key] for key in composition_keys if key in candidate and _is_json_scalar(candidate[key])
    }
    if not composition and material_id is None:
        return None
    return MaterialSpec(material_id=material_id, composition=composition)


def _planned_execution_ref(
    *,
    campaign_id: str,
    round_index: int,
    candidate_index: int,
    candidate: Mapping[str, Any],
    synthesis_route: SynthesisRouteSpec,
    protocol_template: Mapping[str, Any],
    protocol_pattern_id: str,
    required_instruments: Sequence[str],
) -> ExecutionPlanRef:
    payload = {
        "candidate": dict(candidate),
        "protocol_template": dict(protocol_template),
        "protocol_pattern_id": protocol_pattern_id,
        "route_id": synthesis_route.route_id,
    }
    graph_hash = _hash_payload(payload)
    graph_key = _hash_payload(
        {
            "campaign_id": campaign_id,
            "round_index": round_index,
            "candidate_index": candidate_index,
            "graph_hash": graph_hash,
        }
    )[:24]
    return ExecutionPlanRef(
        graph_id=f"planned-{graph_key}",
        graph_hash=graph_hash,
        backend="orchestrator_compiler_pending",
        resource_ids=tuple(required_instruments),
        compiled=False,
    )


def _first_finite(
    values: Mapping[str, Any],
    *keys: str,
    default: float,
) -> float:
    value = _optional_first_finite(values, *keys)
    return default if value is None else value


def _optional_first_finite(
    values: Mapping[str, Any],
    *keys: str,
) -> float | None:
    for key in keys:
        value = values.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number):
                return number
    return None


def _bounded_cost(value: float) -> float:
    bounded = max(0.0, float(value))
    return bounded / (1.0 + bounded)


def _optional_text(value: Any) -> str | None:
    return str(value) if value is not None and str(value) else None


def _policy_string_list(policy: Mapping[str, Any], key: str) -> list[str]:
    raw = policy.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list | tuple):
        raise ValueError(f"{key} must be a list")
    return list(dict.fromkeys(str(item) for item in raw if str(item)))


def _optional_policy_text(policy: Mapping[str, Any], key: str) -> str | None:
    value = policy.get(key)
    return str(value) if value is not None and str(value) else None


def _optional_policy_int(policy: Mapping[str, Any], key: str) -> int | None:
    value = policy.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def _is_json_scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | bool) or (isinstance(value, float) and math.isfinite(value))


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), allow_nan=False, separators=(",", ":"), sort_keys=True)


def _hash_payload(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


__all__ = [
    "ScientificInterventionPortfolioBuild",
    "build_campaign_intervention_portfolio",
    "build_scientific_intervention_portfolio",
    "constraints_from_policy",
    "derive_campaign_endpoint",
    "measurement_protocol_for_endpoint",
    "synthesis_route_from_campaign",
]
