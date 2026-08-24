from __future__ import annotations

import app.optimization  # noqa: F401
import benchmarks.methods.helios_full  # noqa: F401
from app.services.optimization_backends import Observation, get_backend, list_backends
from benchmarks.methods.helios_full import (
    _apply_execution_aware_route_utility,
    _apply_failure_memory,
    _early_stage_anchor_candidates,
    _early_stage_report,
    _observations_for_helios,
    _primary_backend_for_benchmark,
)
from benchmarks.methods.pathologies import RouteSwitchCost, apply_pathology
from benchmarks.methods.problems import get_problem
from benchmarks.methods.runner import run_cell


def test_helios_full_backend_registered():
    assert list_backends()["helios_full"] is True
    assert get_backend("helios_full").name == "helios_full"


def test_helios_full_run_records_effective_backend_history():
    trace = run_cell(get_problem("sphere_2d"), "helios_full", seed=0, budget=6, n_init=2)
    assert trace.error is None
    assert len(trace.best_so_far) == 6
    assert trace.backend_history[0] == "initial_random"
    assert len(trace.backend_history) >= 2


def test_helios_full_filters_early_stage_target_infeasible_range():
    backend = get_backend("helios_full")
    problem = get_problem("early_stage_controllability")

    candidates = backend.suggest(problem.space, 12, [], seed=2)

    assert len(candidates) == 12
    assert all(
        not 84.0 <= float(candidate["target_temp"]) <= 96.0
        for candidate in candidates
    )


def test_helios_full_uses_true_objective_for_objective_uncertainty():
    problem = get_problem("early_stage_objective_uncertainty")
    report = _early_stage_report(problem.space)
    proxy_favored = problem.evaluate(
        {"additive": "fast_yield", "temp": 86.0, "dwell_h": 1.2}
    )
    observations = [
        Observation(
            params={"additive": "fast_yield", "temp": 86.0, "dwell_h": 1.2},
            objective=-proxy_favored.optimizer_value,
            objectives=proxy_favored.observation_objectives(),
        )
    ]

    converted = _observations_for_helios(report, observations)

    assert converted[0].objective == proxy_favored.observation_objectives()[
        "true_objective"
    ]
    assert converted[0].objective < observations[0].objective


def test_helios_full_uses_corrected_objective_for_batch_effect():
    problem = get_problem("early_stage_batch_effect")
    report = _early_stage_report(problem.space)
    biased = problem.evaluate(
        {
            "screen_protocol": "fast_screen",
            "ligand": "L1",
            "temp": 82.0,
            "hold_h": 1.2,
        }
    )
    observations = [
        Observation(
            params={
                "screen_protocol": "fast_screen",
                "ligand": "L1",
                "temp": 82.0,
                "hold_h": 1.2,
            },
            objective=-biased.optimizer_value,
            objectives=biased.observation_objectives(),
        )
    ]

    converted = _observations_for_helios(report, observations)

    assert converted[0].objective == biased.observation_objectives()[
        "corrected_objective"
    ]
    assert converted[0].objective < observations[0].objective


def test_helios_full_uses_independently_observed_endpoint_without_report():
    observation = Observation(
        params={"x1": 0.2, "x2": 0.3},
        objective=-9.0,
        objectives={
            "true_objective": -1.0,
            "observed_objective": -9.0,
            "execution_success": 1.0,
            "qc_passed": 1.0,
            "endpoint_observed": 1.0,
        },
    )

    converted = _observations_for_helios(None, [observation])

    assert converted[0].objective == -1.0


def test_helios_full_does_not_replace_failed_measurement_with_endpoint_ruler():
    observation = Observation(
        params={"x1": 0.2, "x2": 0.3},
        objective=-9.0,
        objectives={
            "true_objective": -1.0,
            "observed_objective": -9.0,
            "execution_success": 0.0,
            "qc_passed": 0.0,
            "endpoint_observed": 1.0,
        },
    )

    converted = _observations_for_helios(None, [observation])

    assert converted[0].objective == observation.objective


