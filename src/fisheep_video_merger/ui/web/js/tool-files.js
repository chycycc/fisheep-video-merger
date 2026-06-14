/**
 * tool-files.js — 工具文件管理模块
 * 负责工具面板的文件拖拽、添加、表格渲染、任务执行、结果展示
 */

import { callPython } from './bridge.js';
import { showToast } from './ui.js';

// 各工具的任务列表缓存
window.toolFiles = { convert: [], extract: [], compress: [], trim: [], 'audio-convert': [], 'audio-trim': [], subtitle: [] };
const toolFiles = window.toolFiles;

/**
 * 为工具面板初始化拖拽区域
 */
export function initToolDropZones() {
    ['convert', 'extract', 'compress', 'trim', 'audio-convert', 'audio-trim', 'subtitle'].forEach(tool => {
        const panel = document.getElementById(`tool-${tool}`);
        if (!panel) return;

        let dragCounter = 0;

        panel.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter++;
            if (dragCounter === 1) panel.classList.add('drag-over');
        });

        panel.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
        });

        panel.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter--;
            if (dragCounter === 0) panel.classList.remove('drag-over');
        });

        panel.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter = 0;
            panel.classList.remove('drag-over');

            const files = Array.from(e.dataTransfer.files);
            if (files.length === 0) return;

            if (window.chrome && window.chrome.webview && window.chrome.webview.postMessageWithAdditionalObjects) {
                window.chrome.webview.postMessageWithAdditionalObjects('FilesDropped', e.dataTransfer.files);
                const fileNames = Array.from(files).map(f => f.name);
                setTimeout(() => {
                    window.pywebview.api.resolve_dropped_paths(fileNames).then(res => {
                        if (res && res.paths && res.paths.length > 0) {
                            addFilesToTool(tool, res.paths);
                        } else {
                            showToast('路径解析失败，请使用"添加文件"按钮', 'warning');
                        }
                    });
                }, 100);
            } else {
                const paths = Array.from(files).map(f => f.path || f.name).filter(p => p);
                if (paths.length > 0) addFilesToTool(tool, paths);
            }
        });
    });
}

/**
 * 选择工具文件
 */
export function selectFilesForTool(tool) {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_tool_files().then(res => {
            if (res && res.status === 'success' && res.files) {
                addFilesToTool(tool, res.files);
            }
        });
    }
}

/**
 * 添加文件到工具面板
 */
function addFilesToTool(tool, paths) {
    let supportedExts = ['.mp4', '.mkv', '.flv', '.mov', '.avi', '.webm', '.m4s', '.ts', '.wmv'];
    if (tool === 'audio-trim' || tool === 'audio-convert') {
        supportedExts = supportedExts.concat(['.mp3', '.aac', '.flac', '.wav', '.opus', '.ogg', '.m4a', '.wma']);
    }
    const validPaths = paths.filter(p => {
        const ext = p.toLowerCase().substring(p.lastIndexOf('.'));
        return supportedExts.includes(ext);
    });

    if (validPaths.length === 0) {
        showToast('未找到支持的视频文件', 'warning');
        return;
    }

    validPaths.forEach(path => {
        const baseName = path.split(/[\\/]/).pop();
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_file_info(path).then(info => {
                const fileData = { filepath: path, name: baseName, ...(info || {}) };
                if (!fileData.name) fileData.name = baseName;
                if (!fileData.filepath) fileData.filepath = path;
                toolFiles[tool].push(fileData);
                if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
                renderToolTable(tool);
                updateToolStartButton(tool);
                showToast(`已添加: ${baseName}`, 'success');

                if (tool === 'trim' && fileData.duration > 0 && window.setTrimDuration) {
                    window.setTrimDuration(fileData.duration);
                }
            }).catch(() => {
                toolFiles[tool].push({ filepath: path, name: baseName });
                if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
                renderToolTable(tool);
                updateToolStartButton(tool);
                showToast(`已添加: ${baseName}`, 'success');
            });
        } else {
            toolFiles[tool].push({ filepath: path, name: path.split(/[\\/]/).pop(), size: '未知' });
            if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
            renderToolTable(tool);
            updateToolStartButton(tool);
        }
    });
}

