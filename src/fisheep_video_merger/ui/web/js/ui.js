/**
 * ui.js — UI 交互组件模块
 * 负责主题切换、侧栏折叠、Toast 弹窗、右键菜单、行选择高亮、剪贴板复制、自定义提示
 */

import { callPython } from './bridge.js';

// 右键菜单模式：'custom' = 自定义菜单, 'native' = 系统原生菜单
let contextMenuMode = localStorage.getItem('contextMenuMode') || 'native';

/**
 * 复制文字到剪贴板（优先 Python bridge，file:// 下 navigator.clipboard 不可用）
 * @param {string} text - 要复制的文字
 */
export function copyText(text) {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.copy_to_clipboard(text).then(res => {
            if (res && res.status === 'success') {
                showToast('已复制到剪贴板', 'success');
            } else {
                jsCopyFallback(text);
            }
        }).catch(() => jsCopyFallback(text));
    } else {
        jsCopyFallback(text);
    }
}

/**
 * JS 降级复制（textarea + execCommand，file:// 下可用）
 * @param {string} text - 要复制的文字
 */
export function jsCopyFallback(text) {
    try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0;left:-9999px;';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('已复制到剪贴板', 'success');
    } catch (e) {
        showToast('复制失败，请手动选择文字', 'error');
    }
}

/**
 * 切换右键菜单模式（自定义 / 系统原生）
 */
export function toggleContextMenu() {
    contextMenuMode = contextMenuMode === 'custom' ? 'native' : 'custom';
    localStorage.setItem('contextMenuMode', contextMenuMode);
    showToast(`右键菜单: ${contextMenuMode === 'custom' ? '自定义' : '原生'}`, 'info');
}

/**
 * 主题自适应初始化（Dark/Light/Auto）
 */
export function initTheme() {
    const themeBtn = document.getElementById('theme-switch-btn');
    const themeSelect = document.getElementById('theme-select');
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    // 默认载入跟随系统主题
    let currentTheme = localStorage.getItem('theme') || 'auto';
    applyTheme(currentTheme);

    // 监听系统主题颜色切换
    mediaQuery.addEventListener('change', (e) => {
        if (currentTheme === 'auto') {
            const systemTheme = e.matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', systemTheme);
        }
    });

    // 左侧悬浮按钮点击切换 (在深色/浅色之间循环)
    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const resolvedCurrent = document.documentElement.getAttribute('data-theme');
            const nextTheme = resolvedCurrent === 'dark' ? 'light' : 'dark';
            applyTheme(nextTheme);
            notifyPythonTheme(nextTheme);
        });
    }

    // 右侧下拉框选择切换
    if (themeSelect) {
        themeSelect.addEventListener('change', (e) => {
            applyTheme(e.target.value);
            notifyPythonTheme(e.target.value);
        });
    }

    function applyTheme(theme) {
        currentTheme = theme;
        localStorage.setItem('theme', theme);

        let resolvedTheme = theme;
        if (theme === 'auto') {
            resolvedTheme = mediaQuery.matches ? 'dark' : 'light';
        }

        document.documentElement.setAttribute('data-theme', resolvedTheme);

        // 同步修改两个控制组件的视觉属性
        if (themeBtn) {
            themeBtn.textContent = resolvedTheme === 'dark' ? '🌙' : '☀️';
        }
        if (themeSelect) {
            themeSelect.value = theme;
        }
    }

    // 外部或异步调用入口，便于 Python 主动同步
    window.setAppTheme = function(theme) {
        if (theme === 'dark' || theme === 'light' || theme === 'auto') {
            applyTheme(theme);
        }
    };
}

/**
 * 通知 Python 端主题变更
 * @param {string} theme - 主题名称
 */
export function notifyPythonTheme(theme) {
    if (window.pywebview && window.pywebview.api) {
        callPython('update_theme', theme)
            .then(() => {
                let text = "已切换至跟随系统模式";
                if (theme === 'dark') text = "已切换至深色模式";
                if (theme === 'light') text = "已切换至浅色模式";
                showToast(text, 'info');
            });
    } else {
        let text = "已切换至跟随系统模式";
        if (theme === 'dark') text = "已切换至深色模式";
        if (theme === 'light') text = "已切换至浅色模式";
        showToast(text, 'info');
    }
}

