"""
OER measurement templates.
"""

from ...ir import UnitOperation, UOType, Placeholder


OER_LSV_MEASUREMENT_TEMPLATE = UnitOperation(
    name="OER_LSV_Measurement",
    uo_type=UOType.MEASUREMENT,
    description="Linear Sweep Voltammetry for OER characterization",
    description_zh="用于OER表征的线性扫描伏安法",
    inputs={
        "assembled_cell": "cell",
        "rhe_offset_V": "number",
    },
    outputs={
        "lsv_data": "data",
        "overpotential_V": "number",
    },
    parameters={
        "method": "LSV",
        "water_oxidation_potential_V": 1.23,  # vs RHE
    },
    placeholders={
        "scan_rate_mV_s": Placeholder(
            parameter="scan_rate_mV_s",
            question="Scan rate (mV/s)?",
            question_zh="扫描速率(mV/s)？",
            default=5,
            required=True,
            unit="mV/s",
            value_type="number",
            options=["1", "2", "5", "10", "20", "50"],
        ),
        "start_potential_V_vs_RHE": Placeholder(
            parameter="start_potential_V_vs_RHE",
            question="Start potential (V vs RHE)?",
            question_zh="起始电位(V vs RHE)？",
            default=1.0,
            required=True,
            unit="V vs RHE",
            value_type="number",
        ),
        "end_potential_V_vs_RHE": Placeholder(
            parameter="end_potential_V_vs_RHE",
            question="End potential (V vs RHE)?",
            question_zh="终止电位(V vs RHE)？",
            default=1.8,
            required=True,
            unit="V vs RHE",
            value_type="number",
        ),
        "target_current_density_mA_cm2": Placeholder(
            parameter="target_current_density_mA_cm2",
            question="Target current density for overpotential (mA/cm²)?",
            question_zh="过电位对应的目标电流密度(mA/cm²)？",
            default=10,
            required=True,
            unit="mA/cm²",
            value_type="number",
            options=["1", "10", "50", "100"],
        ),
        "num_cycles": Placeholder(
            parameter="num_cycles",
            question="Number of CV cycles for activation (0 to skip)?",
            question_zh="活化CV循环次数(0表示跳过)？",
            default=0,
            required=False,
            value_type="number",
        ),
    },
    preconditions=["cell_assembled", "reference_calibrated"],
    postconditions=["lsv_data_collected", "overpotential_measured"],
    estimated_duration_s=600,  # ~10 minutes
    domain="oer",
    template_id="oer_lsv_measurement",
)


OER_TAFEL_ANALYSIS_TEMPLATE = UnitOperation(
    name="OER_Tafel_Analysis",
    uo_type=UOType.DATA_ANALYSIS,
    description="Tafel slope analysis from LSV data",
    description_zh="从LSV数据进行Tafel斜率分析",
    inputs={
        "lsv_data": "data",
    },
    outputs={
        "tafel_slope_mV_dec": "number",
        "exchange_current_density": "number",
    },
    parameters={
        "analysis_method": "linear_fit",
    },
    placeholders={
        "potential_range_low_V": Placeholder(
            parameter="potential_range_low_V",
            question="Tafel region lower potential (V vs RHE)?",
            question_zh="Tafel区域下限电位(V vs RHE)？",
            default=1.45,
            required=False,
            unit="V vs RHE",
            value_type="number",
        ),
        "potential_range_high_V": Placeholder(
            parameter="potential_range_high_V",
            question="Tafel region upper potential (V vs RHE)?",
            question_zh="Tafel区域上限电位(V vs RHE)？",
            default=1.55,
            required=False,
            unit="V vs RHE",
            value_type="number",
        ),
        "ir_corrected": Placeholder(
            parameter="ir_corrected",
            question="Use iR-corrected data?",
            question_zh="使用iR校正后的数据？",
            default=True,
            required=False,
            value_type="boolean",
        ),
    },
    preconditions=["lsv_data_collected"],
    postconditions=["tafel_slope_calculated"],
    estimated_duration_s=60,  # Analysis is fast
    domain="oer",
    template_id="oer_tafel_analysis",
)


