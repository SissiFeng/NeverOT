"""
Cleanup templates for OER experiments.
"""

from ...ir import UnitOperation, UOType, Placeholder


CLEANUP_TEMPLATE = UnitOperation(
    name="Cleanup",
    uo_type=UOType.CLEANUP,
    description="Clean and rinse electrodes and cell",
    description_zh="清洗电极和电解池",
    inputs={
        "assembled_cell": "cell",
    },
    outputs={},
    parameters={
        "rinse_solvent": "DI water",
    },
    placeholders={
        "rinse_cycles": Placeholder(
            parameter="rinse_cycles",
            question="Number of rinse cycles?",
            question_zh="清洗次数？",
            default=3,
            required=False,
            value_type="number",
        ),
        "dry_electrodes": Placeholder(
            parameter="dry_electrodes",
            question="Dry electrodes after cleaning?",
            question_zh="清洗后干燥电极？",
            default=True,
            required=False,
            value_type="boolean",
        ),
        "dispose_electrolyte": Placeholder(
            parameter="dispose_electrolyte",
            question="Dispose of used electrolyte?",
            question_zh="处理用过的电解液？",
            default=True,
            required=False,
            value_type="boolean",
        ),
        "store_electrodes": Placeholder(
            parameter="store_electrodes",
            question="Store electrodes for reuse?",
            question_zh="保存电极以备复用？",
            default=False,
            required=False,
            value_type="boolean",
        ),
    },
    preconditions=["experiment_complete"],
    postconditions=["cell_cleaned", "electrodes_cleaned"],
    estimated_duration_s=600,  # 10 minutes
    domain="oer",
    template_id="oer_cleanup",
)


CELL_DISASSEMBLY_TEMPLATE = UnitOperation(
    name="CellDisassembly",
    uo_type=UOType.CLEANUP,
    description="Disassemble electrochemical cell",
    description_zh="拆卸电化学电池",
    inputs={
        "assembled_cell": "cell",
    },
    outputs={},
    parameters={},
    placeholders={
        "save_working_electrode": Placeholder(
            parameter="save_working_electrode",
            question="Save working electrode for analysis?",
            question_zh="保存工作电极用于后续分析？",
            default=False,
            required=False,
            value_type="boolean",
        ),
        "record_consumables": Placeholder(
            parameter="record_consumables",
            question="Record consumables usage?",
            question_zh="记录耗材使用情况？",
            default=True,
            required=False,
            value_type="boolean",
        ),
    },
    preconditions=["cell_cleaned"],
    postconditions=["cell_disassembled", "components_stored"],
    estimated_duration_s=300,  # 5 minutes
    domain="oer",
    template_id="oer_cell_disassembly",
)
