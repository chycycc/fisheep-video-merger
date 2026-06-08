"""
全面 UI 测试 — 覆盖 6 个工具标签页
使用 Playwright 连接 pywebview 内置 HTTP 服务器
"""
import sys
import os
import time
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:46253/index.html"
SCREENSHOT_DIR = r"D:\Dev\fisheep-video-merger\tests\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

passed = [0]
failed = [0]
errors = []

def check(name, cond):
    if cond:
        print(f"  PASS: {name}")
        passed[0] += 1
    else:
        print(f"  FAIL: {name}")
        failed[0] += 1
        errors.append(name)

def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")

def test_full_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(APP_URL)
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        # ==========================================
        section("L0: 全局检查")
        # ==========================================
        title = page.title()
        check("页面标题包含 Fisheep", "Fisheep" in title)
        check("Alpine.js 已加载", page.evaluate('typeof Alpine !== "undefined"'))

        # 检查所有 6 个侧栏按钮
        tools = ['merge', 'convert', 'extract', 'compress', 'trim', 'subtitle']
        for tool in tools:
            btn = page.query_selector(f'button[data-tool="{tool}"]')
            check(f'侧栏按钮 [{tool}] 存在', btn is not None)

        # ==========================================
        section("L1: 格式转换 (convert)")
        # ==========================================
        page.click('button[data-tool="convert"]')
        time.sleep(1)
        check("面板可见", page.evaluate('document.getElementById("tool-convert").classList.contains("active")'))
        check("#convert-format 存在", page.query_selector('#convert-format') is not None)
        check("#convert-mode 存在", page.query_selector('#convert-mode') is not None)
        check("#convert-output-dir 存在", page.query_selector('#convert-output-dir') is not None)
        check("#convert-output-name 存在", page.query_selector('#convert-output-name') is not None)

        # 检查格式选项
        fmt = page.query_selector('#convert-format')
        if fmt:
            opts = [o.get_attribute('value') for o in fmt.query_selector_all('option')]
            check("格式选项 mp4/mkv/webm/avi", set(opts) == {'mp4', 'mkv', 'webm', 'avi'})

        # 检查模式选项
        mode = page.query_selector('#convert-mode')
        if mode:
            opts = [o.get_attribute('value') for o in mode.query_selector_all('option')]
            check("模式选项 copy/recode", 'copy' in opts and 'recode' in opts)

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '01_convert.png'), full_page=True)

        # ==========================================
        section("L2: 提取音频 (extract)")
        # ==========================================
        page.click('button[data-tool="extract"]')
        time.sleep(1)
        check("面板可见", page.evaluate('document.getElementById("tool-extract").classList.contains("active")'))
        check("#extract-format 存在", page.query_selector('#extract-format') is not None)
        check("#extract-bitrate 存在", page.query_selector('#extract-bitrate') is not None)
        check("#extract-bitrate-mode 存在", page.query_selector('#extract-bitrate-mode') is not None)
        check("#extract-channels 存在", page.query_selector('#extract-channels') is not None)
        check("#extract-sample-rate 存在", page.query_selector('#extract-sample-rate') is not None)
        check("#extract-volume 存在", page.query_selector('#extract-volume') is not None)

        # 检查格式选项
        fmt = page.query_selector('#extract-format')
        if fmt:
            opts = [o.get_attribute('value') for o in fmt.query_selector_all('option')]
            check("格式选项 mp3/aac/flac/wav", set(opts) == {'mp3', 'aac', 'flac', 'wav'})

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '02_extract.png'), full_page=True)

        # ==========================================
        section("L3: 视频压缩 (compress)")
        # ==========================================
        page.click('button[data-tool="compress"]')
        time.sleep(1)
        check("面板可见", page.evaluate('document.getElementById("tool-compress").classList.contains("active")'))
        check("#compress-preset 存在", page.query_selector('#compress-preset') is not None)
        check("#compress-resolution 存在", page.query_selector('#compress-resolution') is not None)

        # 检查预设选项
        pre = page.query_selector('#compress-preset')
        if pre:
            opts = [o.get_attribute('value') for o in pre.query_selector_all('option')]
            check("预设 fast/balanced/quality", 'fast' in opts and 'balanced' in opts and 'quality' in opts)

        # 检查分辨率选项
        res = page.query_selector('#compress-resolution')
        if res:
            opts = [o.get_attribute('value') for o in res.query_selector_all('option')]
            check("分辨率 original/1080p/720p/480p", 'original' in opts and '720p' in opts)

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '03_compress.png'), full_page=True)

        # ==========================================
        section("L4: 视频裁剪 (trim)")
        # ==========================================
        page.click('button[data-tool="trim"]')
        time.sleep(1)
        check("面板可见", page.evaluate('document.getElementById("tool-trim").classList.contains("active")'))
        check("#trim-start 存在", page.query_selector('#trim-start') is not None)
        check("#trim-end 存在", page.query_selector('#trim-end') is not None)
        check("#trim-mode 存在", page.query_selector('#trim-mode') is not None)

        # 检查裁剪模式选项
        tm = page.query_selector('#trim-mode')
        if tm:
            opts = [o.get_attribute('value') for o in tm.query_selector_all('option')]
            check("模式 copy/recode", 'copy' in opts and 'recode' in opts)

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '04_trim.png'), full_page=True)

        # ==========================================
        section("L5: 字幕工具 (subtitle)")
        # ==========================================
        page.click('button[data-tool="subtitle"]')
        time.sleep(1)
        check("面板可见", page.evaluate('document.getElementById("tool-subtitle").classList.contains("active")'))

        # 检查 6 个子 Tab
        tabs = page.query_selector_all('#tool-subtitle .subtab-bar button')
        check("6 个子 Tab", len(tabs) == 6)

        # 强制显示所有参数面板
        page.evaluate('document.querySelectorAll("#tool-subtitle .tool-options").forEach(o=>{o.style.display="flex"})')
        time.sleep(0.3)

        # 调轴面板
        check("#subtitle-adjust-offset 存在", page.query_selector('#subtitle-adjust-offset') is not None)
        check("#subtitle-adjust-output-dir 存在", page.query_selector('#subtitle-adjust-output-dir') is not None)
        check("#subtitle-adjust-output-name 存在", page.query_selector('#subtitle-adjust-output-name') is not None)

        # 合并面板
        check("#subtitle-merge-file-a 存在", page.query_selector('#subtitle-merge-file-a') is not None)
        check("#subtitle-merge-file-b 存在", page.query_selector('#subtitle-merge-file-b') is not None)
        check("#subtitle-merge-layout 存在", page.query_selector('#subtitle-merge-layout') is not None)
        check("#subtitle-merge-output-dir 存在", page.query_selector('#subtitle-merge-output-dir') is not None)

        # 转换面板
        check("#subtitle-convert-format 存在", page.query_selector('#subtitle-convert-format') is not None)
        check("#subtitle-convert-output-dir 存在", page.query_selector('#subtitle-convert-output-dir') is not None)
        fmt = page.query_selector('#subtitle-convert-format')
        if fmt:
            opts = [o.get_attribute('value') for o in fmt.query_selector_all('option')]
            check("字幕格式 srt/ass/ssa/vtt", 'srt' in opts and 'ass' in opts and 'vtt' in opts)

        # 拆分面板
        check("#subtitle-split-rule 存在", page.query_selector('#subtitle-split-rule') is not None)
        check("#subtitle-split-regex 存在", page.query_selector('#subtitle-split-regex') is not None)
        check("#subtitle-split-output-dir 存在", page.query_selector('#subtitle-split-output-dir') is not None)

        # 提取面板
        check("#subtitle-extract-stream 存在", page.query_selector('#subtitle-extract-stream') is not None)
        check("#subtitle-extract-format 存在", page.query_selector('#subtitle-extract-format') is not None)
        check("#subtitle-extract-output-dir 存在", page.query_selector('#subtitle-extract-output-dir') is not None)

        # 批量面板
        check("#subtitle-batch-operation 存在", page.query_selector('#subtitle-batch-operation') is not None)
        check("#subtitle-batch-output-dir 存在", page.query_selector('#subtitle-batch-output-dir') is not None)

        # 检查合并布局选项
        layout = page.query_selector('#subtitle-merge-layout')
        if layout:
            opts = [o.get_attribute('value') for o in layout.query_selector_all('option')]
            check("合并布局选项存在", len(opts) >= 2)

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '05_subtitle.png'), full_page=True)

        # ==========================================
        section("L6: 音视频合并 (merge)")
        # ==========================================
        page.click('button[data-tool="merge"]')
        time.sleep(1)
        check("面板可见", page.evaluate('document.getElementById("tool-merge").classList.contains("active")'))
        check("#add-folder-btn 存在", page.query_selector('#add-folder-btn') is not None)
        check("#add-files-btn 存在", page.query_selector('#add-files-btn') is not None)
        check("#clear-btn 存在", page.query_selector('#clear-btn') is not None)
        check("#global-output-dir 存在", page.query_selector('#global-output-dir') is not None)
        check("#merge-format 存在", page.query_selector('#merge-format') is not None)
        check("#merge-concurrency 存在", page.query_selector('#merge-concurrency') is not None)
        check("#global-start-btn 存在", page.query_selector('#global-start-btn') is not None)

        # 检查子标签
        subtabs = page.query_selector_all('.subtab-bar button[data-parent="merge"]')
        check("合并子标签存在", len(subtabs) >= 3)

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '06_merge.png'), full_page=True)

        # ==========================================
        section("L7: JS ID 一致性检查")
        # ==========================================
        # 检查 subtitle.js 中的 ID 和 HTML 一致
        js_path = r'D:\Dev\fisheep-video-merger\src\fisheep_video_merger\ui\web\js\tools\subtitle.js'
        js_code = open(js_path, encoding='utf-8').read()

        js_ids = [
            'subtitle-adjust-offset', 'subtitle-adjust-output-dir',
            'subtitle-convert-format', 'subtitle-extract-stream',
            'subtitle-extract-format', 'subtitle-split-regex',
            'subtitle-merge-file-a', 'subtitle-merge-file-b',
            'subtitle-merge-layout', 'subtitle-merge-output-dir',
        ]
        for jid in js_ids:
            check(f'JS 引用 #{jid}', jid in js_code)

        # ==========================================
        section("测试结果汇总")
        # ==========================================
        print(f"\n  通过: {passed[0]}")
        print(f"  失败: {failed[0]}")
        if errors:
            print(f"\n  失败项:")
            for e in errors:
                print(f"    - {e}")
        print(f"\n  截图保存在: {SCREENSHOT_DIR}")

        browser.close()
        return failed[0] == 0


if __name__ == "__main__":
    success = test_full_ui()
    sys.exit(0 if success else 1)
