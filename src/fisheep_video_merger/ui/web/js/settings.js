/**
 * settings.js — 设置与配置模块
 * 负责设置面板初始化、硬件加速/平台统计加载、配置导出导入、工具面板、Profile 管理、面板拖拽调整
 */

import { callPython, handleBackendResponse, syncSettingsFromPython } from './bridge.js';
import { showToast } from './ui.js';
import { Subtitle } from './tools/subtitle.js';

/**
 * 监听配置面板中表单控件的值变化并更新到 Python
 */
export function initSettingsListeners() {
    // 输出格式、并发数、复选框已由 Alpine x-model + @change 绑定，无需手动 addEventListener

    const filenameInput = document.getElementById('global-output-name');
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
    const tplInput = document.getElementById('global-output-name');
    if (tplInput) {
        tplInput.addEventListener('change', (e) => {
            callPython('update_setting', 'naming_template', e.target.value.trim());
        });
    }

    // 输出目录模板输入
    const dirTplInput = document.getElementById('global-output-dir-template');
    if (dirTplInput) {
        dirTplInput.addEventListener('change', (e) => {
            callPython('update_setting', 'output_dir_template', e.target.value.trim());
        });
    }

    // 路径层级
    const depthSelect = document.getElementById('global-path-depth');
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

/**
 * 加载硬件加速信息
 */
export function loadHwAccelInfo() {
    callPython('get_hw_accel_info').then(res => {
        const el = document.getElementById('hw-accel-info');
        if (!el || !res || res.status !== 'success') return;
        if (res.encoder) {
            el.innerHTML = `<span style="color: var(--primary-color);">✅ ${res.desc}</span>（${res.encoder}）`;
        } else {
            el.innerHTML = `<span>软编码</span>（未检测到 GPU 加速）`;
        }
    });
}

/**
 * 加载平台统计信息
 */
export function loadPlatformStats() {
    callPython('get_platform_stats').then(res => {
        const el = document.getElementById('platform-stats');
        if (!el || !res || res.status !== 'success') return;
        const s = res.stats;
        el.innerHTML = `共 <strong>${res.total}</strong> 个文件 · B站: ${s['B站']} · YouTube: ${s['YouTube']} · 通用: ${s['通用']}`;
    });
}

/**
 * 导出配置文件
 */
export function exportConfig() {
    callPython('export_config_file').then(res => {
        if (res && res.status === 'success') {
            showToast(`配置已导出到 ${res.path}`, 'success');
        } else if (res && res.status === 'cancelled') {
            // 用户取消
        } else {
            showToast(`导出失败: ${res?.message || '未知错误'}`, 'error');
        }
    });
}

/**
 * 导入配置文件
 */
export function importConfig() {
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
}

/**
 * 选择输出目录
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

/**
 * 设置面板初始化
 */
export function initSettingsPanel() {
    // 从 Python 同步设置到 UI（仅同步实际存在的元素）
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_current_settings().then(settings => {
            if (!settings) return;
            const themeSelect = document.getElementById('settings-theme');
            if (themeSelect) themeSelect.value = settings.theme || 'auto';
        });
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

    // 注意：输出目录、格式、并发数、覆盖、删除源文件等设置
    // 已在合并配置面板（右侧 config panel）中管理，此处不再重复
}

/**
 * 选择设置面板的输出目录
 */
export function selectSettingsOutputDir() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_output_dir_dialog().then(res => {
            if (res && res.output_dir) {
                // 输出目录设置已在合并配置面板中管理
                callPython('update_setting', 'output_dir', res.output_dir);
            }
        });
    }
}

/**
 * 选择工具输出目录
 * @param {string} tool - 工具名称
 */
export function selectToolOutputDir(tool) {
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
}

/**
 * 音频提取质量预设
 * @param {string} preset - 预设名称：high / medium / low
 */
export function applyExtractPreset(preset) {
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
}

/**
 * 收集当前设置快照
 * @returns {object} 当前设置对象
 */
export function gatherCurrentSettings() {
    return {
        output_format: Alpine.store('settings').outputFormat,
        concurrency: Alpine.store('settings').concurrency,
        overwrite: Alpine.store('settings').overwrite,
        delete_source: Alpine.store('settings').deleteSource,
        output_dir: document.getElementById('global-output-dir')?.value || '',
        naming_template: document.getElementById('global-output-name')?.value || '',
        tool_settings: Alpine.store('settings').toolSettings
    };
}