/**
 * 侧栏折叠/展开切换初始化
 */
export function initSidebarToggle() {
    const store = Alpine.store('app');
    let userManuallyToggled = false;

    // 小屏幕下默认收起
    if (window.innerWidth <= 900) {
        store.sidebarCollapsed = true;
    }

    // 窗口缩放时自动收起/展开（仅在用户未手动操作时生效）
    window.addEventListener('resize', () => {
        if (userManuallyToggled) return;
        store.sidebarCollapsed = window.innerWidth <= 900;
    });

    // 用户手动点击折叠按钮时标记
    const logoArea = document.getElementById('logo-area-toggle');
    if (logoArea) {
        logoArea.addEventListener('click', () => {
            userManuallyToggled = true;
        });
    }
}

/**
 * 现代化轻量级 Toast 弹出式浮层
 * @param {string} message - 消息内容
 * @param {string} type - 类型：info / success / error / warning
 */
export function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let emoji = 'ℹ️';
    if (type === 'success') emoji = '🎉';
    if (type === 'error') emoji = '❌';
    if (type === 'warning') emoji = '⚠️';

    toast.innerHTML = `<span>${emoji}</span><span>${message}</span>`;
    container.appendChild(toast);

    // 微动画淡入
    setTimeout(() => {
        toast.classList.add('show');
    }, 50);

    // 3.5秒后自动淡出并移除，防内存泄露
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            container.removeChild(toast);
        }, 300);
    }, 3500);
}

/**
 * 带操作按钮的 Toast
 * @param {string} message - 消息内容
 * @param {string} actionLabel - 按钮文字
 * @param {Function} actionFn - 按钮点击回调
 */
export function showToastWithAction(message, actionLabel, actionFn) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast toast-success';
    const msgSpan = document.createElement('span');
    msgSpan.textContent = '🎉 ' + message;
    const btn = document.createElement('button');
    btn.textContent = actionLabel;
    btn.style.cssText = 'background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); border-radius: 4px; padding: 2px 8px; color: white; cursor: pointer; font-size: 11px; margin-left: 8px;';
    btn.addEventListener('click', () => { toast.remove(); if (typeof actionFn === 'function') actionFn(); });
    toast.appendChild(msgSpan);
    toast.appendChild(btn);
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 50);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => { if (toast.parentNode) toast.remove(); }, 300); }, 8000);
}

/**
 * 全局自定义上下文菜单初始化（右键菜单）
 */
