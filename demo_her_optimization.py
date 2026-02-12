#!/usr/bin/env python3
"""
Demo: Autonomous HER Catalyst Discovery Workflow

自动演示电化学催化剂发现的完整闭环workflow：
1. 初始化任务（24轮实验预算）
2. 第一轮：多样性探索（LHS采样）
3. 第二轮：贝叶斯优化（EI acquisition）
4. 展示agent思考过程、实验参数、结果
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

# API endpoint
BASE_URL = "http://localhost:8000"


def print_header(title: str):
    """打印美化的标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_thinking(agent: str, thought: str):
    """展示agent思考过程"""
    print(f"\n🤖 [{agent}] {thought}")


async def demo_her_optimization():
    """完整演示HER催化剂优化workflow"""

    async with httpx.AsyncClient(timeout=300.0) as client:

        # ===================================================================
        # Step 1: 创建Session - HER Catalyst Discovery任务
        # ===================================================================
        print_header("Step 1: 初始化HER催化剂发现任务")

        print_thinking("User Input", "我需要发现高效的HER催化剂...")

        task_description = """
Role & Goal: 自主实验规划agent，控制Opentrons OT-2电化学自驱动实验室。
目标：通过自动电沉积+电化学验证，发现混合金属(氧)氢氧化物/氧化物电催化剂用于碱性HER。

Objective: 最小化HER过电位 η10 (10 mA/cm²测量，1 M KOH)
- Target: η10 < 50 mV (成功标准)
- Primary metric: η10 (mV)
- Secondary: Tafel slope, EIS (RΩ, Rct), stability

Resource Context:
- 10种前驱体溶液 + DI water + 1 M KOH
- Ni foil工作电极（新鲜制备）
- 反应器清洁：水/酸冲洗 + 超声
- 反应器加热：35°C（提高沉积动力学）

Experiment Budget: 最大24轮实验
每轮全自动：制备前驱体混合物 → 电沉积 → 拍照 → HER测试 → 记录结果 → 决策下一轮

决策变量（每轮选择）：
1. 10种溶液的组成向量（非负分数，和为1）
2. 总前驱体体积
3. 电沉积条件：电流密度（默认10 mA/cm²）、时间（30-60s范围）
4. 可选：混合/超声、反应器温度

优化策略：
- 起始：4-6个多样性种子recipe（空间填充）
- 闭环：贝叶斯优化/bandit风格，η10为目标
- Acquisition: qEI/UCB（平衡探索vs利用）
- 修复规则：如果模型提出风险recipe，自动调整到最近安全区域

停止条件：
- 达到η10 < 50 mV（预算允许时重复确认）
- 或24轮用尽
"""

        # 模拟conversation flow初始化
        init_payload = {
            "user_input": task_description,
            "metadata": {
                "workflow_type": "ampere2_style_her",
                "max_rounds": 24,
                "target_metric": "eta10_mv",
                "target_value": 50.0,
                "maximize": False  # Minimize η10
            }
        }

        print("\n📤 Sending initialization request...")
        print(f"Target: η10 < 50 mV (minimize overpotential)")
        print(f"Budget: 24 rounds")
        print(f"Stock solutions: 10")

        # 假设使用/init API
        try:
            resp = await client.post(
                f"{BASE_URL}/api/v1/init",
                json=init_payload
            )

            if resp.status_code == 200:
                session_data = resp.json()
                session_id = session_data.get("session_id", "demo-session-001")
                print(f"\n✅ Session created: {session_id}")
                print(f"   Task type: HER catalyst optimization")
                print(f"   Strategy: Bayesian optimization with space-filling LHS start")
            else:
                print(f"\n⚠️  Using mock session (API returned {resp.status_code})")
                session_id = "demo-session-001"
        except Exception as e:
            print(f"\n⚠️  Using mock session (API error: {e})")
            session_id = "demo-session-001"

        time.sleep(2)

        # ===================================================================
        # Step 2: Round 1 - 多样性探索（Space-Filling LHS）
        # ===================================================================
        print_header("Step 2: Round 1 - 多样性探索阶段")

        print_thinking("PlannerAgent", "第一轮：使用Latin Hypercube Sampling生成多样性种子...")
        time.sleep(1)

        print("\n🔬 Experiment Design:")
        print("   Strategy: LHS (Latin Hypercube Sampling)")
        print("   Goal: Explore diverse regions of 10D composition space")

        # 模拟LHS生成的recipe
        recipe_1 = {
            "stock_fractions": [0.15, 0.08, 0.22, 0.05, 0.12, 0.18, 0.03, 0.09, 0.06, 0.02],
            "total_volume_ml": 2.5,
            "deposition": {
                "current_density_ma_cm2": 10.0,
                "time_seconds": 45
            },
            "temperature_c": 35.0,
            "ultrasound_during_dosing": True
        }

        print(f"\n📊 Recipe #1:")
        print(f"   Composition: {[f'{f:.2f}' for f in recipe_1['stock_fractions']]}")
        print(f"   Volume: {recipe_1['total_volume_ml']} mL")
        print(f"   Deposition: {recipe_1['deposition']['current_density_ma_cm2']} mA/cm², {recipe_1['deposition']['time_seconds']}s")
        print(f"   Temperature: {recipe_1['temperature_c']}°C")

        time.sleep(1)

        print_thinking("CompilerAgent", "生成OT-2 protocol...")
        print("\n🔧 Protocol Steps:")
        print("   1. Pre-clean reactor (water rinse + ultrasound 30s)")
        print("   2. Acid rinse (1M H2SO4, 10s)")
        print("   3. Final water rinse + ultrasound (20s)")
        print("   4. Dispense precursor mixture to well A1")
        print("   5. Run electrodeposition (10 mA/cm², 45s)")
        print("   6. Clean deposition tool (acid + water + ultrasound)")
        print("   7. Capture photo (top-view, well A1)")
        print("   8. Flush precursor, fill 1M KOH")
        print("   9. Insert 3-electrode HER test setup")
        print("   10. Run HER protocol (CV + EIS + galvanostatic step)")
        print("   11. Compute η10 from polarization data")

        time.sleep(2)

        print_thinking("SafetyAgent", "验证协议安全性...")
        print("   ✅ Volume within well capacity (3.0 mL max)")
        print("   ✅ Current density safe (10 mA/cm² < 50 mA/cm² limit)")
        print("   ✅ No incompatible simultaneous movements")
        print("   ✅ Acid exposure time within limits")

        time.sleep(1)

        print_header("Round 1: 执行实验")

        print("⚗️  Executing synthesis...")
        for step in ["Cleaning reactor", "Dispensing precursors", "Electrodeposition", "Photo capture"]:
            print(f"   {step}...", end="", flush=True)
            time.sleep(0.8)
            print(" ✓")

        print("\n🧪 HER Testing...")
        for step in ["CV scan (-0.2 to -0.6V vs RHE)", "EIS (100kHz-0.1Hz)", "Galvanostatic (10 mA/cm², 60s)"]:
            print(f"   {step}...", end="", flush=True)
            time.sleep(1.0)
            print(" ✓")

        time.sleep(1)

        # 模拟结果
        result_1 = {
            "round_id": 1,
            "eta10_mv": 127.3,
            "tafel_slope_mv_dec": 89.2,
            "r_ohm": 3.8,
            "r_ct": 12.4,
            "photo_qc": "good",
            "validity": "valid"
        }

        print(f"\n📈 Results:")
        print(f"   η10 = {result_1['eta10_mv']:.1f} mV")
        print(f"   Tafel slope = {result_1['tafel_slope_mv_dec']:.1f} mV/dec")
        print(f"   RΩ = {result_1['r_ohm']:.1f} Ω")
        print(f"   Rct = {result_1['r_ct']:.1f} Ω")
        print(f"   Photo QC: {result_1['photo_qc']}")
        print(f"   Status: {result_1['validity']} ✅")

        time.sleep(2)

        # ===================================================================
        # Step 3: Round 2 - Bayesian Optimization
        # ===================================================================
        print_header("Step 3: Round 2 - 贝叶斯优化阶段")

        print_thinking("StrategySelector", "分析Round 1数据，选择下一轮策略...")
        print("\n📊 Campaign State:")
        print(f"   Rounds completed: 1 / 24")
        print(f"   Valid data points: 1")
        print(f"   Best η10 so far: {result_1['eta10_mv']:.1f} mV")
        print(f"   Target: 50 mV (Gap: {result_1['eta10_mv'] - 50:.1f} mV)")
        print(f"   Progress: {(1 - (result_1['eta10_mv'] - 50) / result_1['eta10_mv']) * 100:.1f}%")

        time.sleep(1)

        print_thinking("StrategySelector", "决策：切换到Bayesian优化（数据点>=1，未收敛）")
        print("   Selected: bayesian_knn (KNN surrogate + EI acquisition)")
        print("   Reason: Enough data for model, far from target")

        time.sleep(1)

        print_thinking("CandidateGenerator", "训练KNN surrogate model...")
        print("   Features: 10D composition + volume + deposition params")
        print("   Target: η10 (minimize)")
        print("   Model: KNN regressor (k=3)")
        print("   Acquisition: Expected Improvement (EI)")

        time.sleep(1)

        print("\n🎯 Proposing next candidate...")
        print("   Acquisition function: EI(x) = E[max(0, f_best - f(x))]")
        print("   Optimization: Differential Evolution over 10D simplex")

        recipe_2 = {
            "stock_fractions": [0.09, 0.21, 0.18, 0.03, 0.15, 0.11, 0.08, 0.07, 0.05, 0.03],
            "total_volume_ml": 2.8,
            "deposition": {
                "current_density_ma_cm2": 10.0,
                "time_seconds": 50
            },
            "temperature_c": 35.0,
            "ultrasound_during_dosing": True
        }

        print(f"\n📊 Recipe #2 (BO-proposed):")
        print(f"   Composition: {[f'{f:.2f}' for f in recipe_2['stock_fractions']]}")
        print(f"   Volume: {recipe_2['total_volume_ml']} mL")
        print(f"   Deposition: {recipe_2['deposition']['current_density_ma_cm2']} mA/cm², {recipe_2['deposition']['time_seconds']}s")
        print(f"   Expected improvement: High (EI = 15.3)")

        time.sleep(2)

        print_thinking("SafetyAgent", "验证新recipe安全性...")
        print("   ✅ All constraints satisfied")
        print("   ✅ Similar to validated region (low risk)")

        time.sleep(1)

        print_header("Round 2: 执行实验")

        print("⚗️  Executing synthesis...")
        for step in ["Cleaning", "Dispensing", "Deposition", "Photo"]:
            print(f"   {step}...", end="", flush=True)
            time.sleep(0.6)
            print(" ✓")

        print("\n🧪 HER Testing...")
        time.sleep(1.5)

        result_2 = {
            "round_id": 2,
            "eta10_mv": 89.7,
            "tafel_slope_mv_dec": 72.1,
            "r_ohm": 3.5,
            "r_ct": 8.9,
            "photo_qc": "good",
            "validity": "valid"
        }

        print(f"\n📈 Results:")
        print(f"   η10 = {result_2['eta10_mv']:.1f} mV  ⬇️ ({result_1['eta10_mv'] - result_2['eta10_mv']:.1f} mV improvement!)")
        print(f"   Tafel slope = {result_2['tafel_slope_mv_dec']:.1f} mV/dec  ⬇️")
        print(f"   RΩ = {result_2['r_ohm']:.1f} Ω")
        print(f"   Rct = {result_2['r_ct']:.1f} Ω  ⬇️")
        print(f"   Status: {result_2['validity']} ✅")

        time.sleep(2)

        # ===================================================================
        # Step 4: Convergence Analysis
        # ===================================================================
        print_header("Step 4: 收敛分析")

        print_thinking("ConvergenceDetector", "分析当前进展...")

        print("\n📊 Campaign Progress:")
        print(f"   Rounds: 2 / 24 (8.3% budget used)")
        print(f"   Valid experiments: 2")
        print(f"   Best η10: {result_2['eta10_mv']:.1f} mV")
        print(f"   Improvement: {result_1['eta10_mv'] - result_2['eta10_mv']:.1f} mV (29.5%)")
        print(f"   Gap to target: {result_2['eta10_mv'] - 50:.1f} mV")

        print("\n🔍 Advanced Convergence Analysis:")
        print("   Status: IMPROVING")
        print("   Short-term trend: strong improvement")
        print("   Long-term trend: insufficient data")
        print("   Oscillation: not detected")
        print("   Noise level: low (high SNR)")
        print("   Uncertainty: high (only 2 data points)")
        print("   Cost-benefit: favorable (improvement >> cost)")

        print("\n💡 Decision: CONTINUE")
        print("   Reason: Strong improvement, far from target, low budget usage")
        print("   Recommendation: Continue BO for 2-3 more rounds, then reassess")

        time.sleep(2)

        # ===================================================================
        # Step 5: Summary & Next Steps
        # ===================================================================
        print_header("Summary & Next Steps")

        print("\n✨ Completed Rounds: 2 / 24")
        print("\n📊 Results So Far:")
        print(f"   Best η10: {result_2['eta10_mv']:.1f} mV (Round 2)")
        print(f"   Improvement: {((result_1['eta10_mv'] - result_2['eta10_mv']) / result_1['eta10_mv'] * 100):.1f}%")
        print(f"   Target achievement: {((50 / result_2['eta10_mv']) * 100):.1f}%")

        print("\n🎯 Top Candidates:")
        print("   1. Recipe #2: η10 = 89.7 mV, Tafel = 72.1 mV/dec")
        print("   2. Recipe #1: η10 = 127.3 mV, Tafel = 89.2 mV/dec")

        print("\n🔮 Next Actions:")
        print("   Round 3-4: Continue Bayesian optimization")
        print("   Round 5: Consider exploitation (refine best region)")
        print("   Round 10: Reassess convergence, consider multi-objective")
        print("   Round 20: Final exploitation phase")

        print("\n💡 Preliminary Insights:")
        print("   - Stock #3 (22% → 18%) shows positive correlation")
        print("   - Stock #2 (8% → 21%) strong positive impact")
        print("   - Longer deposition time (45s → 50s) beneficial")
        print("   - Temperature 35°C + ultrasound optimal so far")

        print("\n🎬 Demo Complete!")
        print(f"   Real workflow would continue for remaining 22 rounds...")
        print(f"   Expected to reach η10 < 50 mV within 10-15 rounds")
        print(f"   Full autonomous operation with no manual intervention")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\n🚀 OTbot - HER Catalyst Discovery Demo")
    print("   Autonomous Electrochemical Self-Driving Lab")
    print("   AMPERE-2 Style Workflow\n")

    asyncio.run(demo_her_optimization())

    print("\n✅ Demo finished!")
    print("   Frontend UI: http://localhost:8000/static/lab.html")
    print("   API Docs: http://localhost:8000/docs")
    print("\n")
