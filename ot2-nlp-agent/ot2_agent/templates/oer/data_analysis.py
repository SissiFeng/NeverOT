"""
Data analysis templates for OER experiments.
"""

from ...ir import UnitOperation, UOType, Placeholder


DATA_SAVE_TEMPLATE = UnitOperation(
    name="DataSave",
    uo_type=UOType.DATA_LOGGING,
    description="Save experimental data and metadata",
    description_zh="保存实验数据和元数据",
    inputs={
        "experiment_data": "data",
    },
    outputs={
        "saved_file_path": "string",
    },
    parameters={
        "include_metadata": True,
        "include_raw_data": True,
    },
    placeholders={
        "sample_name": Placeholder(
            parameter="sample_name",
            question="Sample name/identifier?",
            question_zh="样品名称/标识符？",
            required=True,
            value_type="string",
        ),
        "output_format": Placeholder(
            parameter="output_format",
            question="Output format?",
            question_zh="输出格式？",
            default="csv",
            required=False,
            options=["csv", "xlsx", "json", "hdf5"],
            value_type="string",
        ),
        "save_plots": Placeholder(
            parameter="save_plots",
            question="Save plots as images?",
            question_zh="是否保存图像？",
            default=True,
            required=False,
            value_type="boolean",
        ),
        "notes": Placeholder(
            parameter="notes",
            question="Additional notes?",
            question_zh="附加备注？",
            required=False,
            value_type="string",
        ),
    },
    preconditions=["lsv_data_collected"],
    postconditions=["data_saved"],
    estimated_duration_s=30,
    domain="oer",
    template_id="oer_data_save",
)


OVERPOTENTIAL_ANALYSIS_TEMPLATE = UnitOperation(
    name="OverpotentialAnalysis",
    uo_type=UOType.DATA_ANALYSIS,
    description="Calculate OER overpotential from LSV data",
    description_zh="从LSV数据计算OER过电位",
    inputs={
        "lsv_data": "data",
        "electrode_area_cm2": "number",
    },
    outputs={
        "overpotential_mV": "number",
        "current_density_at_target": "number",
    },
    parameters={
        "water_oxidation_potential_V": 1.23,  # Thermodynamic potential
    },
    placeholders={
        "target_current_density_mA_cm2": Placeholder(
            parameter="target_current_density_mA_cm2",
            question="Target current density (mA/cm²)?",
            question_zh="目标电流密度(mA/cm²)？",
            default=10,
            required=True,
            unit="mA/cm²",
            value_type="number",
            options=["1", "10", "50", "100"],
        ),
        "apply_ir_correction": Placeholder(
            parameter="apply_ir_correction",
            question="Apply iR correction?",
            question_zh="是否进行iR校正？",
            default=True,
            required=False,
            value_type="boolean",
        ),
    },
    preconditions=["lsv_data_collected"],
    postconditions=["overpotential_calculated"],
    estimated_duration_s=10,
    domain="oer",
    template_id="oer_overpotential_analysis",
)
