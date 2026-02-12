# Case Study: Log → Decision → Recovery Pipeline

## Scenario: Heater Overshoot during Temperature Ramp

**Goal**: Heat sample to 120°C
**Fault Mode**: Overshoot (heater overshoots target due to thermal inertia)

---

## Phase 1: Raw Telemetry Log

```
[T+0.0s]  OBSERVE   temperature=25.0°C  target=null    heating=false  status=idle
[T+0.5s]  ACTION    set_temperature(120)
[T+1.0s]  OBSERVE   temperature=25.0°C  target=120.0   heating=true   status=heating
[T+2.0s]  OBSERVE   temperature=38.5°C  target=120.0   heating=true   status=heating
[T+3.0s]  OBSERVE   temperature=52.0°C  target=120.0   heating=true   status=heating
[T+4.0s]  OBSERVE   temperature=65.5°C  target=120.0   heating=true   status=heating
[T+5.0s]  OBSERVE   temperature=79.0°C  target=120.0   heating=true   status=heating
[T+6.0s]  OBSERVE   temperature=92.5°C  target=120.0   heating=true   status=heating
[T+7.0s]  OBSERVE   temperature=106.0°C target=120.0   heating=true   status=heating
[T+8.0s]  OBSERVE   temperature=119.5°C target=120.0   heating=true   status=heating
[T+9.0s]  ERROR     temperature=128.0°C target=120.0   OVERSHOOT DETECTED
```

---

## Phase 2: Error Classification

```python
# Input
error = HardwareError(type="overshoot", message="Temperature 128.0°C exceeds target 120.0°C")

# classifier.classify_error(error) →
ErrorProfile(
    unsafe=True,           # Safety violation
    recoverable=True,      # Can recover via degradation
    default_strategy="degrade",
    safe_shutdown_required=True
)
```

**Classification Logic**:
- `overshoot` → Safety violation category
- Technically recoverable (temperature can be reduced)
- But sample may be compromised

---

## Phase 3: Signature Analysis

```python
# Input: Last 8 temperature readings
history = [25.0, 38.5, 52.0, 65.5, 79.0, 92.5, 106.0, 119.5, 128.0]

# policy.analyze_signature(history) →
SignatureResult(
    mode="drift",
    confidence=0.85,
    features={
        "avg_slope": 12.875,      # °C per step (>> 0.5 threshold)
        "variance": 1089.5,
        "sign_changes": 0,        # All positive deltas
        "max_amplitude": 103.0
    }
)
```

**Signature Logic**:
- Consistent upward trend → "drift" mode
- avg_slope (12.875) >> drift_slope_threshold (0.5)
- No oscillation (sign_changes=0)
- High confidence (0.85)

---

## Phase 4: Policy Decision

```python
# Inputs
profile = ErrorProfile(unsafe=True, recoverable=True, ...)
signature = SignatureResult(mode="drift", confidence=0.85)
target = 120.0
retry_count = 0

# policy.decide_recovery(...) →
RecoveryDecision(
    kind="degrade",
    rationale="Unsafe condition (overshoot) with drift signature. Degrading to 110.0°C.",
    actions=[
        Action(name="cool_down", effect="write"),
        Action(name="set_temperature", params={"temperature": 110.0}),
        Action(name="wait", params={"duration": 5.0})
    ],
    sample_status="compromised"
)
```

**Decision Logic**:
1. `unsafe=True` → Enter unsafe preemption path
2. `recoverable=True` + `mode=drift` → Allow degradation
3. `compute_degraded_target(120, "drift")` → 120 - 10 = 110°C
4. `stabilize_time("drift")` → 5s wait

---

## Phase 5: Recovery Execution

```
[T+9.0s]  DECISION  kind=degrade  rationale="Unsafe condition (overshoot) with drift signature"
[T+9.1s]  RECOVERY  >>> Executing 3 Recovery Actions (Guarded)
[T+9.2s]  ACTION    cool_down()
[T+9.5s]  OBSERVE   temperature=126.0°C  heating=false  status=cooling
[T+10.0s] ACTION    set_temperature(110)
[T+10.5s] OBSERVE   temperature=122.0°C  target=110.0   heating=false  status=cooling
[T+11.0s] OBSERVE   temperature=118.0°C  target=110.0   heating=false  status=cooling
[T+12.0s] OBSERVE   temperature=114.0°C  target=110.0   heating=false  status=cooling
[T+13.0s] OBSERVE   temperature=110.5°C  target=110.0   heating=false  status=cooling
[T+14.0s] OBSERVE   temperature=109.8°C  target=110.0   heating=true   status=stabilizing
[T+15.0s] ACTION    wait(5.0)
[T+20.0s] OBSERVE   temperature=110.2°C  target=110.0   heating=false  status=stable
[T+20.1s] COMPLETE  sample_status=compromised  recovery_steps=3  time_to_recover=11s
```

---

## Summary: Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RAW TELEMETRY LOG                                 │
│  [T+9.0s] temperature=128.0°C exceeds target=120.0°C                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ERROR CLASSIFICATION                                │
│  HardwareError(type="overshoot")                                            │
│  ──────────────────────────────────────────────────────────────────────     │
│  → ErrorProfile(unsafe=True, recoverable=True, strategy="degrade")          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SIGNATURE ANALYSIS                                  │
│  history=[25.0, 38.5, 52.0, 65.5, 79.0, 92.5, 106.0, 119.5, 128.0]         │
│  ──────────────────────────────────────────────────────────────────────     │
│  → SignatureResult(mode="drift", confidence=0.85)                           │
│    Features: avg_slope=12.875, sign_changes=0                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          POLICY DECISION                                    │
│  profile.unsafe=True + profile.recoverable=True + mode="drift"              │
│  ──────────────────────────────────────────────────────────────────────     │
│  → RecoveryDecision(                                                        │
│        kind="degrade",                                                      │
│        rationale="Unsafe with drift. Degrading to 110°C",                   │
│        sample_status="compromised"                                          │
│    )                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RECOVERY EXECUTION                                   │
│  Action 1: cool_down()           → Stop heating immediately                 │
│  Action 2: set_temperature(110)  → Set new degraded target                  │
│  Action 3: wait(5.0)             → Stabilization period                     │
│  ──────────────────────────────────────────────────────────────────────     │
│  Result: temperature=110.2°C, stable, sample=compromised                    │
│          Not a retry. Not an abort. Semantic recovery.                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Metrics Captured

| Metric | Value |
|--------|-------|
| `error_type` | overshoot |
| `signature_mode` | drift |
| `signature_confidence` | 0.85 |
| `decision_kind` | degrade |
| `recovery_steps` | 3 |
| `time_to_recover` | 11.0s |
| `sample_status` | compromised |
| `original_target` | 120.0°C |
| `degraded_target` | 110.0°C |
| `max_overshoot` | 128.0°C (+8°C) |

---

## Why This Matters

**Traditional Approach (Retry/Abort)**:
- Retry: Would attempt 120°C again → same overshoot
- Abort: Would destroy experiment entirely

**Our Approach (Semantic Recovery)**:
- Recognized overshoot is recoverable via degradation
- Analyzed drift pattern to choose appropriate strategy
- Preserved sample (compromised but usable)
- Continued experiment at safer temperature

**This is what hierarchical agents need**: an execution layer that understands physical reality.
