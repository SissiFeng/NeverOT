"""
OER (Oxygen Evolution Reaction) experiment templates.

Provides Unit Operation templates for electrochemical OER
measurements, including electrode preparation, cell assembly,
measurement, and cleanup.
"""

from .electrode_prep import (
    ELECTRODE_INFO_TEMPLATE,
    ELECTRODE_PREPARATION_TEMPLATE,
)
from .electrolyte_prep import (
    ELECTROLYTE_PREPARATION_TEMPLATE,
)
from .cell_assembly import (
    CELL_ASSEMBLY_TEMPLATE,
    REFERENCE_CALIBRATION_TEMPLATE,
)
from .oer_measurement import (
    OER_LSV_MEASUREMENT_TEMPLATE,
    OER_TAFEL_ANALYSIS_TEMPLATE,
    OER_EIS_MEASUREMENT_TEMPLATE,
    OER_STABILITY_TEST_TEMPLATE,
)
from .data_analysis import (
    DATA_SAVE_TEMPLATE,
    OVERPOTENTIAL_ANALYSIS_TEMPLATE,
)
from .cleanup import (
    CLEANUP_TEMPLATE,
    CELL_DISASSEMBLY_TEMPLATE,
)

# Register all templates
from .. import TemplateRegistry

_TEMPLATES = [
    # Electrode
    ELECTRODE_INFO_TEMPLATE,
    ELECTRODE_PREPARATION_TEMPLATE,
    # Electrolyte
    ELECTROLYTE_PREPARATION_TEMPLATE,
    # Cell
    CELL_ASSEMBLY_TEMPLATE,
    REFERENCE_CALIBRATION_TEMPLATE,
    # Measurement
    OER_LSV_MEASUREMENT_TEMPLATE,
    OER_TAFEL_ANALYSIS_TEMPLATE,
    OER_EIS_MEASUREMENT_TEMPLATE,
    OER_STABILITY_TEST_TEMPLATE,
    # Data
    DATA_SAVE_TEMPLATE,
    OVERPOTENTIAL_ANALYSIS_TEMPLATE,
    # Cleanup
    CLEANUP_TEMPLATE,
    CELL_DISASSEMBLY_TEMPLATE,
]

for template in _TEMPLATES:
    TemplateRegistry.register("oer", template.name, template)

__all__ = [
    # Electrode
    "ELECTRODE_INFO_TEMPLATE",
    "ELECTRODE_PREPARATION_TEMPLATE",
    # Electrolyte
    "ELECTROLYTE_PREPARATION_TEMPLATE",
    # Cell
    "CELL_ASSEMBLY_TEMPLATE",
    "REFERENCE_CALIBRATION_TEMPLATE",
    # Measurement
    "OER_LSV_MEASUREMENT_TEMPLATE",
    "OER_TAFEL_ANALYSIS_TEMPLATE",
    "OER_EIS_MEASUREMENT_TEMPLATE",
    "OER_STABILITY_TEST_TEMPLATE",
    # Data
    "DATA_SAVE_TEMPLATE",
    "OVERPOTENTIAL_ANALYSIS_TEMPLATE",
    # Cleanup
    "CLEANUP_TEMPLATE",
    "CELL_DISASSEMBLY_TEMPLATE",
]
