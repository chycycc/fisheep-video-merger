/**
 * settings.js — 设置与配置模块
 * 负责设置面板初始化、硬件加速/平台统计加载、配置导出导入、Profile 管理、面板拖拽调整、裁剪时间轴
 */

import { callPython, handleBackendResponse, syncSettingsFromPython } from './bridge.js';
import { showToast } from './ui.js';

/**
 * 监听配置面板中表单控件的值变化并更新到 Python
 */
export function initSettingsListeners() {
    const filenameInput = document.getElementById('global-output-name');
    if (filenameInput) {
        filenameInput.addEventListener('input', () => {
            if (window.updatePathPreview) window.updatePathPreview();
        });
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
                const index = parseInt(activeRows[0].id.replace('queue-row-', ''), 10);
                if (tasks[index]) singleSelectIndex = index;
            } else if (checkedBoxes.length === 1) {
                const index = parseInt(checkedBoxes[0].getAttribute('data-index'), 10);
                if (tasks[index]) singleSelectIndex = index;
            }
            if (singleSelectIndex !== -1 && newName) {
                callPython('rename_task', singleSelectIndex, newName).then(res => {
                    handleBackendResponse(res);
                    showToast('已更新输出文件名', 'success');
                });
            }
        });
    }

    const tplInput = document.getElementById('global-output-name');
    if (tplInput) {
        tplInput.addEventListener('change', (e) => {
            callPython('update_setting', 'naming_template', e.target.value.trim());
        });
    }

    const dirTplInput = document.getElementById('global-output-dir-template');
    if (dirTplInput) {
        dirTplInput.addEventListener('change', (e) => {
            callPython('update_setting', 'output_dir_template', e.target.value.trim());
        });
    }

    const depthSelect = document.getElementById('global-path-depth');
    if (depthSelect) {
        depthSelect.addEventListener('change', (e) => {
            callPython('update_setting', 'path_depth', parseInt(e.target.value, 10));
        });
    }

    document.querySelectorAll('.format-cb').forEach(cb => {
        cb.addEventListener('change', () => {
            const enabled = Array.from(document.querySelectorAll('.format-cb:checked')).map(c => c.dataset.ext);
            callPython('update_setting', 'enabled_formats', enabled);
        });
    });
}

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

export function loadPlatformStats() {
    callPython('get_platform_stats').then(res => {
        const el = document.getElementById('platform-stats');
        if (!el || !res || res.status !== 'success') return;
        const s = res.stats;
        el.innerHTML = `共 <strong>${res.total}</strong> 个文件 · B站: ${s['B站']} · YouTube: ${s['YouTube']} · 通用: ${s['通用']}`;
    });
}

export function exportConfig() {
    callPython('export_config_file').then(res => {
        if (res && res.status === 'success') {
            showToast(`配置已导出到 ${res.path}`, 'success');
        } else if (res && res.status !== 'cancelled') {
            showToast(`导出失败: ${res?.message || '未知错误'}`, 'error');
        }
    });
}

export function importConfig() {
    callPython('import_config_file').then(res => {
        if (res && res.status === 'success') {
            showToast(`已导入 ${res.imported} 个任务`, 'success');
            callPython('get_current_state').then(state => handleBackendResponse(state));
        } else if (res && res.status !== 'cancelled') {
            showToast(`导入失败: ${res?.message || '未知错误'}`, 'error');
        }
    });
}

export function selectOutputDir() {
    callPython('select_output_dir_dialog').then(res => {
        if (res && res.output_dir) {
            Alpine.store('settings').outputDir = res.output_dir;
            showToast(`输出目录已设置为: ${res.output_dir}`, 'success');
            callPython('get_current_state').then(state => handleBackendResponse(state));
        }
    });
}

export function initSettingsPanel() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_current_settings().then(settings => {
            if (!settings) return;
            const themeSelect = document.getElementById('settings-theme');
            if (themeSelect) themeSelect.value = settings.theme || 'auto';
        });
    }

    const themeSelect = document.getElementById('settings-theme');
    if (themeSelect) {
        themeSelect.addEventListener('change', (e) => {
            if (window.setAppTheme) window.setAppTheme(e.target.value);
            if (window.pywebview && window.pywebview.api) callPython('update_theme', e.target.value);
        });
    }
}

export function selectSettingsOutputDir() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_output_dir_dialog().then(res => {
            if (res && res.output_dir) callPython('update_setting', 'output_dir', res.output_dir);
        });
    }
}

export function selectToolOutputDir(tool) {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_output_dir_dialog().then(res => {
            if (res && res.output_dir) {
                const input = document.getElementById(`${tool}-output-dir`);
                if (input) input.value = res.output_dir;
                callPython('update_tool_output_dir', tool, res.output_dir);
            }
        });
    }
}

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
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.preset === preset);
    });
}

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
        for (const tool in settings.tool_settings) {
            if (store.toolSettings[tool]) {
                store.toolSettings[tool] = { ...store.toolSettings[tool], ...settings.tool_settings[tool] };
            }
        }
    }
}

export function exportProfile() {
    const currentSettings = gatherCurrentSettings();
    callPython('update_settings', currentSettings).then(() => {
        callPython('export_profile_file').then(res => {
            if (res && res.status === 'success') showToast('配置模板导出成功！', 'success');
            else if (res && res.status === 'error') showToast(res.message, 'warning');
        });
    });
}

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

// =====================================================
// 面板拖拽调整
// =====================================================

