"""
Electrolyte preparation templates for OER experiments.
"""

from ...ir import UnitOperation, UOType, Placeholder


ELECTROLYTE_PREPARATION_TEMPLATE = UnitOperation(
    name="ElectrolytePreparation",
    uo_type=UOType.ELECTROLYTE_PREPARATION,
    description="Prepare electrolyte solution for OER measurement",
    description_zh="配制OER测量用电解液",
    inputs={},
    outputs={
        "electrolyte": "solution",
    },
    parameters={
        "default_electrolyte": "KOH",
    },
    placeholders={
        "electrolyte_type": Placeholder(
            parameter="electrolyte_type",
            question="Electrolyte type?",
            question_zh="电解液类型？",
            default="1M KOH",
            required=True,
            options=["1M KOH", "0.5M H2SO4", "1M NaOH", "0.1M KOH", "0.1M HClO4", "Other"],
            value_type="string",
        ),
        "electrolyte_volume_ml": Placeholder(
            parameter="electrolyte_volume_ml",
            question="Electrolyte volume (mL)?",
            question_zh="电解液体积(mL)？",
            default=50,
            required=True,
            unit="mL",
            value_type="number",
        ),
        "purge_gas": Placeholder(
            parameter="purge_gas",
            question="Purge gas type?",
            question_zh="吹扫气体类型？",
            default="O2",
            required=False,
            options=["O2", "N2", "Ar", "None"],
            value_type="string",
        ),
        "purge_time_min": Placeholder(
            parameter="purge_time_min",
            question="Gas purge time (minutes)?",
            question_zh="气体吹扫时间(分钟)？",
            default=30,
            required=False,
            unit="min",
            value_type="number",
        ),
        "temperature_C": Placeholder(
            parameter="temperature_C",
            question="Electrolyte temperature (°C)?",
            question_zh="电解液温度(°C)？",
            default=25,
            required=False,
            unit="°C",
            value_type="number",
        ),
    },
    preconditions=[],
    postconditions=["electrolyte_prepared", "electrolyte_saturated"],
    estimated_duration_s=1800,  # 30 min for gas purge
    domain="oer",
    template_id="oer_electrolyte_preparation",
)
