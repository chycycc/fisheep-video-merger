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
 * 工具进度回调（由 Python 通过 evaluate_js 调用）
 */
export function updateToolProgress(tool, text, pct) {
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
}

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

// =====================================================
// 任务执行
// =====================================================

export function getSelectedFiles(tool) {
    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return [];
    const checkboxes = tbody.querySelectorAll('.tool-row-cb:checked');
    if (checkboxes.length === 0) return toolFiles[tool];
    return Array.from(checkboxes).map(cb => {
        const idx = parseInt(cb.getAttribute('data-index'), 10);
        return toolFiles[tool][idx];
    }).filter(Boolean);
}

export function runToolTask(tool, taskFn) {
    const selectedFiles = getSelectedFiles(tool);
    if (selectedFiles.length === 0) { showToast('请先添加文件', 'warning'); return; }
    if (!window.pywebview || !window.pywebview.api) { showToast('请在桌面客户端中使用此功能', 'warning'); return; }

    const btn = document.getElementById(`${tool}-start-btn`);
    if (btn) { btn.disabled = true; btn.textContent = '⏳ 处理中...'; }

    let completed = 0, failed = 0;
    const concurrency = Alpine.store('settings').concurrency || 2;

    selectedFiles.forEach(file => { file._status = 'waiting'; });
    renderToolTable(tool);

    async function processFile(file) {
        file._status = 'processing';
        renderToolTable(tool);
        try {
            const result = await taskFn(file);
            if (result && result.status === 'success') {
                completed++;
                file._status = 'completed';
                file._outputPath = result.output_path || '';
            } else {
                failed++;
                file._status = 'failed';
                file._error = result?.error || result?.message || '失败';
            }
        } catch (e) {
            failed++;
            file._status = 'failed';
            file._error = String(e);
        }
        renderToolTable(tool);
    }

    async function runPool() {
        const queue = [...selectedFiles];
        const workers = [];
        for (let i = 0; i < Math.min(concurrency, queue.length); i++) {
            workers.push((async () => {
                while (queue.length > 0) {
                    const file = queue.shift();
                    if (file) await processFile(file);
                }
            })());
        }
        await Promise.all(workers);

        if (btn) { btn.textContent = '🚀 开始处理'; btn.disabled = false; }
        showToast(`处理完成：成功 ${completed}，失败 ${failed}`, failed > 0 ? 'warning' : 'success');

        if (completed > 0) {
            renderConvertResult(tool);
            document.dispatchEvent(new CustomEvent('tool-switch-result-tab', { detail: { tool } }));
        }
    }

    runPool();
}

/**
 * 初始化工具开始按钮事件绑定
 */
export function initToolStartButtons() {
    import('./tools/subtitle.js').then(({ Subtitle }) => {
        const convertBtn = document.getElementById('convert-start-btn');
        if (convertBtn) {
            convertBtn.addEventListener('click', () => {
                const format = document.getElementById('convert-format').value;
                const mode = document.getElementById('convert-mode').value;
                const outputDir = document.getElementById('convert-output-dir')?.value || '';
                const outputName = document.getElementById('convert-output-name')?.value?.trim() || '';
                const checkedCount = document.querySelectorAll('#convert-tbody .tool-row-cb:checked').length;
                const selCount = checkedCount || toolFiles.convert.length;
                const nameForBatch = selCount === 1 ? outputName : '';
                runToolTask('convert', (file) => window.pywebview.api.convert_file(file.filepath, format, mode, outputDir, nameForBatch));
            });
        }

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
                const selCount = checkedCount || toolFiles.extract.length;
                const nameForBatch = selCount === 1 ? outputName : '';
                runToolTask('extract', (file) => window.pywebview.api.extract_audio_api(file.filepath, format, bitrate, outputDir, nameForBatch, channels, sampleRate, volume, bitrateMode));
            });
        }

        const trimBtn = document.getElementById('trim-start-btn');
        if (trimBtn) {
            trimBtn.addEventListener('click', () => {
                const start = document.getElementById('trim-start').value;
                const end = document.getElementById('trim-end').value;
                const mode = document.getElementById('trim-mode').value;
                const outputDir = document.getElementById('trim-output-dir')?.value || '';
                const outputName = document.getElementById('trim-output-name')?.value?.trim() || '';
                const checkedCount = document.querySelectorAll('#trim-tbody .tool-row-cb:checked').length;
                const selCount = checkedCount || toolFiles.trim.length;
                const nameForBatch = selCount === 1 ? outputName : '';
                if (!end) { showToast('请填写结束时间', 'warning'); return; }
                runToolTask('trim', (file) => window.pywebview.api.trim_video_api(file.filepath, start, end, mode, outputDir, nameForBatch));
            });
        }

        const subtitleBtn = document.getElementById('subtitle-start-btn');
        if (subtitleBtn) subtitleBtn.addEventListener('click', () => Subtitle.start());

        const subtitleMergeBtn = document.getElementById('subtitle-merge-btn');
        if (subtitleMergeBtn) subtitleMergeBtn.addEventListener('click', () => Subtitle.startMerge());
    });
}
