/* ====================================================================
   🐑 B站 m4s 视频合并工具 v0.4.0 核心客户端逻辑 (JS)
   处理界面渲染、拖拽捕获、选项卡切换、并作为 Bridge 终点对接 Python 后端
   ==================================================================== */

// 全局工作空间状态缓存
let currentTasks = [];
let currentPending = [];
let currentMuxed = [];
window.selectedTaskIndex = -1;

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initTabs();
    initDragAndDrop();
    initDashboardToggle();
    initConfigPanelToggle();
    initMockOrBridge();
    initSettingsListeners();
    initContextMenu();
    bindRowSelectionListeners();
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

/* === 2. 选项卡无缝切换 (Tab Controller) === */
function initTabs() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const headerTitle = document.getElementById('current-tab-title');
    const headerDesc = document.getElementById('current-tab-desc');
    
    const tabMetaData = {
        'merge-queue': {
            title: '合并队列',
            desc: '拖入B站缓存文件夹或导入 .m4s 音视频即可开始并行合并'
        },
        'pending': {
            title: '待整理',
            desc: '系统检测到的零散音视频片段，支持批量手动合并或清理'
        },
        'muxed': {
            title: '已完整',
            desc: '已成功合并的高清视频合辑，支持直接播放或打开所在位置'
        }
    };

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            // 切换按钮激活态
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 切换面板显示
            tabPanels.forEach(p => p.classList.remove('active'));
            document.getElementById(`panel-${targetTab}`).classList.add('active');
            
            // 刷新头部标题与描述
            if (tabMetaData[targetTab]) {
                headerTitle.textContent = tabMetaData[targetTab].title;
                headerDesc.textContent = tabMetaData[targetTab].desc;
            }
        });
    });
}

/* === 3. 高性能 Drag & Drop 捕获 (OS 级文件拖拽) === */
function initDragAndDrop() {
    const dropOverlay = document.getElementById('drop-overlay');
    let dragCounter = 0; // 解决子元素 hover 导致 dragleave 闪烁的经典 Bug
    
    window.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (dragCounter === 1) {
            dropOverlay.classList.remove('hidden');
        }
    });

    window.addEventListener('dragover', (e) => {
        e.preventDefault(); // 必须 preventDefault，鼠标指针才会变成“复制/移动”样式
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) {
            dropOverlay.classList.add('hidden');
        }
    });

    window.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dropOverlay.classList.add('hidden');

        // 收集拖入的本地文件或文件夹路径
        const files = e.dataTransfer.files;
        if (files.length === 0) return;

        const filePaths = Array.from(files).map(file => file.path || file.name);
        
        showToast(`已捕获 ${files.length} 个项目，正在提交后端进行依赖扫描与匹配...`, 'info');
        
        // 核心：若 pywebview 环境已就绪，直接调用 Python 后端
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

