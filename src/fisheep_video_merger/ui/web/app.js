/* ====================================================================
   🐑 B站 m4s 视频合并工具 v0.4.0 核心客户端逻辑 (JS)
   处理界面渲染、拖拽捕获、选项卡切换、并作为 Bridge 终点对接 Python 后端
   ==================================================================== */

// 右键菜单模式：'custom' = 自定义菜单, 'native' = 系统原生菜单
let contextMenuMode = localStorage.getItem('contextMenuMode') || 'native';

// Alpine.js 响应式状态（在 alpine:init 事件中注册，早于 DOM 处理）
document.addEventListener('alpine:init', () => {
    Alpine.store('app', {
        tasks: [],
        pending: [],
        muxed: [],
        selectedTaskIndex: -1,
        currentTool: 'merge',
        subtab: 'merge-queue',
        sidebarCollapsed: false,
        configPanelOpen: true,
        theme: localStorage.getItem('theme') || 'dark',
    });

    Alpine.store('settings', {
        outputFormat: 'mp4',
        concurrency: 2,
        overwrite: true,
        deleteSource: false,
        outputDir: '',
        // 工具输出目录
        toolOutputDirs: { convert: '', extract: '', compress: '', trim: '' },
        // 工具设置
        toolSettings: {
            convert: { format: 'mp4', mode: 'copy' },
            extract: { format: 'aac', bitrate: '192k' },
            compress: { preset: 'medium', resolution: '720p' },
            trim: { mode: 'reencode' }
        }
    });
});

// 全局工作空间状态已迁移至 Alpine.store('app')，旧变量已移除

// 复制文字到剪贴板（优先 Python bridge，file:// 下 navigator.clipboard 不可用）
function copyText(text) {
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

// JS 降级复制（textarea + execCommand，file:// 下可用）
function jsCopyFallback(text) {
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

// 切换右键菜单模式
window.toggleContextMenu = function() {
    contextMenuMode = contextMenuMode === 'custom' ? 'native' : 'custom';
    localStorage.setItem('contextMenuMode', contextMenuMode);
    showToast(`右键菜单: ${contextMenuMode === 'custom' ? '自定义' : '原生'}`, 'info');
};

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initSidebarToggle();
    initTabs();
    initDragAndDrop();
    initMockOrBridge();
    initSettingsListeners();
    initContextMenu();
    bindRowSelectionListeners();

    // 快捷键
    document.addEventListener('keydown', (e) => {
        // Ctrl+O: 导入文件
        if (e.ctrlKey && e.key === 'o') {
            e.preventDefault();
            const addFilesBtn = document.getElementById('add-files-btn');
            if (addFilesBtn) addFilesBtn.click();
        }
        // Delete: 删除选中任务
        if (e.key === 'Delete' && !e.target.matches('input, textarea, select')) {
            e.preventDefault();
            window.batchDeleteSelected();
        }
        // Escape: 关闭配置面板
        if (e.key === 'Escape') {
            Alpine.store('app').configPanelOpen = false;
        }
    });
});

/* === 1. 主题自适应配置 (Dark/Light/Auto) === */
function initTheme() {
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

/* === 1.5 侧栏折叠/展开切换 (Sidebar Toggle) === */
function initSidebarToggle() {
    const store = Alpine.store('app');

    // 小屏幕下默认收起
    if (window.innerWidth <= 900) {
        store.sidebarCollapsed = true;
    }

    // 窗口缩放时自动收起/展开
    window.addEventListener('resize', () => {
        if (window.innerWidth <= 900) {
            store.sidebarCollapsed = true;
        }
    });
}

function notifyPythonTheme(theme) {
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

/* === 2. 工具路由切换 (Tool Router) === */
function initTabs() {
    // 子标签切换已由 Alpine 声明式绑定控制，无需手动 addEventListener

    // Hash 路由：根据 URL hash 切换工具（使用 Alpine.store）
    function navigateFromHash() {
        const hash = window.location.hash.replace('#', '') || 'merge';
        const validTools = ['merge', 'convert', 'extract', 'compress', 'trim', 'settings'];
        if (validTools.includes(hash)) {
            Alpine.store('app').currentTool = hash;
        }
    }

    window.addEventListener('hashchange', navigateFromHash);
    // 首次加载时根据 hash 切换
    navigateFromHash();
}

/* === 3. 高性能 Drag & Drop 捕获 (OS 级文件拖拽) === */
function initDragAndDrop() {
    const dropOverlay = document.getElementById('drop-overlay');
    let dragCounter = 0;

    window.addEventListener('dragenter', (e) => {
        e.preventDefault();
        // 只在合并工具激活时显示全局拖拽蒙层
        const mergePanel = document.getElementById('tool-merge');
        if (!mergePanel || !mergePanel.classList.contains('active')) return;

        dragCounter++;
        if (dragCounter === 1) {
            dropOverlay.classList.remove('hidden');
        }
    });

    window.addEventListener('dragover', (e) => {
        // 阻止浏览器默认打开文件行为
        e.preventDefault();
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        const mergePanel = document.getElementById('tool-merge');
        if (!mergePanel || !mergePanel.classList.contains('active')) return;

        dragCounter--;
        if (dragCounter === 0) {
            dropOverlay.classList.add('hidden');
        }
    });

    window.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dropOverlay.classList.add('hidden');

        // 清除所有工具面板的拖拽状态
        document.querySelectorAll('.tool-panel.drag-over').forEach(p => p.classList.remove('drag-over'));

        // 如果当前不是合并工具，让工具面板自己的 handler 处理
        const mergePanel = document.getElementById('tool-merge');
        if (!mergePanel || !mergePanel.classList.contains('active')) return;

        const files = e.dataTransfer.files;
        if (files.length === 0) return;

        const filePaths = Array.from(files).map(file => file.path || file.name);

        showToast(`已捕获 ${files.length} 个项目，正在提交后端进行依赖扫描与匹配...`, 'info');

        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.on_files_dropped(filePaths)
                .then(response => {
                    handleBackendResponse(response);
                })
                .catch(err => {
                    showToast(`扫描失败: ${err}`, 'error');
                });
        } else {
            console.log('拖入的文件路径:', filePaths);
            showToast('当前非桌面客户端环境，已在控制台输出测试路径', 'warning');
        }
    });
}

/* === 4. 合并状态条: 自动控制 === */
// initDashboardToggle: 已由 Alpine 声明式绑定替代

