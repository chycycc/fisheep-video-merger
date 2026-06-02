export const Trimmer = {
    start: () => {
        const tool = 'trim';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const start = Alpine.store('settings').toolSettings.trim.start;
        const end = Alpine.store('settings').toolSettings.trim.end;
        const mode = Alpine.store('settings').toolSettings.trim.mode;
        
        if (!end) {
            window.showToast('请填写结束时间', 'warning');
            return;
        }

        const outputDir = document.getElementById('trim-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.trim.outputName.trim();
        
        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.trim_video_api(file.filepath, start, end, mode, outputDir, nameForBatch);
        });
    }
};
