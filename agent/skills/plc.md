---
name: plc-controller
description: "PLC-controlled peristaltic pumps and ultrasonic stirrers via Modbus TCP"
version: "1.0.0"
instrument: plc-controller
resource_id: plc-controller
primitives:
  - name: plc.dispense_ml
    error_class: BYPASS
    safety_class: REVERSIBLE
    params:
      pump: {type: integer, description: "Pump number (1-3)"}
      volume_ml: {type: number, description: "Volume to dispense in mL"}
    description: "Dispense a volume of liquid via peristaltic pump (best-effort)"
    contract:
      preconditions: []
      effects: []
    timeout:
      seconds: 30
      retries: 2
  - name: plc.set_pump_on_timer
    error_class: CRITICAL
    safety_class: CAREFUL
    params:
      pump: {type: integer, description: "Pump number (1-3)"}
      duration_ms: {type: integer, description: "Run duration in milliseconds"}
    description: "Run a pump for an exact duration (timed operation)"
    contract:
      preconditions: []
      effects: []
    timeout:
      seconds: 120
      retries: 1
  - name: plc.set_ultrasonic_on_timer
    error_class: CRITICAL
    safety_class: CAREFUL
    params:
      unit: {type: integer, description: "Ultrasonic unit number (1-2)"}
      duration_ms: {type: integer, description: "Run duration in milliseconds"}
    description: "Run an ultrasonic stirrer for an exact duration"
    contract:
      preconditions: []
      effects: []
    timeout:
      seconds: 120
      retries: 1
---

# PLC Controller — Pumps & Stirrers

The PLC manages bulk fluid operations via Modbus TCP. It controls peristaltic
pumps for electrolyte delivery/rinsing and ultrasonic stirrers for mixing.

## When to Use

Use PLC primitives when the protocol requires:
- Delivering electrolyte solution to electrochemical cells
- Rinsing substrates between deposition cycles
- Agitating solutions during preparation
- Timed fluid operations (pump for X ms)

## Workflow Pattern

Typical electrolyte delivery:
```
plc.set_pump_on_timer (pump=1, duration_ms=5000)   # deliver electrolyte
  -> wait (duration_seconds=2)                       # settle time
  -> plc.set_ultrasonic_on_timer (unit=1, duration_ms=3000)  # mix
```

## Two Dispensing Modes

1. **`plc.dispense_ml`** (REVERSIBLE): Best-effort volume dispensing. The PLC
   estimates pump duration from a calibrated flow rate. If calibration drifts,
   the actual volume may differ. Safe to retry on failure.

2. **`plc.set_pump_on_timer`** (CAREFUL): Exact timed operation. The pump
   runs for precisely the specified duration. Used when timing matters more
   than exact volume (e.g., synchronized with electrochemistry).

## Safety Constraints

- **Maximum duration**: Pumps should not run continuously for more than
  60 seconds without a pause to prevent overheating.
- **Pump numbering**: Only pumps 1-3 are connected. Requesting pump 4+
  will fail.
- **Ultrasonic units**: Only units 1-2 are available.

## Resource Locking

All PLC primitives require the `plc-controller` resource lock.
PLC operations can run in parallel with robot or relay operations.

## Error Behavior

| Primitive | Error Class | Safety Class | On Failure |
|-----------|------------|-------------|------------|
| plc.dispense_ml | BYPASS | REVERSIBLE | Retry (2x), log and continue |
| plc.set_pump_on_timer | CRITICAL | CAREFUL | Retry (1x), then abort |
| plc.set_ultrasonic_on_timer | CRITICAL | CAREFUL | Retry (1x), then abort |

*3 primitives. 1 REVERSIBLE, 2 CAREFUL.*
