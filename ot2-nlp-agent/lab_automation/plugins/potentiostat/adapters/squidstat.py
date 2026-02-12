"""
SquidStat Hardware Adapter

Translates generic electrochemistry operations to SquidStat specific commands.
"""

from typing import Any, Dict


class SquidStatAdapter:
    """
    Adapter for Admiral Instruments SquidStat potentiostats.

    Translates generic electrochemistry operations to SquidStat
    API calls matching the zinc workflow format.
    """

    name = "squidstat"
    manufacturer = "Admiral Instruments"
    model = "SquidStat"

    def translate_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate generic action to SquidStat specific command.

        Args:
            action: Generic action string (e.g., "potentiostat.run_eis")
            params: Action parameters

        Returns:
            SquidStat specific command dictionary
        """
        action_map = {
            "potentiostat.ocv": "squidstat.ocv",
            "potentiostat.run_eis": "squidstat.run_experiment",
            "potentiostat.run_cv": "squidstat.run_experiment",
            "potentiostat.run_cp": "squidstat.run_experiment",
            "potentiostat.run_ca": "squidstat.run_experiment",
            "potentiostat.run_lsv": "squidstat.run_experiment",
            "potentiostat.reset_plot": "squidstat.reset_plot",
            "potentiostat.save_data": "squidstat.save_data",
            "potentiostat.save_snapshot": "squidstat.save_snapshot",
        }

        squidstat_action = action_map.get(action, action)

        # Translate params to SquidStat format
        translated_params = self._translate_params(action, params)

        return {
            "action": squidstat_action,
            "params": translated_params,
        }

    def _translate_params(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate generic params to SquidStat specific format."""
        if "eis" in action:
            return self._translate_eis_params(params)
        elif "cv" in action:
            return self._translate_cv_params(params)
        elif "cp" in action:
            return self._translate_cp_params(params)
        return params

    def _translate_eis_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate EIS parameters to SquidStat format."""
        return {
            "type": "EIS",
            "freq_start_hz": params.get("freq_start_hz", 10000),
            "freq_stop_hz": params.get("freq_stop_hz", 0.1),
            "points_per_decade": params.get("points_per_decade", 5.0),
            "amplitude_v": params.get("amplitude_v", 0.01),
            "bias_voltage": params.get("bias_voltage", 0.0),
            "bias_vs_ocp": params.get("bias_vs_ocp", True),
            "min_cycles": params.get("min_cycles", 1),
        }

    def _translate_cv_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate CV parameters to SquidStat format."""
        return {
            "type": "CV",
            "start_v": params.get("start_v", 0),
            "vertex1_v": params.get("vertex1_v", 0.5),
            "vertex2_v": params.get("vertex2_v", -0.5),
            "end_v": params.get("end_v", 0),
            "scan_rate_v_s": params.get("scan_rate_v_s", 0.05),
            "cycles": params.get("cycles", 3),
        }

    def _translate_cp_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate CP parameters to SquidStat format."""
        result = {
            "type": "CP",
            "current_a": params.get("current_a", 0.001),
            "duration_s": params.get("duration_s", 60),
            "sampling_interval_s": params.get("sampling_interval_s", 0.5),
        }
        if "max_voltage" in params:
            result["max_voltage"] = params["max_voltage"]
        if "min_voltage" in params:
            result["min_voltage"] = params["min_voltage"]
        return result

    def get_capabilities(self) -> Dict[str, Any]:
        """Get SquidStat adapter capabilities."""
        return {
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "channels": 4,
            "techniques": [
                "OCV", "EIS", "CV", "CP", "CA", "LSV", "DPV", "SWV"
            ],
            "max_current_a": 1.5,
            "voltage_range_v": [-5, 5],
            "frequency_range_hz": [0.001, 1000000],
        }
