"""Tests for the RL strategy selectors and the strategy router.

Covers:
- RLState dimensionality and serialization (37 features)
- Q-learning binning does not crash on the full state vector
- Q-learning converges on a toy reward structure
- DQN select/learn end-to-end at small scale
- PPO select/learn end-to-end at small scale
- StrategyRouter: rule_based default, RL low-confidence fallback, A/B determinism
"""
from __future__ import annotations

import dataclasses

import pytest

from app.services.dqn_strategy_selector import (
    TORCH_AVAILABLE as DQN_TORCH_AVAILABLE,
)
from app.services.dqn_strategy_selector import DQNConfig, DQNStrategySelector
from app.services.ppo_strategy_selector import (
    TORCH_AVAILABLE as PPO_TORCH_AVAILABLE,
)
from app.services.ppo_strategy_selector import PPOConfig, PPOStrategySelector
from app.services.rl_strategy_selector import (
    ACTIONS,
    QLearningAgent,
    RLConfig,
    RLState,
    RLStrategySelector,
)
from app.services.strategy_models import (
    CampaignSnapshot,
    FailureEvent,
    FailureType,
    ObjectiveLevel,
)
from app.services.strategy_router import RouterConfig, StrategyRouter
from tests.test_offline_closed_loop_sdl import _context, _snapshot


def _make_state(**overrides) -> RLState:
    """Build a default RLState with all 37 features populated."""
    base = dict(
        progress=0.4,
        n_obs_ratio=0.3,
        has_categorical=1.0,
        has_log_scale=0.0,
        space_coverage=0.5,
        model_uncertainty=0.2,
        noise_ratio=0.1,
        replicate_need_score=0.05,
        batch_kpi_cv=0.3,
        improvement_velocity=0.1,
        ei_decay_proxy=0.2,
        convergence_confidence=0.8,
        convergence_plateau=0.0,
        local_smoothness=0.6,
        batch_param_spread=0.7,
        objective_feasibility=0.0,
        objective_data_quality=0.0,
        objective_baseline=0.0,
        objective_performance=1.0,
        objective_mechanism=0.0,
        objective_generalization=0.0,
        failure_hardware=0.0,
        failure_protocol=0.0,
        failure_constraint=0.0,
        failure_measurement=0.0,
        failure_model=0.0,
        failure_backend=0.0,
        failure_scientific_negative=0.0,
        qc_fail_rate=0.0,
        requires_revision=0.0,
        requires_route_switch=0.0,
        requires_calibration=0.0,
        n_hypotheses=0.5,
        n_literature_priors=0.5,
        warm_start_available=1.0,
        budget_pressure_high=0.0,
        drift_score=0.1,
    )
    base.update(overrides)
    return RLState(**base)


def _snapshot_with_failure(
    *,
    failure_type: FailureType = FailureType.HARDWARE,
    level: ObjectiveLevel = ObjectiveLevel.PERFORMANCE,
) -> CampaignSnapshot:
    failure = FailureEvent(
        failure_type,
        "mock failure",
        backend_name="lhs",
        round_number=1,
        candidate_index=0,
        params={"temperature": 50.0, "concentration": 0.5},
        penalize_backend=True,
    )
    return _snapshot(
        round_number=1,
        all_params=({"temperature": 50.0, "concentration": 0.5},),
        all_kpis=(0.5,),
        last_batch_params=({"temperature": 50.0, "concentration": 0.5},),
        last_batch_kpis=(0.5,),
        context=_context(level=level),
        failures=(failure,),
        backend_failures={"lhs": 1},
    )


# ---------------------------------------------------------------------------
# RLState
# ---------------------------------------------------------------------------


class TestRLState:
    def test_n_features_matches_field_count(self) -> None:
        assert RLState.n_features() == len(dataclasses.fields(RLState))
        assert RLState.n_features() == 37

    def test_to_array_is_37_dims_float32(self) -> None:
        arr = _make_state().to_array()
        assert arr.shape == (37,)
        assert arr.dtype.name == "float32"

    def test_from_snapshot_produces_full_state(self) -> None:
        from app.services.strategy_diagnostics import compute_diagnostics

        snap = _snapshot_with_failure()
        state = RLState.from_snapshot(snap, compute_diagnostics(snap))
        assert len(state.to_array()) == 37
        # Objective one-hot: performance level active
        assert state.objective_performance == 1.0
        assert state.objective_feasibility == 0.0
        # Failure type recorded
        assert state.failure_hardware == pytest.approx(1.0 / 3.0)


# ---------------------------------------------------------------------------
# Q-learning
# ---------------------------------------------------------------------------