/* === 4. 底部高并发卡片面板折叠切换 (Dashboard Toggle) === */
function initDashboardToggle() {
    const dashboard = document.getElementById('active-tasks-dashboard');
    const toggleBar = document.getElementById('dashboard-toggle-bar');
    
    toggleBar.addEventListener('click', () => {
        if (dashboard.classList.contains('dashboard-collapsed')) {
            dashboard.classList.remove('dashboard-collapsed');
            dashboard.classList.add('dashboard-expanded');
        } else {
            dashboard.classList.remove('dashboard-expanded');
            dashboard.classList.add('dashboard-collapsed');
        }
    });
}

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

    document.getElementById('select-output-btn').addEventListener('click', () => {
        callPython('select_output_dir_dialog').then(res => {
            if (res && res.output_dir) {
                document.getElementById('output-dir-input').value = res.output_dir;
                showToast(`输出目录已设置为: ${res.output_dir}`, 'success');
                callPython('get_current_state').then(state => {
                    handleBackendResponse(state);
                });
            }
        });
    });

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
function renderQueue(tasks) {
    const tbody = document.getElementById('queue-tbody');
    if (!tasks || tasks.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">🐑</div>
                        <h3>目前队列空空如也</h3>
                        <p>直接拖入B站手机/电脑版缓存目录，或点击上方导入文件夹</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = tasks.map((task, index) => {
        let statusBadge = '';
        if (task.status === 'pending') {
            statusBadge = `<span style="color: var(--text-muted);">⏳ 待命</span>`;
        } else if (task.status === 'processing') {
            statusBadge = `
                <div class="table-progress-bar" id="t-prog-${index}">
                    <div class="table-progress-chunk" id="t-chunk-${index}" style="width: ${task.percent || 0}%;"></div>
                    <span class="table-progress-text" id="t-text-${index}">${task.percent || 0}%</span>
                </div>`;
        } else if (task.status === 'completed') {
            statusBadge = `<span style="color: var(--primary-color);">✅ 完成</span>`;
        } else if (task.status === 'failed') {
            statusBadge = `<span style="color: #EF4444;" title="${task.error || ''}">❌ 失败</span>`;
        }

        return `
            <tr id="queue-row-${index}" class="${task.status === 'completed' ? 'selected' : ''}" onclick="selectQueueRow(${index}, event)">
                <td><input type="checkbox" class="row-checkbox" data-index="${index}"></td>
                <td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${task.name}</td>
                <td><span style="background-color: var(--alt-base-bg); padding: 2px 6px; border-radius: 4px; font-size: 11px;">${task.format}</span></td>
                <td>${task.resolution || '未知'}</td>
                <td>${task.size || '未知'}</td>
                <td id="queue-status-td-${index}">${statusBadge}</td>
                <td>
                    <button class="mini-action-btn" onclick="deleteTask(${index})" style="color: #EF4444; border-color: rgba(239,68,68,0.2);">🗑️</button>
                </td>
            </tr>`;
    }).join('');
    
    // 恢复先前选中的行高亮并刷新输出路径预览
    if (window.selectedTaskIndex !== undefined && window.selectedTaskIndex !== -1 && window.selectedTaskIndex < tasks.length) {
        setTimeout(() => {
            const row = document.getElementById(`queue-row-${window.selectedTaskIndex}`);
            if (row) {
                row.classList.add('active-row');
            }
            if (window.updatePathPreview) {
                window.updatePathPreview();
            }
        }, 0);
    } else {
        if (window.updatePathPreview) {
            window.updatePathPreview();
        }
    }
}

// A2. 单击列表行，更新右侧的预计输出路径预览
window.selectQueueRow = function(index, event) {
    if (event && (event.target.type === 'checkbox' || event.target.tagName === 'BUTTON')) {
        return;
    }
    
    window.selectedTaskIndex = index;
    
    // 移除所有行的 active-row 样式，并将当前行加上 active-row 样式
    const rows = document.querySelectorAll('#queue-tbody tr');
    rows.forEach(r => r.classList.remove('active-row'));
    
    const row = document.getElementById(`queue-row-${index}`);
    if (row) {
        row.classList.add('active-row');
    }
    
    window.updatePathPreview();
};

window.updatePathPreview = function() {
    const label = document.getElementById('detail-path-label');
    const filenameInput = document.getElementById('output-filename-input');
    if (!label) return;
    
    const activeRows = document.querySelectorAll('#queue-tbody tr.active-row');
    const checkedBoxes = document.querySelectorAll('#queue-tbody .row-checkbox:checked');
    
    // 找出唯一的单选任务索引
    let singleSelectIndex = -1;
    if (window.selectedTaskIndex !== -1 && currentTasks && currentTasks[window.selectedTaskIndex]) {
        singleSelectIndex = window.selectedTaskIndex;
    } else if (activeRows.length === 1) {
        const idStr = activeRows[0].id;
        const index = parseInt(idStr.replace('queue-row-', ''), 10);
        if (currentTasks && currentTasks[index]) {
            singleSelectIndex = index;
        }
    } else if (checkedBoxes.length === 1) {
        const index = parseInt(checkedBoxes[0].getAttribute('data-index'), 10);
        if (currentTasks && currentTasks[index]) {
            singleSelectIndex = index;
        }
    }
    
    // 更新文件名输入框的可用状态与内容
    if (filenameInput) {
        if (singleSelectIndex !== -1 && currentTasks[singleSelectIndex]) {
            const task = currentTasks[singleSelectIndex];
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
    
    if (singleSelectIndex !== -1 && currentTasks[singleSelectIndex]) {
        const task = currentTasks[singleSelectIndex];
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

// B. 动态更新某条任务的合并进度 (在后台线程并发合并时，由 Python 通过 window.evaluate_js 回调此函数)
window.updateTaskProgress = function(index, percent, eta, speed) {
    // 1. 刷新主表格中的嵌入式进度条
    const chunk = document.getElementById(`t-chunk-${index}`);
    const text = document.getElementById(`t-text-${index}`);
    if (chunk && text) {
        chunk.style.width = `${percent}%`;
        text.textContent = `${percent}%`;
    }
    
    // 2. 刷新底部卡片容器中的相应卡片
    const cardChunk = document.getElementById(`card-chunk-${index}`);
    const cardEta = document.getElementById(`card-eta-${index}`);
    const cardSpeed = document.getElementById(`card-speed-${index}`);
    if (cardChunk) cardChunk.style.width = `${percent}%`;
    if (cardEta) cardEta.textContent = `剩余时间: ${eta}`;
    if (cardSpeed) cardSpeed.textContent = `速率: ${speed}`;
};

// C. 动态更新单个任务卡片与列表行状态
window.updateTaskStatus = function(index, status, errorMsg = '') {
    const statusTd = document.getElementById(`queue-status-td-${index}`);
    if (statusTd) {
        if (status === 'processing') {
            statusTd.innerHTML = `
                <div class="table-progress-bar" id="t-prog-${index}">
                    <div class="table-progress-chunk" id="t-chunk-${index}" style="width: 0%;"></div>
                    <span class="table-progress-text" id="t-text-${index}">0%</span>
                </div>`;
            const cardStatus = document.getElementById(`card-status-${index}`);
            if (cardStatus) {
                cardStatus.textContent = '合并中';
                cardStatus.style.color = 'var(--primary-color)';
            }
        } else if (status === 'completed') {
            statusTd.innerHTML = `<span style="color: var(--primary-color);">✅ 完成</span>`;
            document.getElementById(`queue-row-${index}`)?.classList.add('selected');
            const cardStatus = document.getElementById(`card-status-${index}`);
            if (cardStatus) {
                cardStatus.textContent = '已完成';
                cardStatus.style.color = 'var(--primary-color)';
            }
            const cardChunk = document.getElementById(`card-chunk-${index}`);
            if (cardChunk) {
                cardChunk.style.width = '100%';
            }
            const cardEta = document.getElementById(`card-eta-${index}`);
            if (cardEta) {
                cardEta.textContent = '已完成';
            }
            const cardSpeed = document.getElementById(`card-speed-${index}`);
            if (cardSpeed) {
                cardSpeed.textContent = '已结束';
            }
        } else if (status === 'failed') {
            statusTd.innerHTML = `<span style="color: #EF4444;" title="${errorMsg || ''}">❌ 失败</span>`;
            const cardStatus = document.getElementById(`card-status-${index}`);
            if (cardStatus) {
                cardStatus.textContent = '失败';
                cardStatus.style.color = '#EF4444';
            }
        }
    }
};

// C2. 初始化并发任务底盘卡片
window.initDashboardCards = function(tasks) {
    const container = document.getElementById('dashboard-cards-container');
    const activeCount = document.getElementById('active-count');
    
    // 过滤出未完成任务作为并发工作任务数显示
    const activeTasks = tasks.filter(t => t.status !== 'completed');
    activeCount.textContent = activeTasks.length;
    
    if (activeTasks.length > 0) {
        const dashboard = document.getElementById('active-tasks-dashboard');
        dashboard.classList.remove('dashboard-collapsed');
        dashboard.classList.add('dashboard-expanded');
    }
    
    container.innerHTML = tasks.map((task, index) => {
        if (task.status === 'completed') return '';
        
        return `
            <div class="task-card" id="task-card-${index}">
                <div class="task-card-header">
                    <span class="task-card-title" title="${task.name}">${task.name}</span>
                    <span class="task-card-status" id="card-status-${index}">等待中</span>
                </div>
                <div class="task-card-progress">
                    <div class="task-card-progress-chunk" id="card-chunk-${index}" style="width: 0%;"></div>
                </div>
                <div class="task-card-footer">
                    <span id="card-speed-${index}">速率: 0 B/s</span>
                    <span id="card-eta-${index}">剩余时间: --:--</span>
                </div>
            </div>`;
    }).join('');
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
            document.getElementById('output-dir-input').value = settings.output_dir || '';
            document.getElementById('output-format-select').value = settings.output_format || 'mp4';
            document.getElementById('concurrency-input').value = settings.concurrency || 2;
            document.getElementById('overwrite-checkbox').checked = !!settings.overwrite;
            document.getElementById('delete-source-checkbox').checked = !!settings.delete_source;
            
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
    
    if (res.tasks) {
        currentTasks = res.tasks;
        renderQueue(res.tasks);
    }
    
    if (res.pending) {
        currentPending = res.pending;
        renderPending(res.pending);
    }
    
    if (res.muxed) {
        currentMuxed = res.muxed;
        renderMuxed(res.muxed);
    }
}

// E2. 渲染待整理零散音视频表格
function renderPending(pending) {
    const tbody = document.getElementById('pending-tbody');
    if (!tbody) return;
    
    if (pending.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="5">
                    <div class="empty-state">
                        <div class="empty-icon">📁</div>
                        <h3>没有需要整理的零散片段</h3>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    tbody.innerHTML = pending.map((item, index) => {
        const typeBadge = item.stream_type === 'video' 
            ? `<span style="background-color: rgba(16,185,129,0.15); color: var(--primary-color); padding: 2px 6px; border-radius: 4px; font-size: 11px;">视频</span>`
            : `<span style="background-color: rgba(59,130,246,0.15); color: #3B82F6; padding: 2px 6px; border-radius: 4px; font-size: 11px;">音频</span>`;
            
        return `
            <tr>
                <td><input type="checkbox" class="row-checkbox-pending" data-filepath="${item.filepath}"></td>
                <td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.filepath}">
                    ${item.name} ${typeBadge}
                </td>
                <td>${item.size || '未知'}</td>
                <td>${item.mtime || '未知'}</td>
                <td>
                    <button class="mini-action-btn" onclick="deletePendingFile('${item.filepath.replace(/\\/g, '\\\\')}')" style="color: #EF4444; border-color: rgba(239,68,68,0.2);">🗑️</button>
                </td>
            </tr>`;
    }).join('');
}

// E3. 渲染已完整视频文件表格
function renderMuxed(muxed) {
    const tbody = document.getElementById('muxed-tbody');
    if (!tbody) return;
    
    if (muxed.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="6">
                    <div class="empty-state">
                        <div class="empty-icon">🎬</div>
                        <h3>尚未完成任何视频合并</h3>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    tbody.innerHTML = muxed.map((item, index) => {
        return `
            <tr>
                <td><input type="checkbox" class="row-checkbox-muxed" data-filepath="${item.filepath}"></td>
                <td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.filepath}">
                    ${item.name}
                </td>
                <td>${item.resolution || '自动'}</td>
                <td>${item.size || '未知'}</td>
                <td>${item.mtime || '未知'}</td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="mini-action-btn" onclick="playVideo('${item.filepath.replace(/\\/g, '\\\\')}')" style="color: var(--primary-color); border-color: rgba(16,185,129,0.2);" title="使用系统播放器播放">▶️</button>
                        <button class="mini-action-btn" onclick="openFileFolder('${item.filepath.replace(/\\/g, '\\\\')}')" style="color: var(--text-color); border-color: var(--border-color);" title="在资源管理器中定位">📂</button>
                        <button class="mini-action-btn" onclick="deleteMuxedFile('${item.filepath.replace(/\\/g, '\\\\')}')" style="color: #EF4444; border-color: rgba(239,68,68,0.2);" title="从列表中移除">🗑️</button>
                    </div>
                </td>
            </tr>`;
    }).join('');
}

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

/* === 9. 监听配置面板中表单控件的值变化并更新到 Python === */
function initSettingsListeners() {
    const outputFormat = document.getElementById('output-format-select');
    const concurrency = document.getElementById('concurrency-input');
    const overwrite = document.getElementById('overwrite-checkbox');
    const deleteSource = document.getElementById('delete-source-checkbox');

    if (outputFormat) {
        outputFormat.addEventListener('change', (e) => {
            callPython('update_setting', 'output_format', e.target.value);
        });
    }

    if (concurrency) {
        concurrency.addEventListener('change', (e) => {
            let val = parseInt(e.target.value, 10);
            if (isNaN(val) || val < 1) val = 1;
            if (val > 8) val = 8;
            e.target.value = val;
            callPython('update_setting', 'concurrency', val);
        });
    }

    if (overwrite) {
        overwrite.addEventListener('change', (e) => {
            callPython('update_setting', 'overwrite', e.target.checked);
        });
    }

    if (deleteSource) {
        deleteSource.addEventListener('change', (e) => {
            callPython('update_setting', 'delete_source', e.target.checked);
        });
    }

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
            
            let singleSelectIndex = -1;
            if (window.selectedTaskIndex !== -1 && currentTasks && currentTasks[window.selectedTaskIndex]) {
                singleSelectIndex = window.selectedTaskIndex;
            } else if (activeRows.length === 1) {
                const idStr = activeRows[0].id;
                const index = parseInt(idStr.replace('queue-row-', ''), 10);
                if (currentTasks && currentTasks[index]) {
                    singleSelectIndex = index;
                }
            } else if (checkedBoxes.length === 1) {
                const index = parseInt(checkedBoxes[0].getAttribute('data-index'), 10);
                if (currentTasks && currentTasks[index]) {
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
        
        e.preventDefault();
        
        let menuItems = [];
        
        // 判断右击目标
        const trQueue = e.target.closest('#queue-tbody tr');
        const trPending = e.target.closest('#pending-tbody tr');
        const trMuxed = e.target.closest('#muxed-tbody tr');
        
        if (trQueue && !trQueue.classList.contains('empty-state-row')) {
            // A. 合并队列行
            const index = parseInt(trQueue.id.replace('queue-row-', ''), 10);
            const task = currentTasks[index];
            if (task) {
                // 高亮当前行
                document.querySelectorAll('#queue-tbody tr').forEach(r => r.classList.remove('active-row'));
                trQueue.classList.add('active-row');
                window.selectedTaskIndex = index;
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
            window.selectedTaskIndex = -1;
            if (window.updatePathPreview) {
                window.updatePathPreview();
            }
            
            menuItems = [
                { label: '📂 导入 B站 缓存文件夹', action: () => document.getElementById('add-folder-btn').click() },
                { label: '📄 导入 .m4s 单文件', action: () => document.getElementById('add-files-btn').click() },
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
            
            if ((cb && cb.checked) || (idx !== -1 && window.selectedTaskIndex === idx)) {
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
                            window.selectedTaskIndex = parseInt(e.target.getAttribute('data-index'), 10);
                        }
                    } else {
                        tr.classList.remove('active-row');
                        if (e.target.classList.contains('row-checkbox')) {
                            const idx = parseInt(e.target.getAttribute('data-index'), 10);
                            if (window.selectedTaskIndex === idx) {
                                window.selectedTaskIndex = -1;
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

/* === 12. 右侧配置侧边栏折叠/显示控制器 (Config Panel Toggle) === */
function initConfigPanelToggle() {
    const configPanel = document.querySelector('.config-panel');
    const toggleBtn = document.getElementById('config-toggle-btn');
    const closeBtn = document.getElementById('config-close-btn');
    
    // 初始化时，如果面板未折叠，则给按钮加上 active 激活态
    if (toggleBtn && configPanel && !configPanel.classList.contains('collapsed')) {
        toggleBtn.classList.add('active');
    }
    
    if (toggleBtn && configPanel) {
        toggleBtn.addEventListener('click', () => {
            if (configPanel.classList.contains('collapsed')) {
                configPanel.classList.remove('collapsed');
                toggleBtn.classList.add('active');
            } else {
                configPanel.classList.add('collapsed');
                toggleBtn.classList.remove('active');
            }
        });
    }
    
    if (closeBtn && configPanel) {
        closeBtn.addEventListener('click', () => {
            configPanel.classList.add('collapsed');
            if (toggleBtn) {
                toggleBtn.classList.remove('active');
            }
        });
    }
}
