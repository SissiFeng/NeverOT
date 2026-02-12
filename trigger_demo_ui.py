"""
触发Demo Campaign并打开前端UI

展示完整的agent执行树和硬件操控过程
"""
import json
import urllib.request
import time
import subprocess

API_BASE = "http://localhost:8000"

def trigger_demo():
    """触发demo campaign"""
    print("🎬 OTbot Demo - 触发详细执行演示\n")
    print("="*80)

    # 打开前端UI
    print("📱 打开前端UI...")
    subprocess.run(["open", f"{API_BASE}/static/lab.html"], check=False)
    time.sleep(2)

    print("\n📹 录屏准备:")
    print("   1. 按 Cmd + Shift + 5")
    print("   2. 选择'录制所选部分'")
    print("   3. 框选浏览器窗口")
    print("   4. 点击'录制'")
    print("\n⏰ 5秒后自动触发demo...\n")

    for i in range(5, 0, -1):
        print(f"   {i}...")
        time.sleep(1)

    print("\n🚀 触发demo campaign...\n")

    # 调用demo endpoint
    try:
        data = json.dumps({
            "objective_kpi": "overpotential_eta10",
            "max_rounds": 2
        }).encode('utf-8')

        req = urllib.request.Request(
            f"{API_BASE}/api/v1/orchestrate/demo",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            campaign_id = result.get('campaign_id', 'unknown')

            print(f"✅ Demo campaign started!")
            print(f"   Campaign ID: {campaign_id}")
            print(f"   Status: {result.get('status', 'unknown')}")
            print(f"\n💡 前端UI将实时显示:")
            print(f"   • Agent思考过程（PlannerAgent, SafetyAgent等）")
            print(f"   • 工具调用链（P300, P20 pipettes等）")
            print(f"   • 硬件操控步骤（清洗、分配、沉积、测试）")
            print(f"   • 协议步骤（11步详细workflow）")
            print(f"   • 安全检查（5项验证）")
            print(f"   • QC验证（photo, CV, EIS）")

            print(f"\n📊 Demo包含2轮实验:")
            print(f"   Round 1: LHS策略（探索）")
            print(f"   Round 2: Bayesian优化（利用）")

            print(f"\n🎯 预期结果:")
            print(f"   Round 1: η10 = 127.3 mV")
            print(f"   Round 2: η10 = 89.7 mV (29.5% improvement!)")

            print(f"\n⏱️  预计时长: ~30-40秒")
            print(f"   (带模拟延迟，便于观察)")

            print(f"\n🔗 SSE事件流: {API_BASE}/api/v1/orchestrate/{campaign_id}/events/stream")

    except Exception as e:
        print(f"❌ 触发失败: {e}")
        print(f"\n💡 请确保:")
        print(f"   1. Backend正在运行 (python3 -m uvicorn app.main:app --port 8000)")
        print(f"   2. 前端已打开 ({API_BASE}/static/lab.html)")
        return

    print(f"\n{'='*80}")
    print(f"✅ Demo已触发，请观察前端UI的实时更新！")
    print(f"   停止录屏: Cmd + Ctrl + Esc")
    print(f"   录屏保存: ~/Desktop/Screen Recording.mov")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    trigger_demo()
