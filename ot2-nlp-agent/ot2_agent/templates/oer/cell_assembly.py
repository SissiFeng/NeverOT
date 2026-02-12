"""
Cell assembly templates for OER experiments.
"""

from ...ir import UnitOperation, UOType, Placeholder


CELL_ASSEMBLY_TEMPLATE = UnitOperation(
    name="CellAssembly",
    uo_type=UOType.CELL_ASSEMBLY,
    description="Assemble three-electrode electrochemical cell",
    description_zh="组装三电极电化学电池",
    inputs={
        "working_electrode": "electrode",
        "electrolyte": "solution",
    },
    outputs={
        "assembled_cell": "cell",
    },
    parameters={
        "cell_type": "three_electrode",
        "electrode_configuration": "standard",
    },
    placeholders={
        "reference_electrode": Placeholder(
            parameter="reference_electrode",
            question="Reference electrode type?",
            question_zh="参比电极类型？",
            default="Ag/AgCl (sat. KCl)",
            required=True,
            options=[
                "Ag/AgCl (sat. KCl)",
                "Ag/AgCl (3M KCl)",
                "SCE",
                "Hg/HgO (1M KOH)",
                "RHE",
                "Other"
            ],
            value_type="string",
        ),
        "counter_electrode": Placeholder(
            parameter="counter_electrode",
            question="Counter electrode material?",
            question_zh="对电极材料？",
            default="Pt wire",
            required=True,
            options=["Pt wire", "Pt mesh", "Pt foil", "Graphite rod", "Carbon"],
            value_type="string",
        ),
        "working_electrode_area_cm2": Placeholder(
            parameter="working_electrode_area_cm2",
            question="Working electrode area (cm²)?",
            question_zh="工作电极面积(cm²)？",
            required=True,
            unit="cm²",
            value_type="number",
        ),
        "cell_volume_ml": Placeholder(
            parameter="cell_volume_ml",
            question="Cell volume (mL)?",
            question_zh="电解池体积(mL)？",
            default=50,
            required=False,
            unit="mL",
            value_type="number",
        ),
    },
    preconditions=["electrode_prepared", "electrolyte_prepared"],
    postconditions=["cell_assembled", "connections_verified"],
    estimated_duration_s=300,  # 5 minutes
    domain="oer",
    template_id="oer_cell_assembly",
)


REFERENCE_CALIBRATION_TEMPLATE = UnitOperation(
    name="ReferenceCalibration",
    uo_type=UOType.CALIBRATION,
    description="Calibrate reference electrode to RHE scale",
    description_zh="将参比电极校准到RHE标度",
    inputs={
        "assembled_cell": "cell",
    },
    outputs={
        "rhe_offset_V": "number",
    },
    parameters={
        "calibration_method": "hydrogen_equilibrium",
    },
    placeholders={
        "ph_value": Placeholder(
            parameter="ph_value",
            question="Electrolyte pH value?",
            question_zh="电解液pH值？",
            default=14,  # For 1M KOH
            required=True,
            value_type="number",
        ),
        "reference_potential_V": Placeholder(
            parameter="reference_potential_V",
            question="Reference electrode potential vs SHE (V)?",
            question_zh="参比电极相对SHE的电位(V)？",
            default=0.197,  # For Ag/AgCl sat. KCl
            required=True,
            unit="V",
            value_type="number",
        ),
        "ir_compensation": Placeholder(
            parameter="ir_compensation",
            question="Apply iR compensation?",
            question_zh="是否进行iR补偿？",
            default=True,
            required=False,
            options=["Yes", "No"],
            value_type="boolean",
        ),
        "solution_resistance_ohm": Placeholder(
            parameter="solution_resistance_ohm",
            question="Solution resistance (Ohm, if known)?",
            question_zh="溶液电阻(Ohm，如果已知)？",
            required=False,
            unit="Ohm",
            value_type="number",
        ),
    },
    preconditions=["cell_assembled"],
    postconditions=["reference_calibrated", "rhe_offset_known"],
    estimated_duration_s=180,  # 3 minutes
    domain="oer",
    template_id="oer_reference_calibration",
)
