export const Compressor = {
    start: () => {
        const tool = 'compress';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const mode = Alpine.store('settings').toolSettings.compress.mode;
        const targetSize = Alpine.store('settings').toolSettings.compress.targetSize;
        const resolution = Alpine.store('settings').toolSettings.compress.resolution;
        const preset = mode === 'twopass' ? `target:${targetSize}` : Alpine.store('settings').toolSettings.compress.preset;

        const outputDir = document.getElementById('compress-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.compress.outputName.trim();
        
        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.compress_video_api(file.filepath, preset, resolution, outputDir, nameForBatch);
        });
    }
};
