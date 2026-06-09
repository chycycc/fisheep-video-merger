/**
 * 音频裁剪工具前端模块
 */
export const AudioTrimmer = {
    start: () => {
        const tool = 'audio-trim';
        if (!window.toolFiles || !window.toolFiles[tool] || window.toolFiles[tool].length === 0) {
            window.showToast('当前队列中没有文件', 'warning');
            return;
        }

        const trimSettings = Alpine.store('settings').toolSettings.audioTrim;
        const start = trimSettings.start || '00:00:00';
        const end = trimSettings.end || '';
        const mode = trimSettings.mode || 'fast';
        const outputFormat = trimSettings.outputFormat || '';
        const bitrate = trimSettings.bitrate || '192k';

        if (!end) {
            window.showToast('请填写结束时间', 'warning');
            return;
        }

        const outputDir = document.getElementById('audio-trim-output-dir')?.value || '';
        const outputName = trimSettings.outputName.trim();

        const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
        const selCount = checkedCount || window.toolFiles[tool].length;
        const nameForBatch = selCount === 1 ? outputName : '';

        window.runToolTask(tool, (file) => {
            return window.pywebview.api.trim_audio_api(
                file.filepath, start, end, mode, outputDir, nameForBatch,
                outputFormat, bitrate
            );
        });
    }
};
