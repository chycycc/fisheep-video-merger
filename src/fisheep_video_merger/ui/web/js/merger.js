/**
 * merger.js — 合并队列管理模块
 * 负责队列行选择、视频预览、进度更新、批量操作、拖拽排序、状态管理等
 */

import { callPython, handleBackendResponse } from './bridge.js';
import { showToast } from './ui.js';

// 预览请求计数器（防竞态）
window._previewDebounce = null;
window._previewRequestId = 0;
window._currentPreviewFile = null;  // 当前预览的文件路径（muxed/pending）

// 拖拽排序起始索引
window._dragFromIndex = null;

/**
 * 配置面板开关
 */
export function toggleConfigPanel() {
    const store = Alpine.store('app');
    store.configPanelCollapsed = !store.configPanelCollapsed;
}

/**
 * 单击列表行，更新右侧的预计输出路径预览 + 视频预览
 * 同时同步行首 checkbox 选中状态与 active-row 样式
 * @param {number} index - 任务索引
 * @param {Event} event - 点击事件
 */
export function selectQueueRow(index, event) {
    if (event && event.target.tagName === 'BUTTON') {
        return;
    }

    const store = Alpine.store('app');

    // 切换到合并队列时，清除 muxed/pending 预览文件标记
    window._currentPreviewFile = null;

    // 辅助函数：清除所有行的 active-row 样式
    function clearAllActiveRows() {
        document.querySelectorAll('#queue-tbody tr').forEach(tr => {
            tr.classList.remove('active-row');
        });
    }

    // 辅助函数：设置指定行的 active-row 样式
    function setActiveRow(idx) {
        const tr = document.getElementById(`queue-row-${idx}`);
        if (tr) tr.classList.add('active-row');
    }

    // 如果点击的是 checkbox，同步选中状态
    if (event && event.target.type === 'checkbox') {
        const isChecked = event.target.checked;
        const tr = event.target.closest('tr');
        if (tr) tr.classList.toggle('active-row', isChecked);
        if (isChecked) {
            store.selectedTaskIndex = index;
            store.configPanelCollapsed = false;
            window.loadVideoPreview(index);
        } else {
            // 检查是否还有其他选中的行
            const anyChecked = document.querySelectorAll('#queue-tbody .row-checkbox:checked').length > 0;
            if (!anyChecked) {
                store.selectedTaskIndex = -1;
                window.hideVideoPreview();
            }
        }
        window.updatePathPreview();
        return;
    }

    // 点击行：切换选中状态
    if (store.selectedTaskIndex == index) {
        // 再次点击同一行则取消选中
        store.selectedTaskIndex = -1;
        clearAllActiveRows();
        // 同步取消所有 checkbox
        document.querySelectorAll('#queue-tbody .row-checkbox').forEach(cb => cb.checked = false);
        window.hideVideoPreview();
        window.updatePathPreview();
        return;
    }

    store.selectedTaskIndex = index;

    // 同步：清除所有 active-row，设置当前行
    clearAllActiveRows();
    setActiveRow(index);

    // 同步：勾选当前行 checkbox
    const cb = document.querySelector(`#queue-row-${index} .row-checkbox`);
    if (cb) cb.checked = true;

    // 自动展开配置面板显示预览
    store.configPanelCollapsed = false;

    // 自动填充输出目录为视频所在目录
    const task = store.tasks[index];
    if (task && task.source_dir) {
        const outputDirInput = document.getElementById('global-output-dir');
        if (outputDirInput && !outputDirInput.value.trim()) {
            outputDirInput.value = task.source_dir;
        }
    }

    // 自动展开配置面板显示预览
    store.configPanelCollapsed = false;

    window.updatePathPreview();
    window.loadVideoPreview(index);
}

/**
 * 通用预览加载（供 pending/muxed 标签页使用）
 * @param {string} filepath - 文件路径
 */
