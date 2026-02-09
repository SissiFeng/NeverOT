---
name: relay-controller
description: "USB 16-channel relay board for electrode and cell switching"
version: "1.0.0"
instrument: relay-controller
resource_id: relay-controller
primitives:
  - name: relay.set_channel
    error_class: BYPASS
    safety_class: REVERSIBLE
    params:
      channel: {type: integer, description: "Channel number (1-16)"}
      state: {type: boolean, description: "true = ON, false = OFF"}
    description: "Set a specific relay channel on or off"
    contract:
      preconditions: []
      effects:
        - "set:active_relay_channel:{channel}"
    timeout:
      seconds: 5
      retries: 3
  - name: relay.switch_to
    error_class: BYPASS
    safety_class: REVERSIBLE
    params:
      channel: {type: integer, description: "Channel number to activate (others in group deactivated)"}
    description: "Activate one channel and deactivate others in the same group"
    contract:
      preconditions: []
      effects:
        - "set:active_relay_channel:{channel}"
    timeout:
      seconds: 5
      retries: 3
  - name: relay.turn_on
    error_class: BYPASS
    safety_class: REVERSIBLE
    params:
      channel: {type: integer, description: "Channel number (1-16)"}
    description: "Turn on a relay channel"
    contract:
      preconditions: []
      effects:
        - "set:active_relay_channel:{channel}"
    timeout:
      seconds: 5
      retries: 3
  - name: relay.turn_off
    error_class: BYPASS
    safety_class: REVERSIBLE
    params:
      channel: {type: integer, description: "Channel number (1-16)"}
    description: "Turn off a relay channel"
    contract:
      preconditions: []
      effects:
        - "set:active_relay_channel:none"
    timeout:
      seconds: 5
      retries: 3
---

# Relay Controller — Electrode Switching

The 16-channel USB relay board manages physical connections between the
potentiostat and multiple electrochemical cells. By switching relay channels,
the system can route the potentiostat to different working, counter, and
reference electrodes without manual rewiring.

## When to Use

Use relay primitives when the protocol requires:
- Switching between electrochemical cells
- Selecting which electrode is connected to the potentiostat
- Routing signals during multi-cell experiments
- Isolating cells during sequential measurements

## Channel Layout

The 16 channels are organized into functional groups:
- **CH1-CH4**: Working electrode selection
- **CH5-CH8**: Counter electrode selection
- **CH9-CH12**: Reference electrode selection
- **CH13-CH16**: Auxiliary / spare channels

## Workflow Pattern

Switching to a new cell:
```
relay.switch_to (channel=1)    # connect working electrode to cell 1
relay.switch_to (channel=5)    # connect counter electrode to cell 1
relay.switch_to (channel=9)    # connect reference electrode to cell 1
  -> squidstat.run_experiment  # run measurement on cell 1
```

## Safety Constraints

- **All REVERSIBLE**: Relay operations are non-destructive. A failed switch
  means the previous routing remains active, which is safe.
- **Channel validation**: Only channels 1-16 are valid.
- **No hot-switching during measurement**: Always complete any running
  squidstat experiment before changing relay channels.

## Resource Locking

All relay primitives require the `relay-controller` resource lock.
Relay operations can run in parallel with robot or PLC operations,
but should be coordinated with squidstat operations.

## Error Behavior

| Primitive | Error Class | Safety Class | On Failure |
|-----------|------------|-------------|------------|
| relay.set_channel | BYPASS | REVERSIBLE | Retry (3x), log and continue |
| relay.switch_to | BYPASS | REVERSIBLE | Retry (3x), log and continue |
| relay.turn_on | BYPASS | REVERSIBLE | Retry (3x), log and continue |
| relay.turn_off | BYPASS | REVERSIBLE | Retry (3x), log and continue |

*4 primitives. All REVERSIBLE.*
