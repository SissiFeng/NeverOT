# A-Priori-Freezing Benchmark

This benchmark is a simulated promotion gate for HELIOS campaign-control
mechanisms. It does not represent physical-laboratory validation and it must not
be used to claim hardware safety, instrument portability, or causal scientific
discovery.

## Operational definition

An **a-priori freeze** occurs when a campaign cannot revise one or more of the
following after new evidence invalidates the initial choice:

1. the optimization metric or its relationship to the scientific endpoint;
2. the admissible action space;
3. the experimental route or execution cost model;
4. the decision policy used to select the next experiment.

A pathology event records the point at which an initial assumption becomes
invalid. A response is credited only when a predeclared, observable mechanism
changes subsequent selection. Event records and backend decision evidence are
stored separately, so a benchmark cannot infer adaptation from a score change
alone.

## Compared decision levels

The study uses four deliberately different scopes:

| Method | Authority represented by the benchmark |
|---|---|
| `predictor_ranker` | Rank a fixed candidate pool by a deterministic predictor; no acquisition function |
| `gp_backend` | Fixed Gaussian-process Bayesian optimization |
| `agent_recommender` | Deterministic recommendation heuristic; no execution or campaign authority and no live LLM |
| `helios_full` | Benchmark strategy router with observable endpoint correction, failure memory, and constraint guards |

`capability_manifest.json` records which capabilities are active, disabled by an
ablation, shadow-only, or not modelled for every method. In particular,
`ScientificIntervention` ranking and distributional failure attribution remain
shadow-only, while physical execution is not modelled.

## Controlled pathologies

The continuous study includes a clean negative control, spatial execution
failure, a bounded instrument outage, proxy-gap shift, objective shift, noise
drift, and censoring. The route study treats a categorical synthesis route as an
action and charges an observed cost when that route changes.

The simulator always retains an untouched raw objective as a common regret
ruler. Selected observation-stage pathologies also expose a synthetic endpoint
channel with `endpoint_observed=1`. HELIOS may use that channel only after a
successful, quality-controlled evaluation. Failed executions are never replaced
with simulator truth. A physical campaign would need to supply the corresponding
independently measured endpoint; this benchmark does not prove that such a
measurement is available.

Only failures carrying `failure_region_applicable=1` may update the learned
parameter-space failure region. Spatial failures set this evidence flag;
instrument outages do not. Outages still contribute to failed-experiment and
recovery metrics, but they cannot condemn the tested composition.

## System-level endpoints

Artifacts include endpoint-attainment rate, uncensored and budget-censored
evaluations to target, failed experiments, simulated decision-to-outcome time,
observed resource cost, observed human interventions, recovery success,
recovery efficiency, adaptation lag, dynamic regret, epoch-local regret, and
decision quality. Missing physical quantities remain null rather than being
reported as zero.

Comparisons are paired by seed under identical disturbance definitions. The
study uses paired bootstrap confidence intervals and Holm correction within
predeclared comparison families. Positive `mean_reference_advantage` always
means the declared reference method performed better, regardless of metric
direction.

## Reproduction

Run the continuous pathology study:

```bash
uv run --frozen --extra dev python -m benchmarks.methods pathology-study \
  --study-config benchmarks/methods/configs/studies/a_priori_freezing_continuous_v1.yaml \
  --output-dir benchmark_results/a_priori_freezing
```

Run the route-as-action study:

```bash
uv run --frozen --extra dev python -m benchmarks.methods pathology-study \
  --study-config benchmarks/methods/configs/studies/a_priori_freezing_route_v1.yaml \
  --output-dir benchmark_results/a_priori_freezing
```

Each content-addressed study directory contains the full matrix, environment
provenance, capability manifest, raw traces, ground-truth event ledgers,
per-cell metrics, paired comparisons, and paper-facing tables. A dirty worktree
is recorded in the manifest and should not be treated as publication evidence.
The study identifier includes the commit, dirty-tree fingerprint, dependency
lock, Python version, pathology schema, matrix, and metric configuration.

## Interpretation boundary

Clean-cell parity is a required negative control. A capability is not promoted
because its trace is complete or its switch is exercised. Promotion requires a
predeclared outcome improvement in the pathology family governed by that
mechanism, without unacceptable clean-cell regression. A study that ties the
corresponding ablation is evidence that the mechanism has not yet demonstrated
incremental value.