/**
 * 选中工具表格行
 */
window.selectToolRow = function(tool, index, event) {
    if (event && event.target.tagName === 'BUTTON') return;

    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return;

    tbody.querySelectorAll('tr.active-row').forEach(tr => tr.classList.remove('active-row'));
    const tr = event.target.closest('tr');
    if (!tr) return;

    if (event.target.type === 'checkbox') {
        if (event.target.checked) tr.classList.add('active-row');
        return;
    }

    const cb = tr.querySelector('.tool-row-cb');
    if (cb) {
        tbody.querySelectorAll('.tool-row-cb').forEach(other => { if (other !== cb) other.checked = false; });
        cb.checked = true;
        tr.classList.add('active-row');
    }
};

/**
 * 渲染工具表格
 */
function renderToolTable(tool) {
    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return;

    const checkedPaths = new Set();
    tbody.querySelectorAll('.tool-row-cb:checked').forEach(cb => {
        const idx = parseInt(cb.getAttribute('data-index'), 10);
        if (toolFiles[tool][idx]) checkedPaths.add(toolFiles[tool][idx].filepath);
    });

    const files = toolFiles[tool];
    if (files.length === 0) {
        const emptyIcons = { convert: '🔄', extract: '🎵', compress: '📦', trim: '✂️', 'audio-convert': '🎧', 'audio-trim': '✂️', subtitle: '📝' };
        tbody.innerHTML = `
            <tr class="empty-state-row" onclick="selectFilesForTool('${tool}')" style="cursor: pointer;">
                <td colspan="10">
                    <div class="empty-state">
                        <div class="empty-icon">${emptyIcons[tool]}</div>
                        <h3>拖入视频文件或点击此处选择</h3>
                        <p>支持 mp4 / mkv / flv / mov / avi / webm</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    function getStatusHtml(file) {
        const s = file._status || 'pending';
        if (s === 'completed') return '✅ 完成';
        if (s === 'failed') return `❌ ${file._error || '失败'}`;
        if (s === 'processing') return '⚡ 处理中...';
        return '⏳ 待处理';
    }

    if (tool === 'extract') {
        tbody.innerHTML = files.map((file, index) => `
            <tr class="${file._status === 'processing' ? 'tool-processing' : ''}" onclick="selectToolRow('${tool}', ${index}, event)">
                <td width="40"><input type="checkbox" class="tool-row-cb" data-index="${index}" ${checkedPaths.has(file.filepath) ? 'checked' : ''}></td>
                <td style="font-weight: 600; max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.filepath}">${file.name}</td>
                <td>${file.codec || '未知'}</td>
                <td>${file.bitrate ? file.bitrate + ' kbps' : '未知'}</td>
                <td>${file.channels === 1 ? '单声道' : file.channels === 2 ? '立体声' : file.channel_layout || '未知'}</td>
                <td>${file.duration_str || '未知'}</td>
                <td>${file.size || '未知'}</td>
                <td class="tool-status">${getStatusHtml(file)}</td>
                <td style="white-space: nowrap;">
                    <button class="mini-action-btn" onclick="openToolFile('${tool}', ${index})" title="播放" style="color: #10B981;">▶</button>
                    <button class="mini-action-btn" onclick="openToolFileFolder('${tool}', ${index})" title="打开目录" style="color: #3B82F6;">📂</button>
                    <button class="mini-action-btn" onclick="removeToolFile('${tool}', ${index})" style="color: #EF4444;" title="移除">✕</button>
                </td>
            </tr>`).join('');
    } else {
        tbody.innerHTML = files.map((file, index) => `
            <tr class="${file._status === 'processing' ? 'tool-processing' : ''}" onclick="selectToolRow('${tool}', ${index}, event)">
                <td width="40"><input type="checkbox" class="tool-row-cb" data-index="${index}" ${checkedPaths.has(file.filepath) ? 'checked' : ''}></td>
                <td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.filepath}">${file.name}</td>
                <td>${file.duration_str || file.size || '未知'}</td>
                <td>${file.size || '未知'}</td>
                <td class="tool-status">${getStatusHtml(file)}</td>
                <td style="white-space: nowrap;">
                    <button class="mini-action-btn" onclick="openToolFile('${tool}', ${index})" title="播放" style="color: #10B981;">▶</button>
                    <button class="mini-action-btn" onclick="openToolFileFolder('${tool}', ${index})" title="打开目录" style="color: #3B82F6;">📂</button>
                    <button class="mini-action-btn" onclick="removeToolFile('${tool}', ${index})" style="color: #EF4444;" title="移除">✕</button>
                </td>
            </tr>`).join('');
    }
}

// 暴露给 tool-runner.js 调用
window.renderToolTable = renderToolTable;

// =====================================================
// 结果页
// =====================================================

const RESULT_COLUMNS = {
    convert: [
        { key: 'source', label: '源文件名', width: '', td: f => `<td class="cell-ellipsis" title="${f.name}">${f.name}</td>` },
        { key: 'outputName', label: '输出文件名', width: '', td: f => { const n = f._outputPath ? f._outputPath.split(/[\\/]/).pop() : '—'; return `<td class="cell-ellipsis" title="${n}">${n}</td>`; } },
        { key: 'format', label: '输出格式', width: '80', td: f => `<td>${f._outputPath ? f._outputPath.split('.').pop().toUpperCase() : '—'}</td>` },
        { key: 'outputDir', label: '输出目录', width: '', td: f => { const d = f._outputPath ? f._outputPath.replace(/[\\/][^\\/]+$/, '') : ''; return `<td class="cell-ellipsis" title="${d}">${d || '—'}</td>`; } },
        { key: 'actions', label: '操作', width: '80', td: f => renderResultActions(f) },
    ],
    extract: [
        { key: 'source', label: '源文件名', width: '', td: f => `<td class="cell-ellipsis" title="${f.name}">${f.name}</td>` },
        { key: 'outputName', label: '输出文件名', width: '', td: f => { const n = f._outputPath ? f._outputPath.split(/[\\/]/).pop() : '—'; return `<td class="cell-ellipsis" title="${n}">${n}</td>`; } },
        { key: 'format', label: '音频格式', width: '80', td: f => `<td>${f._outputPath ? f._outputPath.split('.').pop().toUpperCase() : '—'}</td>` },
        { key: 'bitrate', label: '码率', width: '80', td: () => `<td>${Alpine.store('settings').toolSettings.extract.bitrate || '—'}</td>` },
        { key: 'outputDir', label: '输出目录', width: '', td: f => { const d = f._outputPath ? f._outputPath.replace(/[\\/][^\\/]+$/, '') : ''; return `<td class="cell-ellipsis" title="${d}">${d || '—'}</td>`; } },
        { key: 'actions', label: '操作', width: '80', td: f => renderResultActions(f) },
    ],
    'audio-convert': [
        { key: 'source', label: '源文件名', width: '', td: f => `<td class="cell-ellipsis" title="${f.name}">${f.name}</td>` },
        { key: 'outputName', label: '输出文件名', width: '', td: f => { const n = f._outputPath ? f._outputPath.split(/[\\/]/).pop() : '—'; return `<td class="cell-ellipsis" title="${n}">${n}</td>`; } },
        { key: 'format', label: '输出格式', width: '80', td: f => `<td>${f._outputPath ? f._outputPath.split('.').pop().toUpperCase() : '—'}</td>` },
        { key: 'outputDir', label: '输出目录', width: '', td: f => { const d = f._outputPath ? f._outputPath.replace(/[\\/][^\\/]+$/, '') : ''; return `<td class="cell-ellipsis" title="${d}">${d || '—'}</td>`; } },
        { key: 'actions', label: '操作', width: '80', td: f => renderResultActions(f) },
    ],
    compress: [
        { key: 'source', label: '源文件名', width: '', td: f => `<td class="cell-ellipsis" title="${f.name}">${f.name}</td>` },
        { key: 'outputName', label: '输出文件名', width: '', td: f => { const n = f._outputPath ? f._outputPath.split(/[\\/]/).pop() : '—'; return `<td class="cell-ellipsis" title="${n}">${n}</td>`; } },
        { key: 'preset', label: '压缩模式', width: '100', td: () => { const p = Alpine.store('settings').toolSettings.compress.preset; const m = { fast: '⚡ 快速', balanced: '🎯 均衡', quality: '💎 高质量' }; return `<td>${m[p] || p || '—'}</td>`; } },
        { key: 'outputDir', label: '输出目录', width: '', td: f => { const d = f._outputPath ? f._outputPath.replace(/[\\/][^\\/]+$/, '') : ''; return `<td class="cell-ellipsis" title="${d}">${d || '—'}</td>`; } },
        { key: 'actions', label: '操作', width: '80', td: f => renderResultActions(f) },
    ],
};

function renderResultActions(file) {
    if (!file._outputPath) return '<td></td>';
    const p = file._outputPath.replace(/\\/g, '\\\\');
    return `<td style="white-space: nowrap;">
        <button class="mini-action-btn" onclick="openToolResultFile('${p}')" title="播放" style="color: #10B981;">▶</button>
        <button class="mini-action-btn" onclick="openToolResultFolder('${p}')" title="打开目录" style="color: #3B82F6;">📂</button>
    </td>`;
}

window.renderConvertResult = function(tool) {
    const columns = RESULT_COLUMNS[tool];
    if (!columns) return;

    const thead = document.getElementById(`${tool}-result-thead`);
    const tbody = document.getElementById(`${tool}-result-tbody`);
    if (!tbody) return;

    if (thead) {
        thead.innerHTML = `<tr>${columns.map(c => `<th${c.width ? ` width="${c.width}"` : ''}>${c.label}</th>`).join('')}</tr>`;
    }

    const completedFiles = (toolFiles[tool] || []).filter(f => f._status === 'completed');
    if (completedFiles.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="${columns.length}">
                    <div class="empty-state">
                        <div class="empty-icon">📭</div>
                        <h3>暂无处理结果</h3>
                        <p>完成处理后将在此显示输出文件信息</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = completedFiles.map(file =>
        `<tr>${columns.map(c => c.td(file)).join('')}</tr>`
    ).join('');
};

window.openToolResultFile = function(filepath) { callPython('play_video', filepath); };
window.openToolResultFolder = function(filepath) { callPython('open_file_folder', filepath); };

// =====================================================
// 文件操作
// =====================================================

export function openToolFile(tool, index) {
    const file = toolFiles[tool][index];
    if (file && file.filepath) callPython('play_video', file.filepath);
}

export function openToolFileFolder(tool, index) {
    const file = toolFiles[tool][index];
    if (file && file.filepath) callPython('open_file_folder', file.filepath);
}

export function removeToolFile(tool, index) {
    toolFiles[tool].splice(index, 1);
    if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
    renderToolTable(tool);
    updateToolStartButton(tool);
    if (tool === 'trim' && toolFiles[tool].length === 0 && window.resetTrimTimeline) {
        window.resetTrimTimeline();
    }
}

function updateToolStartButton(tool) {
    const btn = document.getElementById(`${tool}-start-btn`);
    if (btn) btn.disabled = toolFiles[tool].length === 0;
}