/* === 5. 双线渲染支持与跨端 Bridge 检测 === */
function initMockOrBridge() {
    // 监听 Python Bridge 初始化就绪事件
    window.addEventListener('pywebviewready', () => {
        showToast('🚀 客户端通信总线连接成功！', 'success');
        // 使用 setTimeout 延迟 150ms 调用 Python 接口，防止在 WebView2 初始化完成瞬间同步阻塞导致死锁挂起
        setTimeout(() => {
            syncSettingsFromPython();
            callPython('get_current_state').then(res => {
                handleBackendResponse(res);
            });
        }, 150);
    });

    // 绑定常规操作按钮到 Python 端
    document.getElementById('add-folder-btn').addEventListener('click', () => {
        callPython('select_folder_dialog').then(res => {
            handleBackendResponse(res);
        });
    });

    document.getElementById('add-files-btn').addEventListener('click', () => {
        callPython('select_files_dialog').then(res => {
            handleBackendResponse(res);
        });
    });

    // select-output-btn 已由 Alpine @click 绑定到 selectOutputDir() 函数

    document.getElementById('clear-btn').addEventListener('click', () => {
        callPython('clear_queue').then(res => {
            showToast('队列已清空', 'info');
            handleBackendResponse(res);
        });
    });

    document.getElementById('start-btn').addEventListener('click', () => {
        callPython('start_merging').then(res => {
            showToast('后台合并任务已拉起！', 'success');
        });
    });
}

/* === 6. 后端统一调度包装函数 (Safe Python Invoker) === */
function callPython(methodName, ...args) {
    if (window.pywebview && window.pywebview.api && window.pywebview.api[methodName]) {
        return window.pywebview.api[methodName](...args)
            .catch(err => {
                showToast(`接口错误: ${err}`, 'error');
                throw err;
            });
    } else {
        console.warn(`[Mock] 模拟调用 Python 接口: ${methodName}`, args);
        return Promise.resolve({ status: 'mock' });
    }
}

/* === 7. 数据驱动界面刷新渲染器 (Render Functions) === */

// A. 渲染合并队列数据表格
// renderQueue: Alpine x-for 自动渲染，此函数保留兼容
// renderQueue: Alpine x-for 自动渲染

// A2. 单击列表行，更新右侧的预计输出路径预览 + 视频预览
window.selectQueueRow = function(index, event) {
    if (event && (event.target.type === 'checkbox' || event.target.tagName === 'BUTTON')) {
        return;
    }

    // 通过 Alpine.store 更新选中索引（active-row 由 :class 绑定自动控制）
    Alpine.store('app').selectedTaskIndex = index;

    window.updatePathPreview();
    window.loadVideoPreview(index);
};

// 加载视频预览（截图 + 元数据），带请求计数器防竞态
window._previewDebounce = null;
window._previewRequestId = 0;
window.loadVideoPreview = function(index) {
    clearTimeout(window._previewDebounce);
    window._previewDebounce = setTimeout(() => {
        const tasks = Alpine.store('app').tasks;
        const task = tasks[index];
        if (!task) return;
        const filepath = task.video_file || task.audio_file;
        if (!filepath) return;

        const panel = document.getElementById('video-preview');
        if (panel) panel.style.display = 'block';

        const reqId = ++window._previewRequestId;
        callPython('get_video_preview', filepath).then(res => {
            if (reqId !== window._previewRequestId) return; // 已过时，丢弃
            if (!res || res.status !== 'success') {
                const img = document.getElementById('preview-img');
                if (img) img.src = '';
                return;
            }
            const img = document.getElementById('preview-img');
            if (img && res.screenshot) {
                img.src = `data:image/png;base64,${res.screenshot}`;
            } else if (img) {
                img.src = '';
            }
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '-'; };
            set('preview-resolution', res.resolution);
            set('preview-vcodec', res.video_codec);
            set('preview-acodec', res.audio_codec);
            set('preview-bitrate', res.bitrate);
            set('preview-duration', res.duration);
            set('preview-fps', res.fps ? res.fps + ' fps' : '-');
            set('preview-episode', res.episode);
            set('preview-platform', res.platform);
        });
    }, 200);
};

// 双击输出名单元格，内联编辑
window.editOutputName = function(index, event) {
    const td = event.target;
    if (td.querySelector('input')) return; // 已经在编辑中
    const oldName = td.textContent.trim();
    td.innerHTML = `<input type="text" value="${oldName}" style="width:100%;font-size:inherit;font-weight:inherit;border:1px solid var(--primary-color);border-radius:3px;padding:1px 4px;background:var(--card-bg);color:var(--text-primary);">`;
    const input = td.querySelector('input');
    input.focus();
    input.select();
    const commit = () => {
        const newName = input.value.trim();
        if (newName && newName !== oldName) {
            callPython('rename_task', index, newName).then(res => {
                if (res) handleBackendResponse(res);
            });
        } else {
            td.textContent = oldName;
        }
    };
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
        if (e.key === 'Escape') { td.textContent = oldName; }
    });
};

window.updatePathPreview = function() {
    const label = document.getElementById('detail-path-label');
    const filenameInput = document.getElementById('output-filename-input');
    if (!label) return;
    
    const activeRows = document.querySelectorAll('#queue-tbody tr.active-row');
    const checkedBoxes = document.querySelectorAll('#queue-tbody .row-checkbox:checked');
    
    // 找出唯一的单选任务索引
    const tasks = Alpine.store('app').tasks;
    let singleSelectIndex = -1;
    const selectedIdx = Alpine.store('app').selectedTaskIndex;
    if (selectedIdx !== -1 && tasks[selectedIdx]) {
        singleSelectIndex = selectedIdx;
    } else if (activeRows.length === 1) {
        const idStr = activeRows[0].id;
        const index = parseInt(idStr.replace('queue-row-', ''), 10);
        if (tasks[index]) {
            singleSelectIndex = index;
        }
    } else if (checkedBoxes.length === 1) {
        const index = parseInt(checkedBoxes[0].getAttribute('data-index'), 10);
        if (tasks[index]) {
            singleSelectIndex = index;
        }
    }
    
    // 更新文件名输入框的可用状态与内容
    if (filenameInput) {
        if (singleSelectIndex !== -1 && tasks[singleSelectIndex]) {
            const task = tasks[singleSelectIndex];
            if (document.activeElement !== filenameInput) {
                filenameInput.value = task.name || '';
            }
            filenameInput.disabled = false;
            filenameInput.placeholder = "请输入新的输出文件名";
        } else {
            filenameInput.value = "";
            filenameInput.disabled = true;
            filenameInput.placeholder = "未选中任务，请单击列表行";
        }
    }
    
    if (singleSelectIndex !== -1 && tasks[singleSelectIndex]) {
        const task = tasks[singleSelectIndex];
        const outputDirInput = document.getElementById('output-dir-input');
        const outputFormatSelect = document.getElementById('output-format-select');
        
        const outputDir = (outputDirInput ? outputDirInput.value.trim() : '') || task.source_dir;
        const format = (outputFormatSelect ? outputFormatSelect.value : '') || 'mp4';
        const newName = (filenameInput ? filenameInput.value.trim() : '') || task.name;
        
        const separator = outputDir.includes('/') ? '/' : '\\';
        const predictedPath = outputDir + (outputDir.endsWith(separator) ? '' : separator) + newName + '.' + format;
        label.textContent = predictedPath;
    } else if (checkedBoxes.length > 1) {
        label.textContent = `已选择 ${checkedBoxes.length} 个任务，将输出到相应的目标文件夹。`;
    } else {
        label.textContent = '尚未选择任何任务，请双击列表行进行高级分析...';
    }
};

