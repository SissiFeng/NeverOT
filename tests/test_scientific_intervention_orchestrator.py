from __future__ import annotations

import logging
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.campaign_mode import CampaignMode, CampaignModeDecision
from app.services.dynamic_action_space import ActionSpec, build_action_space_snapshot
from tests.fixtures.scientific_ledger import decision_trace

_NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


class _Settings:
    def __init__(self, *, enabled: bool) -> None:
        self.scientific_intervention_shadow_enabled = enabled


def _adaptive_snapshot():
    mode = CampaignModeDecision(
        campaign_id="campaign-32",
        round_index=3,
        mode=CampaignMode.BO_OPTIMIZATION,
        priority_rank=7,
        reason="optimization mode",
        created_at=_NOW,
    )
    action_space = build_action_space_snapshot(
        mode_decision=mode,
        actions=[ActionSpec(name="log", kind="report", base_risk=0.1)],
        available_capabilities=[],
        now=_NOW,
    )
    return SimpleNamespace(
        dynamic_action_space_snapshot=action_space,
        metadata={"available_capabilities_source": "campaign_deck"},
    )


def _kwargs():
    return {
        "campaign_id": "campaign-32",
        "round_index": 3,
        "decision_trace": decision_trace(),
        "objective_kpi": "yield",
        "direction": "maximize",
        "target_value": 0.9,
        "max_rounds": 10,
        "batch_size": 2,
        "explicit_endpoint": None,
        "candidates": [{"x": 0.1}, {"x": 0.2}],
        "route_graph": {},
        "active_experimental_node_id": None,
        "experimental_route_decision": {},
        "protocol_template": {"steps": [{"primitive": "log"}]},
        "protocol_pattern_id": "",
        "adaptive_campaign_snapshot": _adaptive_snapshot(),
        "candidate_evidence": [
            {"params": {"x": 0.1}, "utility": 0.2},
            {"params": {"x": 0.2}, "utility": 0.8},
        ],
        "available_capabilities": [],
        "policy_snapshot": {
            "scientific_intervention_recommendation_count": 1,
        },
        "now": _NOW,
    }


def test_shadow_hook_builds_portfolio_without_reordering_live_candidates(monkeypatch):
    import app.agents.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_settings", lambda: _Settings(enabled=True))
    kwargs = _kwargs()
    candidates_before = deepcopy(kwargs["candidates"])

    result = orchestrator._maybe_build_scientific_intervention_portfolio(**kwargs)

    assert result is not None
    assert [item.design_parameters for item in result.interventions] == candidates_before
    assert result.portfolio.ranked_intervention_ids[0] == result.interventions[1].intervention_id
    assert result.portfolio.provenance["live_order_preserved"] is True
    assert kwargs["candidates"] == candidates_before


def test_shadow_hook_is_default_off(monkeypatch):
    import app.agents.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_settings", lambda: _Settings(enabled=False))

    assert orchestrator._maybe_build_scientific_intervention_portfolio(**_kwargs()) is None


def test_shadow_hook_requires_endpoint_evidence(monkeypatch, caplog):
    import app.agents.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_settings", lambda: _Settings(enabled=True))
    kwargs = _kwargs()
    kwargs["target_value"] = None

    with caplog.at_level(logging.INFO):
        result = orchestrator._maybe_build_scientific_intervention_portfolio(**kwargs)

    assert result is None
    assert "reason=no_campaign_endpoint" in caplog.text


def test_shadow_hook_invalid_policy_fails_open(monkeypatch, caplog):
    import app.agents.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_settings", lambda: _Settings(enabled=True))
    kwargs = _kwargs()
    kwargs["policy_snapshot"] = {"scientific_intervention_utility_weights": "not-an-object"}

    assert orchestrator._maybe_build_scientific_intervention_portfolio(**kwargs) is None
    assert "preserving live candidate order" in caplog.text
