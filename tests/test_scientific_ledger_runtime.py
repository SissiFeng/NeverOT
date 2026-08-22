from __future__ import annotations

from pathlib import Path

import pytest

from app.services.scientific_ledger_runtime import (
    finalize_scientific_decision,
    record_pending_scientific_decision,
    should_capture_decision_trace,
)
from tests.fixtures.scientific_ledger import decision_trace, scientific_intervention


@pytest.fixture
def runtime_env(monkeypatch, request, tmp_path):
    from app.core.config import get_settings
    from app.core.db import init_db

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "data" / "orchestrator.db"))
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("SCIENTIFIC_LEDGER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setenv("SCIENTIFIC_LEDGER_ENABLED", "true")
    monkeypatch.setenv("SCIENTIFIC_LEDGER_GIT_ENABLED", "false")
    get_settings.cache_clear()
    request.addfinalizer(get_settings.cache_clear)
    init_db()
    return tmp_path


def test_runtime_bridge_records_pending_and_closes_full_accounting(runtime_env):
    from app.services.decision_trajectory import load_trajectories

    trace = decision_trace()
    pending = record_pending_scientific_decision(trace)
    assert pending is not None
    card = Path(pending.campaign_directory) / "rounds/003/decision_003.md"
    assert "status: pending" in card.read_text()

    result = finalize_scientific_decision(
        trace,
        observed_action="propose_candidates",
        observed_backend="bo_mcp",
        candidate_count=4,
        execution_success=True,
        failure_count=1,
        objective_delta=0.2,
        recovery_attempted=True,
        recovery_success=True,
        observations=[{"yield": 0.84}],
        failures=[{"failure_type": "hardware", "root_cause": "pipette offset"}],
        recovery_events=[{"fix": "increase z offset 0.5mm", "result": "pass"}],
    )
    assert result.trajectory_id.startswith("traj-")
    assert result.accounting.reward.recovery_reward == 0.1
    assert result.ledger_result is not None
    assert "status: completed" in card.read_text()
    rows = load_trajectories("campaign-32")
    assert len(rows) == 1
    assert rows[0]["trajectory"]["outcome"]["recovery_success"] is True


def test_runtime_bridge_persists_typed_accounting_when_markdown_disabled(
    runtime_env, monkeypatch
):
    from app.core.config import get_settings
    from app.services.decision_trajectory import load_trajectories

    monkeypatch.setenv("SCIENTIFIC_LEDGER_ENABLED", "false")
    get_settings.cache_clear()
    trace = decision_trace(campaign_id="typed-only", trace_id="typed-only-trace")
    result = finalize_scientific_decision(trace, execution_success=False)
    assert result.ledger_result is None
    assert len(load_trajectories("typed-only")) == 1


def test_runtime_bridge_persists_batch_aware_scientific_interventions(runtime_env):
    from app.services.decision_trajectory import load_trajectories

    trace = decision_trace()
    interventions = [
        scientific_intervention(candidate_index=0),
        scientific_intervention(candidate_index=1),
    ]
    result = finalize_scientific_decision(
        trace,
        observed_action="propose_candidates",
        candidate_count=2,
        execution_success=True,
        interventions=interventions,
    )

    expected_ids = [item.intervention_id for item in interventions]
    assert result.accounting.trace.intervention_ids == expected_ids
    assert result.accounting.outcome.intervention_ids == expected_ids
    assert [
        item.intervention_id for item in result.accounting.interventions
    ] == expected_ids
    assert all(
        item.decision_trace_id == trace.trace_id
        for item in result.accounting.interventions
    )
    stored = load_trajectories(trace.campaign_id)[0]["trajectory"]
    assert [item["intervention_id"] for item in stored["interventions"]] == expected_ids

    assert result.ledger_result is not None
    card = (
        Path(result.ledger_result.campaign_directory)
        / "rounds/003/decision_003.md"
    ).read_text()
    assert "## Scientific Interventions" in card
    assert interventions[0].intervention_id in card
    assert "yield-endpoint" in card
    assert "route-a" in card


def test_runtime_bridge_rejects_intervention_from_another_campaign(runtime_env):
    with pytest.raises(ValueError, match="campaign_id"):
        finalize_scientific_decision(
            decision_trace(),
            interventions=[scientific_intervention(campaign_id="other-campaign")],
        )


def test_runtime_bridge_does_not_drop_prebound_intervention_ids(runtime_env):
    trace = decision_trace().model_copy(
        deep=True,
        update={"intervention_ids": ["si-prebound"]},
    )

    with pytest.raises(ValueError, match="must match the decision trace"):
        finalize_scientific_decision(trace)


def test_runtime_bridge_allows_multiple_routes_for_one_candidate(runtime_env):
    first = scientific_intervention(candidate_index=0)
    route = first.synthesis_route.model_copy(
        update={"route_id": "route-b", "route_name": "alternate synthesis route"}
    )
    second = first.model_copy(
        deep=True,
        update={
            "intervention_id": f"{first.intervention_id}-route-b",
            "synthesis_route": route,
        },
    )

    result = finalize_scientific_decision(
        decision_trace(),
        interventions=[first, second],
    )

    assert [item.candidate_index for item in result.accounting.interventions] == [0, 0]


def test_runtime_finalize_aligns_trace_with_observed_action(runtime_env):
    trace = decision_trace()
    result = finalize_scientific_decision(
        trace,
        observed_action="recover_failure",
        execution_success=False,
        recovery_attempted=True,
        recovery_success=False,
    )

    stored_trace = result.accounting.trace
    assert stored_trace.actual_action == "recover_failure"
    assert stored_trace.comparison["actual_action"] == "recover_failure"
    assert stored_trace.would_change_route is True
    assert result.accounting.outcome.observed_action == "recover_failure"


def test_trace_capture_gate_includes_markdown(runtime_env, monkeypatch):
    from app.core.config import get_settings

    assert should_capture_decision_trace() is True
    monkeypatch.setenv("SCIENTIFIC_LEDGER_ENABLED", "false")
    monkeypatch.setenv("CONTEXTUAL_DECISION_SHADOW_ENABLED", "false")
    get_settings.cache_clear()
    assert should_capture_decision_trace() is False


def test_trace_capture_gate_includes_live_authority(runtime_env, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SCIENTIFIC_LEDGER_ENABLED", "false")
    monkeypatch.setenv("CONTEXTUAL_DECISION_SHADOW_ENABLED", "false")
    monkeypatch.setenv("CAMPAIGN_DECISION_AUTHORITY_ENABLED", "true")
    get_settings.cache_clear()

    assert should_capture_decision_trace() is True