OER_EIS_MEASUREMENT_TEMPLATE = UnitOperation(
    name="OER_EIS_Measurement",
    uo_type=UOType.MEASUREMENT,
    description="Electrochemical Impedance Spectroscopy at OER potential",
    description_zh="在OER电位下的电化学阻抗谱测量",
    inputs={
        "assembled_cell": "cell",
        "rhe_offset_V": "number",
    },
    outputs={
        "eis_data": "data",
        "charge_transfer_resistance_ohm": "number",
    },
    parameters={
        "method": "EIS",
    },
    placeholders={
        "dc_potential_V_vs_RHE": Placeholder(
            parameter="dc_potential_V_vs_RHE",
            question="DC potential for EIS (V vs RHE)?",
            question_zh="EIS的直流电位(V vs RHE)？",
            default=1.55,
            required=True,
            unit="V vs RHE",
            value_type="number",
        ),
        "ac_amplitude_mV": Placeholder(
            parameter="ac_amplitude_mV",
            question="AC amplitude (mV)?",
            question_zh="交流振幅(mV)？",
            default=10,
            required=True,
            unit="mV",
            value_type="number",
            options=["5", "10", "20"],
        ),
        "frequency_start_Hz": Placeholder(
            parameter="frequency_start_Hz",
            question="Start frequency (Hz)?",
            question_zh="起始频率(Hz)？",
            default=100000,
            required=True,
            unit="Hz",
            value_type="number",
        ),
        "frequency_end_Hz": Placeholder(
            parameter="frequency_end_Hz",
            question="End frequency (Hz)?",
            question_zh="终止频率(Hz)？",
            default=0.1,
            required=True,
            unit="Hz",
            value_type="number",
        ),
        "points_per_decade": Placeholder(
            parameter="points_per_decade",
            question="Points per decade?",
            question_zh="每十倍频程点数？",
            default=10,
            required=False,
            value_type="number",
        ),
    },
    preconditions=["cell_assembled", "reference_calibrated"],
    postconditions=["eis_data_collected"],
    estimated_duration_s=900,  # ~15 minutes
    domain="oer",
    template_id="oer_eis_measurement",
)


OER_STABILITY_TEST_TEMPLATE = UnitOperation(
    name="OER_Stability_Test",
    uo_type=UOType.STABILITY_TEST,
    description="Long-term stability test at constant current",
    description_zh="恒电流条件下的长期稳定性测试",
    inputs={
        "assembled_cell": "cell",
    },
    outputs={
        "stability_data": "data",
        "potential_change_V": "number",
    },
    parameters={
        "method": "chronopotentiometry",
    },
    placeholders={
        "current_density_mA_cm2": Placeholder(
            parameter="current_density_mA_cm2",
            question="Current density for stability test (mA/cm²)?",
            question_zh="稳定性测试的电流密度(mA/cm²)？",
            default=10,
            required=True,
            unit="mA/cm²",
            value_type="number",
        ),
        "duration_hours": Placeholder(
            parameter="duration_hours",
            question="Test duration (hours)?",
            question_zh="测试时长(小时)？",
            default=10,
            required=True,
            unit="hours",
            value_type="number",
        ),
        "sampling_interval_s": Placeholder(
            parameter="sampling_interval_s",
            question="Data sampling interval (seconds)?",
            question_zh="数据采样间隔(秒)？",
            default=10,
            required=False,
            unit="s",
            value_type="number",
        ),
    },
    preconditions=["cell_assembled", "reference_calibrated", "lsv_data_collected"],
    postconditions=["stability_data_collected"],
    estimated_duration_s=36000,  # 10 hours default
    domain="oer",
    template_id="oer_stability_test",
)
