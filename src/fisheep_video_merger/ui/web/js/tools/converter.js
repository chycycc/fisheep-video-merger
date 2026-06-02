export const Converter = {
    start: () => {
        const tool = 'convert';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const format = Alpine.store('settings').toolSettings.convert.format;
        const mode = Alpine.store('settings').toolSettings.convert.mode;
        const outputDir = document.getElementById('convert-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.convert.outputName.trim();
        
        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.convert_file(file.filepath, format, mode, outputDir, nameForBatch);
        });
    }
};