export function startConfigResize(e) {
    e.preventDefault();
    const startX = e.clientX;
    const store = Alpine.store('app');
    const startWidth = store.configWidth;
    document.body.classList.add('is-resizing');

    function onMouseMove(moveEvent) {
        const delta = startX - moveEvent.clientX;
        let newWidth = startWidth + delta;
        if (newWidth < 200) {
            store.configPanelCollapsed = true;
            newWidth = 320;
            cleanup();
        } else {
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

export function startSidebarResize(e) {
    e.preventDefault();
    const startX = e.clientX;
    const store = Alpine.store('app');
    const startWidth = store.sidebarCollapsed ? 72 : store.sidebarWidth;
    let hasMoved = false;

    function onMouseMove(moveEvent) {
        const delta = moveEvent.clientX - startX;
        if (!hasMoved && Math.abs(delta) > 3) {
            hasMoved = true;
            store.sidebarCollapsed = false;
            document.body.classList.add('is-resizing');
        }
        if (hasMoved) {
            let newWidth = startWidth + delta;
            store.sidebarWidth = Math.max(72, Math.min(400, newWidth));
        }
    }

    function cleanup() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', cleanup);
        if (hasMoved) {
            document.body.style.cursor = '';
            document.body.classList.remove('is-resizing');
            if (store.sidebarWidth < 150) {
                store.sidebarCollapsed = true;
                store.sidebarWidth = 240;
            } else if (store.sidebarWidth < 200) {
                store.sidebarWidth = 200;
            }
        }
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', cleanup);
    document.body.style.cursor = 'col-resize';
}

// =====================================================
// 视频裁剪时间轴滑块
// =====================================================

let trimDuration = 0;
let trimStartSec = 0;
let trimEndSec = 0;

export function initTrimTimeline() {
    const handleStart = document.getElementById('trim-handle-start');
    const handleEnd = document.getElementById('trim-handle-end');
    const track = document.querySelector('.trim-track');
    if (!handleStart || !handleEnd || !track) return;

    let dragging = null;

    function getPercent(e) {
        const rect = track.getBoundingClientRect();
        return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
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
        if (dragging === 'start') trimStartSec = Math.min(sec, trimEndSec - 1);
        else trimEndSec = Math.max(sec, trimStartSec + 1);
        updateVisual();
    }

    function onUp() {
        dragging = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
    }

    handleStart.addEventListener('mousedown', (e) => { e.preventDefault(); dragging = 'start'; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); });
    handleEnd.addEventListener('mousedown', (e) => { e.preventDefault(); dragging = 'end'; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); });

    track.addEventListener('click', (e) => {
        if (e.target.classList.contains('trim-handle')) return;
        const pct = getPercent(e);
        const sec = pct * trimDuration;
        if (Math.abs(sec - trimStartSec) < Math.abs(sec - trimEndSec)) trimStartSec = Math.min(sec, trimEndSec - 1);
        else trimEndSec = Math.max(sec, trimStartSec + 1);
        updateVisual();
    });

    document.getElementById('trim-start').addEventListener('change', (e) => { trimStartSec = Math.min(timeToSec(e.target.value), trimEndSec - 1); updateVisual(); });
    document.getElementById('trim-end').addEventListener('change', (e) => { trimEndSec = Math.max(timeToSec(e.target.value), trimStartSec + 1); updateVisual(); });

    window.setTrimDuration = function(duration) {
        trimDuration = Number(duration) || 0;
        trimStartSec = 0;
        trimEndSec = trimDuration;
        const hint = document.getElementById('trim-duration-hint');
        if (hint && trimDuration > 0) {
            const h = Math.floor(trimDuration / 3600);
            const m = Math.floor((trimDuration % 3600) / 60);
            const s = Math.floor(trimDuration % 60);
            hint.textContent = `(总时长: ${h}h ${m}m ${s}s)`;
        }
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
        }
    };

    window.resetTrimTimeline = function() {
        trimDuration = 0; trimStartSec = 0; trimEndSec = 0;
        const hint = document.getElementById('trim-duration-hint');
        if (hint) hint.textContent = '';
        const hs = document.getElementById('trim-handle-start');
        const he = document.getElementById('trim-handle-end');
        const sel = document.getElementById('trim-selected');
        if (hs) hs.style.left = '0%';
        if (he) he.style.left = '100%';
        if (sel) { sel.style.left = '0%'; sel.style.width = '100%'; }
        document.getElementById('trim-label-start').textContent = '00:00:00';
        document.getElementById('trim-label-end').textContent = '00:00:00';
        document.getElementById('trim-start').value = '00:00:00';
        document.getElementById('trim-end').value = '';
    };

    window.resetTrimTimeline();
}

// =====================================================
// 恢复默认设置
// =====================================================

window.restoreDefaults = function() {
    if (!confirm('确定要恢复所有设置为默认值吗？')) return;
    callPython('update_settings', {
        output_format: 'mp4', concurrency: 2, overwrite: true, delete_allowed: false,
        output_dir: '', naming_template: '', theme: 'auto',
        tool_settings: {
            convert: { format: 'mp4', mode: 'copy' },
            extract: { format: 'aac', bitrate: '192k', bitrateMode: 'cbr', channels: 'original', sampleRate: 'original', volume: '1.0' },
            compress: { preset: 'balanced', resolution: 'original' },
            trim: { mode: 'copy' }
        }
    }).then(() => {
        syncSettingsFromPython();
        if (window.showToast) window.showToast('已恢复默认设置', 'success');
    });
};
