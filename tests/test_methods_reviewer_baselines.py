from __future__ import annotations

import benchmarks.methods.__main__  # noqa: F401 - CLI registers benchmark backends
from app.services.candidate_gen import ParameterSpace, SearchDimension
from app.services.optimization_backends import Observation, get_backend


def _space() -> ParameterSpace:
    return ParameterSpace(
        dimensions=(
            SearchDimension(
                param_name="x",
                param_type="number",
                min_value=0.0,
                max_value=1.0,
            ),
            SearchDimension(
                param_name="route",
                param_type="categorical",
                choices=("fast", "stable"),
            ),
        ),
        protocol_template={},
    )


def _observations() -> list[Observation]:
    return [
        Observation(params={"x": 0.0, "route": "fast"}, objective=0.0),
        Observation(params={"x": 0.5, "route": "stable"}, objective=0.5),
        Observation(params={"x": 1.0, "route": "stable"}, objective=1.0),
    ]


def test_predictor_ranker_is_deterministic_and_exploitative() -> None:
    backend = get_backend("predictor_ranker")

    first = backend.suggest(_space(), 2, _observations(), seed=7)
    second = backend.suggest(_space(), 2, _observations(), seed=7)

    assert first == second
    assert len(first) == 2
    assert all(candidate["route"] in {"fast", "stable"} for candidate in first)
    assert all(0.0 <= float(candidate["x"]) <= 1.0 for candidate in first)
    assert max(float(candidate["x"]) for candidate in first) > 0.8


def test_agent_recommender_is_deterministic_and_keeps_valid_candidates() -> None:
    backend = get_backend("agent_recommender")

    first = backend.suggest(_space(), 4, _observations(), seed=11)
    second = backend.suggest(_space(), 4, _observations(), seed=11)

    assert first == second
    assert len(first) == 4
    assert all(candidate["route"] in {"fast", "stable"} for candidate in first)
    assert all(0.0 <= float(candidate["x"]) <= 1.0 for candidate in first)
