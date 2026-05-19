/* ====================================================================
   🐑 B站 m4s 视频合并工具 v0.4.0 核心客户端逻辑 (JS)
   处理界面渲染、拖拽捕获、选项卡切换、并作为 Bridge 终点对接 Python 后端
   ==================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initTabs();
    initDragAndDrop();
    initDashboardToggle();
    initMockOrBridge();
});

/* === 1. 主题自适应配置 (Dark/Light) === */
function initTheme() {
    const themeBtn = document.getElementById('theme-switch-btn');
    const themeSelect = document.getElementById('theme-select');
    
    // 默认载入深色主题
    let currentTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(currentTheme);
    
    // 左侧悬浮按钮点击切换
    themeBtn.addEventListener('click', () => {
        const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
        notifyPythonTheme(nextTheme);
    });

    // 右侧下拉框选择切换
    themeSelect.addEventListener('change', (e) => {
        applyTheme(e.target.value);
        notifyPythonTheme(e.target.value);
    });
    
    function applyTheme(theme) {
        currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // 同步修改两个控件的视觉属性
        themeBtn.textContent = theme === 'dark' ? '🌙' : '☀️';
        themeSelect.value = theme;
    }
    
    // 外部或异步调用入口，便于 Python 主动同步
    window.setAppTheme = function(theme) {
        if (theme === 'dark' || theme === 'light') {
            applyTheme(theme);
        }
    };
}

function notifyPythonTheme(theme) {
    if (window.pywebview && window.pywebview.api) {
        callPython('update_theme', theme)
            .then(() => {
                showToast(`已切换至 ${theme === 'dark' ? '深色模式' : '浅色模式'}`, 'info');
            });
    } else {
        showToast(`已切换至 ${theme === 'dark' ? '深色模式' : '浅色模式'}`, 'info');
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
        syncSettingsFromPython();
    });

    // 绑定常规操作按钮到 Python 端
    document.getElementById('add-folder-btn').addEventListener('click', () => {
        callPython('select_folder_dialog');
    });

    document.getElementById('add-files-btn').addEventListener('click', () => {
        callPython('select_files_dialog');
    });

    document.getElementById('select-output-btn').addEventListener('click', () => {
        callPython('select_output_dir_dialog');
    });

    document.getElementById('clear-btn').addEventListener('click', () => {
        callPython('clear_queue').then(res => {
            showToast('队列已清空', 'info');
            renderQueue([]);
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
            <tr id="queue-row-${index}" class="${task.status === 'completed' ? 'selected' : ''}">
                <td><input type="checkbox" class="row-checkbox" data-index="${index}"></td>
                <td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${task.name}</td>
                <td><span style="background-color: var(--alt-base-bg); padding: 2px 6px; border-radius: 4px; font-size: 11px;">${task.format}</span></td>
                <td>${task.resolution || '未知'}</td>
                <td>${task.size || '未知'}</td>
                <td id="queue-status-td-${index}">${statusBadge}</td>
                <td>
                    <button class="mini-action-btn" onclick="callPython('delete_task', ${index})" style="color: #EF4444; border-color: rgba(239,68,68,0.2);">🗑️</button>
                </td>
            </tr>`;
    }).join('');
}

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

// C. 动态更新单个任务卡片状态
window.updateTaskStatus = function(index, status, errorMsg) {
    const statusTd = document.getElementById(`queue-status-td-${index}`);
    if (statusTd) {
        if (status === 'completed') {
            statusTd.innerHTML = `<span style="color: var(--primary-color);">✅ 完成</span>`;
            document.getElementById(`queue-row-${index}`)?.classList.add('selected');
        } else if (status === 'failed') {
            statusTd.innerHTML = `<span style="color: #EF4444;" title="${errorMsg || ''}">❌ 失败</span>`;
        }
    }
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

// E. 接收拖拽扫描结果，进行列表初次填充
function handleBackendResponse(res) {
    if (res && res.tasks) {
        renderQueue(res.tasks);
        showToast(`成功扫描到 ${res.tasks.length} 个视频合并任务！`, 'success');
    }
}

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
