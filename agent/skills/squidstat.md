---
name: squidstat-potentiostat
description: "Admiral Instruments Squidstat potentiostat for electrochemical experiments"
version: "1.0.0"
instrument: squidstat
resource_id: squidstat
primitives:
  - name: squidstat.run_experiment
    error_class: CRITICAL
    safety_class: HAZARDOUS
    params:
      experiment_name: {type: string, description: "Name identifying this experiment run"}
      channel: {type: integer, description: "Potentiostat channel (1-4)"}
      elements: {type: array, description: "List of electrochemical technique elements (CV, LSV, EIS, CP, CA, OCV)"}
      num_cycles: {type: integer, optional: true, default: 1, description: "Number of cycles to run"}
      enable_live_plot: {type: boolean, optional: true, default: false, description: "Enable real-time data visualization"}
      csv_filename: {type: string, optional: true, description: "Output CSV filename for data export"}
      snapshot_folder: {type: string, optional: true, description: "Folder for plot snapshots"}
      current_phase: {type: string, optional: true, description: "Current experiment phase label"}
    description: "Run a full electrochemical experiment with specified techniques"
    contract:
      preconditions:
        - "experiment_idle:{channel}"
      effects:
        - "set:experiment_running:{channel}:false"
    timeout:
      seconds: 7200
      retries: 0
  - name: squidstat.get_data
    error_class: BYPASS
    safety_class: INFORMATIONAL
    params: {}
    description: "Retrieve the latest experimental data from the potentiostat"
    contract:
      preconditions: []
      effects: []
    timeout:
      seconds: 10
      retries: 1
  - name: squidstat.save_snapshot
    error_class: BYPASS
    safety_class: INFORMATIONAL
    params:
      phase: {type: string, description: "Experiment phase label"}
      cycle: {type: integer, description: "Cycle number"}
    description: "Save a plot snapshot of the current experiment state"
    contract:
      preconditions: []
      effects: []
    timeout:
      seconds: 10
      retries: 1
  - name: squidstat.reset_plot
    error_class: BYPASS
    safety_class: INFORMATIONAL
    params:
      title: {type: string, optional: true, description: "New plot title"}
    description: "Reset the live plot display for a new experiment"
    contract:
      preconditions: []
      effects: []
    timeout:
      seconds: 5
      retries: 0
---

# Squidstat Potentiostat — Electrochemical Measurements

The Squidstat is the core measurement instrument. It applies controlled
electrical signals to electrochemical cells and records the response,
producing the primary scientific data from each experiment.

## When to Use

Use squidstat primitives when the protocol requires:
- Running cyclic voltammetry (CV) to characterize electrode behavior
- Performing electrochemical impedance spectroscopy (EIS)
- Running chronoamperometry (CA) or chronopotentiometry (CP) for deposition
- Open circuit voltage (OCV) measurements
- Any electrochemical technique that applies voltage/current and records response

## Supported Techniques

The `elements` parameter accepts technique specifications:
- **CV**: Cyclic Voltammetry — sweep voltage, measure current
- **LSV**: Linear Sweep Voltammetry — one-direction voltage sweep
- **EIS**: Electrochemical Impedance Spectroscopy — frequency response
- **CP**: Chronopotentiometry — apply constant current, measure voltage
- **CA**: Chronoamperometry — apply constant voltage, measure current
- **OCV**: Open Circuit Voltage — passive measurement

## Workflow Pattern

Typical electrochemical measurement:
```
relay.switch_to (channel=1)         # select cell
squidstat.reset_plot (title="CV Run 1")  # prepare visualization
  -> squidstat.run_experiment (
       experiment_name="cv_cell1",
       channel=1,
       elements=[{technique: "CV", ...}],
       num_cycles=3,
       csv_filename="cv_cell1.csv"
     )
  -> squidstat.save_snapshot (phase="deposition", cycle=3)
  -> squidstat.get_data
```

## Data Output

Each experiment produces:
- **CSV file**: Time-series data (voltage, current, impedance) automatically
  saved to the configured data directory
- **Plot snapshots**: PNG images of current vs. voltage (or impedance vs. frequency)
- **Artifacts**: Both CSV and PNG files are ingested into the artifact store
  with SHA-256 checksums for provenance tracking

## Safety Constraints

- **One experiment at a time**: The squidstat cannot run multiple experiments
  simultaneously on the same channel.
- **Relay coordination**: Ensure the correct cell is connected via relay
  before starting an experiment.
- **Long-running operations**: Electrochemical experiments can take minutes
  to hours. The worker thread blocks until completion.
- **Qt event loop**: The Squidstat SDK requires a Qt event loop. In the
  real hardware adapter, this runs on a dedicated thread.

## Resource Locking

The `squidstat.run_experiment` primitive requires the `squidstat` resource lock.
Data retrieval and plot operations also require the lock to prevent
concurrent access to the instrument state.

## Error Behavior

| Primitive | Error Class | Safety Class | On Failure |
|-----------|------------|-------------|------------|
| squidstat.run_experiment | CRITICAL | HAZARDOUS | Abort immediately |
| squidstat.get_data | BYPASS | INFORMATIONAL | Retry (1x), log and continue |
| squidstat.save_snapshot | BYPASS | INFORMATIONAL | Retry (1x), log and continue |
| squidstat.reset_plot | BYPASS | INFORMATIONAL | Log and continue |

*4 primitives. 3 INFORMATIONAL, 1 HAZARDOUS.*
