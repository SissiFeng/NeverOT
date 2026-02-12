"""
Frontend UI Demo - 使用标准库urllib (无需安装requests)

简单版本，使用标准库触发前端更新
"""
import time
import json
import urllib.request
import urllib.error

API_BASE = "http://localhost:8000"

def print_step(step_num, title):
    print(f"\n{'='*80}")
    print(f"  Step {step_num}: {title}")
    print(f"{'='*80}\n")

def http_post(url, data):
    """使用urllib发送POST请求"""
    try:
        headers = {'Content-Type': 'application/json'}
        json_data = json.dumps(data).encode('utf-8')

        req = urllib.request.Request(url, data=json_data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode('utf-8'))

    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode('utf-8')}
    except Exception as e:
        return None, {"error": str(e)}

def http_get(url):
    """使用urllib发送GET请求"""
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode('utf-8')}
    except Exception as e:
        return None, {"error": str(e)}


def main():
    """主入口 - 简化版演示"""

    print("\n" + "🎬 " * 25)
    print("  OTbot Frontend UI Demo - 录屏演示")
    print("🎬 " * 25)

    print("\n📹 录屏步骤:")
    print("   1. 浏览器应该已经打开: http://localhost:8000/static/lab.html")
    print("   2. 按 Cmd + Shift + 5 启动macOS录屏")
    print("   3. 选择'录制所选部分'，框选浏览器窗口")
    print("   4. 点击'录制'按钮开始")
    print("   5. 准备好后按Enter继续...")

    input("\n按Enter键开始演示... ")

    print("\n🎬 开始演示...\n")

    # Step 1: 初始化session
    print_step(1, "初始化任务 (前端会显示输入界面)")

    session_id = "demo_" + str(int(time.time()))
    print(f"📋 Session ID: {session_id}")

    user_input = {
        "user_message": """
        我需要优化HER催化剂配方。

        目标：最小化过电位 η10 < 50 mV
        预算：24轮实验
        搜索空间：10种precursor的配比
        """
    }

    print(f"🤖 发送用户输入...")
    time.sleep(1)

    status, data = http_post(f"{API_BASE}/init/{session_id}", user_input)

    if status == 200:
        print("✅ 任务已接收")
        print(f"   前端UI应该显示: 任务参数解析界面")

        injection_pack = data.get("injection_pack", {})
        if injection_pack:
            print(f"\n📊 提取的参数:")
            print(f"   - Objective: {injection_pack.get('objective', 'N/A')}")
            print(f"   - Primary KPI: {injection_pack.get('primary_kpi', 'N/A')}")
            print(f"   - Max rounds: {injection_pack.get('max_rounds', 'N/A')}")

        time.sleep(3)

        # Step 2: 确认参数
        print_step(2, "确认参数 (前端会显示确认界面)")

        confirm_data = {
            "max_rounds": 24,
            "target_kpi_value": 50.0,
            "primary_kpi": "overpotential_eta10"
        }

        print(f"✅ 确认参数...")
        time.sleep(1)

        status2, data2 = http_post(f"{API_BASE}/init/{session_id}/confirm", confirm_data)

        if status2 == 200:
            print("✅ 参数已确认")
            print(f"   前端UI应该显示: Campaign配置完成")

            if "task_contract" in data2:
                contract = data2["task_contract"]
                print(f"\n📋 TaskContract:")
                print(f"   - Contract ID: {contract.get('contract_id', 'N/A')}")
                print(f"   - Created by: {contract.get('created_by', 'N/A')}")

            time.sleep(3)

            # Step 3: 说明实验执行
            print_step(3, "实验执行阶段")

            print("⚗️  说明: 实际执行需要OT-2硬件连接")
            print("   在真实环境中，前端会显示:")
            print("   - 实时进度条")
            print("   - 每轮实验的参数和结果")
            print("   - 收敛曲线图")
            print("   - Agent思考过程日志")

            time.sleep(3)

            # Step 4: 展示前端功能
            print_step(4, "前端UI功能展示")

            print("🖥️  请在浏览器中演示以下功能:")
            print("   1. 查看任务详情页面")
            print("   2. 滚动查看解析的参数")
            print("   3. 点击'确认'按钮（如果可见）")
            print("   4. 查看实验进度区域")
            print("   5. 展示响应式布局（可选）")

            time.sleep(5)

        else:
            print(f"❌ 确认失败: {status2}")
            print(f"   Response: {data2.get('error', 'unknown')[:200]}")

    else:
        print(f"❌ 初始化失败: {status}")
        print(f"   Response: {data.get('error', 'unknown')[:200]}")
        print(f"\n💡 请确保backend正在运行:")
        print(f"   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000")

    # Final
    print("\n" + "="*80)
    print("✅ 演示完成!")
    print("   请停止录屏: 按 Cmd + Ctrl + Esc")
    print("   录屏文件保存在: ~/Desktop/")
    print("="*80)

    print("\n💡 提示:")
    print("   - 可以在前端手动操作展示更多功能")
    print("   - 录屏文件可用于presentation")
    print("   - 建议录制时长: 1-2分钟")


if __name__ == "__main__":
    main()
