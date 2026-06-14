/**
 * tool-runner.js — 工具任务执行模块
 * 负责工具进度更新、文件选择、任务执行（并发池）、按钮初始化
 */

import { showToast } from './ui.js';

// 引用 tool-files 的共享状态和渲染函数
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
 * 获取选中的文件（带复选框的行）
 */
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

/**
 * 运行工具任务（并发池模式）
 */
export function runToolTask(tool, taskFn) {
    const selectedFiles = getSelectedFiles(tool);
    if (selectedFiles.length === 0) { showToast('请先添加文件', 'warning'); return; }
    if (!window.pywebview || !window.pywebview.api) { showToast('请在桌面客户端中使用此功能', 'warning'); return; }

    const btn = document.getElementById(`${tool}-start-btn`);
    if (btn) { btn.disabled = true; btn.textContent = '⏳ 处理中...'; }

    let completed = 0, failed = 0;
    const concurrency = Alpine.store('settings').concurrency || 2;

    selectedFiles.forEach(file => { file._status = 'waiting'; });
    window.renderToolTable(tool);

    async function processFile(file) {
        file._status = 'processing';
        window.renderToolTable(tool);
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
        window.renderToolTable(tool);
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
            window.renderConvertResult(tool);
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
