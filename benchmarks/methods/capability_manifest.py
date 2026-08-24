"""Versioned live/shadow capability evidence for benchmark methods."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from benchmarks.methods.helios_full import BACKEND_VARIANTS

CapabilityState = Literal[
    "active",
    "disabled_by_ablation",
    "shadow_only",
    "not_modeled",
]


@dataclass(frozen=True)
class BenchmarkCapabilityProfile:
    method: str
    method_level: str
    selection_authority: str
    evidence_scope: str
    capabilities: dict[str, CapabilityState]
    source_modules: tuple[str, ...]


def _baseline_profile(method: str) -> BenchmarkCapabilityProfile:
    levels = {
        "predictor_ranker": "predictor",
        "gp_backend": "bo",
        "agent_recommender": "agent_recommender",
    }
    active = {
        "predictor_ranker": {"prediction_ranking"},
        "gp_backend": {"prediction_ranking", "acquisition_optimization"},
        "agent_recommender": {"candidate_recommendation"},
    }.get(method, set())
    capabilities = {
        name: "active" if name in active else "not_modeled"
        for name in (
            "prediction_ranking",
            "acquisition_optimization",
            "candidate_recommendation",
            "campaign_mode_selection",
            "failure_memory",
            "observation_correction",
            "constraint_controller",
            "execution_aware_routing",
            "scientific_intervention_ranking",
            "distributional_failure_attribution",
            "physical_execution",
        )
    }
    return BenchmarkCapabilityProfile(
        method=method,
        method_level=levels.get(method, "unclassified"),
        selection_authority="candidate_only" if method in levels else "not_classified",
        evidence_scope="simulated_candidate_selection",
        capabilities=capabilities,
        source_modules=("benchmarks.methods.reviewer_baselines",)
        if method in {"predictor_ranker", "agent_recommender"}
        else ("app.services.optimization_backends",),
    )


def _helios_profile(method: str) -> BenchmarkCapabilityProfile:
    config = BACKEND_VARIANTS[method]
    capabilities: dict[str, CapabilityState] = {
        "prediction_ranking": "active",
        "acquisition_optimization": "active",
        "candidate_recommendation": "active",
        "campaign_mode_selection": (
            "active" if config.strategy_selection else "disabled_by_ablation"
        ),
        "failure_memory": (
            "active" if config.failure_memory else "disabled_by_ablation"
        ),
        "observation_correction": (
            "active" if config.observation_correction else "disabled_by_ablation"
        ),
        "constraint_controller": (
            "active" if config.constraint_controller else "disabled_by_ablation"
        ),
        "execution_aware_routing": (
            "active" if config.execution_aware_routing else "disabled_by_ablation"
        ),
        "scientific_intervention_ranking": "shadow_only",
        "distributional_failure_attribution": "shadow_only",
        "physical_execution": "not_modeled",
    }
    return BenchmarkCapabilityProfile(
        method=method,
        method_level="helios",
        selection_authority="benchmark_strategy_router",
        evidence_scope="simulated_pathology_benchmark",
        capabilities=capabilities,
        source_modules=(
            "benchmarks.methods.helios_full",
            "app.services.strategy_selector",
            "app.contracts.scientific_intervention",
            "app.services.failure_attribution",
        ),
    )


def build_capability_manifest(config_names: tuple[str, ...]) -> dict:
    """Return a JSON-safe method capability manifest without hidden defaults."""
    profiles = [
        _helios_profile(name) if name in BACKEND_VARIANTS else _baseline_profile(name)
        for name in config_names
    ]
    return {
        "contract_version": "benchmark_capabilities.v1",
        "interpretation": (
            "active means exercised in candidate selection by this benchmark; "
            "shadow_only means recorded but not allowed to change selection; "
            "not_modeled means the benchmark supplies no evidence for the capability"
        ),
        "methods": [asdict(profile) for profile in profiles],
    }
