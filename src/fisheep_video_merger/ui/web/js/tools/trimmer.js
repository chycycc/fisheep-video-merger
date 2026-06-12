export const Trimmer = {
    start: () => {
        const tool = 'trim';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const trimSettings = Alpine.store('settings').toolSettings.trim;
        const start = trimSettings.start;
        const end = trimSettings.end;
        const mode = trimSettings.mode;
        const audioMode = trimSettings.audioMode || 'keep';
        const keepAudio = audioMode !== 'remove';
        const keepVideo = audioMode !== 'only';
        const outputFormat = trimSettings.outputFormat || '';

        if (!end) {
            window.showToast('请填写结束时间', 'warning');
            return;
        }

        const outputDir = document.getElementById('trim-output-dir')?.value || '';
        const outputName = (trimSettings.outputName || '').trim();

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.trim_video_api(file.filepath, start, end, mode, outputDir, nameForBatch, keepAudio, keepVideo, outputFormat);
        });
    }
};
