# OTbot Frontend UI 录屏指南

## 方案1: 手动操作录屏（推荐）

### 步骤

1. **准备录屏**
   ```bash
   # 1. 确保backend运行
   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

   # 2. 打开浏览器
   open http://localhost:8000/static/lab.html
   ```

2. **开始录屏**
   - 按 `Cmd + Shift + 5` 打开录屏工具
   - 选择 "录制所选部分"
   - 框选浏览器窗口
   - 点击 "录制" 按钮

3. **演示操作流程**（2-3分钟）

   **Scene 1: 初始界面** (10秒)
   - 展示OTbot主页
   - 介绍系统名称和用途

   **Scene 2: 任务输入** (30秒)
   - 在输入框输入任务描述：
     ```
     我需要优化HER催化剂配方。
     目标：最小化过电位 η10 < 50 mV
     预算：24轮实验
     搜索空间：10种precursor的配比 + 工艺参数
     ```
   - 点击 "提交" 或 "开始" 按钮

   **Scene 3: 参数解析** (20秒)
   - 展示AI自动提取的参数
   - 滚动查看完整参数列表
   - 突出显示关键参数（目标KPI、轮数等）

   **Scene 4: 确认配置** (15秒)
   - 点击 "确认" 按钮
   - 展示Campaign配置完成界面

   **Scene 5: 执行界面** (30秒)
   - 展示实验进度区域
   - 说明：真实环境会显示实时数据
   - 展示预期的UI元素：
     * 进度条
     * 结果表格
     * 收敛曲线图
     * Agent日志

   **Scene 6: 功能亮点** (20秒)
   - 展示侧边栏或菜单
   - 突出显示关键功能
   - 展示响应式布局（缩放浏览器）

4. **停止录屏**
   - 按 `Cmd + Ctrl + Esc` 或点击菜单栏的停止按钮
   - 录屏自动保存到 `~/Desktop/Screen Recording.mov`

---

## 方案2: 使用模拟数据演示

如果真实API不可用，使用浏览器开发者工具模拟数据：

### 步骤

1. **打开开发者工具**
   ```
   在浏览器中按 Cmd + Option + I
   切换到 Console 标签
   ```

2. **注入模拟数据**（在Console中执行）
   ```javascript
   // 模拟任务初始化
   document.querySelector('#task-description').value = `
   我需要优化HER催化剂配方。
   目标：η10 < 50 mV
   预算：24轮实验
   `;

   // 模拟参数显示
   const params = {
       objective: 'minimize_overpotential',
       primary_kpi: 'eta10',
       target: '50 mV',
       max_rounds: 24,
       search_dims: 14
   };

   console.log('Parsed parameters:', params);

   // 模拟实验结果（如果有results div）
   const results = [
       {round: 1, eta10: 127.3, strategy: 'LHS'},
       {round: 2, eta10: 89.7, strategy: 'Bayesian', improvement: '29.5%'}
   ];

   console.table(results);
   ```

3. **手动填充UI**
   - 在输入框输入任务描述
   - 如果有静态demo数据，点击加载
   - 展示UI响应和布局

---

## 方案3: 使用正确的API调用

```python
# demo_frontend_correct.py
import time
import json
import urllib.request

API_BASE = "http://localhost:8000"

def demo():
    print("🎬 OTbot Frontend Demo - 开始录屏！\n")

    # 使用正确的endpoint
    # 1. 启动对话
    data = {
        "protocol_pattern": "her_catalyst_discovery",
        "experiment_goal": "minimize overpotential eta10 < 50 mV",
        "max_rounds": 24
    }

    print("Step 1: 启动campaign")
    response = urllib.request.urlopen(
        urllib.request.Request(
            f"{API_BASE}/init/start",
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
    )

    result = json.loads(response.read())
    session_id = result.get('session_id')
    print(f"✅ Session ID: {session_id}\n")
    time.sleep(3)

    # 2. 获取状态
    print("Step 2: 查询状态")
    status_response = urllib.request.urlopen(
        f"{API_BASE}/init/{session_id}/status"
    )

    status = json.loads(status_response.read())
    print(f"✅ Status: {status}\n")
    time.sleep(3)

    print("✅ Demo完成！请停止录屏。")

if __name__ == "__main__":
    demo()
```

