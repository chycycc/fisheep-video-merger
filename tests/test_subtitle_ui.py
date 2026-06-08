"""
字幕工具 UI 自动化测试
使用 Playwright 打开应用前端，验证字幕工具面板的 UI 元素
"""
import sys
import os
import time

PROJECT_ROOT = r"D:\Dev\fisheep-video-merger"
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from playwright.sync_api import sync_playwright


def test_subtitle_ui():
    """测试字幕工具 UI 元素"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 注入 mock pywebview API（Alpine.js 初始化需要）
        page.add_init_script("""
            window.pywebview = {
                api: new Proxy({}, {
                    get: (target, prop) => {
                        return (...args) => {
                            console.log('[Mock] ' + prop + '(' + JSON.stringify(args) + ')');
                            return Promise.resolve({ status: 'success', message: 'mock' });
                        };
                    }
                })
            };
        """)

        html_path = os.path.join(
            PROJECT_ROOT, "src", "fisheep_video_merger", "ui", "web", "index.html"
        )
        page.goto(f"file:///{html_path.replace(os.sep, '/')}")
        page.wait_for_load_state("networkidle")
        time.sleep(2)  # 等待 Alpine.js 完全初始化

        passed = 0
        failed = 0

        def check(name, condition):
            nonlocal passed, failed
            if condition:
                print(f"  PASS: {name}")
                passed += 1
            else:
                print(f"  FAIL: {name}")
                failed += 1

        print("=== 1. 侧栏按钮 ===")
        subtitle_btn = page.query_selector('button[data-tool="subtitle"]')
        check("字幕工具按钮存在", subtitle_btn is not None)
        if subtitle_btn:
            text = subtitle_btn.inner_text()
            check("按钮文字包含'字幕工具'", "字幕工具" in text)

        print("\n=== 2. 点击按钮切换面板 ===")
        if subtitle_btn:
            subtitle_btn.click()
            time.sleep(1)
            panel = page.query_selector("#tool-subtitle")
            check("字幕工具面板存在", panel is not None)
            # 检查面板是否可见（active class 或 style display）
            is_visible = page.evaluate("""
                () => {
                    const panel = document.getElementById('tool-subtitle');
                    if (!panel) return false;
                    const cls = panel.className || '';
                    const style = window.getComputedStyle(panel);
                    return cls.includes('active') || style.display !== 'none';
                }
            """)
            check("面板处于可见状态", is_visible)

        print("\n=== 3. 子功能 Tab 栏 ===")
        tabs = page.query_selector_all("#tool-subtitle .subtab-bar button")
        check("有 6 个子功能 Tab", len(tabs) == 6)
        if len(tabs) >= 6:
            tab_texts = [t.inner_text().strip() for t in tabs]
            print(f"    Tab 文字: {tab_texts}")
            check("'调轴' Tab 存在", any("调轴" in t for t in tab_texts))
            check("'合并' Tab 存在", any("合并" in t for t in tab_texts))
            check("'转换' Tab 存在", any("转换" in t for t in tab_texts))
            check("'拆分' Tab 存在", any("拆分" in t for t in tab_texts))
            check("'提取' Tab 存在", any("提取" in t for t in tab_texts))
            check("'批量' Tab 存在", any("批量" in t for t in tab_texts))

        print("\n=== 4. 调轴参数面板（默认显示）===")
        # 调轴面板默认可见（activeTab = 'adjust'）
        offset_input = page.query_selector("#subtitle-offset")
        check("偏移量输入框存在", offset_input is not None)
        # 检查是否可见
        offset_visible = page.evaluate("""
            () => {
                const el = document.getElementById('subtitle-offset');
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden';
            }
        """)
        check("偏移量输入框可见", offset_visible)

        print("\n=== 5. 切换到合并 Tab ===")
        if len(tabs) >= 2:
            tabs[1].click()  # 合并是第 2 个 Tab
            time.sleep(0.5)
            file_a = page.query_selector("#subtitle-merge-file-a")
            check("合并文件 A 输入框存在", file_a is not None)
            file_b = page.query_selector("#subtitle-merge-file-b")
            check("合并文件 B 输入框存在", file_b is not None)
            layout = page.query_selector("#subtitle-merge-layout")
            check("布局选择下拉存在", layout is not None)

        print("\n=== 6. 切换到转换 Tab ===")
        if len(tabs) >= 3:
            tabs[2].click()  # 转换是第 3 个 Tab
            time.sleep(0.5)
            fmt = page.query_selector("#subtitle-format")
            check("目标格式下拉存在", fmt is not None)
            if fmt:
                options = fmt.query_selector_all("option")
                check("有 4 个格式选项", len(options) == 4)

        print("\n=== 7. 切换到拆分 Tab ===")
        if len(tabs) >= 4:
            tabs[3].click()  # 拆分是第 4 个 Tab
            time.sleep(0.5)
            mode = page.query_selector("#subtitle-split-mode")
            check("拆分规则下拉存在", mode is not None)
            pattern = page.query_selector("#subtitle-split-pattern")
            check("正则输入框存在", pattern is not None)

        print("\n=== 8. 切换到提取 Tab ===")
        if len(tabs) >= 5:
            tabs[4].click()  # 提取是第 5 个 Tab
            time.sleep(0.5)
            stream = page.query_selector("#subtitle-stream")
            check("字幕流选择下拉存在", stream is not None)
            ext_fmt = page.query_selector("#subtitle-extract-format")
            check("提取格式下拉存在", ext_fmt is not None)

        print("\n=== 9. 切换到批量 Tab ===")
        if len(tabs) >= 6:
            tabs[5].click()  # 批量是第 6 个 Tab
            time.sleep(0.5)
            batch_op = page.query_selector("#subtitle-batch-operation")
            check("批量操作下拉存在", batch_op is not None)

        print("\n=== 10. 添加文件按钮 ===")
        add_btn = page.query_selector('#tool-subtitle .header-actions button')
        check("添加文件按钮存在", add_btn is not None)

        # 截图保存
        page.screenshot(path=os.path.join(PROJECT_ROOT, "tests", "subtitle_tool_screenshot.png"), full_page=True)
        print("\n截图已保存到 tests/subtitle_tool_screenshot.png")

        browser.close()

        print(f"\n{'='*40}")
        print(f"Result: {passed} passed, {failed} failed")
        return failed == 0


if __name__ == "__main__":
    success = test_subtitle_ui()
    sys.exit(0 if success else 1)