export function loadPreviewForFile(filepath) {
    if (!filepath) return;
    // 记录当前预览文件
    window._currentPreviewFile = filepath;
    // 自动展开配置面板
    Alpine.store('app').configPanelCollapsed = false;
    const panel = document.getElementById('video-preview');
    if (panel) panel.style.display = 'block';

    // 立即显示文件路径
    const pathLabel = document.getElementById('detail-path-label');
    if (pathLabel) pathLabel.textContent = filepath;

    const reqId = ++window._previewRequestId;
    callPython('get_video_preview', filepath).then(res => {
        if (reqId !== window._previewRequestId) return;
        if (!res || res.status !== 'success') {
            window.hideVideoPreview();
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
}

/**
 * 隐藏预览面板
 */
export function hideVideoPreview() {
    window._currentPreviewFile = null;
    const panel = document.getElementById('video-preview');
    if (panel) panel.style.display = 'none';
    const img = document.getElementById('preview-img');
    if (img) img.src = '';
    ['resolution','vcodec','acodec','bitrate','duration','fps','episode','platform'].forEach(id => {
        const el = document.getElementById('preview-' + id);
        if (el) el.textContent = '-';
    });
}

/**
 * 加载视频预览（截图 + 元数据），带请求计数器防竞态
 * @param {number} index - 任务索引
 */
export function loadVideoPreview(index) {
    clearTimeout(window._previewDebounce);
    window._previewDebounce = setTimeout(() => {
        const tasks = Alpine.store('app').tasks;
        const task = tasks[index];
        if (!task) {
            window.hideVideoPreview();
            return;
        }
        const filepath = task.video_file || task.audio_file;
        if (!filepath) {
            window.hideVideoPreview();
            return;
        }

        const panel = document.getElementById('video-preview');
        if (panel) panel.style.display = 'block';

        const reqId = ++window._previewRequestId;
        callPython('get_video_preview', filepath).then(res => {
            if (reqId !== window._previewRequestId) return; // 已过时，丢弃
            if (!res || res.status !== 'success') {
                window.hideVideoPreview();
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
}

/**
 * 双击输出名单元格，内联编辑
 * @param {number} index - 任务索引
 * @param {Event} event - 双击事件
 */
export function editOutputName(index, event) {
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
}

/**
 * 更新路径预览（右侧配置面板中显示预计输出路径）
 */
export function updatePathPreview() {
    const label = document.getElementById('detail-path-label');
    const filenameInput = document.getElementById('global-output-name');
    if (!label) return;

    // 如果当前有预览的 muxed/pending 文件，优先显示其路径
    if (window._currentPreviewFile) {
        label.textContent = window._currentPreviewFile;
        return;
    }

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
        const outputDirInput = document.getElementById('global-output-dir');
        const outputFormatSelect = document.getElementById('merge-format');

        const outputDir = (outputDirInput ? outputDirInput.value.trim() : '') || task.source_dir || '';
        const format = (outputFormatSelect ? outputFormatSelect.value : '') || 'mp4';
        const newName = (filenameInput ? filenameInput.value.trim() : '') || task.name || '';

        const separator = outputDir.includes('/') ? '/' : '\\';
        const predictedPath = outputDir + (outputDir.endsWith(separator) ? '' : separator) + newName + '.' + format;
        label.textContent = predictedPath;
    } else if (checkedBoxes.length > 1) {
        label.textContent = `已选择 ${checkedBoxes.length} 个任务，将输出到相应的目标文件夹。`;
    } else {
        label.textContent = '尚未选择任何任务，请双击列表行进行高级分析...';
    }
}

/**
 * 动态更新某条任务的合并进度（通过 Alpine.store 触发响应式更新）
 * @param {number} index - 任务索引
 * @param {number} percent - 进度百分比
 * @param {string} eta - 预计剩余时间
 * @param {string} speed - 处理速度
 */
export function updateTaskProgress(index, percent, eta, speed) {
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
}

/**
 * 动态更新列表行状态（通过 Alpine.store 触发响应式更新）
 * @param {number} index - 任务索引
 * @param {string} status - 状态值
 * @param {string} errorMsg - 错误信息
 * @param {string} outputPath - 输出路径
 */
export function updateTaskStatus(index, status, errorMsg = '', outputPath = '') {
    const store = Alpine.store('app');
    if (store.tasks[index]) {
        store.tasks[index].status = status;
        store.tasks[index].error = errorMsg || '';
        if (outputPath) store.tasks[index].output_path = outputPath;
        if (status === 'processing') {
            store.tasks[index].percent = 0;
        }
        updateMergeStatusBar();
    }
}

/**
 * 更新合并状态条（进度条文字与宽度）
 */
export function updateMergeStatusBar() {
    const store = Alpine.store('app');
    const tasks = store.tasks;
    const total = tasks.length;
    const done = tasks.filter(t => t.status === 'completed' || t.status === 'failed').length;

    const statusBar = document.getElementById('merge-status-bar');
    const statusText = document.getElementById('merge-status-text');
    const statusChunk = document.getElementById('merge-status-chunk');

    if (!statusBar || !statusText || !statusChunk) return;

    if (total > 0 && done < total) {
        statusBar.classList.remove('hidden');
        statusText.textContent = `⚡ 正在合并: ${done}/${total}`;
        statusChunk.style.width = `${(done / total) * 100}%`;
    } else if (done >= total && total > 0) {
        statusBar.classList.add('hidden');
    }
}

/**
 * 初始化合并状态条
 * @param {Array} tasks - 任务列表
 */
export function initDashboardCards(tasks) {
    const statusBar = document.getElementById('merge-status-bar');
    const statusText = document.getElementById('merge-status-text');
    const statusSpeed = document.getElementById('merge-status-speed');
    const statusChunk = document.getElementById('merge-status-chunk');

    if (!statusBar || !statusText || !statusSpeed || !statusChunk) return;

    const activeTasks = tasks.filter(t => t.status !== 'completed');
    const total = tasks.length;
    const done = total - activeTasks.length;

    if (activeTasks.length > 0) {
        statusBar.classList.remove('hidden');
        statusText.textContent = `⚡ 正在合并: ${done}/${total}`;
        statusSpeed.textContent = '';
        statusChunk.style.width = `${(done / total) * 100}%`;
    }
}

/**
 * 全选/取消全选合并队列
 * @param {boolean} checked - 是否选中
 */
export function toggleSelectAll(checked) {
    document.querySelectorAll('#queue-tbody .row-checkbox').forEach(cb => {
        cb.checked = checked;
        const tr = cb.closest('tr');
        if (tr) tr.classList.toggle('active-row', checked);
    });
}

/**
 * 工具面板全选/取消全选
 * @param {boolean} checked - 是否选中
 * @param {string} tool - 工具名称
 */
export function toggleSelectAllLocal(checked, tool) {
    document.querySelectorAll('#' + tool + '-tbody .tool-row-cb').forEach(cb => {
        cb.checked = checked;
        const tr = cb.closest('tr');
        if (tr) tr.classList.toggle('active-row', checked);
    });
}

/**
 * 批量删除选中的合并队列任务
 */
export function batchDeleteSelected() {
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
}

/**
 * 批量重试失败的任务
 */
export function batchRetryFailed() {
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
}

/**
 * 拖拽排序 - 拖拽开始
 * @param {number} index - 起始索引
 * @param {DragEvent} event - 拖拽事件
 */
export function onTaskDragStart(index, event) {
    window._dragFromIndex = index;
    event.dataTransfer.effectAllowed = 'move';
    event.target.style.opacity = '0.5';
}

/**
 * 拖拽排序 - 拖拽经过
 * @param {DragEvent} event - 拖拽事件
 */
export function onTaskDragOver(event) {
    event.dataTransfer.dropEffect = 'move';
}

/**
 * 拖拽排序 - 放置
 * @param {number} toIndex - 目标索引
 * @param {DragEvent} event - 拖拽事件
 */
export function onTaskDrop(toIndex, event) {
    event.preventDefault();
    const fromIndex = window._dragFromIndex;
    if (fromIndex === null || fromIndex === toIndex) return;
    callPython('reorder_tasks', fromIndex, toIndex).then(res => {
        if (res) handleBackendResponse(res);
    });
    window._dragFromIndex = null;
    // 恢复所有行透明度
    document.querySelectorAll('#queue-tbody tr').forEach(tr => tr.style.opacity = '1');
}

/**
 * 删除单个任务
 * @param {number} index - 任务索引
 */
export function deleteTask(index) {
    callPython('delete_task', index).then(res => {
        handleBackendResponse(res);
        showToast('任务已从列表中移除', 'info');
    });
}

/**
 * 重置任务状态为待命
 * @param {number} index - 任务索引
 */
export function resetTaskStatus(index) {
    callPython('reset_task', index).then(res => {
        if (res && res.status !== 'error') {
            handleBackendResponse(res);
            showToast('已重置为待命', 'info');
        }
    });
}

/**
 * 取消正在合并的任务
 */
export function cancelMerging() {
    callPython('cancel_merging').then(res => {
        if (res && res.status === 'success') {
            showToast('正在取消合并...', 'warning');
        }
    });
}

/**
 * 批量重命名对话框
 */
export function showBatchRenameDialog() {
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
}

// =====================================================
// 待整理 (Pending) 与已完整 (Muxed) 相关操作
// =====================================================

let manualMatchCache = null;

/**
 * 删除零散文件记录
 * @param {string} filepath - 文件路径
 */
export function deletePendingFile(filepath) {
    callPython('delete_pending_file', filepath).then(res => {
        if (res) {
            handleBackendResponse(res);
            showToast('零散文件记录已从列表中移除', 'info');
        }
    });
}

/**
 * 手动配对待整理文件
 */
export function manualMatchPending() {
    const checkboxes = document.querySelectorAll('#pending-tbody .row-checkbox-pending:checked');
    if (checkboxes.length !== 2) {
        showToast('请精确勾选 1 个视频和 1 个音频', 'warning');
        return;
    }

    let videoFile = null;
    let audioFile = null;

    const store = Alpine.store('app');

    Array.from(checkboxes).forEach(cb => {
        const filepath = cb.getAttribute('data-filepath');
        // Determine if it's video or audio from store
        const item = store.pending.find(i => i.filepath === filepath);
        if (item) {
            if (item.stream_type === 'video_only') videoFile = item;
            else if (item.stream_type === 'audio_only') audioFile = item;
        }
    });

    if (!videoFile || !audioFile) {
        showToast('必须包含 1 个视频和 1 个音频', 'warning');
        return;
    }

    // Default name
    let defaultName = videoFile.name.split('.').slice(0, -1).join('.');

    document.getElementById('mm-video-name').textContent = videoFile.name;
    document.getElementById('mm-audio-name').textContent = audioFile.name;
    document.getElementById('mm-output-name').value = defaultName;

    manualMatchCache = [videoFile.filepath, audioFile.filepath];

    const modal = document.getElementById('manual-match-modal');
    modal.style.display = 'flex';
}

/**
 * 关闭手动配对模态框
 */
export function closeManualMatchModal() {
    document.getElementById('manual-match-modal').style.display = 'none';
    manualMatchCache = null;
}

/**
 * 确认手动配对
 */
export function confirmManualMatch() {
    if (!manualMatchCache) return;

    const outputName = document.getElementById('mm-output-name').value.trim();
    if (!outputName) {
        showToast('文件名不能为空', 'warning');
        return;
    }

    callPython('manual_match', manualMatchCache, outputName).then(res => {
        if (res && res.status === 'error') {
            showToast(res.message, 'error');
        } else if (res) {
            handleBackendResponse(res);
            showToast('手动配对成功，已移入合并队列', 'success');
            closeManualMatchModal();
            // Deselect all
            const selectAll = document.getElementById('select-all-pending');
            if(selectAll) selectAll.checked = false;
        }
    });
}

/**
 * 自动配对待整理文件
 */
export function autoMatchPending() {
    callPython('auto_match_pending').then(res => {
        if (res && res.status === 'error') {
            showToast(res.message, 'error');
        } else if (res && res.status === 'success') {
            handleBackendResponse(res);
            if (res.message) showToast(res.message, 'success');
        } else if (res) {
            handleBackendResponse(res);
            showToast('智能配对完成', 'success');
        }
    });
}

/**
 * 删除已完整文件记录
 * @param {string} filepath - 文件路径
 */
export function deleteMuxedFile(filepath) {
    callPython('delete_muxed_file', filepath).then(res => {
        if (res) {
            handleBackendResponse(res);
            showToast('合并文件记录已从列表中移除', 'info');
        }
    });
}

/**
 * 播放视频
 * @param {string} filepath - 文件路径
 */
export function playVideo(filepath) {
    callPython('play_video', filepath).then(res => {
        if (res && res.status === 'error') {
            showToast(`播放失败: ${res.message}`, 'error');
        }
    });
}

/**
 * 打开文件所在目录
 * @param {string} filepath - 文件路径
 */
export function openFileFolder(filepath) {
    callPython('open_file_folder', filepath).then(res => {
        if (res && res.status === 'error') {
            showToast(`定位失败: ${res.message}`, 'error');
        }
    });
}

/**
 * 选择输出目录（由 Alpine @click 调用）
 */
export function selectOutputDir() {
    callPython('select_output_dir_dialog').then(res => {
        if (res && res.output_dir) {
            Alpine.store('settings').outputDir = res.output_dir;
            showToast(`输出目录已设置为: ${res.output_dir}`, 'success');
            callPython('get_current_state').then(state => {
                handleBackendResponse(state);
            });
        }
    });
}

// === 批量处理 ===

/**
 * 处理批次面板的拖拽导入事件
 * @param {DragEvent} event - 拖拽事件
 */
window.handleBatchDrop = function(event) {
    // 从拖拽事件中获取文件夹路径
    const files = Array.from(event.dataTransfer.files);
    const paths = files.map(f => f.path || f.name).filter(p => p);
    if (paths.length === 0) {
        showToast('请拖入文件夹', 'warning');
        return;
    }
    window.batchImport(paths);
};

/**
 * 通过文件夹选择对话框批量导入
 */
window.selectBatchFolders = function() {
    callPython('select_folder_dialog').then(res => {
        if (res && res.folders && res.folders.length > 0) {
            window.batchImport(res.folders);
        }
    });
};

/**
 * 获取批次面板的 Alpine 数据（兼容 Alpine v2/v3）
 */
function getBatchData() {
    // 优先查找带有 x-data 的内部 div（Alpine 绑定的实际元素）
    const xDataDiv = document.querySelector('.batch-panel div[x-data]');
    if (xDataDiv) {
        if (typeof Alpine !== 'undefined' && Alpine.$data) {
            return Alpine.$data(xDataDiv);
        }
        return xDataDiv._x_dataStack?.[0] || xDataDiv.__x?.$data || null;
    }
    // 回退：查找 .batch-panel 本身
    const panel = document.querySelector('.batch-panel');
    if (!panel) return null;
    if (typeof Alpine !== 'undefined' && Alpine.$data) {
        return Alpine.$data(panel);
    }
    return panel._x_dataStack?.[0] || panel.__x?.$data || null;
}

/**
 * 批量导入文件夹到批次（异步扫描）
 * @param {string[]} folders - 文件夹路径列表
 */
window.batchImport = function(folders) {
    const data = getBatchData();
    const seriesName = data?.seriesName || '';

    showToast('正在识别文件夹...', 'info');

    callPython('batch_import', folders, seriesName).then(res => {
        if (res && res.status === 'success') {
            showToast('正在扫描文件夹内容...', 'info');
            // 重新获取 Alpine 数据引用（防止过期引用）
            const batchData = getBatchData();
            if (batchData) {
                batchData.batchId = res.batch_id;
            }
        } else {
            showToast(`批量导入失败：${res?.message || '未知错误'}`, 'error');
        }
    }).catch(err => {
        showToast(`批量导入异常：${err}`, 'error');
    });
};

/**
 * 处理批量扫描完成消息（由 bridge.js 调用）
 */
window.handleBatchScanDone = function(data) {
    const panelData = getBatchData();
    if (panelData) {
        panelData.batchId = data.batch_id;
        panelData.taskCount = data.tasks;
    }
    showToast(`批量扫描完成：${data.tasks} 个任务`, 'success');
    window.refreshPreview();
};

/**
 * 刷新批次预览
 */
window.refreshPreview = function() {
    const data = getBatchData();
    if (!data || !data.batchId) return;

    callPython('batch_preview', data.batchId, data.template).then(res => {
        if (res && res.status === 'success') {
            data.previews = res.previews || [];
        }
    });
};

/**
 * 启动批量合并
 */
window.startBatchMerge = function() {
    const data = getBatchData();
    if (!data || !data.batchId) {
        showToast('请先导入批次', 'warning');
        return;
    }

    const settings = {
        output_format: Alpine.store('settings').outputFormat,
        concurrency: Alpine.store('settings').concurrency,
        overwrite: Alpine.store('settings').overwrite,
    };

    callPython('batch_merge', data.batchId, settings).then(res => {
        if (res && res.status === 'error') {
            showToast(res.message, 'warning');
        } else {
            showToast('批量合并已启动', 'success');
        }
    });
};

/**
 * 清空当前批次
 */
window.clearBatch = function() {
    const data = getBatchData();
    if (data) {
        data.batchId = null;
        data.previews = [];
        data.taskCount = 0;
    }
    showToast('批次已清空', 'info');
};

// 防抖预览
let _previewTimer = null;
/**
 * 防抖刷新批次预览（500ms）
 */
window.debouncePreview = function() {
    clearTimeout(_previewTimer);
    _previewTimer = setTimeout(() => window.refreshPreview(), 500);
};