/**
 * 应用加载的设置到 UI
 * @param {object} settings - 设置对象
 */
export function applyLoadedSettings(settings) {
    if (!settings) return;
    const store = Alpine.store('settings');
    if (settings.output_format) store.outputFormat = settings.output_format;
    if (settings.concurrency) store.concurrency = settings.concurrency;
    if (settings.overwrite !== undefined) store.overwrite = settings.overwrite;
    if (settings.delete_source !== undefined) store.deleteSource = settings.delete_source;

    if (settings.output_dir && document.getElementById('global-output-dir')) {
        document.getElementById('global-output-dir').value = settings.output_dir;
    }
    if (settings.naming_template && document.getElementById('global-output-name')) {
        document.getElementById('global-output-name').value = settings.naming_template;
    }

    if (settings.tool_settings) {
        // Deep merge tool settings to trigger Alpine reactivity
        for (const tool in settings.tool_settings) {
            if (store.toolSettings[tool]) {
                store.toolSettings[tool] = { ...store.toolSettings[tool], ...settings.tool_settings[tool] };
            }
        }
    }
}

/**
 * 导出配置模板 (Profile)
 */
export function exportProfile() {
    const currentSettings = gatherCurrentSettings();
    callPython('update_settings', currentSettings).then(() => {
        callPython('export_profile_file').then(res => {
            if (res && res.status === 'success') {
                showToast('配置模板导出成功！', 'success');
            } else if (res && res.status === 'error') {
                showToast(res.message, 'warning');
            }
        });
    });
}

/**
 * 导入配置模板 (Profile)
 */
export function importProfile() {
    callPython('import_profile_file').then(res => {
        if (res && res.status === 'success' && res.settings) {
            applyLoadedSettings(res.settings);
            showToast('配置模板加载成功！', 'success');
        } else if (res && res.status === 'error') {
            showToast(res.message, 'warning');
        }
    });
}

/**
 * 全局配置面板拖拽调整宽度逻辑
 * @param {MouseEvent} e - 鼠标按下事件
 */
export function startConfigResize(e) {
    e.preventDefault();
    const startX = e.clientX;
    const store = Alpine.store('app');
    const startWidth = store.configWidth;

    document.body.classList.add('is-resizing');

    function onMouseMove(moveEvent) {
        // 由于调整条在左侧，向左拖动（clientX变小）意味着宽度增加
        const delta = startX - moveEvent.clientX;
        let newWidth = startWidth + delta;

        // 如果宽度小于 200，则自动隐藏
        if (newWidth < 200) {
            store.configPanelCollapsed = true;
            newWidth = 320; // 记录一个恢复后的默认宽度
            cleanup();
        } else {
            // 否则展开面板，并限制最大宽度为 600
            store.configPanelCollapsed = false;
            store.configWidth = Math.min(600, newWidth);
        }
    }

    function cleanup() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', cleanup);
        document.body.style.cursor = '';
        document.body.classList.remove('is-resizing');
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', cleanup);
    document.body.style.cursor = 'col-resize';
}

/**
 * 左侧导航栏拖拽调整宽度逻辑
 * @param {MouseEvent} e - 鼠标按下事件
 */
export function startSidebarResize(e) {
    e.preventDefault();
    const startX = e.clientX;
    const store = Alpine.store('app');
    const startWidth = store.sidebarCollapsed ? 72 : store.sidebarWidth;
    let hasMoved = false;

    function onMouseMove(moveEvent) {
        const delta = moveEvent.clientX - startX;

        // 只有发生实际拖拽(>3px)才解除折叠，防止仅仅点击就瞬间弹开
        if (!hasMoved && Math.abs(delta) > 3) {
            hasMoved = true;
            store.sidebarCollapsed = false;
            document.body.classList.add('is-resizing');
        }

        if (hasMoved) {
            let newWidth = startWidth + delta;
            // 允许宽度平滑变化，最小允许拖到 72px，最大 400px
            store.sidebarWidth = Math.max(72, Math.min(400, newWidth));
        }
    }

    function cleanup() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', cleanup);

        if (hasMoved) {
            document.body.style.cursor = '';
            document.body.classList.remove('is-resizing');

            // 拖动结束时，如果宽度小于 150，则自动收起并带上平滑过渡
            if (store.sidebarWidth < 150) {
                store.sidebarCollapsed = true;
                // 记住一个恢复用的合适宽度
                store.sidebarWidth = 240;
            } else if (store.sidebarWidth < 200) {
                // 如果介于 150~200 之间，吸附到 200
                store.sidebarWidth = 200;
            }
        }
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', cleanup);
    document.body.style.cursor = 'col-resize';
}