---

## 录屏最佳实践

### 技术设置
- **分辨率**: 1920x1080 (Full HD)
- **帧率**: 30 fps
- **格式**: MOV (macOS默认) 或 MP4
- **音频**: 可选（配音解说）

### 内容建议
1. **开场** (5秒)
   - 显示OTbot logo
   - 标题: "OTbot - Autonomous Lab Orchestration System"

2. **主体** (2分钟)
   - 快速流畅，不要停顿
   - 突出关键功能
   - 清晰的鼠标移动

3. **结尾** (5秒)
   - 展示logo或主页
   - 显示联系方式/GitHub链接

### 后期处理
```bash
# 使用ffmpeg转换格式（如果需要）
ffmpeg -i "Screen Recording.mov" -vcodec h264 -acodec aac demo.mp4

# 压缩大小
ffmpeg -i demo.mp4 -vcodec h264 -crf 28 demo_compressed.mp4

# 添加字幕（使用iMovie或Final Cut Pro）
```

---

## 快速录屏脚本

```bash
#!/bin/bash
# quick_record.sh

echo "🎬 OTbot Frontend UI 录屏助手"
echo "================================"

# 1. 检查backend
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend未运行，启动中..."
    python3 -m uvicorn app.main:app --port 8000 &
    sleep 5
fi

# 2. 打开浏览器
echo "✅ 打开浏览器..."
open http://localhost:8000/static/lab.html

# 3. 等待用户准备
echo ""
echo "📹 请按以下步骤操作:"
echo "   1. 按 Cmd+Shift+5 开始录屏"
echo "   2. 选择浏览器窗口"
echo "   3. 点击'录制'"
echo "   4. 在浏览器中演示功能"
echo "   5. 按 Cmd+Ctrl+Esc 停止"
echo ""
echo "💡 建议录制时长: 2-3分钟"
echo "💡 录屏保存位置: ~/Desktop/"
echo ""
echo "准备好后请手动操作前端UI..."
```

---

## 故障排查

### 问题1: Backend未运行
```bash
# 解决方案
cd /Users/sissifeng/OTbot
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 问题2: 前端显示空白
- 检查浏览器Console是否有错误
- 确认 `app/static/lab.html` 存在
- 刷新页面 (Cmd + R)

### 问题3: API调用失败
- 检查Network标签查看请求详情
- 确认endpoint路径正确
- 查看backend日志

---

## 录屏示例脚本

### 旁白文案（可选）

```
[0:00-0:05]
"欢迎来到OTbot - 自主实验室编排系统"

[0:05-0:15]
"让我们演示如何启动一个HER催化剂优化任务"
（输入任务描述）

[0:15-0:30]
"AI自动解析任务参数，包括目标KPI、搜索空间和预算"
（展示参数列表）

[0:30-0:45]
"用户确认参数后，系统生成TaskContract"
（点击确认按钮）

[0:45-1:15]
"在真实环境中，OT-2机器人会自动执行实验，
前端实时显示进度、结果和收敛曲线"
（展示UI布局）

[1:15-1:30]
"OTbot支持多种优化算法：
Bayesian Optimization、Reinforcement Learning、
Multi-Objective Pareto Optimization"

[1:30-1:45]
"多层Agent协同工作：
Planner、Compiler、Safety、Sensing、Stop"

[1:45-2:00]
"感谢观看！
OTbot - 让实验室自主运行"
（显示logo和GitHub链接）
```

---

## 完成

录屏完成后，视频文件位于:
```
~/Desktop/Screen Recording YYYY-MM-DD at HH.MM.SS.mov
```

可用于:
- ✅ Presentation演示
- ✅ 视频会议分享
- ✅ 投资人展示
- ✅ 技术文档
- ✅ GitHub README

祝录制顺利！🎬
