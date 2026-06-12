export const Compressor = {
    start: () => {
        const tool = 'compress';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const settings = Alpine.store('settings').toolSettings.compress;
        const mode = settings.mode;
        const targetSize = settings.targetSize;
        const targetBitrate = settings.targetBitrate?.trim() || '';
        const resolution = settings.resolution;
        const preset = mode === 'twopass' ? `target:${targetSize}` : settings.preset;
        const crf = settings.crf?.trim() || '';
        const audioCodec = settings.audioCodec || 'copy';
        const audioBitrate = settings.audioBitrate || '128k';
        const audioCopy = audioCodec === 'copy';

        const outputDir = document.getElementById('compress-output-dir')?.value || '';
        const outputName = (settings.outputName || '').trim();

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.compress_video_api(
                file.filepath, preset, resolution, outputDir, nameForBatch,
                targetSize || null, targetBitrate || null,
                crf || null, audioCodec, audioBitrate, audioCopy
            );
        });
    }
};