// =====================================================
// 通用视频工具前端逻辑 (Convert / Extract / Compress / Trim)
// =====================================================

// 各工具的任务列表缓存
window.toolFiles = { convert: [], extract: [], compress: [], trim: [], 'audio-convert': [], 'audio-trim': [], subtitle: [] };
const toolFiles = window.toolFiles;

/**
 * 工具进度回调（由 Python 通过 evaluate_js 调用）
 * @param {string} tool - 工具名称
 * @param {string} text - 状态文字
 * @param {number} pct - 进度百分比
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

            // WebView2: 通过 pywebview 的 postMessageWithAdditionalObjects 获取完整路径
            if (window.chrome && window.chrome.webview && window.chrome.webview.postMessageWithAdditionalObjects) {
                window.chrome.webview.postMessageWithAdditionalObjects('FilesDropped', e.dataTransfer.files);
                // 等待 Python 端处理完 _dnd_state 后，通过 API 获取路径
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
                // 非 WebView2 环境，直接用 file.path
                const paths = Array.from(files).map(f => f.path || f.name).filter(p => p);
                if (paths.length > 0) addFilesToTool(tool, paths);
            }
        });
    });
}

/**
 * 选择工具文件
 * @param {string} tool - 工具名称
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
 * @param {string} tool - 工具名称
 * @param {Array} paths - 文件路径列表
 */
function addFilesToTool(tool, paths) {
    // 过滤支持的格式
    let supportedExts = ['.mp4', '.mkv', '.flv', '.mov', '.avi', '.webm', '.m4s', '.ts', '.wmv'];
    // 音频工具额外支持音频格式
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

    // 获取文件信息（提取音频用 get_file_info 获取详细音频信息）
    validPaths.forEach(path => {
        const baseName = path.split(/[\\/]/).pop();
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_file_info(path).then(info => {
                console.log('[addFilesToTool] get_file_info 成功:', JSON.stringify(info));
                const fileData = { filepath: path, name: baseName, ...(info || {}) };
                if (!fileData.name) fileData.name = baseName;
                if (!fileData.filepath) fileData.filepath = path;
                toolFiles[tool].push(fileData);
                if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
                renderToolTable(tool);
                updateToolStartButton(tool);
                showToast(`已添加: ${baseName}`, 'success');

                // 裁剪工具：激活时间轴滑块
                console.log('[addFilesToTool] tool:', tool, 'duration:', fileData.duration, 'setTrimDuration:', !!window.setTrimDuration);
                if (tool === 'trim' && fileData.duration > 0 && window.setTrimDuration) {
                    window.setTrimDuration(fileData.duration);
                }
            }).catch(err => {
                console.error('[addFilesToTool] get_file_info 失败:', err);
                toolFiles[tool].push({ filepath: path, name: baseName });
                if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
                renderToolTable(tool);
                updateToolStartButton(tool);
                showToast(`已添加: ${baseName}`, 'success');
            });
        } else {
            toolFiles[tool].push({
                filepath: path,
                name: path.split(/[\\/]/).pop(),
                size: '未知',
            });
            if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
            renderToolTable(tool);
            updateToolStartButton(tool);
        }
    });
}

/**
 * 选中工具表格行（与合并页 selectQueueRow 对应）
 * @param {string} tool - 工具名称
 * @param {number} index - 行索引
 * @param {Event} event - 点击事件
 */
window.selectToolRow = function(tool, index, event) {
    // 点击按钮时不处理
    if (event && event.target.tagName === 'BUTTON') return;

    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return;

    // 清除所有行的高亮
    tbody.querySelectorAll('tr.active-row').forEach(tr => tr.classList.remove('active-row'));

    const tr = event.target.closest('tr');
    if (!tr) return;

    // 如果点击的是 checkbox，同步选中状态
    if (event.target.type === 'checkbox') {
        if (event.target.checked) {
            tr.classList.add('active-row');
        }
        return;
    }

    // 点击行文字：选中当前行，取消其他
    const cb = tr.querySelector('.tool-row-cb');
    if (cb) {
        tbody.querySelectorAll('.tool-row-cb').forEach(other => {
            if (other !== cb) other.checked = false;
        });
        cb.checked = true;
        tr.classList.add('active-row');
    }
};

