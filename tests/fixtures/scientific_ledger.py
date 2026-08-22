from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.scientific_intervention import (
    CampaignEndpointSpec,
    EndpointComparison,
    EndpointCriterion,
    InterventionFeasibilityAssessment,
    InterventionFeasibilityStatus,
    MeasurementProtocolSpec,
    SynthesisRouteSpec,
)
from app.services.decision_layer import CampaignDecisionLayer
from app.services.decision_outcome import (
    CampaignDecisionAccounting,
    CampaignDecisionAccountingBuilder,
    CampaignDecisionOutcomeBuilder,
)
from app.services.decision_trace import CampaignDecisionTrace, CampaignDecisionTraceBuilder
from app.services.round_context import CampaignRoundContextBuilder
from app.services.scientific_intervention import (
    build_intervention_utility,
    build_scientific_intervention,
)


def decision_trace(
    *,
    campaign_id: str = "campaign-32",
    round_index: int = 3,
    trace_id: str = "cdt-ledger-003",
) -> CampaignDecisionTrace:
    context = CampaignRoundContextBuilder().build(
        campaign_id=campaign_id,
        round_index=round_index,
        objective_summary={
            "objective_kpi": "yield",
            "direction": "maximize",
            "target_value": 0.9,
        },
        failure_summary={"failure_count": 0},
        nexus_diagnostics={
            "contract_version": "early_stage_system_characterization.v1",
            "entropy_score": 0.21,
            "failure_attribution_distribution": {"pipette_offset": 0.72},
        },
        human_observations=["Meniscus was stable."],
        strategy_selection_result={
            "campaign_intent": "optimize",
            "optimization_mode": "exploit",
            "candidate_generation_backend": "bo_mcp",
            "confidence": 0.83,
            "strategy_trace": {
                "policy_id": "campaign-meta-controller",
                "policy_version": "v4",
                "selected_backend": "bo_mcp",
                "available_actions": [
                    {
                        "name": "validation",
                        "backend_name": "built_in",
                        "expected_improvement": 0.2,
                        "expected_info_gain": 0.82,
                        "risk": 0.1,
                        "utility": 0.77,
                        "reason": "Resolve uncertainty before optimization",
                    },
                    {
                        "name": "exploit",
                        "backend_name": "bo_mcp",
                        "expected_improvement": 0.72,
                        "expected_info_gain": 0.45,
                        "risk": 0.18,
                        "utility": 0.69,
                        "reason": "Stable objective and calibrated model",
                    },
                    {
                        "name": "random",
                        "backend_name": "random",
                        "expected_improvement": 0.1,
                        "expected_info_gain": 0.3,
                        "risk": 0.2,
                        "utility": 0.12,
                        "reason": "Fallback exploration",
                    },
                ],
            },
            "evidence": [
                {
                    "source": "dataset",
                    "kind": "sample_size",
                    "summary": "Dataset size = 18",
                    "weight": 0.8,
                },
                {
                    "source": "optimizer",
                    "kind": "acquisition_confidence",
                    "summary": "Acquisition confidence = 0.83",
                    "weight": 0.83,
                },
            ],
        },
        metadata={"operator_note": "do not expose sk-test-secret-value"},
    )
    plan = CampaignDecisionLayer().decide(context)
    return CampaignDecisionTraceBuilder().build(
        context=context,
        decision_plan=plan,
        actual_stage="candidate_generation",
        actual_action="propose_candidates",
        trace_id=trace_id,
    )


def decision_accounting(
    *,
    campaign_id: str = "campaign-32",
    round_index: int = 3,
    trace_id: str = "cdt-ledger-003",
) -> CampaignDecisionAccounting:
    trace = decision_trace(
        campaign_id=campaign_id,
        round_index=round_index,
        trace_id=trace_id,
    )
    outcome = CampaignDecisionOutcomeBuilder().build(
        trace=trace,
        observed_action="propose_candidates",
        observed_backend="bo_mcp",
        candidate_count=4,
        execution_success=True,
        failure_count=1,
        objective_delta=0.18,
        validation_success=True,
        context_request_fulfilled=True,
        metadata={"authorization": "Bearer super-secret-token"},
    )
    return CampaignDecisionAccountingBuilder().build(trace=trace, outcome=outcome)


def scientific_intervention(
    *,
    campaign_id: str = "campaign-32",
    round_index: int = 3,
    candidate_index: int = 0,
    trace_id: str | None = "cdt-ledger-003",
):
    endpoint = CampaignEndpointSpec(
        endpoint_id="yield-endpoint",
        statement="Reach reproducible yield within the campaign budget.",
        criteria=(
            EndpointCriterion(
                criterion_id="yield",
                metric_name="yield",
                comparison=EndpointComparison.AT_LEAST,
                threshold=0.9,
                minimum_replicates=2,
                measurement_protocol_id="yield-v1",
            ),
        ),
        max_experiments=20,
    )
    utility = build_intervention_utility(
        scientific_value=0.7,
        information_value=0.3,
        failure_penalty=0.1,
        execution_cost_penalty=0.05,
        execution_time_penalty=0.05,
        expected_endpoint_impact=0.2,
        expected_information_gain=0.3,
        rationale="Endpoint value exceeds bounded execution penalties.",
    )
    return build_scientific_intervention(
        campaign_id=campaign_id,
        round_index=round_index,
        candidate_index=candidate_index,
        decision_trace_id=trace_id,
        endpoint=endpoint,
        scientific_target="Test the selected formulation against the yield endpoint.",
        design_parameters={"x": 0.2 + candidate_index * 0.1},
        synthesis_route=SynthesisRouteSpec(
            route_id="route-a",
            route_name="baseline synthesis route",
            process_parameters={"mix_s": 30},
            required_capabilities=("liquid_handler",),
        ),
        measurement_protocol=MeasurementProtocolSpec(
            protocol_id="yield-v1",
            metric_names=("yield",),
            instrument_ids=("reader-1",),
            replicates=2,
        ),
        required_instruments=("reader-1",),
        feasibility=InterventionFeasibilityAssessment(
            status=InterventionFeasibilityStatus.ELIGIBLE,
            expected_failure_risk=0.1,
            expected_cost=5.0,
            expected_duration_s=120.0,
        ),
        utility=utility,
        provenance={"source": "fixture"},
        created_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )
