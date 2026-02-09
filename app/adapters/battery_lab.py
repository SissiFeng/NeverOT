"""Battery lab adapter — wraps ActionDispatcher for real hardware execution.

Supports a ``dry_run`` mode where every primitive is logged but no actual
hardware calls are made.  This lets us validate the adapter layer and the
workflow translator without powering on the OT-2 / PLC / relay / squidstat.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BatteryLabAdapter:
    """InstrumentAdapter implementation backed by real lab hardware.

    Each *run* should create its own adapter instance so that labware-id
    tracking (inside ActionDispatcher) does not leak across runs.
    """

    def __init__(self, *, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self._dispatcher: Any = None  # ActionDispatcher (lazy)
        self._robot: Any = None
        self._plc: Any = None
        self._relay: Any = None
        self._squidstat: Any = None
        self._connected = False

    # ---- InstrumentAdapter protocol ----

    def connect(self) -> None:
        """Initialise hardware controllers (or stub them for dry-run)."""
        if self._connected:
            return

        settings = get_settings()

        if self.dry_run:
            logger.info("BatteryLabAdapter: dry-run mode — no real hardware")
            self._dispatcher = _DryRunDispatcher()
        else:
            # Import hardware modules only when actually needed
            from app.hardware.opentrons_controller import OpentronsController
            from app.hardware.plc_controller import PLCController
            from app.hardware.relay_controller import RelayController
            from app.hardware.dispatcher import ActionDispatcher

            logger.info("BatteryLabAdapter: connecting to real hardware …")
            self._robot = OpentronsController(robot_ip=settings.robot_ip)
            self._plc = PLCController()
            self._relay = RelayController(port=settings.relay_port)
            # squidstat is optional — requires Qt runtime
            self._squidstat = None

            self._dispatcher = ActionDispatcher(
                robot=self._robot,
                squidstat=self._squidstat,
                relay=self._relay,
                plc=self._plc,
            )

        self._connected = True
        logger.info("BatteryLabAdapter: connected (dry_run=%s)", self.dry_run)

    def disconnect(self) -> None:
        """Release all hardware connections."""
        if not self._connected:
            return

        if not self.dry_run:
            if self._relay:
                try:
                    self._relay.close()
                except Exception:
                    logger.exception("Error closing relay")
            if self._plc:
                try:
                    self._plc.close()
                except Exception:
                    logger.exception("Error closing PLC")
            # robot / squidstat may also need cleanup
        self._connected = False
        logger.info("BatteryLabAdapter: disconnected")

    def execute_primitive(
        self, *, instrument_id: str, primitive: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Delegate to ActionDispatcher.dispatch()."""
        if not self._connected:
            raise RuntimeError("BatteryLabAdapter is not connected; call connect() first")

        try:
            result = self._dispatcher.dispatch(action=primitive, params=params)
            return {
                "instrument_id": instrument_id,
                "primitive": primitive,
                "raw_result": result,
                "ok": True,
            }
        except Exception as exc:
            logger.error("Primitive %s failed: %s", primitive, exc)
            raise

    def health_check(self) -> dict[str, Any]:
        """Return health status of connected hardware."""
        return {
            "adapter": "battery_lab",
            "dry_run": self.dry_run,
            "connected": self._connected,
            "robot": self._robot is not None if not self.dry_run else "stub",
            "plc": self._plc is not None if not self.dry_run else "stub",
            "relay": self._relay is not None if not self.dry_run else "stub",
            "squidstat": self._squidstat is not None if not self.dry_run else "stub",
        }


# ---------------------------------------------------------------------------
# Dry-run dispatcher stub
# ---------------------------------------------------------------------------

class _DryRunDispatcher:
    """Mimics ActionDispatcher but only logs actions — no hardware calls."""

    # All known actions from the real dispatcher
    KNOWN_ACTIONS = frozenset([
        "robot.home", "robot.load_pipettes", "robot.set_lights",
        "robot.load_labware", "robot.load_custom_labware",
        "robot.move_to_well", "robot.pick_up_tip", "robot.drop_tip",
        "robot.aspirate", "robot.dispense", "robot.blowout",
        "plc.dispense_ml", "plc.set_pump_on_timer", "plc.set_ultrasonic_on_timer",
        "relay.set_channel", "relay.turn_on", "relay.turn_off", "relay.switch_to",
        "squidstat.run_experiment", "squidstat.get_data",
        "squidstat.save_snapshot", "squidstat.reset_plot",
        "cleanup.run_full",
        "sample.prepare_from_csv",
        "ssh.start_stream", "ssh.stop_stream",
        "wait", "log",
    ])

    def dispatch(self, action: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        if action not in self.KNOWN_ACTIONS:
            raise ValueError(f"Unknown action: {action}")
        logger.info("[DRY-RUN] %s  params=%s", action, params)

        # For 'wait' we still sleep (optionally shorter) so timing tests work
        if action == "wait":
            duration = float(params.get("duration_seconds", 0))
            # In dry-run, cap wait to 0.1s for fast testing
            time.sleep(min(duration, 0.1))

        return True