def test_helios_full_uses_prior_successful_regions_as_anchors():
    problem = get_problem("early_stage_prior_warm_start")
    report = _early_stage_report(problem.space)

    anchors = _early_stage_anchor_candidates(report, problem.space)

    assert anchors[0] == problem.optimum_x


def test_helios_full_routes_clean_low_dim_benchmark_to_gp():
    problem = get_problem("branin")

    assert _primary_backend_for_benchmark(
        None,
        "built_in",
        problem.space,
    ) == "gp_backend"


# ---------------------------------------------------------------------------
# Ablation variants (backend-owned; consumed by benchmarks.methods.ablation)
# ---------------------------------------------------------------------------


def _observations(n: int) -> list[Observation]:
    return [
        Observation(
            params={"x1": float(i) / n, "x2": 1.0 - float(i) / n},
            objective=-float(i),
            objectives={"execution_success": 1.0},
        )
        for i in range(n)
    ]


def test_backend_variants_all_registered():
    from benchmarks.methods.helios_full import BACKEND_VARIANTS

    backends = list_backends()
    assert set(BACKEND_VARIANTS) == {
        "helios_full",
        "helios_full/no-strategy",
        "helios_full/no-failure-memory",
        "helios_full/no-observation-correction",
        "helios_full/no-constraint-controller",
        "helios_full/no-execution-utility",
    }
    for name in BACKEND_VARIANTS:
        assert backends[name] is True
        assert get_backend(name).name == name


def test_variant_ablation_configs_wired():
    from benchmarks.methods.helios_full import BACKEND_VARIANTS, AblationConfig

    assert BACKEND_VARIANTS["helios_full"] == AblationConfig()
    assert get_backend("helios_full").ablation == AblationConfig()
    assert get_backend("helios_full/no-strategy").ablation.strategy_selection is False
    assert get_backend("helios_full/no-failure-memory").ablation.failure_memory is False
    assert (
        get_backend("helios_full/no-observation-correction").ablation.observation_correction
        is False
    )
    assert (
        get_backend("helios_full/no-constraint-controller").ablation.constraint_controller
        is False
    )
    assert (
        get_backend("helios_full/no-execution-utility").ablation.execution_aware_routing
        is False
    )


def test_execution_aware_route_utility_uses_observed_switch_cost():
    problem = get_problem("mixed_categorical")
    observations = [
        Observation(
            params={"shape": "circle", "x": 0.2},
            objective=-0.09,
            objectives={"true_objective": -0.09},
        ),
        Observation(
            params={"shape": "square", "x": 0.2},
            objective=-3.59,
            objectives={
                "true_objective": -1.59,
                "route_switch_cost": 2.0,
            },
        ),
    ]
    proposed = [
        {"shape": "circle", "x": 0.5},
        {"shape": "square", "x": 0.5},
        {"shape": "triangle", "x": 0.5},
    ]

    selected, evidence = _apply_execution_aware_route_utility(
        proposed,
        problem.space,
        observations,
        n=1,
    )

    assert selected == [{"shape": "square", "x": 0.5}]
    assert evidence == {
        "execution_aware_route_utility_enabled": True,
        "known_route_switch_cost": 2.0,
        "route_candidates_considered": 3,
        "route_candidates_reranked": True,
        "route_parameters": ["shape"],
        "selected_route_switches": 0,
    }


def test_execution_aware_route_utility_is_inert_without_cost_evidence():
    problem = get_problem("mixed_categorical")
    proposed = [
        {"shape": "circle", "x": 0.5},
        {"shape": "square", "x": 0.5},
    ]

    selected, evidence = _apply_execution_aware_route_utility(
        proposed,
        problem.space,
        [],
        n=1,
    )

    assert selected == proposed[:1]
    assert evidence["known_route_switch_cost"] == 0.0
    assert evidence["route_candidates_reranked"] is False