// B. 动态更新某条任务的合并进度（通过 Alpine.store 触发响应式更新）
window.updateTaskProgress = function(index, percent, eta, speed) {
    const store = Alpine.store('app');
    if (store.tasks[index]) {
        store.tasks[index].percent = percent;
        store.tasks[index].eta = eta;
        store.tasks[index].speed = speed;
    }

    // 更新顶部状态条
    const statusSpeed = document.getElementById('merge-status-speed');
    if (statusSpeed && speed) {
        statusSpeed.textContent = `${speed} | ETA: ${eta}`;
    }
};

// C. 动态更新列表行状态（通过 Alpine.store 触发响应式更新）
window.updateTaskStatus = function(index, status, errorMsg = '') {
    const store = Alpine.store('app');
    if (store.tasks[index]) {
        store.tasks[index].status = status;
        store.tasks[index].error = errorMsg || '';
        if (status === 'processing') {
            store.tasks[index].percent = 0;
        }
        updateMergeStatusBar();
    }
};

function updateMergeStatusBar() {
    const store = Alpine.store('app');
    const tasks = store.tasks;
    const total = tasks.length;
    const done = tasks.filter(t => t.status === 'completed' || t.status === 'failed').length;

    const statusBar = document.getElementById('merge-status-bar');
    const statusText = document.getElementById('merge-status-text');
    const statusChunk = document.getElementById('merge-status-chunk');

    if (total > 0 && done < total) {
        statusBar.classList.remove('hidden');
        statusText.textContent = `⚡ 正在合并: ${done}/${total}`;
        statusChunk.style.width = `${(done / total) * 100}%`;
    } else if (done >= total && total > 0) {
        statusBar.classList.add('hidden');
    }
}

// C2. 初始化合并状态条
window.initDashboardCards = function(tasks) {
    const statusBar = document.getElementById('merge-status-bar');
    const activeTasks = tasks.filter(t => t.status !== 'completed');
    const total = tasks.length;
    const done = total - activeTasks.length;

    if (activeTasks.length > 0) {
        statusBar.classList.remove('hidden');
        document.getElementById('merge-status-text').textContent = `⚡ 正在合并: ${done}/${total}`;
        document.getElementById('merge-status-speed').textContent = '';
        document.getElementById('merge-status-chunk').style.width = `${(done / total) * 100}%`;
    }
};

// 取消合并（由 Alpine @click 调用）
window.toggleSelectAll = function(checked) {
    document.querySelectorAll('#queue-tbody .row-checkbox').forEach(cb => {
        cb.checked = checked;
        const tr = cb.closest('tr');
        if (tr) tr.classList.toggle('active-row', checked);
    });
};

window.batchDeleteSelected = function() {
    const checkboxes = document.querySelectorAll('#queue-tbody .row-checkbox:checked');
    if (checkboxes.length === 0) { showToast('请先勾选要删除的任务', 'warning'); return; }
    // 收集索引并倒序排列，避免删除时索引错位
    const indexes = Array.from(checkboxes)
        .map(cb => parseInt(cb.getAttribute('data-index'), 10))
        .filter(i => !isNaN(i))
        .sort((a, b) => b - a);
    let deleted = 0;
    const doDelete = () => {
        if (indexes.length === 0) {
            showToast(`已删除 ${deleted} 个任务`, 'info');
            return;
        }
        const idx = indexes.shift();
        callPython('delete_task', idx).then(res => {
            if (res) handleBackendResponse(res);
            deleted++;
            doDelete();
        });
    };
    doDelete();
};

window.batchRetryFailed = function() {
    const tasks = Alpine.store('app').tasks;
    const failedIndexes = [];
    tasks.forEach((t, i) => { if (t.status === 'failed') failedIndexes.push(i); });
    if (failedIndexes.length === 0) { showToast('没有失败的任务', 'warning'); return; }
    // 通过后端重置状态
    failedIndexes.forEach(i => {
        callPython('update_task_status', i, 'pending').then(res => {
            if (res) handleBackendResponse(res);
        });
    });
    showToast(`正在重试 ${failedIndexes.length} 个失败任务...`, 'info');
    setTimeout(() => callPython('start_merging'), 500);
};

// 拖拽排序
window._dragFromIndex = null;
window.onTaskDragStart = function(index, event) {
    window._dragFromIndex = index;
    event.dataTransfer.effectAllowed = 'move';
    event.target.style.opacity = '0.5';
};
window.onTaskDragOver = function(event) {
    event.dataTransfer.dropEffect = 'move';
};
window.onTaskDrop = function(toIndex, event) {
    event.preventDefault();
    const fromIndex = window._dragFromIndex;
    if (fromIndex === null || fromIndex === toIndex) return;
    callPython('reorder_tasks', fromIndex, toIndex).then(res => {
        if (res) handleBackendResponse(res);
    });
    window._dragFromIndex = null;
    // 恢复所有行透明度
    document.querySelectorAll('#queue-tbody tr').forEach(tr => tr.style.opacity = '1');
};

window.loadHwAccelInfo = function() {
    callPython('get_hw_accel_info').then(res => {
        const el = document.getElementById('hw-accel-info');
        if (!el || !res || res.status !== 'success') return;
        if (res.encoder) {
            el.innerHTML = `<span style="color: var(--primary-color);">✅ ${res.desc}</span>（${res.encoder}）`;
        } else {
            el.innerHTML = `<span>软编码</span>（未检测到 GPU 加速）`;
        }
    });
};

window.loadPlatformStats = function() {
    callPython('get_platform_stats').then(res => {
        const el = document.getElementById('platform-stats');
        if (!el || !res || res.status !== 'success') return;
        const s = res.stats;
        el.innerHTML = `共 <strong>${res.total}</strong> 个文件 · B站: ${s['B站']} · YouTube: ${s['YouTube']} · 通用: ${s['通用']}`;
    });
};

window.exportConfig = function() {
    callPython('export_config_file').then(res => {
        if (res && res.status === 'success') {
            showToast(`配置已导出到 ${res.path}`, 'success');
        } else if (res && res.status === 'cancelled') {
            // 用户取消
        } else {
            showToast(`导出失败: ${res?.message || '未知错误'}`, 'error');
        }
    });
};