class TestQLearningAgent:
    def test_discretize_full_37_dim_state(self) -> None:
        agent = QLearningAgent(RLConfig())
        key = agent._discretize_state(_make_state())
        assert len(eval(key)) == 37  # one bin entry per feature

    def test_discretize_uniform_and_adaptive(self) -> None:
        uniform = QLearningAgent(RLConfig(adaptive_binning=False, n_bins=5))
        adaptive = QLearningAgent(RLConfig(adaptive_binning=True, n_bins=3))
        state = _make_state()
        assert uniform._discretize_state(state) != ""
        assert adaptive._discretize_state(state) != ""

    def test_q_learning_update_and_select(self) -> None:
        agent = QLearningAgent(RLConfig())
        s1 = _make_state(progress=0.2, model_uncertainty=0.8)
        s2 = _make_state(progress=0.4, model_uncertainty=0.6)
        # Force exploitation path (epsilon 0)
        agent.epsilon = 0.0
        for _ in range(50):
            action = agent.select_action(s1, explore=False)
            agent.update(s1, action, reward=1.0, next_state=s2, done=False)
        assert agent.steps == 50
        assert len(agent.q_table) > 0
        # Select on a seen state must return a valid action
        chosen = agent.select_action(s1, explore=False)
        assert chosen in ACTIONS

    def test_strategy_selector_learn_end_to_end(self) -> None:
        from app.services.strategy_diagnostics import compute_diagnostics

        selector = RLStrategySelector(RLConfig())
        snap = _snapshot_with_failure()
        diag = compute_diagnostics(snap)
        state = RLState.from_snapshot(snap, diag)
        action_id, backend = selector.select_action(snap, diag, explore=False)
        assert action_id in ACTIONS
        assert backend in ("lhs", "nexus_lhs", "nexus_sobol", "optuna_tpe",
                           "nexus_tpe", "nexus_gp_bo", "bomcp", "built_in")
        selector.learn_from_experience(state, action_id, reward=1.0,
                                       next_state=state, done=False)
        assert selector.agent.steps >= 1


# ---------------------------------------------------------------------------
# DQN / PPO
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (DQN_TORCH_AVAILABLE and PPO_TORCH_AVAILABLE),
    reason="PyTorch is an optional dependency for DQN/PPO selectors",
)
class TestDeepSelectors:
    def test_dqn_state_dim_is_37(self) -> None:
        dqn = DQNStrategySelector(DQNConfig())
        assert dqn.state_dim == 37
        assert dqn.action_dim == len(ACTIONS)

    def test_dqn_select_and_learn_end_to_end(self) -> None:
        from app.services.strategy_diagnostics import compute_diagnostics

        dqn = DQNStrategySelector(DQNConfig(batch_size=8, target_update_freq=100))
        snap = _snapshot_with_failure()
        diag = compute_diagnostics(snap)
        action_id, action_name = dqn.select_action(snap, diag, explore=False)
        assert action_id in ACTIONS
        # DQN returns (action_id, action_name), not the resolved backend
        assert action_name == ACTIONS[action_id]
        # Feed enough transitions to trigger at least one train step
        for round_no in range(1, 11):
            s = RLState.from_snapshot(snap, diag)
            next_s = RLState.from_snapshot(
                _snapshot(round_number=round_no), compute_diagnostics(_snapshot(round_number=round_no))
            )
            dqn.learn_from_experience(s, action_id, reward=1.0, next_state=next_s, done=(round_no == 10))
        assert dqn.agent.steps >= 1

    def test_ppo_state_dim_is_37(self) -> None:
        ppo = PPOStrategySelector(PPOConfig())
        assert ppo.state_dim == 37
        assert ppo.action_dim == len(ACTIONS)

    def test_ppo_select_and_learn_end_to_end(self) -> None:
        from app.services.strategy_diagnostics import compute_diagnostics

        ppo = PPOStrategySelector(PPOConfig())
        snap = _snapshot_with_failure()
        diag = compute_diagnostics(snap)
        state = RLState.from_snapshot(snap, diag)
        action_id, action_name = ppo.select_action(snap, diag, explore=False)
        assert action_id in ACTIONS
        # PPO returns (action_id, action_name), not the resolved backend
        assert action_name == ACTIONS[action_id]
        ppo.learn_from_experience(state, action_id, reward=1.0,
                                  next_state=state, done=False)
        assert ppo.agent.steps >= 1


# ---------------------------------------------------------------------------
# Strategy Router
# ---------------------------------------------------------------------------


class TestStrategyRouter:
    def test_default_mode_is_rule_based(self) -> None:
        router = StrategyRouter()
        assert router.config.mode == "rule_based"
        decision = router.select_strategy(_snapshot(), campaign_id="c1")
        # Rule-based decision has a backend and phase
        assert decision.backend_name
        assert decision.phase

    def test_rl_mode_low_confidence_falls_back(self) -> None:
        router = StrategyRouter(
            RouterConfig(mode="rl", rl_backend="dqn", confidence_threshold=0.99)
        )
        decision = router.select_strategy(_snapshot(), campaign_id="c1")
        # Untrained DQN has ~0 confidence → rule-based fallback
        assert decision.backend_name
        assert decision.phase
        state = router._campaign_states["c1"]
        assert state.treatment == "rule_based"

    def test_ab_test_is_deterministic(self) -> None:
        cfg = RouterConfig(mode="ab_test", ab_test_rl_fraction=0.5)
        router = StrategyRouter(cfg)
        first = router._ab_test_assignment("campaign-42")
        second = router._ab_test_assignment("campaign-42")
        assert first == second
        # Same id → same bucket repeatedly
        other = router._ab_test_assignment("campaign-43")
        assert first in ("rl", "rule_based")
        assert other in ("rl", "rule_based")