export function initContextMenu() {
    const menu = document.getElementById('custom-context-menu');
    if (!menu) return;
    const list = menu.querySelector('.context-menu-list');
    if (!list) return;

    // 监听全局 contextmenu 事件
    document.addEventListener('contextmenu', (e) => {
        // 如果是在输入框等原生可右击区域，则保留系统默认右键菜单
        if (e.target.closest('input:not([type="checkbox"]):not([type="radio"]), textarea')) {
            return;
        }
        // 原生模式：不拦截，使用系统右键菜单
        if (contextMenuMode === 'native') {
            return;
        }

        e.preventDefault();

        let menuItems = [];

        // 通用：右键点击有文字的元素时，添加"复制"选项
        const clickedEl = e.target;
        const textContent = clickedEl.textContent?.trim();
        if (textContent && textContent.length > 0 && textContent.length < 500) {
            menuItems.push({
                label: '📋 复制文字',
                action: () => {
                    copyText(textContent);
                }
            });
            menuItems.push({ separator: true });
        }

        // 判断右击目标
        const trQueue = e.target.closest('#queue-tbody tr');
        const trPending = e.target.closest('#pending-tbody tr');
        const trMuxed = e.target.closest('#muxed-tbody tr');

        if (trQueue && !trQueue.classList.contains('empty-state-row')) {
            // A. 合并队列行
            const index = parseInt(trQueue.id.replace('queue-row-', ''), 10);
            const task = Alpine.store('app').tasks[index];
            if (task) {
                // 高亮当前行
                document.querySelectorAll('#queue-tbody tr').forEach(r => r.classList.remove('active-row'));
                trQueue.classList.add('active-row');
                Alpine.store('app').selectedTaskIndex = index;
                if (window.updatePathPreview) {
                    window.updatePathPreview();
                }

                menuItems = [
                    { label: '🚀 开始合并此队列', action: () => document.getElementById('start-btn').click() },
                    { label: '📂 定位视频源文件', action: () => window.openFileFolder(task.video_file) },
                    { label: '📂 定位音频源文件', action: () => window.openFileFolder(task.audio_file) },
                    { separator: true },
                    { label: '🗑️ 从列表中移除', class: 'danger', action: () => window.deleteTask(index) }
                ];
            }
        } else if (trPending && !trPending.classList.contains('empty-state-row')) {
            // B. 待整理行
            const checkbox = trPending.querySelector('.row-checkbox-pending');
            if (checkbox) {
                const filepath = checkbox.getAttribute('data-filepath');
                document.querySelectorAll('#pending-tbody tr').forEach(r => r.classList.remove('active-row'));
                trPending.classList.add('active-row');

                menuItems = [
                    { label: '📂 在资源管理器中定位', action: () => window.openFileFolder(filepath) },
                    { separator: true },
                    { label: '🗑️ 移除该零散记录', class: 'danger', action: () => window.deletePendingFile(filepath) }
                ];
            }
        } else if (trMuxed && !trMuxed.classList.contains('empty-state-row')) {
            // C. 已完整行
            const checkbox = trMuxed.querySelector('.row-checkbox-muxed');
            if (checkbox) {
                const filepath = checkbox.getAttribute('data-filepath');
                document.querySelectorAll('#muxed-tbody tr').forEach(r => r.classList.remove('active-row'));
                trMuxed.classList.add('active-row');

                menuItems = [
                    { label: '▶️ 使用系统播放器播放', action: () => window.playVideo(filepath) },
                    { label: '📂 在资源管理器中定位', action: () => window.openFileFolder(filepath) },
                    { separator: true },
                    { label: '🗑️ 从列表中移除', class: 'danger', action: () => window.deleteMuxedFile(filepath) }
                ];
            }
        } else {
            // D. 空白区域
            // 清除所有表格行高亮
            document.querySelectorAll('.data-table tbody tr').forEach(r => r.classList.remove('active-row'));
            Alpine.store('app').selectedTaskIndex = -1;
            if (window.updatePathPreview) {
                window.updatePathPreview();
            }

            menuItems = [
                { label: '📂 导入文件夹', action: () => document.getElementById('add-folder-btn').click() },
                { label: '📄 导入音视频文件', action: () => document.getElementById('add-files-btn').click() },
                { separator: true },
                { label: '🌓 切换主题配色', action: () => document.getElementById('theme-switch-btn').click() },
                { separator: true },
                { label: '🧹 清空队列与缓存', class: 'danger', action: () => document.getElementById('clear-btn').click() }
            ];
        }

        if (menuItems.length === 0) return;

        // 渲染菜单项
        list.innerHTML = '';
        menuItems.forEach(item => {
            if (item.separator) {
                const sep = document.createElement('li');
                sep.className = 'context-menu-separator';
                list.appendChild(sep);
            } else {
                const li = document.createElement('li');
                li.className = 'context-menu-item' + (item.class ? ' ' + item.class : '');
                li.textContent = item.label;
                li.addEventListener('click', () => {
                    item.action();
                    hideMenu();
                });
                list.appendChild(li);
            }
        });

        // 计算定位防溢出
        menu.classList.remove('hidden');
        setTimeout(() => {
            menu.classList.add('show');
            const menuWidth = menu.offsetWidth || 200;
            const menuHeight = menu.offsetHeight || 150;

            let posX = e.pageX;
            let posY = e.pageY;

            if (posX + menuWidth > window.innerWidth + window.scrollX) {
                posX = window.innerWidth + window.scrollX - menuWidth - 10;
            }
            if (posY + menuHeight > window.innerHeight + window.scrollY) {
                posY = window.innerHeight + window.scrollY - menuHeight - 10;
            }

            menu.style.left = `${posX}px`;
            menu.style.top = `${posY}px`;
        }, 10);
    });

    // 隐藏菜单
    function hideMenu() {
        menu.classList.remove('show');
        setTimeout(() => {
            if (!menu.classList.contains('show')) {
                menu.classList.add('hidden');
            }
        }, 150);
        document.querySelectorAll('.data-table tbody tr').forEach(r => {
            const cb = r.querySelector('input[type="checkbox"]');
            const idxAttr = cb ? cb.getAttribute('data-index') : null;
            const idx = idxAttr !== null ? parseInt(idxAttr, 10) : -1;

            if ((cb && cb.checked) || (idx !== -1 && Alpine.store('app').selectedTaskIndex === idx)) {
                r.classList.add('active-row');
            } else {
                r.classList.remove('active-row');
            }
        });
        if (window.updatePathPreview) {
            window.updatePathPreview();
        }
    }

    // 点击其他地方隐藏
    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target)) {
            hideMenu();
        }
    });

    document.addEventListener('scroll', hideMenu);
    window.addEventListener('resize', hideMenu);
}

