export const AudioConverter = {
    start: () => {
        const tool = 'audio-convert';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const format = Alpine.store('settings').toolSettings.audioConvert.format;
        const bitrate = Alpine.store('settings').toolSettings.audioConvert.bitrate;
        const bitrateMode = Alpine.store('settings').toolSettings.audioConvert.bitrateMode;
        const channels = Alpine.store('settings').toolSettings.audioConvert.channels;
        const sampleRate = Alpine.store('settings').toolSettings.audioConvert.sampleRate;
        const volume = Alpine.store('settings').toolSettings.audioConvert.volume;
        const volumeFloat = parseFloat(volume === 'original' ? '1.0' : volume);

        const outputDir = document.getElementById('audio-convert-output-dir')?.value || '';
        const outputName = Alpine.store('settings').toolSettings.audioConvert.outputName.trim();

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.convert_audio_api(
                file.filepath, format, bitrate, outputDir, nameForBatch,
                channels, sampleRate, volumeFloat, bitrateMode
            );
        });
    }
};
