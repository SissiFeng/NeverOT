"""
Dispatcher - Translates JSON workflow actions into actual hardware function calls
"""
import logging
import time
import threading
from typing import Dict, Any, Optional

# Hardware constants (originally from config.constants in refactored_battery)
PIPETTE_LARGE = "p1000_single_v2.2"
PIPETTE_SMALL = "p300_single_v2.1"
ROBOT_MOVE_SPEED = 200


class ActionDispatcher:
    """Dispatches workflow actions to appropriate hardware controllers"""

    def __init__(self, robot, squidstat, relay, plc, cleanup=None, sample_preparator=None, ssh_streamer=None):
        """
        Initialize dispatcher with hardware controllers

        Args:
            robot: OpentronsController instance
            squidstat: SquidstatController instance
            relay: RelayController instance
            plc: PLCController instance
            cleanup: CleanupWorkflows instance (optional)
            sample_preparator: SamplePreparator instance (optional)
            ssh_streamer: SshDataStreamer instance (optional)
        """
        self.robot = robot
        self.squidstat = squidstat
        self.relay = relay
        self.plc = plc
        self.cleanup = cleanup
        self.sample_preparator = sample_preparator
        self.ssh_streamer = ssh_streamer

        # Track labware IDs (name -> ID mapping)
        self.labware_ids = {}
        self._csv_progress = {}

        # Map action types to handler methods
        self.action_handlers = {
            # Robot actions
            'robot.home': self._handle_robot_home,
            'robot.load_pipettes': self._handle_robot_load_pipettes,
            'robot.set_lights': self._handle_robot_lights,
            'robot.load_labware': self._handle_robot_load_labware,
            'robot.load_custom_labware': self._handle_robot_load_custom_labware,
            'robot.move_to_well': self._handle_robot_move_to_well,
            'robot.pick_up_tip': self._handle_robot_pick_up_tip,
            'robot.drop_tip': self._handle_robot_drop_tip,
            'robot.aspirate': self._handle_robot_aspirate,
            'robot.dispense': self._handle_robot_dispense,
            'robot.blowout': self._handle_robot_blowout,
            
            # PLC actions
            'plc.dispense_ml': self._handle_plc_dispense,
            'plc.set_pump_on_timer': self._handle_plc_pump_timer,
            'plc.set_ultrasonic_on_timer': self._handle_plc_ultrasonic,
            
            # Relay actions
            'relay.set_channel': self._handle_relay_set_channel,
            'relay.turn_on': self._handle_relay_turn_on,
            'relay.turn_off': self._handle_relay_turn_off,
            'relay.switch_to': self._handle_relay_switch_to,
            
            # Squidstat actions
            'squidstat.run_experiment': self._handle_squidstat_run,
            'squidstat.get_data': self._handle_squidstat_get_data,
            'squidstat.save_snapshot': self._handle_squidstat_save_snapshot,
            'squidstat.reset_plot': self._handle_squidstat_reset_plot,

            # Cleanup (high level)
            'cleanup.run_full': self._handle_cleanup_run_full,

            # Sample preparation (CSV-driven additives)
            'sample.prepare_from_csv': self._handle_sample_prepare_from_csv,

            # SSH Actions
            'ssh.start_stream': self._handle_ssh_start,
            'ssh.stop_stream': self._handle_ssh_stop,

            # Utility actions
            'wait': self._handle_wait,
            'log': self._handle_log,
        }
    
    @staticmethod
    def _hard_log(message: str):
        """Hard logging with immediate flush for debugging parallel execution"""
        timestamp = time.monotonic()
        thread_name = threading.current_thread().name
        print(f"[T={timestamp:.4f}] [{thread_name}] {message}", flush=True)
        logging.info(f"[T={timestamp:.4f}] [{thread_name}] {message}")
        # Force flush all handlers
        for handler in logging.getLogger().handlers:
            if hasattr(handler, 'flush'):
                handler.flush()

    def dispatch(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Dispatch an action to the appropriate handler
        
        Args:
            action: Action string (e.g., 'robot.home', 'plc.dispense_ml')
            params: Dictionary of parameters for the action
            
        Returns:
            Result from the action handler
            
        Raises:
            ValueError: If action is not recognized
        """
        if action not in self.action_handlers:
            raise ValueError(f"Unknown action: {action}")
        
        handler = self.action_handlers[action]
        params = params or {}
        
        # 🔥 HARD CHECKPOINT: Handler enter
        handler_name = handler.__name__
        self._hard_log(f"🔧 HANDLER_ENTER: action={action}, handler={handler_name}, params={params}")

        try:
            result = handler(**params)

            # 🔥 HARD CHECKPOINT: Handler exit
            self._hard_log(f"🔧 HANDLER_EXIT: action={action}, handler={handler_name}, result={result}")
            return result

        except Exception as e:
            # 🔥 HARD CHECKPOINT: Handler error
            self._hard_log(f"❌ HANDLER_ERROR: action={action}, handler={handler_name}, error={e}")
            raise

    def _sync_cleanup_labware(self):
        """
        If a CleanupWorkflows instance is attached, push the latest labware IDs
        so threaded cleanup routines can reuse them without extra JSON steps.
        """
        if not self.cleanup:
            return

        wash_station = self.labware_ids.get('wash_station')
        reactor = self.labware_ids.get('reactor')
        electrode_tip_rack = self.labware_ids.get('electrode_tip_rack')

        if wash_station and reactor and electrode_tip_rack:
            try:
                self.cleanup.set_labware_ids(
                    wash_station_id=wash_station,
                    reactor_id=reactor,
                    electrode_tip_rack_id=electrode_tip_rack,
                    pipette_name=PIPETTE_LARGE
                )
            except Exception as e:
                logging.warning(f"Failed to sync cleanup labware IDs: {e}")

    def _sync_sample_preparator_labware(self):
        """
        If a SamplePreparator is attached, push the latest labware IDs so it can
        pick the correct racks/reactor when called from CSV-driven prep.
        """
        if not self.sample_preparator:
            return

        tip_rack_1000 = self.labware_ids.get('opentrons_96_tiprack_1000ul')
        tip_rack_300 = self.labware_ids.get('opentrons_96_tiprack_300ul')
        vial_rack_5 = self.labware_ids.get('vial_rack_slot5')
        vial_rack_6 = self.labware_ids.get('vial_rack_slot6')
        reactor = self.labware_ids.get('reactor')

        if tip_rack_1000 and tip_rack_300 and vial_rack_5 and vial_rack_6 and reactor:
            try:
                self.sample_preparator.set_labware_ids(
                    tip_rack_1=tip_rack_1000,
                    tip_rack_4=tip_rack_300,
                    vial_rack_5=vial_rack_5,
                    vial_rack_6=vial_rack_6,
                    reactor=reactor
                )
            except Exception as e:
                logging.warning(f"Failed to sync sample preparator labware IDs: {e}")
    
    # ========== Robot Action Handlers ==========

    def _handle_robot_home(self, **kwargs):
        """Home the robot"""
        try:
            self.robot.home_robot()
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to home robot: {e}")
            logging.warning("[BYPASS] Continuing workflow without homing")
            return False

    def _handle_robot_load_pipettes(self, small_mount: str = 'left', large_mount: str = 'right', **kwargs):
        """Load pipettes onto robot mounts"""
        try:
            self.robot.initialize_pipettes(small_mount=small_mount, large_mount=large_mount)
            logging.info(f"Pipettes loaded: small on {small_mount}, large on {large_mount}")
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to load pipettes: {e}")
            logging.warning("[BYPASS] Continuing workflow without pipettes loaded")
            return False

    def _handle_robot_lights(self, on: bool, **kwargs):
        """Set robot lights"""
        try:
            self.robot.set_lights(on)
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to set lights: {e}")
            logging.warning("[BYPASS] Continuing workflow without changing lights")
            return False

    def _handle_robot_load_labware(self, slot: int, labware: str, name: str = None, **kwargs):
        """Load standard labware"""
        try:
            labware_id = self.robot.load_standard_labware(slot=slot, labware_name=labware)
            # Store labware ID with a friendly name
            friendly_name = name or labware
            self.labware_ids[friendly_name] = labware_id
            logging.info(f"Loaded labware '{friendly_name}' in slot {slot} (ID: {labware_id})")
            self._sync_cleanup_labware()
            self._sync_sample_preparator_labware()
            return labware_id
        except Exception as e:
            logging.critical(f"CRITICAL: Failed to load labware {name or labware}: {e}")
            raise  # Stop workflow on labware load failure

    def _handle_robot_load_custom_labware(self, slot: int, labware_file: str, name: str = None, **kwargs):
        """Load custom labware from JSON file"""
        import os

        try:
            # EMERGENCY FIX: Direct path construction
            if labware_file.startswith('labware/'):
                # Remove 'labware/' prefix and rebuild path
                filename = labware_file.replace('labware/', '')
                labware_file = os.path.join(os.getcwd(), 'labware', filename)
            
            labware_file = os.path.normpath(labware_file)
            
            logging.info(f"Loading custom labware from: {labware_file}")
            
            labware_id = self.robot.load_custom_labware(slot=slot, labware_json_path=labware_file)
            friendly_name = name or f"custom_labware_slot_{slot}"
            self.labware_ids[friendly_name] = labware_id
            logging.info(f"Loaded custom labware '{friendly_name}' in slot {slot} (ID: {labware_id})")
            self._sync_cleanup_labware()
            self._sync_sample_preparator_labware()
            return labware_id
        except Exception as e:
            logging.critical(f"CRITICAL: Failed to load custom labware {name or labware_file}: {e}")
            raise

    def _resolve_labware_id(self, labware_name: str) -> str:
        """Resolve labware name to ID"""
        if labware_name in self.labware_ids:
            return self.labware_ids[labware_name]
        # If not found, assume it's already an ID
        return labware_name

    def _handle_robot_move_to_well(self, labware: str, well: str, pipette: str,
                                    offset_start: str = 'top',
                                    offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                                    speed: int = 200, **kwargs):
        """Move pipette to well"""
        try:
            labware_id = self._resolve_labware_id(labware)
            self.robot.move_to_well(
                labware_id=labware_id,
                well_name=well,
                pipette_name=pipette,
                offset_start=offset_start,
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z,
                speed=speed
            )
            return True
        except Exception as e:
            logging.critical(f"CRITICAL: Failed to move to {labware}/{well}: {e}")
            raise  # Stop workflow on movement failure

    def _handle_robot_pick_up_tip(self, labware: str, well: str, pipette: str,
                                   offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                                   **kwargs):
        """Pick up tip"""
        try:
            labware_id = self._resolve_labware_id(labware)
            self.robot.pick_up_tip(
                labware_id=labware_id,
                well_name=well,
                pipette_name=pipette,
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z
            )
            return True
        except Exception as e:
            logging.critical(f"CRITICAL: Failed to pick up tip from {labware}/{well}: {e}")
            raise  # Stop workflow on tip pick up failure

    def _handle_robot_drop_tip(self, pipette: str, labware: str = None, well: str = None,
                                drop_in_trash: bool = False,
                                offset_start: str = 'top',
                                offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                                **kwargs):
        """Drop tip"""
        try:
            labware_id = self._resolve_labware_id(labware) if labware else None
            self.robot.drop_tip(
                pipette_name=pipette,
                labware_id=labware_id,
                well_name=well,
                drop_in_trash=drop_in_trash,
                offset_start=offset_start,
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z
            )
            return True
        except Exception as e:
            logging.critical(f"CRITICAL: Failed to drop tip: {e}")
            raise  # Stop workflow on tip drop failure

    def _handle_robot_aspirate(self, labware: str, well: str, pipette: str, volume: float,
                                offset_start: str = 'top',
                                offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                                **kwargs):
        """Aspirate liquid"""
        try:
            labware_id = self._resolve_labware_id(labware)
            self.robot.aspirate(
                labware_id=labware_id,
                well_name=well,
                pipette_name=pipette,
                volume=volume,
                offset_start=offset_start,
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z
            )
            return True
        except Exception as e:
            logging.critical(f"CRITICAL: Failed to aspirate {volume}uL from {labware}/{well}: {e}")
            raise  # Stop workflow on aspiration failure

    def _handle_robot_dispense(self, labware: str, well: str, pipette: str, volume: float,
                                offset_start: str = 'top',
                                offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                                **kwargs):
        """Dispense liquid"""
        try:
            labware_id = self._resolve_labware_id(labware)
            self.robot.dispense(
                labware_id=labware_id,
                well_name=well,
                pipette_name=pipette,
                volume=volume,
                offset_start=offset_start,
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z
            )
            return True
        except Exception as e:
            logging.critical(f"CRITICAL: Failed to dispense {volume}uL to {labware}/{well}: {e}")
            raise  # Stop workflow on dispense failure

    def _handle_robot_blowout(self, labware: str, well: str, pipette: str,
                               offset_start: str = 'top',
                               offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                               **kwargs):
        """Blowout remaining liquid"""
        try:
            labware_id = self._resolve_labware_id(labware)
            self.robot.blowout(
                labware_id=labware_id,
                well_name=well,
                pipette_name=pipette,
                offset_start=offset_start,
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z
            )
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to blowout at {labware}/{well}: {e}")
            logging.warning("[BYPASS] Continuing workflow without blowout")
            return False

    # ========== PLC Action Handlers ==========

    def _handle_plc_dispense(self, pump: int, volume_ml: float, **kwargs):
        """Dispense liquid using PLC pump"""
        try:
            logging.info(f"[PLC] Dispensing {volume_ml}mL with pump {pump}")
            self.plc.dispense_ml(pump_number=pump, volume_ml=volume_ml)
            logging.info(f"[PLC] Dispense completed")
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to dispense with pump {pump}: {e}")
            logging.warning("[BYPASS] PLC connection may have been lost - continuing workflow")
            return False

    def _handle_plc_pump_timer(self, pump: int, duration_ms: int, **kwargs):
        """Run PLC pump for specified duration"""
        try:
            logging.info(f"[PLC] Running pump {pump} for {duration_ms}ms")
            self.plc.set_pump_on_timer(pump_number=pump, duration_ms=duration_ms)
            logging.info(f"[PLC] Pump timer set")
            return True
        except Exception as e:
            logging.error(f"CRITICAL: Failed to set pump timer for pump {pump}: {e}")
            raise  # Stop workflow on PLC failure

    def _handle_plc_ultrasonic(self, unit: int, duration_ms: int, **kwargs):
        """Run ultrasonic cleaner for specified duration"""
        try:
            logging.info(f"[PLC] Running ultrasonic unit {unit} for {duration_ms}ms")
            self.plc.setUltrasonicOnTimer(unit_number=unit, duration_ms=duration_ms)
            logging.info(f"[PLC] Ultrasonic timer set")
            return True
        except Exception as e:
            logging.error(f"CRITICAL: Failed to set ultrasonic timer for unit {unit}: {e}")
            raise  # Stop workflow on PLC failure

    # ========== Relay Action Handlers ==========

    def _handle_relay_set_channel(self, channel: int, state: bool, **kwargs):
        """Set relay channel state"""
        try:
            if state:
                self.relay.activate_channel(channel=channel)
                logging.info(f"[RELAY] Channel {channel} ACTIVATED")
            else:
                self.relay.deactivate_channel(channel=channel)
                logging.info(f"[RELAY] Channel {channel} DEACTIVATED")
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to set relay channel {channel}: {e}")
            logging.warning("[BYPASS] Relay connection may have been lost - continuing workflow")
            return False

    def _handle_relay_switch_to(self, channel: int, **kwargs):
        """Switch to specific relay channel (exclusive)"""
        try:
            self.relay.switch_to_channel(channel=channel)
            logging.info(f"[RELAY] Switched to channel {channel}")
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to switch to relay channel {channel}: {e}")
            logging.warning("[BYPASS] Relay connection may have been lost - continuing workflow")
            return False

    def _handle_relay_turn_on(self, channel: int, **kwargs):
        """Turn on relay channel"""
        try:
            self.relay.turn_on(channel=channel)
            logging.info(f"[RELAY] Channel {channel} turned ON")
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to turn on relay channel {channel}: {e}")
            logging.warning("[BYPASS] Relay connection may have been lost - continuing workflow")
            return False

    def _handle_relay_turn_off(self, channel: int, **kwargs):
        """Turn off relay channel"""
        try:
            self.relay.turn_off(channel=channel)
            logging.info(f"[RELAY] Channel {channel} turned OFF")
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to turn off relay channel {channel}: {e}")
            logging.warning("[BYPASS] Relay connection may have been lost - continuing workflow")
            return False

    # ========== Squidstat Action Handlers ==========

    def _handle_squidstat_run(self, experiment_name: str = "Experiment",
                              channel: int = 0,
                              elements: list = None,
                              num_cycles: int = 20,
                              **kwargs):
        """Run squidstat experiment"""
        try:
            from SquidstatPyLibrary import (
                AisExperiment,
                AisOpenCircuitElement,
                AisConstantCurrentElement,
                AisEISPotentiostaticElement,
                AisErrorCode
            )
            from datetime import datetime

            if elements is None:
                logging.error("CRITICAL: No experiment elements provided")
                raise ValueError("No experiment elements provided")

            logging.info(f"[SQUIDSTAT] Building experiment: {experiment_name}")
            logging.info(f"[SQUIDSTAT] Number of cycles: {num_cycles}")

            # Build experiment from elements
            exp = AisExperiment()

            def _add_element_to_exp(element_config, cycle_count_context):
                elem_type = element_config.get('type')

                if elem_type == 'LOOP':
                    # Handle looping of sub-elements
                    # Use 'repeats' if specified, otherwise default to global num_cycles
                    repeats = element_config.get('repeats', cycle_count_context)
                    sub_elements = element_config.get('elements', [])
                    logging.info(f"[SQUIDSTAT] Adding LOOP: {repeats} repeats of {len(sub_elements)} elements")
                    
                    for i in range(repeats):
                        for sub_elem in sub_elements:
                            _add_element_to_exp(sub_elem, cycle_count_context)

                elif elem_type == 'OCV':
                    # Open Circuit Voltage
                    duration = element_config.get('duration_s', 30)
                    sampling = element_config.get('sampling_interval_s', 0.5)
                    ocv = AisOpenCircuitElement(duration, sampling)
                    exp.appendElement(ocv)
                    # logging.info(f"[SQUIDSTAT] Added OCV element: {duration}s")

                elif elem_type == 'EIS':
                    # Electrochemical Impedance Spectroscopy
                    f_start = element_config.get('freq_start_hz', 1e4)
                    f_stop = element_config.get('freq_stop_hz', 1e-1)
                    points_per_decade = element_config.get('points_per_decade', 5.0)
                    bias_voltage = element_config.get('bias_voltage', 0.0)
                    amplitude = element_config.get('amplitude_v', 0.01)

                    eis = AisEISPotentiostaticElement(f_start, f_stop, points_per_decade, bias_voltage, amplitude)
                    eis.setBiasVoltageVsOCP(element_config.get('bias_vs_ocp', True))
                    eis.setMinimumCycles(element_config.get('min_cycles', 1))
                    exp.appendElement(eis)
                    # logging.info(f"[SQUIDSTAT] Added EIS element: {f_start}-{f_stop} Hz")

                elif elem_type == 'CP':
                    # Constant Current (Chronopotentiometry)
                    current = element_config.get('current_a', -0.008)
                    sampling = element_config.get('sampling_interval_s', 0.5)
                    duration = element_config.get('duration_s', 90)

                    cp = AisConstantCurrentElement(current, sampling, duration)
                    if 'max_voltage' in element_config:
                        cp.setMaxVoltage(element_config['max_voltage'])
                    exp.appendElement(cp)
                    # logging.info(f"[SQUIDSTAT] Added CP element: {current}A for {duration}s")

            # Process all top-level elements
            for elem in elements:
                _add_element_to_exp(elem, num_cycles)

            # Set experiment name with timestamp
            timestamp = datetime.now().strftime("%H-%M-%S_%Y-%m-%d")
            exp.setExperimentName(f"{experiment_name} {timestamp}")

            # Setup real-time visualization callbacks
            try:
                # Extract visualization parameters from kwargs
                enable_live_plot = kwargs.get('enable_live_plot', False)
                show_dc_plots = kwargs.get('show_dc_plots', True)
                show_eis_plots = kwargs.get('show_eis_plots', True)
                csv_filename = kwargs.get('csv_filename', None)
                snapshot_folder = kwargs.get('snapshot_folder', 'data/snapshots')
                current_phase = kwargs.get('current_phase', 'dep')

                self.squidstat.setup_visualization_callbacks(
                    enable_terminal_print=False,
                    enable_live_plot=enable_live_plot,
                    show_dc_plots=show_dc_plots,
                    show_eis_plots=show_eis_plots,
                    csv_filename=csv_filename,
                    snapshot_folder=snapshot_folder,
                    experiment_title=experiment_name,
                    current_phase=current_phase
                )
                logging.info(f"[SQUIDSTAT] Real-time visualization enabled (live_plot={enable_live_plot}, csv={csv_filename})")
            except Exception as e:
                logging.warning(f"[SQUIDSTAT] Could not enable visualization: {e}")

            # Upload experiment
            logging.info("[SQUIDSTAT] Uploading experiment...")
            err = self.squidstat.handler.uploadExperimentToChannel(channel, exp)
            if err.value() != AisErrorCode.Success:
                logging.critical(f"CRITICAL: Squidstat upload failed: {err.message()}")
                raise RuntimeError(f"Squidstat upload failed: {err.message()}")
            logging.info("[SQUIDSTAT] Experiment uploaded successfully")

            # Start experiment
            logging.info("[SQUIDSTAT] Starting experiment...")
            err = self.squidstat.handler.startUploadedExperiment(channel)
            if err.value() != AisErrorCode.Success:
                logging.critical(f"CRITICAL: Squidstat start failed: {err.message()}")
                raise RuntimeError(f"Squidstat start failed: {err.message()}")
            logging.info("[SQUIDSTAT] Experiment started successfully")

            # Wait for completion (IMPORTANT: This pumps the Qt event loop for live plotting)
            logging.info("[SQUIDSTAT] Waiting for experiment completion...")
            if not self.squidstat.wait_for_completion():
                logging.warning("[SQUIDSTAT] Wait for completion returned False (possible interruption)")

            # CRITICAL FIX: Explicitly save data after experiment completes
            # The experimentStopped callback is unreliable when running multiple experiments rapidly
            # This ensures data is always saved regardless of callback behavior
            logging.info("[SQUIDSTAT] Experiment completed, saving data explicitly...")
            try:
                self.squidstat.save_experiment_data(csv_filename=csv_filename)
            except Exception as e:
                logging.error(f"[SQUIDSTAT] Failed to save experiment data: {e}", exc_info=True)

            return True

        except Exception as e:
            logging.critical(f"CRITICAL: Squidstat experiment failed: {e}")
            raise # Stop workflow on squidstat failure

    def _handle_squidstat_get_data(self, **kwargs):
        """Get data from squidstat"""
        try:
            logging.info("[SQUIDSTAT] Getting squidstat data")
            # This would need to be implemented based on your squidstat controller
            # return self.squidstat.get_data()
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to get Squidstat data: {e}")
            logging.warning("[BYPASS] Continuing workflow without Squidstat data")
            return False

    def _handle_squidstat_save_snapshot(self, phase: str = 'dep', cycle: int = None, **kwargs):
        """Save Nyquist plot snapshot"""
        try:
            logging.info(f"[SQUIDSTAT] Saving snapshot: phase={phase}, cycle={cycle}")
            if self.squidstat:
                self.squidstat.save_snapshot(phase=phase, cycle=cycle)
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to save snapshot: {e}")
            logging.warning("[BYPASS] Snapshot save failed - continuing workflow")
            return False

    def _handle_squidstat_reset_plot(self, title: str = None, **kwargs):
        """Reset live plot for new experiment"""
        try:
            logging.info(f"[SQUIDSTAT] Resetting live plot: title={title}")
            if self.squidstat:
                self.squidstat.reset_live_plot(title=title)
            return True
        except Exception as e:
            logging.error(f"[BYPASS] Failed to reset live plot: {e}")
            logging.warning("[BYPASS] Live plot reset failed - continuing workflow")
            return False

    # ========== Cleanup Action Handlers ==========

    def _handle_cleanup_run_full(self, **kwargs):
        """Run the threaded cleanup workflow (matches long script parallelism)"""
        if not self.cleanup:
            raise ValueError("Cleanup handler not configured in dispatcher")
        return self.cleanup.run_full_cleanup()

    # ========== Sample Preparation (CSV) ==========

    def _handle_sample_prepare_from_csv(self, proposal_file: str = "additive_proposal.csv", row_index: int = None, **kwargs):
        """
        Prepare sample using additive volumes from a CSV row.

        CSV format (header + rows):
        action_number, Zn_solution, TMAC, TMAB, DTAB, MTAB, CTAC, CTAB, DODAB

        Args:
            proposal_file: Path to CSV with additive proposals
            row_index: Optional zero-based row index (excluding header). If None, auto-advances per file.
        """
        if not self.sample_preparator:
            raise ValueError("Sample preparator not configured in dispatcher")

        import csv
        from pathlib import Path

        csv_path = Path(proposal_file)
        if not csv_path.exists():
            raise FileNotFoundError(f"Proposal file not found: {proposal_file}")

        # Determine which row to read
        idx = row_index
        if idx is None:
            idx = self._csv_progress.get(str(csv_path), 0)

        with open(csv_path, 'r', newline='') as f:
            reader = list(csv.reader(f))

        if not reader or len(reader) < 2:
            raise ValueError(f"CSV has no data rows: {proposal_file}")

        header, rows = reader[0], reader[1:]
        if idx < 0 or idx >= len(rows):
            raise IndexError(f"Row index {idx} out of range for {proposal_file} (rows: {len(rows)})")

        row = rows[idx]
        try:
            action_number = row[0]
            Zn_solution, TMAC, TMAB, DTAB, MTAB, CTAC, CTAB, DODAB = [float(row[i]) for i in range(1, 9)]
        except Exception as e:
            raise ValueError(f"Failed to parse row {idx} in {proposal_file}: {e}")

        # Run sample preparation with trash drop strategy to avoid tip conflicts
        # (NIMO mode should always drop tips in trash, not return to tiprack)
        cell = self.sample_preparator.prepare_sample(
            Zn_solution=Zn_solution,
            TMAC=TMAC,
            TMAB=TMAB,
            DTAB=DTAB,
            MTAB=MTAB,
            CTAC=CTAC,
            CTAB=CTAB,
            DODAB=DODAB,
            drop_strategy='trash'  # Prevent dropTip to tiprack conflicts
        )

        # Advance auto-progress counter
        self._csv_progress[str(csv_path)] = idx + 1

        logging.info(f"[CSV PREP] action={action_number}, cell={cell}, volumes(Zn,TMAC,TMAB,DTAB,MTAB,CTAC,CTAB,DODAB)="
                     f"({Zn_solution},{TMAC},{TMAB},{DTAB},{MTAB},{CTAC},{CTAB},{DODAB})")

        return {
            "action_number": action_number,
            "cell": cell,
            "row_index": idx,
            "proposal_file": str(csv_path),
            "volumes": {
                "Zn_solution": Zn_solution,
                "TMAC": TMAC,
                "TMAB": TMAB,
                "DTAB": DTAB,
                "MTAB": MTAB,
                "CTAC": CTAC,
                "CTAB": CTAB,
                "DODAB": DODAB
            }
        }

    # ========== SSH Action Handlers ==========
    
    def _handle_ssh_start(self, filename_prefix: str = "experiment_video", **kwargs):
        """Start SSH video stream"""
        if self.ssh_streamer:
            try:
                logging.info(f"[SSH] Starting video stream with prefix: {filename_prefix}")
                self.ssh_streamer.start(filename_prefix=filename_prefix)
                return True
            except Exception as e:
                logging.error(f"[SSH] Failed to start stream: {e}")
                return False
        else:
            logging.warning("[SSH] Streamer not available (action skipped)")
            return False

    def _handle_ssh_stop(self, **kwargs):
        """Stop SSH video stream"""
        if self.ssh_streamer:
            try:
                logging.info("[SSH] Stopping video stream")
                self.ssh_streamer.stop()
                return True
            except Exception as e:
                logging.error(f"[SSH] Failed to stop stream: {e}")
                return False
        else:
            logging.warning("[SSH] Streamer not available (action skipped)")
            return False

    # ========== Utility Action Handlers ==========

    def _handle_wait(self, duration_seconds: float, **kwargs):
        """Wait for specified duration"""
        self._hard_log(f"⏰ WAIT_START: duration={duration_seconds}s")
        logging.info(f"Waiting for {duration_seconds} seconds")
        time.sleep(duration_seconds)
        self._hard_log(f"⏰ WAIT_END: duration={duration_seconds}s")

    def _handle_log(self, message: str, level: str = 'info', **kwargs):
        """Log a message"""
        log_func = getattr(logging, level.lower(), logging.info)
        log_func(message)

