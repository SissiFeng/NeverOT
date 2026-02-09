"""
PLC Controller Wrapper
Manages pumps and stirrers through OT_PLC_Client_Edit interface
"""
import logging
import time
import threading
from typing import Optional

LOGGER = logging.getLogger(__name__)

# These imports are only available when the PLC client library is installed.
# In simulated / dry-run mode the module is never imported.
try:
    from OT_PLC_Client_Edit import PLCController as ExternalPLCController
except ImportError:
    ExternalPLCController = None  # type: ignore[assignment,misc]


class PLCController:
    # Class-level lock to serialize PLC access across threads
    _plc_lock = threading.Lock()
    """
    Wrapper for PLC controller to manage pumps and stirrers
    Provides a clean interface for the external PLCController
    """

    def __init__(self):
        """Initialize PLC controller"""
        LOGGER.info("Initializing PLC Controller...")
        # Instantiate the external controller directly
        # This will raise an exception if connection fails, which is what we want
        self.plc = ExternalPLCController()
        LOGGER.info("PLC Controller initialized successfully")

    def is_available(self) -> bool:
        """
        Check if PLC controller is available

        Returns:
            True if PLC is initialized and ready
        """
        return self.plc is not None

    def set_pump_on_timer(self, pump_number: int, duration_ms: int):
        """
        Turn on a pump for a specified duration

        Args:
            pump_number: Pump number (1-based index)
            duration_ms: Duration in milliseconds
        """
        if not self.is_available():
            LOGGER.warning("PLC not available - skipping pump command")
            return

        # Use lock to serialize PLC access across threads
        with PLCController._plc_lock:
            try:
                current_thread = threading.current_thread()
                if current_thread.name != 'MainThread':
                    LOGGER.info(
                        f"Activating pump {pump_number}",
                        extra={"thread": current_thread.name, "step_id": f"pump_{pump_number}"}
                    )
                self.plc.setPumpOnTimer(pump_number, duration_ms)
                LOGGER.info(
                    f"PLC pump {pump_number} set to run for {duration_ms}ms",
                    extra={"step_id": f"pump_{pump_number}"}
                )
                # Small delay to ensure Modbus TCP connection is ready for next operation
                time.sleep(0.1)
            except Exception as e:
                LOGGER.error(f"Failed to activate pump {pump_number}: {e}")
                raise # Re-raise to ensure workflow stops on hardware failure

    def set_stirrer_on_timer(self, stirrer_number: int, duration_ms: int):
        """
        Turn on a stirrer for a specified duration

        Args:
            stirrer_number: Stirrer number (1-based index)
            duration_ms: Duration in milliseconds
        """
        if not self.is_available():
            LOGGER.warning("PLC not available - skipping stirrer command")
            return

        with PLCController._plc_lock:
            try:
                current_thread = threading.current_thread()
                if current_thread.name != 'MainThread':
                    LOGGER.info(
                        f"Activating stirrer {stirrer_number}",
                        extra={"thread": current_thread.name, "step_id": f"stirrer_{stirrer_number}"}
                    )
                # Assuming stirrer uses the same interface as pump
                self.plc.setPumpOnTimer(stirrer_number, duration_ms)
                LOGGER.info(
                    f"Stirrer {stirrer_number} activated for {duration_ms}ms",
                    extra={"step_id": f"stirrer_{stirrer_number}"}
                )
                # Small delay to ensure Modbus TCP connection is ready for next operation
                time.sleep(0.1)
            except Exception as e:
                LOGGER.error(f"Failed to activate stirrer {stirrer_number}: {e}")
                raise

    def dispense_ml(self, pump_number: int, volume_ml: float):
        """
        Dispense a specific volume using a pump

        Args:
            pump_number: Pump number (1-based index)
            volume_ml: Volume to dispense in milliliters
        """
        if not self.is_available():
            LOGGER.warning("PLC not available - skipping dispense command")
            return

        # Use lock to serialize PLC access across threads
        with PLCController._plc_lock:
            try:
                current_thread = threading.current_thread()
                if current_thread.name != 'MainThread':
                    LOGGER.info(
                        f"Dispensing {volume_ml}mL with pump {pump_number}",
                        extra={"thread": current_thread.name, "step_id": f"dispense_{pump_number}"}
                    )
                self.plc.dispense_ml(pump_number, volume_ml)
                LOGGER.info(
                    f"PLC pump {pump_number} dispensing {volume_ml}mL",
                    extra={"step_id": f"dispense_{pump_number}"}
                )
                # Small delay to ensure Modbus TCP connection is ready for next operation
                time.sleep(0.1)
            except Exception as e:
                LOGGER.error(f"Failed to dispense with pump {pump_number}: {e}")
                raise

    def close(self):
        """Close PLC connection"""
        if self.plc:
            try:
                self.plc.close()
                LOGGER.info("PLC Controller closed")
            except Exception as e:
                LOGGER.error(f"Error closing PLC controller: {e}")