/**
 * 渲染工具表格
 * @param {string} tool - 工具名称
 */
function renderToolTable(tool) {
    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return;

    // 保存当前 checkbox 选中状态（用 filepath 作为 key）
    const checkedPaths = new Set();
    tbody.querySelectorAll('.tool-row-cb:checked').forEach(cb => {
        const idx = parseInt(cb.getAttribute('data-index'), 10);
        if (toolFiles[tool][idx]) checkedPaths.add(toolFiles[tool][idx].filepath);
    });

    const files = toolFiles[tool];
    if (files.length === 0) {
        const emptyIcons = { convert: '🔄', extract: '🎵', compress: '📦', trim: '✂️', subtitle: '📝' };
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

    function getStatusHtml(file) {
        const s = file._status || 'pending';
        if (s === 'completed') return '✅ 完成';
        if (s === 'failed') return `❌ ${file._error || '失败'}`;
        if (s === 'processing') return '⚡ 处理中...';
        return '⏳ 待处理';
    }

    if (tool === 'extract') {
        // 音频提取：显示 编码/码率/声道/时长/大小
        tbody.innerHTML = files.map((file, index) => {
            return `
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
                </tr>`;
        }).join('');
    } else {
        // 其他工具：标准列
        tbody.innerHTML = files.map((file, index) => {
            const col2 = file.duration_str || file.size || '未知';
            const col3 = file.size || '未知';
            return `
                <tr class="${file._status === 'processing' ? 'tool-processing' : ''}" onclick="selectToolRow('${tool}', ${index}, event)">
                    <td width="40"><input type="checkbox" class="tool-row-cb" data-index="${index}" ${checkedPaths.has(file.filepath) ? 'checked' : ''}></td>
                    <td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.filepath}">${file.name}</td>
                    <td>${col2}</td>
                    <td>${col3}</td>
                    <td class="tool-status">${getStatusHtml(file)}</td>
                    <td style="white-space: nowrap;">
                        <button class="mini-action-btn" onclick="openToolFile('${tool}', ${index})" title="播放" style="color: #10B981;">▶</button>
                        <button class="mini-action-btn" onclick="openToolFileFolder('${tool}', ${index})" title="打开目录" style="color: #3B82F6;">📂</button>
                        <button class="mini-action-btn" onclick="removeToolFile('${tool}', ${index})" style="color: #EF4444;" title="移除">✕</button>
                    </td>
                </tr>`;
        }).join('');
    }
}

/**
 * 结果页列配置（按工具定制）
 * key: 列标识 | label: 表头 | width: 列宽 | td: 渲染函数(file) => html
 */
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

/** 结果操作按钮 */
function renderResultActions(file) {
    if (!file._outputPath) return '<td></td>';
    const p = file._outputPath.replace(/\\/g, '\\\\');
    return `<td style="white-space: nowrap;">
        <button class="mini-action-btn" onclick="openToolResultFile('${p}')" title="播放" style="color: #10B981;">▶</button>
        <button class="mini-action-btn" onclick="openToolResultFolder('${p}')" title="打开目录" style="color: #3B82F6;">📂</button>
    </td>`;
}

/**
 * 渲染结果表格（通用，按工具列配置）
 * @param {string} tool - 工具名称
 */
window.renderConvertResult = function(tool) {
    const columns = RESULT_COLUMNS[tool];
    if (!columns) return;

    const thead = document.getElementById(`${tool}-result-thead`);
    const tbody = document.getElementById(`${tool}-result-tbody`);
    if (!tbody) return;

    // 渲染表头
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

/**
 * 打开转换结果文件（播放）
 */
window.openToolResultFile = function(filepath) {
    callPython('play_video', filepath);
};

/**
 * 打开转换结果文件所在目录
 */
window.openToolResultFolder = function(filepath) {
    callPython('open_file_folder', filepath);
};

/**
 * 打开工具文件（播放）
 * @param {string} tool - 工具名称
 * @param {number} index - 文件索引
 */
export function openToolFile(tool, index) {
    const file = toolFiles[tool][index];
    if (file && file.filepath) {
        callPython('play_video', file.filepath);
    }
}

/**
 * 打开工具文件所在目录
 * @param {string} tool - 工具名称
 * @param {number} index - 文件索引
 */
export function openToolFileFolder(tool, index) {
    const file = toolFiles[tool][index];
    if (file && file.filepath) {
        callPython('open_file_folder', file.filepath);
    }
}

/**
 * 移除工具文件
 * @param {string} tool - 工具名称
 * @param {number} index - 文件索引
 */
export function removeToolFile(tool, index) {
    toolFiles[tool].splice(index, 1);
    if (Alpine.store('app')) Alpine.store('app').toolFilesVersion++;
    renderToolTable(tool);
    updateToolStartButton(tool);
    // 裁剪工具：文件全部移除时重置时间轴
    if (tool === 'trim' && toolFiles[tool].length === 0 && window.resetTrimTimeline) {
        window.resetTrimTimeline();
    }
}

/**
 * 更新工具开始按钮状态
 * @param {string} tool - 工具名称
 */
function updateToolStartButton(tool) {
    const btn = document.getElementById(`${tool}-start-btn`);
    if (btn) {
        btn.disabled = toolFiles[tool].length === 0;
    }
}

/**
 * 初始化工具开始按钮事件绑定
 */
export function initToolStartButtons() {
    // 格式转换
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
            runToolTask('convert', (file) => {
                return window.pywebview.api.convert_file(file.filepath, format, mode, outputDir, nameForBatch);
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

    // 视频裁剪
    const trimBtn = document.getElementById('trim-start-btn');
    if (trimBtn) {
        trimBtn.addEventListener('click', () => {
            const start = document.getElementById('trim-start').value;
            const end = document.getElementById('trim-end').value;
            const mode = document.getElementById('trim-mode').value;
            const outputDir = document.getElementById('trim-output-dir')?.value || '';
            const outputName = document.getElementById('trim-output-name')?.value?.trim() || '';
            const trimSettings = Alpine.store('settings').toolSettings.trim;
            const audioMode = trimSettings.audioMode || 'keep';
            const keepAudio = audioMode !== 'remove';
            const keepVideo = audioMode !== 'only';
            const outputFormat = trimSettings.outputFormat || '';
            const checkedCount = document.querySelectorAll('#trim-tbody .tool-row-cb:checked').length;
            const selCount = checkedCount || toolFiles.trim.length;
            const nameForBatch = selCount === 1 ? outputName : '';
            if (!end) {
                showToast('请填写结束时间', 'warning');
                return;
            }
            runToolTask('trim', (file) => {
                return window.pywebview.api.trim_video_api(file.filepath, start, end, mode, outputDir, nameForBatch, keepAudio, keepVideo, outputFormat);
            });
        });
    }

    // 字幕工具
    const subtitleBtn = document.getElementById('subtitle-start-btn');
    if (subtitleBtn) {
        subtitleBtn.addEventListener('click', () => {
            Subtitle.start();
        });
    }

    // 字幕合并（独立按钮）
    const subtitleMergeBtn = document.getElementById('subtitle-merge-btn');
    if (subtitleMergeBtn) {
        subtitleMergeBtn.addEventListener('click', () => {
            Subtitle.startMerge();
        });
    }
}

/**
 * 获取选中的文件（带复选框的行）
 * @param {string} tool - 工具名称
 * @returns {Array} 选中的文件列表
 */
export function getSelectedFiles(tool) {
    const tbody = document.getElementById(`${tool}-tbody`);
    if (!tbody) return [];
    const checkboxes = tbody.querySelectorAll('.tool-row-cb:checked');
    if (checkboxes.length === 0) return toolFiles[tool]; // 没勾选则全选
    return Array.from(checkboxes).map(cb => {
        const idx = parseInt(cb.getAttribute('data-index'), 10);
        return toolFiles[tool][idx];
    }).filter(Boolean);
}

/**
 * 运行工具任务（并发池模式）
 * @param {string} tool - 工具名称
 * @param {Function} taskFn - 单文件处理函数
 */
export function runToolTask(tool, taskFn) {
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
    const concurrency = Alpine.store('settings').concurrency || 2;

    // 标记选中行为等待中
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

    // 并发处理池
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

        if (btn) {
            btn.textContent = '🚀 开始处理';
            btn.disabled = false;
        }
        showToast(`处理完成：成功 ${completed}，失败 ${failed}`, failed > 0 ? 'warning' : 'success');

        // 渲染结果表格并自动切到结果 tab
        if (completed > 0) {
            renderConvertResult(tool);
            // 自定义事件通知 Alpine 切换 tab
            document.dispatchEvent(new CustomEvent('tool-switch-result-tab', { detail: { tool } }));
        }
    }

    runPool();
}

// =====================================================
// 视频裁剪时间轴滑块
// =====================================================

let trimDuration = 0; // 视频总时长（秒）
let trimStartSec = 0;
let trimEndSec = 0;

/**
 * 初始化裁剪时间轴滑块
 */
export function initTrimTimeline() {
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
        trimDuration = Number(duration) || 0;
        trimStartSec = 0;
        trimEndSec = trimDuration;
        console.log('[setTrimDuration]', duration, '-> trimDuration:', trimDuration, 'handleStart:', !!handleStart, 'handleEnd:', !!handleEnd);
        const hint = document.getElementById('trim-duration-hint');
        if (hint && trimDuration > 0) {
            const h = Math.floor(trimDuration / 3600);
            const m = Math.floor((trimDuration % 3600) / 60);
            const s = Math.floor(trimDuration % 60);
            hint.textContent = `(总时长: ${h}h ${m}m ${s}s)`;
        }
        // 直接操作 DOM 更新手柄位置（不依赖闭包变量，防止元素被重建后引用失效）
        const hs = document.getElementById('trim-handle-start');
        const he = document.getElementById('trim-handle-end');
        const sel = document.getElementById('trim-selected');
        if (trimDuration > 0 && hs && he) {
            hs.style.left = '0%';
            he.style.left = '100%';
            if (sel) { sel.style.left = '0%'; sel.style.width = '100%'; }
            document.getElementById('trim-label-start').textContent = '00:00:00';
            document.getElementById('trim-label-end').textContent = secToTime(trimDuration);
            document.getElementById('trim-start').value = '00:00:00';
            document.getElementById('trim-end').value = secToTime(trimDuration);
            console.log('[setTrimDuration] 时间轴已更新, end:', secToTime(trimDuration));
        } else {
            console.log('[setTrimDuration] 更新失败, trimDuration:', trimDuration, 'hs:', !!hs, 'he:', !!he);
        }
    };

    // 重置时间轴到默认状态（无视频时）
    window.resetTrimTimeline = function() {
        trimDuration = 0;
        trimStartSec = 0;
        trimEndSec = 0;
        const hint = document.getElementById('trim-duration-hint');
        if (hint) hint.textContent = '';
        // 重置手柄位置到默认（全选范围）
        const handleStart = document.getElementById('trim-handle-start');
        const handleEnd = document.getElementById('trim-handle-end');
        const selected = document.getElementById('trim-selected');
        if (handleStart) handleStart.style.left = '0%';
        if (handleEnd) handleEnd.style.left = '100%';
        if (selected) { selected.style.left = '0%'; selected.style.width = '100%'; }
        document.getElementById('trim-label-start').textContent = '00:00:00';
        document.getElementById('trim-label-end').textContent = '00:00:00';
        document.getElementById('trim-start').value = '00:00:00';
        document.getElementById('trim-end').value = '';
    };

    // 初始化时设置默认状态
    window.resetTrimTimeline();
}

/**
 * 恢复默认设置
 */
window.restoreDefaults = function() {
    if (!confirm('确定要恢复所有设置为默认值吗？')) return;

    const defaults = {
        output_format: 'mp4',
        concurrency: 2,
        overwrite: true,
        delete_allowed: false,
        output_dir: '',
        naming_template: '',
        theme: 'auto',
        tool_settings: {
            convert: { format: 'mp4', mode: 'copy' },
            extract: { format: 'aac', bitrate: '192k', bitrateMode: 'cbr', channels: 'original', sampleRate: 'original', volume: '1.0' },
            compress: { preset: 'balanced', resolution: 'original' },
            trim: { mode: 'copy' }
        }
    };

    callPython('update_settings', defaults).then(() => {
        syncSettingsFromPython();
        if (window.showToast) window.showToast('已恢复默认设置', 'success');
    });
};