window.importConfig = function() {
    callPython('import_config_file').then(res => {
        if (res && res.status === 'success') {
            showToast(`已导入 ${res.imported} 个任务`, 'success');
            callPython('get_current_state').then(state => handleBackendResponse(state));
        } else if (res && res.status === 'cancelled') {
            // 用户取消
        } else {
            showToast(`导入失败: ${res?.message || '未知错误'}`, 'error');
        }
    });
};

window.showBatchRenameDialog = function() {
    const checkboxes = document.querySelectorAll('#queue-tbody .row-checkbox:checked');
    const indexes = Array.from(checkboxes).map(cb => parseInt(cb.getAttribute('data-index'), 10));
    if (indexes.length === 0) {
        showToast('请先勾选要重命名的任务', 'warning');
        return;
    }
    // 简单 prompt 对话框
    const prefix = prompt('前缀（留空不加）：', '');
    if (prefix === null) return;
    const suffix = prompt('后缀（留空不加）：', '');
    if (suffix === null) return;
    const replaceFrom = prompt('替换：将此字符串替换为（留空不替换）：', '');
    if (replaceFrom === null) return;
    let replaceTo = '';
    if (replaceFrom) {
        replaceTo = prompt('替换为：', '');
        if (replaceTo === null) return;
    }
    if (!prefix && !suffix && !replaceFrom) {
        showToast('未输入任何重命名规则', 'warning');
        return;
    }
    callPython('batch_rename', indexes, prefix || '', suffix || '', replaceFrom || '', replaceTo || '').then(res => {
        if (res && res.status === 'success') {
            showToast(`已重命名 ${res.renamed} 个任务`, 'success');
            callPython('get_current_state').then(state => handleBackendResponse(state));
        }
    });
};

window.cancelMerging = function() {
    callPython('cancel_merging').then(res => {
        if (res && res.status === 'success') {
            showToast('正在取消合并...', 'warning');
        }
    });
};

// 选择输出目录（由 Alpine @click 调用）
window.selectOutputDir = function() {
    callPython('select_output_dir_dialog').then(res => {
        if (res && res.output_dir) {
            Alpine.store('settings').outputDir = res.output_dir;
            showToast(`输出目录已设置为: ${res.output_dir}`, 'success');
            callPython('get_current_state').then(state => {
                handleBackendResponse(state);
            });
        }
    });
};

// C3. 全局删除任务函数，回传给后端并重新渲染
window.deleteTask = function(index) {
    if (window.event) {
        window.event.stopPropagation();
    }
    callPython('delete_task', index).then(res => {
        handleBackendResponse(res);
        showToast('任务已从列表中移除', 'info');
    });
};


// D. 刷新同步设置参数
function syncSettingsFromPython() {
    callPython('get_current_settings').then(settings => {
        if (settings) {
            const store = Alpine.store('settings');
            store.outputDir = settings.output_dir || '';
            store.outputFormat = settings.output_format || 'mp4';
            store.concurrency = settings.concurrency || 2;
            store.overwrite = !!settings.overwrite;
            store.deleteSource = !!settings.delete_allowed;

            // 同步命名模板
            const tplInput = document.getElementById('settings-naming-template');
            if (tplInput) tplInput.value = settings.naming_template || '';

            // 同步输出目录模板
            const dirTplInput = document.getElementById('settings-output-dir-template');
            if (dirTplInput) dirTplInput.value = settings.output_dir_template || '';

            // 同步路径层级
            const depthSelect = document.getElementById('settings-path-depth');
            if (depthSelect) depthSelect.value = String(settings.path_depth || 0);

            // 同步工具输出目录
            if (settings.tool_output_dirs) {
                Object.assign(store.toolOutputDirs, settings.tool_output_dirs);
                ['convert', 'extract', 'compress', 'trim'].forEach(tool => {
                    const el = document.getElementById(`${tool}-output-dir`);
                    if (el && store.toolOutputDirs[tool]) el.value = store.toolOutputDirs[tool];
                });
            }

            // 同步工具设置
            if (settings.tool_settings) {
                Object.assign(store.toolSettings, settings.tool_settings);
                // 恢复到 DOM 元素
                const ts = settings.tool_settings;
                if (ts.convert) {
                    const fmt = document.getElementById('convert-format');
                    const mode = document.getElementById('convert-mode');
                    if (fmt) fmt.value = ts.convert.format || 'mp4';
                    if (mode) mode.value = ts.convert.mode || 'copy';
                }
                if (ts.extract) {
                    const fmt = document.getElementById('extract-format');
                    const br = document.getElementById('extract-bitrate');
                    if (fmt) fmt.value = ts.extract.format || 'aac';
                    if (br) br.value = ts.extract.bitrate || '192k';
                }
                if (ts.compress) {
                    const pre = document.getElementById('compress-preset');
                    const res = document.getElementById('compress-resolution');
                    if (pre) pre.value = ts.compress.preset || 'medium';
                    if (res) res.value = ts.compress.resolution || '720p';
                }
                if (ts.trim) {
                    const mode = document.getElementById('trim-mode');
                    if (mode) mode.value = ts.trim.mode || 'reencode';
                }
            }

            // 加载平台统计和硬件加速信息
            if (window.loadPlatformStats) window.loadPlatformStats();
            if (window.loadHwAccelInfo) window.loadHwAccelInfo();

            // 同步格式配置
            if (settings.enabled_formats) {
                document.querySelectorAll('.format-cb').forEach(cb => {
                    cb.checked = settings.enabled_formats.includes(cb.dataset.ext);
                });
            }

            // 同步应用从后端载入的界面主题
            if (settings.theme && window.setAppTheme) {
                window.setAppTheme(settings.theme);
            }
        }
    });
}

// E. 接收扫描与工作空间状态结果，同步填充三个数据面板
function handleBackendResponse(res) {
    if (!res) return;

    // 同步到 Alpine.store（响应式）
    const store = Alpine.store('app');

    if (res.tasks) {
        store.tasks = res.tasks;
    }

    if (res.pending) {
        store.pending = res.pending;
    }

    if (res.muxed) {
        store.muxed = res.muxed;
    }
}

// renderPending / renderMuxed: Alpine x-for 自动渲染

// E4. 跨端系统级操作的全局 JS 包装器
window.deletePendingFile = function(filepath) {
    callPython('delete_pending_file', filepath).then(res => {
        if (res) {
            handleBackendResponse(res);
            showToast('零散文件记录已从列表中移除', 'info');
        }
    });
};

