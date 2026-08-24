"""Benchmark-only baselines for the prediction-to-intervention comparison.

These adapters expose two narrower decision capabilities through the existing
optimization-backend interface.

predictor_ranker fits a deterministic nearest-neighbour mean predictor and
ranks a fixed candidate pool without an acquisition function.

agent_recommender uses a deterministic best-observation neighbourhood heuristic
with occasional exploration. It represents recommendation without campaign
authority, execution feasibility, or outcome attribution; it is not a live LLM.
"""
from __future__ import annotations

import math
import random
from typing import Any

from app.services.candidate_gen import ParameterSpace, SearchDimension, sample_lhs
from app.services.optimization_backends import Observation, register_backend


def _unit_value(value: Any, dimension: SearchDimension) -> float:
    if dimension.choices:
        choices = tuple(dimension.choices)
        try:
            index = choices.index(value)
        except ValueError:
            return 0.5
        return index / max(1, len(choices) - 1)
    if dimension.param_type == "boolean":
        return 1.0 if bool(value) else 0.0
    if dimension.min_value is None or dimension.max_value is None:
        return 0.5
    span = float(dimension.max_value) - float(dimension.min_value)
    if span <= 0.0:
        return 0.5
    return max(0.0, min(1.0, (float(value) - float(dimension.min_value)) / span))


def _vector(params: dict[str, Any], space: ParameterSpace) -> tuple[float, ...]:
    return tuple(_unit_value(params.get(dim.param_name), dim) for dim in space.dimensions)


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def _predicted_mean(
    candidate: dict[str, Any],
    space: ParameterSpace,
    observations: list[Observation],
    *,
    k: int = 5,
) -> float:
    query = _vector(candidate, space)
    neighbours = sorted(
        (
            (_distance(query, _vector(observation.params, space)), observation.objective)
            for observation in observations
        ),
        key=lambda item: item[0],
    )[: min(k, len(observations))]
    weights = [1.0 / max(distance, 1e-12) for distance, _ in neighbours]
    return sum(
        weight * float(objective)
        for weight, (_, objective) in zip(weights, neighbours, strict=True)
    ) / sum(weights)


@register_backend
class PredictorRankerBackend:
    """Prediction-only ranking over a deterministic LHS candidate pool."""

    name = "predictor_ranker"

    def suggest(
        self,
        space: ParameterSpace,
        n: int,
        observations: list[Observation],
        *,
        seed: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if n <= 0:
            return []
        pool = sample_lhs(space, max(128, 32 * n), seed=seed)
        if not observations:
            return pool[:n]
        ranked = sorted(
            pool,
            key=lambda candidate: (
                -_predicted_mean(candidate, space, observations),
                tuple(str(candidate.get(dim.param_name)) for dim in space.dimensions),
            ),
        )
        return ranked[:n]

    @staticmethod
    def is_available() -> bool:
        return True


@register_backend
class AgentRecommenderBackend:
    """Deterministic agent-style recommendation without execution authority."""

    name = "agent_recommender"

    def suggest(
        self,
        space: ParameterSpace,
        n: int,
        observations: list[Observation],
        *,
        seed: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if n <= 0:
            return []
        if not observations:
            return sample_lhs(space, n, seed=seed)

        rng = random.Random(seed)
        best = max(observations, key=lambda observation: observation.objective)
        decay = 1.0 / math.sqrt(len(observations) + 1.0)
        proposals: list[dict[str, Any]] = []
        for _ in range(n):
            if rng.random() < 0.2:
                proposals.extend(sample_lhs(space, 1, seed=rng.randrange(2**31)))
                continue
            candidate = dict(best.params)
            for dimension in space.dimensions:
                name = dimension.param_name
                if dimension.choices:
                    if rng.random() < 0.15:
                        candidate[name] = rng.choice(tuple(dimension.choices))
                    continue
                if dimension.param_type == "boolean":
                    if rng.random() < 0.15:
                        candidate[name] = not bool(candidate.get(name, False))
                    continue
                if dimension.min_value is None or dimension.max_value is None:
                    continue
                lower = float(dimension.min_value)
                upper = float(dimension.max_value)
                span = upper - lower
                value = float(candidate.get(name, (lower + upper) / 2.0))
                proposed = max(
                    lower,
                    min(upper, value + rng.gauss(0.0, 0.15 * decay) * span),
                )
                candidate[name] = (
                    int(round(proposed))
                    if dimension.param_type == "integer"
                    else proposed
                )
            proposals.append(candidate)
        return proposals

    @staticmethod
    def is_available() -> bool:
        return True
