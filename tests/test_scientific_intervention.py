from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.contracts.scientific_intervention import (
    CampaignEndpointSpec,
    EndpointAttainmentStatus,
    EndpointComparison,
    EndpointCriterion,
    InterventionConstraint,
    InterventionConstraintType,
    InterventionFeasibilityAssessment,
    InterventionFeasibilityStatus,
    MaterialSpec,
    MeasurementProtocolSpec,
    SynthesisRouteSpec,
)
from app.services.scientific_intervention import (
    build_intervention_utility,
    build_scientific_intervention,
    evaluate_endpoint_attainment,
)

_NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _endpoint() -> CampaignEndpointSpec:
    return CampaignEndpointSpec(
        endpoint_id="oer-campaign-endpoint",
        statement=(
            "Identify a composition and process route satisfying activity, "
            "stability, and reproducibility within 30 experiments."
        ),
        criteria=(
            EndpointCriterion(
                criterion_id="activity",
                metric_name="overpotential_mv",
                comparison=EndpointComparison.AT_MOST,
                threshold=280.0,
                minimum_replicates=3,
                minimum_confidence=0.9,
                measurement_protocol_id="oer-lsv-v1",
            ),
            EndpointCriterion(
                criterion_id="stability",
                metric_name="retention_fraction",
                comparison=EndpointComparison.AT_LEAST,
                threshold=0.9,
                minimum_replicates=3,
                measurement_protocol_id="oer-stability-v1",
            ),
        ),
        max_experiments=30,
        max_wall_clock_s=30 * 24 * 3600,
        max_resource_cost=5000.0,
        validation_protocol_ids=("oer-lsv-v1", "oer-stability-v1"),
    )


def _intervention():
    utility = build_intervention_utility(
        scientific_value=0.8,
        information_value=0.4,
        failure_penalty=0.2,
        execution_cost_penalty=0.1,
        execution_time_penalty=0.05,
        expected_endpoint_impact=0.3,
        expected_information_gain=0.4,
        weights={"scientific": 1.0, "information": 0.5},
        rationale="Second-best predicted activity but immediately executable.",
    )
    return build_scientific_intervention(
        campaign_id="campaign-oer",
        round_index=4,
        candidate_index=1,
        decision_trace_id="trace-oer-4",
        endpoint=_endpoint(),
        scientific_target="Test whether NiFe route ED meets the campaign endpoint.",
        material=MaterialSpec(
            material_id="nife-37",
            composition={"Ni": 0.7, "Fe": 0.3},
        ),
        design_parameters={"loading_mg_cm2": 0.5},
        synthesis_route=SynthesisRouteSpec(
            route_id="ED",
            route_name="electrodeposition",
            location="electrochemistry-bay-1",
            process_parameters={"potential_v": -1.1, "duration_s": 600},
            required_capabilities=("potentiostat",),
        ),
        measurement_protocol=MeasurementProtocolSpec(
            protocol_id="oer-combined-v1",
            metric_names=("overpotential_mv", "retention_fraction"),
            instrument_ids=("potentiostat-1",),
            controls=("blank", "reference_catalyst"),
            replicates=3,
        ),
        required_instruments=("potentiostat-1",),
        safety_constraints=(
            InterventionConstraint(
                constraint_id="potential-envelope",
                constraint_type=InterventionConstraintType.SAFETY,
                statement="Applied potential must remain within the approved envelope.",
            ),
        ),
        feasibility=InterventionFeasibilityAssessment(
            status=InterventionFeasibilityStatus.ELIGIBLE,
            expected_failure_risk=0.15,
            expected_cost=40.0,
            expected_duration_s=3600,
            evidence=("potentiostat-1 available",),
        ),
        utility=utility,
        provenance={"candidate_source": "bo_mcp", "utility_version": "v1"},
        created_at=_NOW,
    )


def test_intervention_is_deterministic_endpoint_conditioned_and_json_safe():
    first = _intervention()
    second = _intervention()

    assert first == second
    assert first.intervention_id.startswith("si-")
    assert first.endpoint.endpoint_id == "oer-campaign-endpoint"
    assert first.synthesis_route.route_id == "ED"
    assert first.utility.total_utility == pytest.approx(0.65)
    assert first.shadow_only is True
    assert first.model_dump(mode="json")["created_at"].endswith("Z")


def test_intervention_identity_changes_when_physical_route_changes():
    first = _intervention()
    changed = build_scientific_intervention(
        campaign_id=first.campaign_id,
        round_index=first.round_index,
        candidate_index=first.candidate_index,
        decision_trace_id=first.decision_trace_id,
        endpoint=first.endpoint,
        scientific_target=first.scientific_target,
        material=first.material,
        design_parameters=first.design_parameters,
        synthesis_route=first.synthesis_route.model_copy(
            update={"route_id": "TD", "route_name": "thermal decomposition"}
        ),
        measurement_protocol=first.measurement_protocol,
        required_instruments=first.required_instruments,
        safety_constraints=first.safety_constraints,
        feasibility=first.feasibility,
        utility=first.utility,
        provenance=first.provenance,
        created_at=_NOW,
    )

    assert changed.intervention_id != first.intervention_id