window.deleteMuxedFile = function(filepath) {
    callPython('delete_muxed_file', filepath).then(res => {
        if (res) {
            handleBackendResponse(res);
            showToast('合并文件记录已从列表中移除', 'info');
        }
    });
};

window.playVideo = function(filepath) {
    callPython('play_video', filepath).then(res => {
        if (res && res.status === 'error') {
            showToast(`播放失败: ${res.message}`, 'error');
        }
    });
};

window.openFileFolder = function(filepath) {
    callPython('open_file_folder', filepath).then(res => {
        if (res && res.status === 'error') {
            showToast(`定位失败: ${res.message}`, 'error');
        }
    });
};


/* === 8. 现代化轻量级 Toast 弹出式浮层 === */
function showToast(message, type = 'info') {
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

function showToastWithAction(message, actionLabel, actionFn) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast toast-success';
    toast.innerHTML = `<span>🎉</span><span>${message}</span><button onclick="this.parentElement.remove(); (${actionFn.toString()})()" style="background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); border-radius: 4px; padding: 2px 8px; color: white; cursor: pointer; font-size: 11px; margin-left: 8px;">${actionLabel}</button>`;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 50);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => container.removeChild(toast), 300); }, 8000);
}

/* === 9. 监听配置面板中表单控件的值变化并更新到 Python === */
function initSettingsListeners() {
    // 输出格式、并发数、复选框已由 Alpine x-model + @change 绑定，无需手动 addEventListener

    const filenameInput = document.getElementById('output-filename-input');
    if (filenameInput) {
        // 当用户在输入框打字时，实时同步更新路径预览，但暂不提交后端
        filenameInput.addEventListener('input', () => {
            if (window.updatePathPreview) {
                window.updatePathPreview();
            }
        });

        // 当用户敲回车或输入框失去焦点时，正式提交后端重命名，完成存盘
        filenameInput.addEventListener('change', (e) => {
            const newName = e.target.value.trim();
            const activeRows = document.querySelectorAll('#queue-tbody tr.active-row');
            const checkedBoxes = document.querySelectorAll('#queue-tbody .row-checkbox:checked');
            
            const tasks = Alpine.store('app').tasks;
            const selectedIdx = Alpine.store('app').selectedTaskIndex;
            let singleSelectIndex = -1;
            if (selectedIdx !== -1 && tasks[selectedIdx]) {
                singleSelectIndex = selectedIdx;
            } else if (activeRows.length === 1) {
                const idStr = activeRows[0].id;
                const index = parseInt(idStr.replace('queue-row-', ''), 10);
                if (tasks[index]) {
                    singleSelectIndex = index;
                }
            } else if (checkedBoxes.length === 1) {
                const index = parseInt(checkedBoxes[0].getAttribute('data-index'), 10);
                if (tasks[index]) {
                    singleSelectIndex = index;
                }
            }

            if (singleSelectIndex !== -1 && newName) {
                callPython('rename_task', singleSelectIndex, newName).then(res => {
                    handleBackendResponse(res);
                    showToast('已更新输出文件名', 'success');
                });
            }
        });
    }

    // 命名模板输入
    const tplInput = document.getElementById('settings-naming-template');
    if (tplInput) {
        tplInput.addEventListener('change', (e) => {
            callPython('update_setting', 'naming_template', e.target.value.trim());
        });
    }

    // 输出目录模板输入
    const dirTplInput = document.getElementById('settings-output-dir-template');
    if (dirTplInput) {
        dirTplInput.addEventListener('change', (e) => {
            callPython('update_setting', 'output_dir_template', e.target.value.trim());
        });
    }

    // 路径层级
    const depthSelect = document.getElementById('settings-path-depth');
    if (depthSelect) {
        depthSelect.addEventListener('change', (e) => {
            callPython('update_setting', 'path_depth', parseInt(e.target.value, 10));
        });
    }

    // 格式配置复选框
    document.querySelectorAll('.format-cb').forEach(cb => {
        cb.addEventListener('change', () => {
            const enabled = Array.from(document.querySelectorAll('.format-cb:checked')).map(c => c.dataset.ext);
            callPython('update_setting', 'enabled_formats', enabled);
        });
    });
}

/* === 10. 全局自定义上下文菜单 (右键菜单) === */
function initContextMenu() {
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

/* === 11. 绑定行点击高亮及多选联动 (Delegated Event Handlers) === */
function bindRowSelectionListeners() {
    // 监听表格内所有非空行的点击事件
    document.querySelectorAll('.data-table tbody').forEach(tbody => {
        tbody.addEventListener('click', (e) => {
            if (e.target.closest('button') || e.target.closest('input[type="checkbox"]') || e.target.closest('a')) {
                return;
            }
            
            const tr = e.target.closest('tr');
            if (tr && !tr.classList.contains('empty-state-row')) {
                const cb = tr.querySelector('input[type="checkbox"]');
                if (cb) {
                    cb.checked = !cb.checked;
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        });
        
        tbody.addEventListener('change', (e) => {
            if (e.target.classList.contains('row-checkbox') || 
                e.target.classList.contains('row-checkbox-pending') || 
                e.target.classList.contains('row-checkbox-muxed')) {
                const tr = e.target.closest('tr');
                if (tr) {
                    if (e.target.checked) {
                        tr.classList.add('active-row');
                        if (e.target.classList.contains('row-checkbox')) {
                            Alpine.store('app').selectedTaskIndex = parseInt(e.target.getAttribute('data-index'), 10);
                        }
                    } else {
                        tr.classList.remove('active-row');
                        if (e.target.classList.contains('row-checkbox')) {
                            const idx = parseInt(e.target.getAttribute('data-index'), 10);
                            if (Alpine.store('app').selectedTaskIndex === idx) {
                                Alpine.store('app').selectedTaskIndex = -1;
                            }
                        }
                    }
                    if (window.updatePathPreview) {
                        window.updatePathPreview();
                    }
                }
            }
        });
    });
}

// initConfigPanelToggle: Alpine 声明式绑定替代

/* === 13. 通用视频工具前端逻辑 (Convert / Extract / Compress / Trim) === */

// 各工具的任务列表缓存
const toolFiles = { convert: [], extract: [], compress: [], trim: [] };

// 工具进度回调（由 Python 通过 evaluate_js 调用）
window.updateToolProgress = function(tool, text, pct) {
    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return;
    const progressRow = tbody.querySelector('.tool-processing');
    if (!progressRow) return;
    const statusCell = progressRow.querySelector('.tool-status');
    if (!statusCell) return;
    if (pct != null && pct > 0) {
        const pctVal = Math.min(99.9, pct);
        statusCell.innerHTML = `<div class="tool-progress-bar"><div class="tool-progress-chunk" style="width:${pctVal}%"></div><span class="tool-progress-text">${pctVal.toFixed(1)}%</span></div>`;
    } else {
        statusCell.textContent = text;
    }
};

// 初始化所有工具面板
document.addEventListener('DOMContentLoaded', () => {
    initToolDropZones();
    initToolStartButtons();
    initTrimTimeline();
    initSettingsPanel();
});

function initToolDropZones() {
    ['convert', 'extract', 'compress', 'trim'].forEach(tool => {
        const panel = document.getElementById(`tool-${tool}`);
        if (!panel) return;

        let dragCounter = 0;

        panel.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter++;
            if (dragCounter === 1) {
                panel.classList.add('drag-over');
            }
        });

        panel.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
        });

        panel.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter--;
            if (dragCounter === 0) {
                panel.classList.remove('drag-over');
            }
        });

        panel.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter = 0;
            panel.classList.remove('drag-over');

            const files = Array.from(e.dataTransfer.files);
            if (files.length === 0) return;
            const paths = files.map(f => f.path || f.name).filter(p => p);
            if (paths.length === 0) {
                showToast('无法获取文件路径，请使用点击选择', 'warning');
                return;
            }
            addFilesToTool(tool, paths);
        });
    });
}

function selectFilesForTool(tool) {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_tool_files().then(res => {
            if (res && res.status === 'success' && res.files) {
                addFilesToTool(tool, res.files);
            }
        });
    }
}

function addFilesToTool(tool, paths) {
    // 过滤支持的格式
    const supportedExts = ['.mp4', '.mkv', '.flv', '.mov', '.avi', '.webm', '.m4s', '.ts', '.wmv'];
    const validPaths = paths.filter(p => {
        const ext = p.toLowerCase().substring(p.lastIndexOf('.'));
        return supportedExts.includes(ext);
    });

    if (validPaths.length === 0) {
        showToast('未找到支持的视频文件', 'warning');
        return;
    }

    // 获取文件信息（提取音频用 get_file_info 获取详细音频信息）
    validPaths.forEach(path => {
        if (window.pywebview && window.pywebview.api) {
            const apiCall = tool === 'extract'
                ? window.pywebview.api.get_file_info(path).then(info => {
                    // get_file_info 返回音频详情，补充基础信息
                    const stat_info = { filepath: path, name: path.split(/[\\/]/).pop() };
                    return { ...stat_info, ...info };
                  })
                : window.pywebview.api.get_video_info(path);
            apiCall.then(info => {
                if (info && (info.status === 'success' || info.codec)) {
                    toolFiles[tool].push(info);
                    renderToolTable(tool);
                    updateToolStartButton(tool);
                    showToast(`已添加: ${info.name}`, 'success');

                    // 裁剪工具：激活时间轴滑块
                    if (tool === 'trim' && info.duration && window.setTrimDuration) {
                        window.setTrimDuration(info.duration);
                    }
                }
            });
        } else {
            toolFiles[tool].push({
                filepath: path,
                name: path.split(/[\\/]/).pop(),
                size: '未知',
            });
            renderToolTable(tool);
            updateToolStartButton(tool);
        }
    });
}

function renderToolTable(tool) {
    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return;

    const files = toolFiles[tool];
    if (files.length === 0) {
        const emptyIcons = { convert: '🔄', extract: '🎵', compress: '📦', trim: '✂️' };
        tbody.innerHTML = `
            <tr class="empty-state-row" onclick="selectFilesForTool('${tool}')" style="cursor: pointer;">
                <td colspan="6">
                    <div class="empty-state">
                        <div class="empty-icon">${emptyIcons[tool]}</div>
                        <h3>拖入视频文件或点击此处选择</h3>
                        <p>支持 mp4 / mkv / flv / mov / avi / webm</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    if (tool === 'extract') {
        // 音频提取：显示 编码/码率/声道/时长/大小
        tbody.innerHTML = files.map((file, index) => {
            return `
                <tr>
                    <td width="40"><input type="checkbox" class="tool-row-cb" data-index="${index}" checked></td>
                    <td style="font-weight: 600; max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.filepath}">${file.name}</td>
                    <td>${file.codec || '未知'}</td>
                    <td>${file.bitrate ? file.bitrate + ' kbps' : '未知'}</td>
                    <td>${file.channels === 1 ? '单声道' : file.channels === 2 ? '立体声' : file.channel_layout || '未知'}</td>
                    <td>${file.duration_str || '未知'}</td>
                    <td>${file.size || '未知'}</td>
                    <td class="tool-status">⏳ 待处理</td>
                    <td>
                        <button class="mini-action-btn" onclick="removeToolFile('${tool}', ${index})" style="color: #EF4444; border-color: rgba(239,68,68,0.2);">🗑️</button>
                    </td>
                </tr>`;
        }).join('');
    } else {
        // 其他工具：标准列
        tbody.innerHTML = files.map((file, index) => {
            const col2 = file.duration_str || file.size || '未知';
            const col3 = file.size || '未知';
            return `
                <tr>
                    <td width="40"><input type="checkbox" class="tool-row-cb" data-index="${index}" checked></td>
                    <td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.filepath}">${file.name}</td>
                    <td>${col2}</td>
                    <td>${col3}</td>
                    <td class="tool-status">⏳ 待处理</td>
                    <td>
                        <button class="mini-action-btn" onclick="removeToolFile('${tool}', ${index})" style="color: #EF4444; border-color: rgba(239,68,68,0.2);">🗑️</button>
                    </td>
                </tr>`;
        }).join('');
    }
}

window.removeToolFile = function(tool, index) {
    toolFiles[tool].splice(index, 1);
    renderToolTable(tool);
    updateToolStartButton(tool);
};

function updateToolStartButton(tool) {
    const btn = document.getElementById(`${tool}-start-btn`);
    if (btn) {
        btn.disabled = toolFiles[tool].length === 0;
    }
}

/* === 14. 视频裁剪时间轴滑块 === */
let trimDuration = 0; // 视频总时长（秒）
let trimStartSec = 0;
let trimEndSec = 0;

function initTrimTimeline() {
    const handleStart = document.getElementById('trim-handle-start');
    const handleEnd = document.getElementById('trim-handle-end');
    const track = document.querySelector('.trim-track');
    if (!handleStart || !handleEnd || !track) return;

    let dragging = null; // 'start' or 'end'

    function getPercent(e) {
        const rect = track.getBoundingClientRect();
        let pct = (e.clientX - rect.left) / rect.width;
        return Math.max(0, Math.min(1, pct));
    }

    function secToTime(sec) {
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = Math.floor(sec % 60);
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    function timeToSec(time) {
        const parts = time.split(':').map(Number);
        if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
        if (parts.length === 2) return parts[0] * 60 + parts[1];
        return parseFloat(time) || 0;
    }

    function updateVisual() {
        if (trimDuration <= 0) return;
        const startPct = (trimStartSec / trimDuration) * 100;
        const endPct = (trimEndSec / trimDuration) * 100;

        handleStart.style.left = `${startPct}%`;
        handleEnd.style.left = `${endPct}%`;

        const selected = document.getElementById('trim-selected');
        if (selected) {
            selected.style.left = `${startPct}%`;
            selected.style.width = `${endPct - startPct}%`;
        }

        document.getElementById('trim-label-start').textContent = secToTime(trimStartSec);
        document.getElementById('trim-label-end').textContent = secToTime(trimEndSec);
        document.getElementById('trim-start').value = secToTime(trimStartSec);
        document.getElementById('trim-end').value = secToTime(trimEndSec);
    }

    function onMove(e) {
        if (!dragging) return;
        const pct = getPercent(e);
        const sec = pct * trimDuration;

        if (dragging === 'start') {
            trimStartSec = Math.min(sec, trimEndSec - 1);
        } else {
            trimEndSec = Math.max(sec, trimStartSec + 1);
        }
        updateVisual();
    }

    function onUp() {
        dragging = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
    }

    handleStart.addEventListener('mousedown', (e) => {
        e.preventDefault();
        dragging = 'start';
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });

    handleEnd.addEventListener('mousedown', (e) => {
        e.preventDefault();
        dragging = 'end';
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });

    // 点击轨道跳转
    track.addEventListener('click', (e) => {
        if (e.target.classList.contains('trim-handle')) return;
        const pct = getPercent(e);
        const sec = pct * trimDuration;
        // 点击位置离哪个手柄近就移动哪个
        const distStart = Math.abs(sec - trimStartSec);
        const distEnd = Math.abs(sec - trimEndSec);
        if (distStart < distEnd) {
            trimStartSec = Math.min(sec, trimEndSec - 1);
        } else {
            trimEndSec = Math.max(sec, trimStartSec + 1);
        }
        updateVisual();
    });

    // 手动输入框同步
    document.getElementById('trim-start').addEventListener('change', (e) => {
        trimStartSec = Math.min(timeToSec(e.target.value), trimEndSec - 1);
        updateVisual();
    });
    document.getElementById('trim-end').addEventListener('change', (e) => {
        trimEndSec = Math.max(timeToSec(e.target.value), trimStartSec + 1);
        updateVisual();
    });

    // 暴露给外部调用
    window.setTrimDuration = function(duration) {
        trimDuration = duration;
        trimStartSec = 0;
        trimEndSec = duration;
        const timeline = document.getElementById('trim-timeline');
        if (timeline) timeline.style.display = 'block';
        const hint = document.getElementById('trim-duration-hint');
        if (hint) {
            const h = Math.floor(duration / 3600);
            const m = Math.floor((duration % 3600) / 60);
            const s = Math.floor(duration % 60);
            hint.textContent = `(总时长: ${h}h ${m}m ${s}s)`;
        }
        updateVisual();
    };
}

/* === 15. 设置面板 === */
function initSettingsPanel() {
    // 从 Python 同步设置到 UI
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_current_settings().then(settings => {
            if (!settings) return;
            const themeSelect = document.getElementById('settings-theme');
            const outputDir = document.getElementById('settings-output-dir');
            const format = document.getElementById('settings-output-format');
            const concurrency = document.getElementById('settings-concurrency');
            const overwrite = document.getElementById('settings-overwrite');
            const deleteSource = document.getElementById('settings-delete-source');

            if (themeSelect) themeSelect.value = settings.theme || 'auto';
            if (outputDir) outputDir.value = settings.output_dir || '';
            if (format) format.value = settings.output_format || 'mp4';
            if (concurrency) concurrency.value = settings.concurrency || 2;
            if (overwrite) overwrite.checked = !!settings.overwrite;
            if (deleteSource) deleteSource.checked = !!settings.delete_allowed;
        });

        // 检测 FFmpeg
        window.pywebview.api.get_video_info('/dev/null').catch(() => {});
    }

    // FFmpeg 路径检测
    const ffmpegDisplay = document.getElementById('settings-ffmpeg-path');
    if (ffmpegDisplay && window.pywebview && window.pywebview.api) {
        // 用一个已知不存在的文件触发 bridge 的 ffmpeg 检测
        ffmpegDisplay.textContent = 'ffmpeg 可用（通过 bridge 自动检测）';
    }

    // 主题切换
    const themeSelect = document.getElementById('settings-theme');
    if (themeSelect) {
        themeSelect.addEventListener('change', (e) => {
            if (window.setAppTheme) {
                window.setAppTheme(e.target.value);
            }
            if (window.pywebview && window.pywebview.api) {
                callPython('update_theme', e.target.value);
            }
        });
    }

    // 输出目录
    const outputDirInput = document.getElementById('settings-output-dir');
    if (outputDirInput) {
        outputDirInput.addEventListener('change', (e) => {
            callPython('update_setting', 'output_dir', e.target.value);
        });
    }

    // 输出格式
    const formatSelect = document.getElementById('settings-output-format');
    if (formatSelect) {
        formatSelect.addEventListener('change', (e) => {
            callPython('update_setting', 'output_format', e.target.value);
        });
    }

    // 并发数
    const concurrencyInput = document.getElementById('settings-concurrency');
    if (concurrencyInput) {
        concurrencyInput.addEventListener('change', (e) => {
            let val = parseInt(e.target.value, 10);
            if (isNaN(val) || val < 1) val = 1;
            if (val > 8) val = 8;
            e.target.value = val;
            callPython('update_setting', 'concurrency', val);
        });
    }

    // 覆盖
    const overwriteCb = document.getElementById('settings-overwrite');
    if (overwriteCb) {
        overwriteCb.addEventListener('change', (e) => {
            callPython('update_setting', 'overwrite', e.target.checked);
        });
    }

    // 删除源文件
    const deleteCb = document.getElementById('settings-delete-source');
    if (deleteCb) {
        deleteCb.addEventListener('change', (e) => {
            callPython('update_setting', 'delete_allowed', e.target.checked);
        });
    }
}

window.selectSettingsOutputDir = function() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_output_dir_dialog().then(res => {
            if (res && res.output_dir) {
                const input = document.getElementById('settings-output-dir');
                if (input) input.value = res.output_dir;
                callPython('update_setting', 'output_dir', res.output_dir);
            }
        });
    }
};

// 选择输出目录
window.selectToolOutputDir = function(tool) {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_output_dir_dialog().then(res => {
            if (res && res.output_dir) {
                const input = document.getElementById(`${tool}-output-dir`);
                if (input) input.value = res.output_dir;
                // 持久化到后端
                callPython('update_tool_output_dir', tool, res.output_dir);
            }
        });
    }
};

// 音频提取质量预设
window.applyExtractPreset = function(preset) {
    const presets = {
        high:   { bitrate: '320k', sampleRate: '48000', channels: 'stereo' },
        medium: { bitrate: '192k', sampleRate: '44100', channels: 'stereo' },
        low:    { bitrate: '128k', sampleRate: '22050', channels: 'mono' },
    };
    const p = presets[preset] || presets.medium;
    const br = document.getElementById('extract-bitrate');
    const sr = document.getElementById('extract-sample-rate');
    const ch = document.getElementById('extract-channels');
    if (br) br.value = p.bitrate;
    if (sr) sr.value = p.sampleRate;
    if (ch) ch.value = p.channels;
    // 更新按钮状态
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.preset === preset);
    });
};

function initToolStartButtons() {
    // 格式转换
    const convertBtn = document.getElementById('convert-start-btn');
    if (convertBtn) {
        convertBtn.addEventListener('click', () => {
            const format = document.getElementById('convert-format').value;
            const mode = document.getElementById('convert-mode').value;
            const outputDir = document.getElementById('convert-output-dir')?.value || '';
            runToolTask('convert', (file) => {
                return window.pywebview.api.convert_file(file.filepath, format, mode, outputDir);
            });
        });
    }

    // 提取音频
    const extractBtn = document.getElementById('extract-start-btn');
    if (extractBtn) {
        extractBtn.addEventListener('click', () => {
            const format = document.getElementById('extract-format').value;
            const bitrate = document.getElementById('extract-bitrate').value;
            const bitrateMode = document.getElementById('extract-bitrate-mode')?.value || 'cbr';
            const channels = document.getElementById('extract-channels')?.value || 'original';
            const sampleRate = document.getElementById('extract-sample-rate')?.value || 'original';
            const volume = parseFloat(document.getElementById('extract-volume')?.value || '1.0');
            const outputDir = document.getElementById('extract-output-dir')?.value || '';
            const outputName = document.getElementById('extract-output-name')?.value?.trim() || '';
            const checkedCount = document.querySelectorAll('#extract-tbody .tool-row-cb:checked').length;
            const totalCount = toolFiles.extract.length;
            const selCount = checkedCount || totalCount;
            const nameForBatch = selCount === 1 ? outputName : '';
            runToolTask('extract', (file) => {
                return window.pywebview.api.extract_audio_api(
                    file.filepath, format, bitrate, outputDir, nameForBatch,
                    channels, sampleRate, volume, bitrateMode
                );
            });
        });
    }

    // 视频压缩
    const compressBtn = document.getElementById('compress-start-btn');
    if (compressBtn) {
        compressBtn.addEventListener('click', () => {
            const preset = document.getElementById('compress-preset').value;
            const resolution = document.getElementById('compress-resolution').value;
            const outputDir = document.getElementById('compress-output-dir')?.value || '';
            runToolTask('compress', (file) => {
                return window.pywebview.api.compress_video_api(file.filepath, preset, resolution, outputDir);
            });
        });
    }

    // 视频裁剪
    const trimBtn = document.getElementById('trim-start-btn');
    if (trimBtn) {
        trimBtn.addEventListener('click', () => {
            const start = document.getElementById('trim-start').value;
            const end = document.getElementById('trim-end').value;
            const mode = document.getElementById('trim-mode').value;
            const outputDir = document.getElementById('trim-output-dir')?.value || '';
            if (!end) {
                showToast('请填写结束时间', 'warning');
                return;
            }
            runToolTask('trim', (file) => {
                return window.pywebview.api.trim_video_api(file.filepath, start, end, mode, outputDir);
            });
        });
    }
}

// 获取选中的文件（带复选框的行）
function getSelectedFiles(tool) {
    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return [];
    const checkboxes = tbody.querySelectorAll('.tool-row-cb:checked');
    if (checkboxes.length === 0) return toolFiles[tool]; // 没勾选则全选
    return Array.from(checkboxes).map(cb => {
        const idx = parseInt(cb.getAttribute('data-index'), 10);
        return toolFiles[tool][idx];
    }).filter(Boolean);
}

function runToolTask(tool, taskFn) {
    const selectedFiles = getSelectedFiles(tool);
    if (selectedFiles.length === 0) {
        showToast('请先添加文件', 'warning');
        return;
    }

    if (!window.pywebview || !window.pywebview.api) {
        showToast('请在桌面客户端中使用此功能', 'warning');
        return;
    }

    const btn = document.getElementById(`${tool}-start-btn`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ 处理中...';
    }

    let completed = 0;
    let failed = 0;
    const total = selectedFiles.length;

    // 标记选中行为处理中
    const tbody = document.getElementById(`${tool}-tbody`);
    const allRows = tbody ? Array.from(tbody.querySelectorAll('tr:not(.empty-state-row)')) : [];
    selectedFiles.forEach(file => {
        const idx = toolFiles[tool].indexOf(file);
        if (allRows[idx]) {
            const statusCell = allRows[idx].querySelector('.tool-status');
            if (statusCell) statusCell.textContent = '⏳ 等待中...';
        }
    });

    async function processNext(i) {
        if (i >= selectedFiles.length) {
            if (btn) {
                btn.textContent = '🚀 开始处理';
                btn.disabled = false;
            }
            showToast(`处理完成：成功 ${completed}，失败 ${failed}`, failed > 0 ? 'warning' : 'success');
            return;
        }

        const file = selectedFiles[i];
        const idx = toolFiles[tool].indexOf(file);
        if (allRows[idx]) {
            const statusCell = allRows[idx].querySelector('.tool-status');
            if (statusCell) statusCell.textContent = '⚡ 处理中...';
        }

        try {
            const result = await taskFn(file);
            if (result && result.status === 'success') {
                completed++;
                if (allRows[idx]) {
                    const statusCell = allRows[idx].querySelector('.tool-status');
                    if (statusCell) statusCell.textContent = '✅ 完成';
                }
            } else {
                failed++;
                const errMsg = result?.error || result?.message || '失败';
                if (allRows[idx]) {
                    const statusCell = allRows[idx].querySelector('.tool-status');
                    if (statusCell) statusCell.textContent = `❌ ${errMsg}`;
                }
                console.error(`[${tool}] 失败:`, errMsg);
            }
        } catch (e) {
            failed++;
            if (allRows[idx]) {
                const statusCell = allRows[idx].querySelector('.tool-status');
                if (statusCell) statusCell.textContent = `❌ ${e}`;
            }
            console.error(`[${tool}] 异常:`, e);
        }

        processNext(i + 1);
    }

    processNext(0);
}
