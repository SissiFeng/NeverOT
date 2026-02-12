"""
Frontend UI Demo - 触发前端显示更新

使用conversation flow API展示前端交互
"""
import time
import requests
import json

API_BASE = "http://localhost:8000"

def print_step(step_num, title):
    print(f"\n{'='*80}")
    print(f"  Step {step_num}: {title}")
    print(f"{'='*80}\n")

def demo_conversation_flow():
    """演示conversation flow - 前端UI会实时更新"""

    print("\n🎬 OTbot Frontend UI Demo")
    print("=" * 80)
    print("请在浏览器中观察前端UI的变化：http://localhost:8000/static/lab.html")
    print("=" * 80)

    # Step 1: 创建session
    print_step(1, "初始化Session")

    session_id = "demo_session_" + str(int(time.time()))
    print(f"📋 Session ID: {session_id}")

    # 模拟用户输入
    user_input = """
    我需要优化HER催化剂配方。

    目标：最小化过电位 η10 < 50 mV
    预算：24轮实验
    搜索空间：10种precursor stock的配比 + 体积、电流密度、时间、温度
    """

    print(f"🤖 User Input:\n{user_input}")

    # Step 2: 发送初始化请求
    print_step(2, "发送任务到后端")

    try:
        response = requests.post(
            f"{API_BASE}/init/{session_id}",
            json={"user_message": user_input},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ 任务已接收")
            print(f"📊 提取的参数:")

            injection_pack = data.get("injection_pack", {})
            if injection_pack:
                print(f"   - Objective: {injection_pack.get('objective', {})}")
                print(f"   - Target KPI: {injection_pack.get('primary_kpi', 'N/A')}")
                print(f"   - Max rounds: {injection_pack.get('max_rounds', 'N/A')}")

            print(f"\n💡 前端UI应该显示任务初始化界面")
            time.sleep(2)

            # Step 3: 确认参数
            print_step(3, "确认参数并启动Campaign")

            confirm_response = requests.post(
                f"{API_BASE}/init/{session_id}/confirm",
                json={
                    "max_rounds": 24,
                    "target_kpi_value": 50.0,
                    "primary_kpi": "overpotential_eta10"
                },
                timeout=30
            )

            if confirm_response.status_code == 200:
                confirm_data = confirm_response.json()
                print("✅ 参数已确认")
                print(f"📋 Campaign ready")

                if "task_contract" in confirm_data:
                    print(f"   - Contract ID: {confirm_data['task_contract'].get('contract_id', 'N/A')}")

                print(f"\n💡 前端UI应该显示campaign配置完成")
                time.sleep(2)

                # Step 4: 模拟实验执行（前端会显示进度）
                print_step(4, "模拟Campaign执行")
                print("⚗️  正在执行实验...")
                print("   (实际执行需要OT-2硬件)")
                print("\n💡 前端UI应该显示实时进度和结果")

                # 提示用户可以在前端查看
                print("\n" + "="*80)
                print("🎯 请在浏览器中查看前端UI的实时更新：")
                print(f"   URL: {API_BASE}/static/lab.html")
                print("="*80)

            else:
                print(f"❌ 确认失败: {confirm_response.status_code}")
                print(f"   Response: {confirm_response.text[:200]}")

        else:
            print(f"❌ 初始化失败: {response.status_code}")
            print(f"   Response: {response.text[:200]}")

    except requests.exceptions.RequestException as e:
        print(f"❌ 连接错误: {str(e)}")
        print(f"   请确保backend正在运行: python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000")


def demo_orchestrate_api():
    """演示orchestrate API - 直接启动campaign"""

    print_step(1, "使用Orchestrate API启动Campaign")

    payload = {
        "objective": {
            "objective_type": "kpi_optimization",
            "primary_kpi": "overpotential_eta10",
            "direction": "minimize",
            "target_value": 50.0
        },
        "exploration_space": {
            "dimensions": [
                {
                    "param_name": f"stock_{i+1}_fraction",
                    "param_type": "number",
                    "min_value": 0.0,
                    "max_value": 1.0
                }
                for i in range(10)
            ] + [
                {"param_name": "total_volume_ml", "param_type": "number", "min_value": 1.0, "max_value": 3.0},
                {"param_name": "deposition_current_density_ma_cm2", "param_type": "number", "min_value": 5.0, "max_value": 20.0},
                {"param_name": "deposition_time_seconds", "param_type": "number", "min_value": 30.0, "max_value": 120.0},
                {"param_name": "temperature_c", "param_type": "number", "min_value": 25.0, "max_value": 45.0}
            ],
            "strategy": "lhs",
            "batch_size": 1
        },
        "stop_conditions": {
            "max_rounds": 24,
            "target_kpi_value": 50.0,
            "target_kpi_direction": "minimize"
        },
        "safety_envelope": {
            "max_volume_ul": 3000.0,
            "max_current_density_ma_cm2": 50.0,
            "max_temperature_c": 50.0
        },
        "protocol_pattern_id": "her_catalyst_discovery",
        "created_by": "demo_user"
    }

    print("📤 发送campaign请求...")
    print(f"   Search space: 14D")
    print(f"   Budget: 24 rounds")
    print(f"   Target: η10 < 50 mV")

    try:
        response = requests.post(
            f"{API_BASE}/orchestrate/start",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            campaign_id = data.get("campaign_id", "unknown")

            print(f"✅ Campaign启动成功!")
            print(f"   Campaign ID: {campaign_id}")
            print(f"   Status: {data.get('status', 'unknown')}")

            print(f"\n💡 前端UI应该显示campaign进度")

            return campaign_id
        else:
            print(f"⚠️  Orchestrate API不可用 (状态码: {response.status_code})")
            print(f"   使用conversation flow代替...")
            return None

    except requests.exceptions.RequestException as e:
        print(f"⚠️  Orchestrate API连接失败: {str(e)}")
        print(f"   使用conversation flow代替...")
        return None


def main():
    """主入口"""

    print("\n" + "🎬 " * 25)
    print("  OTbot Frontend UI Demo - 录屏演示")
    print("🎬 " * 25)

    print("\n📹 录屏准备步骤:")
    print("   1. 在浏览器打开: http://localhost:8000/static/lab.html")
    print("   2. 按 Cmd + Shift + 5 启动macOS录屏")
    print("   3. 选择录制区域（浏览器窗口）")
    print("   4. 点击'录制'按钮")
    print("   5. 然后按Enter继续运行此脚本")

    input("\n按Enter键继续... ")

    print("\n🎬 开始演示...\n")

    # 尝试orchestrate API
    campaign_id = demo_orchestrate_api()

    # 如果orchestrate不可用，使用conversation flow
    if campaign_id is None:
        print("\n" + "="*80)
        print("  切换到Conversation Flow Demo")
        print("="*80)
        demo_conversation_flow()
    else:
        # 如果有campaign，监控状态
        print_step(2, "监控Campaign状态")

        for i in range(10):
            time.sleep(2)
            try:
                status_response = requests.get(
                    f"{API_BASE}/orchestrate/{campaign_id}/status",
                    timeout=5
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    current_round = status_data.get("current_round", 0)
                    status = status_data.get("status", "unknown")

                    print(f"   Round {current_round}: {status}")

                    if status in ["completed", "stopped", "failed"]:
                        print(f"\n✅ Campaign {status}")
                        break
                else:
                    print(f"   ⚠️  状态查询失败")

            except Exception as e:
                print(f"   ⚠️  监控错误: {str(e)}")

    print("\n" + "="*80)
    print("✅ Demo完成!")
    print("   请停止录屏（Cmd + Ctrl + Esc）")
    print("   录屏文件保存在桌面")
    print("="*80)


if __name__ == "__main__":
    main()