/**
 * 绑定行点击高亮及多选联动（委托事件处理）
 */
export function bindRowSelectionListeners() {
    // 监听表格内所有非空行的点击事件
    document.querySelectorAll('.data-table tbody').forEach(tbody => {
        tbody.addEventListener('click', (e) => {
            // Alpine.js 管理的合并队列由 selectQueueRow 处理，不在此干预
            if (tbody.id === 'queue-tbody') return;

            if (e.target.closest('button') || e.target.closest('input[type="checkbox"]') || e.target.closest('a')) {
                return;
            }

            const tr = e.target.closest('tr');
            if (tr && !tr.classList.contains('empty-state-row')) {
                const cb = tr.querySelector('input[type="checkbox"]');
                if (!cb) return;

                if (e.ctrlKey || e.metaKey) {
                    // Ctrl/Cmd + 点击：切换当前行
                    cb.checked = !cb.checked;
                } else {
                    // 普通点击：
                    // 如果该行是唯一选中的行，则再次点击时取消选中
                    const allChecked = tbody.querySelectorAll('.tool-row-cb:checked, .row-checkbox:checked, .row-checkbox-pending:checked, .row-checkbox-muxed:checked');
                    if (allChecked.length === 1 && allChecked[0] === cb) {
                        cb.checked = false;
                    } else {
                        // 否则选中当前行，取消其他
                        tbody.querySelectorAll('.tool-row-cb, .row-checkbox, .row-checkbox-pending, .row-checkbox-muxed').forEach(other => {
                            if (other !== cb) other.checked = false;
                        });
                        cb.checked = true;
                    }
                }
                cb.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });

        tbody.addEventListener('change', (e) => {
            if (e.target.classList.contains('row-checkbox-pending') ||
                e.target.classList.contains('row-checkbox-muxed')) {
                const tr = e.target.closest('tr');
                if (tr) {
                    if (e.target.checked) {
                        tr.classList.add('active-row');
                    } else {
                        tr.classList.remove('active-row');
                    }
                    if (window.updatePathPreview) {
                        window.updatePathPreview();
                    }
                }
            }
        });
    });
}

/**
 * 显示自定义工具提示
 * @param {Event} e - 鼠标事件
 * @param {string} text - 提示文字
 */
export function showCustomTooltip(e, text) {
    let tooltip = document.getElementById("global-vanilla-tooltip");
    if (!tooltip) {
        tooltip = document.createElement("div");
        tooltip.id = "global-vanilla-tooltip";
        tooltip.className = "global-tooltip";
        document.body.appendChild(tooltip);
    }
    tooltip.textContent = text;
    const rect = e.currentTarget.getBoundingClientRect();
    tooltip.style.left = (rect.left + rect.width / 2) + "px";
    tooltip.style.top = rect.top + "px";
    tooltip.style.transform = "translate(-50%, -100%)";
    tooltip.style.marginTop = "-6px";
    tooltip.style.display = "block";
}

/**
 * 隐藏自定义工具提示
 */
export function hideCustomTooltip() {
    let tooltip = document.getElementById("global-vanilla-tooltip");
    if (tooltip) { tooltip.style.display = "none"; }
}
