export const Extractor = {
    start: () => {
        const tool = 'extract';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const format = Alpine.store('settings').toolSettings.extract.format;
        const volume = Alpine.store('settings').toolSettings.extract.volume;
        const bitrate = Alpine.store('settings').toolSettings.extract.bitrate;
        const bitrateMode = Alpine.store('settings').toolSettings.extract.bitrateMode;
        const channels = Alpine.store('settings').toolSettings.extract.channels;
        const sampleRate = Alpine.store('settings').toolSettings.extract.sampleRate;
        const volumeFloat = parseFloat(volume === 'original' ? '1.0' : volume);

        const outputDir = document.getElementById('extract-output-dir')?.value || '';
        const outputName = (Alpine.store('settings').toolSettings.extract.outputName || '').trim();
        
        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.extract_audio_api(
                file.filepath, format, bitrate, outputDir, nameForBatch,
                channels, sampleRate, volumeFloat, bitrateMode
            );
        });
    }
};
