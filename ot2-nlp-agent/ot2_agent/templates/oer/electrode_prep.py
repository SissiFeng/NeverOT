"""
Electrode preparation templates for OER experiments.
"""

from ...ir import UnitOperation, UOType, Placeholder


ELECTRODE_INFO_TEMPLATE = UnitOperation(
    name="ElectrodeInfo",
    uo_type=UOType.ELECTRODE_PREPARATION,
    description="Collect electrode information and specifications",
    description_zh="收集电极信息和规格",
    inputs={},
    outputs={
        "electrode_material": "string",
        "electrode_area_cm2": "number",
        "catalyst_loading_mg_cm2": "number",
    },
    parameters={},
    placeholders={
        "electrode_material": Placeholder(
            parameter="electrode_material",
            question="What is the electrode material/catalyst?",
            question_zh="电极材料/催化剂是什么？",
            default=None,
            required=True,
            value_type="string",
        ),
        "electrode_area_cm2": Placeholder(
            parameter="electrode_area_cm2",
            question="Electrode geometric area (cm²)?",
            question_zh="电极几何面积(cm²)？",
            required=True,
            unit="cm²",
            value_type="number",
            validation="0.01-100",
        ),
        "catalyst_loading_mg_cm2": Placeholder(
            parameter="catalyst_loading_mg_cm2",
            question="Catalyst loading (mg/cm²)?",
            question_zh="催化剂载量(mg/cm²)？",
            required=False,
            unit="mg/cm²",
            value_type="number",
        ),
        "substrate_type": Placeholder(
            parameter="substrate_type",
            question="Substrate type?",
            question_zh="基底类型？",
            required=False,
            options=["GCE", "Carbon paper", "Ni foam", "Ti mesh", "FTO", "Other"],
            default="GCE",
            value_type="string",
        ),
    },
    preconditions=[],
    postconditions=["electrode_info_recorded"],
    estimated_duration_s=60,
    domain="oer",
    template_id="oer_electrode_info",
)


ELECTRODE_PREPARATION_TEMPLATE = UnitOperation(
    name="ElectrodePreparation",
    uo_type=UOType.ELECTRODE_PREPARATION,
    description="Prepare working electrode with catalyst",
    description_zh="制备带有催化剂的工作电极",
    inputs={
        "catalyst_ink": "solution",
    },
    outputs={
        "prepared_electrode": "electrode",
    },
    parameters={
        "preparation_method": "drop_casting",
    },
    placeholders={
        "ink_volume_ul": Placeholder(
            parameter="ink_volume_ul",
            question="Catalyst ink volume to deposit (µL)?",
            question_zh="滴涂催化剂墨水体积(µL)？",
            default=10,
            required=True,
            unit="µL",
            value_type="number",
        ),
        "drying_time_min": Placeholder(
            parameter="drying_time_min",
            question="Drying time (minutes)?",
            question_zh="干燥时间(分钟)？",
            default=30,
            required=False,
            unit="min",
            value_type="number",
        ),
        "drying_temperature_C": Placeholder(
            parameter="drying_temperature_C",
            question="Drying temperature (°C)?",
            question_zh="干燥温度(°C)？",
            default=60,
            required=False,
            unit="°C",
            value_type="number",
        ),
    },
    preconditions=["catalyst_ink_prepared"],
    postconditions=["electrode_prepared", "electrode_dried"],
    estimated_duration_s=1800,  # 30 minutes default drying
    domain="oer",
    template_id="oer_electrode_preparation",
)
