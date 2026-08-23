from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.scientific_intervention import (
    EndpointComparison,
    InterventionFeasibilityStatus,
)
from app.services.campaign_mode import CampaignMode, CampaignModeDecision
from app.services.dynamic_action_space import ActionSpec, build_action_space_snapshot
from app.services.scientific_intervention_portfolio import (
    build_scientific_intervention_portfolio,
    derive_campaign_endpoint,
    measurement_protocol_for_endpoint,
    synthesis_route_from_campaign,
)

_NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _endpoint():
    endpoint = derive_campaign_endpoint(
        objective_kpi="yield",
        direction="maximize",
        target_value=0.9,
        max_rounds=10,
        batch_size=3,
    )
    assert endpoint is not None
    return endpoint


def _action_space(
    *,
    capabilities=("liquid_handler",),
    mode=CampaignMode.BO_OPTIMIZATION,
):
    mode = CampaignModeDecision(
        campaign_id="campaign-portfolio",
        round_index=2,
        mode=mode,
        priority_rank=7,
        reason="optimization mode",
        created_at=_NOW,
    )
    return build_action_space_snapshot(
        mode_decision=mode,
        actions=[
            ActionSpec(
                name="sample.mix",
                kind="experiment",
                base_risk=0.1,
                cost=2.0,
                latency=60.0,
                required_capabilities=["liquid_handler"],
            )
        ],
        available_capabilities=list(capabilities),
        now=_NOW,
    )


def _build(
    *,
    capabilities=("liquid_handler",),
    inventory_known=True,
    mode=CampaignMode.BO_OPTIMIZATION,
):
    endpoint = _endpoint()
    route, route_evidence = synthesis_route_from_campaign(
        route_graph={
            "nodes": [
                {
                    "node_id": "route-ed",
                    "label": "Electrodeposition",
                    "required_capabilities": ["liquid_handler"],
                    "expected_cost": 4.0,
                    "expected_duration_s": 600.0,
                }
            ]
        },
        active_node_id="route-ed",
        protocol_pattern_id="mix-v1",
    )
    return build_scientific_intervention_portfolio(
        campaign_id="campaign-portfolio",
        round_index=2,
        decision_trace_id="trace-portfolio-2",
        endpoint=endpoint,
        candidates=({"x": 0.1}, {"x": 0.2}),
        synthesis_route=route,
        measurement_protocol=measurement_protocol_for_endpoint(endpoint),
        protocol_template={"steps": [{"primitive": "sample.mix"}]},
        protocol_pattern_id="mix-v1",
        action_space=_action_space(capabilities=capabilities, mode=mode),
        available_capabilities=capabilities,
        capability_inventory_known=inventory_known,
        candidate_evidence=(
            {
                "params": {"x": 0.1},
                "source": "bo_mcp",
                "utility": 0.9,
                "info_gain": 0.1,
                "failure_risk": 0.8,
            },
            {
                "params": {"x": 0.2},
                "source": "local",
                "utility": 0.7,
                "info_gain": 0.1,
                "failure_risk": 0.1,
            },
        ),
        route_evidence=route_evidence,
        recommendation_count=1,
        created_at=_NOW,
    )


def test_legacy_target_projects_to_endpoint_native_budget():
    endpoint = _endpoint()

    assert endpoint.criteria[0].comparison == EndpointComparison.AT_LEAST
    assert endpoint.criteria[0].threshold == 0.9
    assert endpoint.max_experiments == 30
    assert endpoint.metadata["source"] == "orchestrator_legacy_target"
    assert (
        derive_campaign_endpoint(
            objective_kpi="yield",
            direction="maximize",
            target_value=None,
            max_rounds=10,
            batch_size=3,
        )
        is None
    )


def test_execution_aware_ranking_can_prefer_second_candidate():
    result = _build()
    first, second = result.interventions

    assert first.candidate_index == 0
    assert second.candidate_index == 1
    assert first.feasibility.expected_failure_risk == 0.8
    assert second.feasibility.expected_failure_risk == 0.1
    assert result.portfolio.ranked_intervention_ids[0] == second.intervention_id
    assert result.portfolio.recommended_intervention_ids == (second.intervention_id,)
    assert result.portfolio.would_change_order is True
    assert result.portfolio.provenance["live_order_preserved"] is True


def test_missing_route_capability_blocks_every_intervention_fail_closed():
    result = _build(capabilities=())

    assert all(item.feasibility.status == InterventionFeasibilityStatus.BLOCKED for item in result.interventions)
    assert all("liquid_handler" in item.feasibility.missing_capabilities for item in result.interventions)
    assert result.portfolio.recommended_intervention_ids == ()


def test_unknown_capability_inventory_is_not_recommended():
    result = _build(inventory_known=False)

    assert all(item.feasibility.status == InterventionFeasibilityStatus.UNKNOWN for item in result.interventions)
    assert result.portfolio.recommended_intervention_ids == ()


def test_dynamic_action_disable_is_a_hard_intervention_gate():
    result = _build(mode=CampaignMode.STOP_RECOMMENDED)

    assert all(item.feasibility.status == InterventionFeasibilityStatus.BLOCKED for item in result.interventions)
    assert all(
        "dynamic_action_disabled:sample.mix" in item.feasibility.hard_gate_reasons for item in result.interventions
    )
    assert result.portfolio.recommended_intervention_ids == ()


def test_portfolio_is_deterministic_json_safe_and_compile_pending():
    first = _build()
    second = _build()

    assert first == second
    assert first.portfolio.portfolio_id.startswith("sip-")
    assert first.interventions[0].execution_plan is not None
    assert first.interventions[0].execution_plan.compiled is False
    dumped = first.portfolio.model_dump(mode="json")
    assert dumped["created_at"].endswith("Z")
