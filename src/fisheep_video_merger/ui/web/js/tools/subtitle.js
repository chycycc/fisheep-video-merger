export const Subtitle = {
    start: () => {
        const tool = 'subtitle';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const operation = Alpine.store('settings').toolSettings.subtitle.operation;
        const outputDir = document.getElementById('subtitle-adjust-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.subtitle.outputName?.trim() || '';

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            switch (operation) {
                case 'adjust': {
                    const offsetMs = parseFloat(document.getElementById('subtitle-adjust-offset')?.value || '0') * 1000;
                    return window.pywebview.api.subtitle_adjust_api(file.filepath, offsetMs, outputDir, nameForBatch);
                }
                case 'convert': {
                    const format = document.getElementById('subtitle-convert-format')?.value || 'srt';
                    return window.pywebview.api.subtitle_convert_api(file.filepath, format, outputDir, nameForBatch);
                }
                case 'extract': {
                    const streamIndex = parseInt(document.getElementById('subtitle-extract-stream')?.value || '0');
                    const format = document.getElementById('subtitle-extract-format')?.value || 'srt';
                    return window.pywebview.api.subtitle_extract_api(file.filepath, outputDir, nameForBatch, streamIndex, format);
                }
                case 'split': {
                    const pattern = document.getElementById('subtitle-split-regex')?.value || '';
                    return window.pywebview.api.subtitle_split_api(file.filepath, outputDir, nameForBatch, pattern);
                }
                default:
                    return Promise.resolve({ status: 'error', message: '未知操作类型' });
            }
        });
    },

    // 按片段调轴（供外部调用）
    startSegments: (segments) => {
        const tool = 'subtitle';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }
        const outputDir = document.getElementById('subtitle-adjust-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.subtitle.outputName?.trim() || '';
        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.subtitle_adjust_segments_api(file.filepath, segments, outputDir, nameForBatch);
        });
    },

    startMerge: () => {
        const tool = 'subtitle';
        const fileA = document.getElementById('subtitle-merge-file-a')?.value || '';
        const fileB = document.getElementById('subtitle-merge-file-b')?.value || '';
        if (!fileA || !fileB) {
            window.showToast('请选择两个字幕文件', 'warning');
            return;
        }
        const layout = document.getElementById('subtitle-merge-layout')?.value || 'top_bottom';
        const outputDir = document.getElementById('subtitle-merge-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.subtitle.outputName?.trim() || '';

        window.pywebview.api.subtitle_merge_api(fileA, fileB, outputDir, outputName, layout).then(result => {
            if (result.status === 'success') {
                window.showToast('字幕合并完成', 'success');
            } else {
                window.showToast(result.message || '合并失败', 'error');
            }
        });
    }
};
