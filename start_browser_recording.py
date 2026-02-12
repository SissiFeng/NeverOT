"""
启动浏览器自动录屏

使用浏览器内置的MediaRecorder API录制前端UI
"""
import subprocess
import time

API_BASE = "http://localhost:8000"

print("\n🎬 OTbot 浏览器录屏系统")
print("="*80)

print("\n📋 使用说明:")
print("   1. 浏览器将自动打开录制页面")
print("   2. 点击'开始录制'按钮")
print("   3. 在弹出窗口中选择要录制的标签页（选择包含OTbot UI的标签页）")
print("   4. 点击'分享'开始录制")
print("   5. 录制将自动运行50秒")
print("   6. 完成后自动下载.webm视频文件")

print("\n⚡ 优势:")
print("   ✓ 无需系统权限")
print("   ✓ 高质量视频（1920x1080, 30fps）")
print("   ✓ 自动触发demo")
print("   ✓ 自动保存和下载")
print("   ✓ 可转换为MP4: ffmpeg -i demo.webm demo.mp4")

print("\n🚀 正在打开浏览器...")
time.sleep(1)

# 打开录制页面
subprocess.run([
    "open",
    f"{API_BASE}/static/auto_record.html"
])

print("\n✅ 录制页面已打开！")
print("\n💡 快捷键:")
print("   Ctrl+R: 开始录制")
print("   Ctrl+S: 停止录制")

print("\n" + "="*80)