def test_execution_aware_route_utility_is_wired_through_benchmark_loop():
    problem, _ = apply_pathology(
        get_problem("mixed_categorical"),
        [RouteSwitchCost(route_parameter="shape", switching_cost=2.0)],
        seed=0,
    )

    trace = run_cell(problem, "helios_full", seed=0, budget=6, n_init=3)

    assert trace.error is None
    active = [
        evidence
        for evidence in trace.backend_decision_history
        if evidence.get("known_route_switch_cost", 0.0) > 0.0
    ]
    assert active
    assert active[0]["route_candidates_considered"] == 8
    assert active[0]["route_candidates_reranked"] is True

    ablated_problem, _ = apply_pathology(
        get_problem("mixed_categorical"),
        [RouteSwitchCost(route_parameter="shape", switching_cost=2.0)],
        seed=0,
    )
    ablated = run_cell(
        ablated_problem,
        "helios_full/no-execution-utility",
        seed=0,
        budget=6,
        n_init=3,
    )
    full_cost = sum(
        float(row["metadata"].get("resource_cost", 0.0))
        for row in trace.evaluation_history
    )
    ablated_cost = sum(
        float(row["metadata"].get("resource_cost", 0.0))
        for row in ablated.evaluation_history
    )
    assert full_cost < ablated_cost


def test_no_strategy_variant_uses_fixed_primary_backend():
    backend = get_backend("helios_full/no-strategy")
    problem = get_problem("sphere_2d")

    candidates = backend.suggest(problem.space, 2, _observations(10), seed=3)

    assert len(candidates) == 2
    assert backend.last_selected_backend.startswith("fixed_primary:")


def test_variants_never_delegate_to_helios_variants():
    backend = get_backend("helios_full/no-failure-memory")
    problem = get_problem("sphere_2d")

    backend.suggest(problem.space, 2, _observations(10), seed=3)

    assert "helios_full" not in backend.last_selected_backend


def test_no_failure_memory_drops_failed_params_from_snapshot():
    from benchmarks.methods.helios_full import _snapshot_from_observations

    problem = get_problem("sphere_2d")
    failed = Observation(
        params={"x1": 2.0, "x2": 2.0},
        objective=-9.0,
        objectives={
            "execution_success": 0.0,
            "failure_region_applicable": 1.0,
        },
    )
    observations = [*_observations(3), failed]

    snap_with = _snapshot_from_observations(problem.space, observations, {})
    snap_without = _snapshot_from_observations(
        problem.space, observations, {}, include_failed=False
    )

    assert snap_with.failed_params == ({"x1": 2.0, "x2": 2.0},)
    assert snap_without.failed_params == ()


def test_failure_memory_does_not_condemn_parameters_after_instrument_outage():
    problem = get_problem("sphere_2d")
    outage = Observation(
        params={"x1": 2.0, "x2": 2.0},
        objective=-9.0,
        objectives={
            "execution_success": 0.0,
            "failure_region_applicable": 0.0,
        },
    )

    selected, evidence = _apply_failure_memory(
        [{"x1": 2.0, "x2": 2.0}],
        problem.space,
        [outage],
        n=1,
        seed=7,
    )

    assert selected == [{"x1": 2.0, "x2": 2.0}]
    assert evidence["known_failure_points"] == 0


def test_failure_memory_filters_failed_region_and_reports_decision_evidence():
    problem = get_problem("sphere_2d")
    failed = Observation(
        params={"x1": 2.0, "x2": 2.0},
        objective=-9.0,
        objectives={
            "execution_success": 0.0,
            "failure_region_applicable": 1.0,
        },
    )
    proposed = [
        {"x1": 2.0, "x2": 2.0},
        {"x1": -2.0, "x2": -2.0},
    ]

    selected, evidence = _apply_failure_memory(
        proposed,
        problem.space,
        [failed],
        n=1,
        seed=7,
    )

    assert selected == [{"x1": -2.0, "x2": -2.0}]
    assert evidence == {
        "failure_memory_enabled": True,
        "known_failure_points": 1,
        "failure_prone_proposals_removed": 1,
    }


def test_no_constraint_controller_returns_plain_lhs_on_cold_start():
    from app.services.candidate_gen import sample_lhs

    variant = get_backend("helios_full/no-constraint-controller")
    problem = get_problem("early_stage_controllability")

    candidates = variant.suggest(problem.space, 6, [], seed=5)

    assert candidates == sample_lhs(problem.space, 6, seed=5)