def test_intervention_identity_includes_decision_utility_evidence():
    first = _intervention()
    changed_utility = build_intervention_utility(
        scientific_value=0.8,
        information_value=0.5,
        failure_penalty=0.2,
        execution_cost_penalty=0.1,
        execution_time_penalty=0.05,
        expected_endpoint_impact=0.3,
        expected_information_gain=0.5,
        weights={"scientific": 1.0, "information": 0.5},
        rationale="Updated information value after feasibility evidence.",
    )
    changed = build_scientific_intervention(
        campaign_id=first.campaign_id,
        round_index=first.round_index,
        candidate_index=first.candidate_index,
        decision_trace_id=first.decision_trace_id,
        endpoint=first.endpoint,
        scientific_target=first.scientific_target,
        material=first.material,
        design_parameters=first.design_parameters,
        synthesis_route=first.synthesis_route,
        measurement_protocol=first.measurement_protocol,
        required_instruments=first.required_instruments,
        safety_constraints=first.safety_constraints,
        feasibility=first.feasibility,
        utility=changed_utility,
        provenance=first.provenance,
        created_at=_NOW,
    )

    assert changed.intervention_id != first.intervention_id


def test_endpoint_requires_at_least_one_required_criterion():
    criterion = _endpoint().criteria[0].model_copy(update={"required": False})
    with pytest.raises(ValidationError, match="at least one required criterion"):
        CampaignEndpointSpec(
            endpoint_id="optional-only",
            statement="An endpoint cannot consist only of optional evidence.",
            criteria=(criterion,),
        )


def test_blocked_feasibility_requires_explicit_reason():
    with pytest.raises(ValidationError, match="explicit gate reason"):
        InterventionFeasibilityAssessment(
            status=InterventionFeasibilityStatus.BLOCKED,
            expected_failure_risk=0.8,
        )


def test_utility_rejects_unsupported_or_negative_lambda_weights():
    common = {
        "scientific_value": 0.8,
        "information_value": 0.4,
        "failure_penalty": 0.2,
        "execution_cost_penalty": 0.1,
        "execution_time_penalty": 0.05,
        "rationale": "Validate the declared utility policy.",
    }
    with pytest.raises(ValidationError, match="unsupported utility weight"):
        build_intervention_utility(**common, weights={"latency": 2.0})
    with pytest.raises(ValidationError, match="non-negative"):
        build_intervention_utility(**common, weights={"failure": -1.0})


def test_measurement_instruments_must_be_declared_as_required():
    intervention = _intervention()
    invalid = intervention.model_dump(mode="python")
    invalid["required_instruments"] = ()
    with pytest.raises(ValidationError, match="measurement instruments"):
        type(intervention).model_validate(invalid)


def test_measurement_protocol_must_cover_required_endpoint_metrics():
    intervention = _intervention()
    invalid = intervention.model_dump(mode="python")
    invalid["measurement_protocol"]["metric_names"] = ("overpotential_mv",)
    with pytest.raises(ValidationError, match="cover all required endpoint metrics"):
        type(intervention).model_validate(invalid)


def test_endpoint_attainment_requires_all_endpoint_evidence():
    endpoint = _endpoint()
    attained = evaluate_endpoint_attainment(
        endpoint,
        measurements={"overpotential_mv": 270.0, "retention_fraction": 0.93},
        replicate_counts={"overpotential_mv": 3, "retention_fraction": 3},
        confidences={"overpotential_mv": 0.95, "retention_fraction": 0.92},
        experiments_used=12,
        elapsed_wall_clock_s=1000,
        resource_cost=800,
        now=_NOW,
    )
    insufficient = evaluate_endpoint_attainment(
        endpoint,
        measurements={"overpotential_mv": 270.0, "retention_fraction": 0.93},
        replicate_counts={"overpotential_mv": 1, "retention_fraction": 3},
        confidences={"overpotential_mv": 0.95, "retention_fraction": 0.92},
        experiments_used=12,
        now=_NOW,
    )

    assert attained.status == EndpointAttainmentStatus.ATTAINED
    assert attained.attained is True
    assert insufficient.status == EndpointAttainmentStatus.INSUFFICIENT_EVIDENCE
    assert insufficient.attained is False


def test_endpoint_reports_budget_exhaustion_without_claiming_attainment():
    assessment = evaluate_endpoint_attainment(
        _endpoint(),
        measurements={"overpotential_mv": 310.0, "retention_fraction": 0.8},
        replicate_counts={"overpotential_mv": 3, "retention_fraction": 3},
        experiments_used=30,
        now=_NOW,
    )

    assert assessment.status == EndpointAttainmentStatus.BUDGET_EXHAUSTED
    assert assessment.attained is False
    assert assessment.exhausted_budgets == ("max_experiments",)
