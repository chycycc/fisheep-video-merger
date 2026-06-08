/**
 * main.js — 应用入口文件
 * 负责导入模块、注册 Alpine Store、初始化全局事件、绑定 window 全局函数
 */

// =====================================================
// 模块导入
// =====================================================

import { Converter } from './tools/converter.js';
import { Extractor } from './tools/extractor.js';
import { Compressor } from './tools/compressor.js';
import { Trimmer } from './tools/trimmer.js';
import { Subtitle } from './tools/subtitle.js';

import { registerComponents } from './store.js';

import {
    callPython,
    handleBackendResponse,
    syncSettingsFromPython
} from './bridge.js';

import {
    showToast,
    showToastWithAction,
    initTheme,
    notifyPythonTheme,
    initSidebarToggle,
    initContextMenu,
    bindRowSelectionListeners,
    showCustomTooltip,
    hideCustomTooltip,
    toggleContextMenu,
    copyText,
    jsCopyFallback
} from './ui.js';

import {
    toggleConfigPanel,
    selectQueueRow,
    loadPreviewForFile,
    hideVideoPreview,
    loadVideoPreview,
    editOutputName,
    updatePathPreview,
    updateTaskProgress,
    updateTaskStatus,
    updateMergeStatusBar,
    initDashboardCards,
    toggleSelectAll,
    toggleSelectAllLocal,
    batchDeleteSelected,
    batchRetryFailed,
    onTaskDragStart,
    onTaskDragOver,
    onTaskDrop,
    deleteTask,
    resetTaskStatus,
    cancelMerging,
    showBatchRenameDialog,
    deletePendingFile,
    manualMatchPending,
    closeManualMatchModal,
    confirmManualMatch,
    autoMatchPending,
    deleteMuxedFile,
    playVideo,
    openFileFolder,
    selectOutputDir
} from './merger.js';

import {
    initSettingsListeners,
    loadHwAccelInfo,
    loadPlatformStats,
    exportConfig,
    importConfig,
    initSettingsPanel,
    selectSettingsOutputDir,
    selectToolOutputDir,
    applyExtractPreset,
    gatherCurrentSettings,
    applyLoadedSettings,
    exportProfile,
    importProfile,
    startConfigResize,
    startSidebarResize,
    updateToolProgress,
    initToolDropZones,
    initToolStartButtons,
    initTrimTimeline,
    selectFilesForTool,
    openToolFile,
    openToolFileFolder,
    removeToolFile,
    runToolTask
} from './settings.js';

// =====================================================
// 工具路由启动
// =====================================================

window.startToolTask = function(tool) {
    if (tool === 'convert') Converter.start();
    else if (tool === 'extract') Extractor.start();
    else if (tool === 'compress') Compressor.start();
    else if (tool === 'trim') Trimmer.start();
    else if (tool === 'subtitle') Subtitle.start();
    else if (tool === 'merge') {
        const globalStartBtn = document.getElementById('global-start-btn');
        if (globalStartBtn) globalStartBtn.click();
    }
};

// =====================================================
// Alpine.js 响应式状态注册
// =====================================================

registerComponents();

document.addEventListener('alpine:init', () => {
    Alpine.store('app', {
        tasks: [],
        pending: [],
        muxed: [],
        selectedTaskIndex: -1,
        currentTool: 'merge',
        subtab: 'merge-queue',
        sidebarCollapsed: false,
        configPanelCollapsed: false,
        openAccordion: 'base',
        settingsExpanded: true,
        theme: localStorage.getItem('theme') || 'dark',
        configWidth: 320,
        sidebarWidth: 240,
        getTasksForTool(tool) {
            return window.toolFiles ? (window.toolFiles[tool] || []) : [];
        },
    });

    Alpine.store('settings', {
        outputFormat: 'mp4',
        concurrency: 2,
        overwrite: true,
        deleteSource: false,
        outputDir: '',
        // 工具输出目录
        toolOutputDirs: { convert: '', extract: '', compress: '', trim: '', subtitle: '' },
        // 工具设置
        toolSettings: {
            convert: { format: 'mp4', mode: 'copy', crf: '23', outputName: '' },
            extract: { format: 'mp3', volume: '1.0', bitrate: '192k', bitrateMode: 'cbr', channels: 'original', sampleRate: 'original', outputName: '' },
            compress: { mode: 'crf', targetSize: '50', preset: 'balanced', resolution: '1080p', outputName: '' },
            trim: { start: '00:00:00', end: '', mode: 'recode', accurate: false, outputName: '' },
            subtitle: { operation: 'adjust', offsetMs: 0, layout: 'top_bottom', outputName: '' }
        }
    });
});

// =====================================================
// 工具路由切换 (Hash Router)
// =====================================================

function initTabs() {
    // 子标签切换已由 Alpine 声明式绑定控制，无需手动 addEventListener

    // Hash 路由：根据 URL hash 切换工具（使用 Alpine.store）
    function navigateFromHash() {
        const hash = window.location.hash.replace('#', '') || 'merge';
        const validTools = ['merge', 'convert', 'extract', 'compress', 'trim', 'settings'];
        if (validTools.includes(hash)) {
            Alpine.store('app').currentTool = hash;
        }
    }

    window.addEventListener('hashchange', navigateFromHash);
    // 首次加载时根据 hash 切换
    navigateFromHash();
}

// =====================================================
// 高性能 Drag & Drop 捕获 (OS 级文件拖拽)
// =====================================================

function initDragAndDrop() {
    const dropOverlay = document.getElementById('drop-overlay');
    let dragCounter = 0;

    window.addEventListener('dragenter', (e) => {
        e.preventDefault();
        // 只在合并工具激活时显示全局拖拽蒙层
        const mergePanel = document.getElementById('tool-merge');
        if (!mergePanel || !mergePanel.classList.contains('active')) return;

        dragCounter++;
        if (dragCounter === 1) {
            dropOverlay.classList.remove('hidden');
        }
    });

    window.addEventListener('dragover', (e) => {
        // 阻止浏览器默认打开文件行为
        e.preventDefault();
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        const mergePanel = document.getElementById('tool-merge');
        if (!mergePanel || !mergePanel.classList.contains('active')) return;

        dragCounter--;
        if (dragCounter === 0) {
            dropOverlay.classList.add('hidden');
        }
    });

    window.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dropOverlay.classList.add('hidden');

        // 清除所有工具面板的拖拽状态
        document.querySelectorAll('.tool-panel.drag-over').forEach(p => p.classList.remove('drag-over'));

        // 如果当前不是合并工具，让工具面板自己的 handler 处理
        const mergePanel = document.getElementById('tool-merge');
        if (!mergePanel || !mergePanel.classList.contains('active')) return;

        const files = e.dataTransfer.files;
        if (files.length === 0) return;

        const filePaths = Array.from(files).map(file => file.path || file.name);

        showToast(`已捕获 ${files.length} 个项目，正在提交后端进行依赖扫描与匹配...`, 'info');

        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.on_files_dropped(filePaths)
                .then(response => {
                    handleBackendResponse(response);
                })
                .catch(err => {
                    showToast(`扫描失败: ${err}`, 'error');
                });
        } else {
            console.log('拖入的文件路径:', filePaths);
            showToast('当前非桌面客户端环境，已在控制台输出测试路径', 'warning');
        }
    });
}

// =====================================================
// 双线渲染支持与跨端 Bridge 检测 + 按钮事件绑定
// =====================================================

function initMockOrBridge() {
    // 监听 Python Bridge 初始化就绪事件
    window.addEventListener('pywebviewready', () => {
        showToast('🚀 客户端通信总线连接成功！', 'success');
        // 使用 setTimeout 延迟 150ms 调用 Python 接口，防止在 WebView2 初始化完成瞬间同步阻塞导致死锁挂起
        setTimeout(() => {
            syncSettingsFromPython();
            callPython('get_current_state').then(res => {
                handleBackendResponse(res);
            });
        }, 150);
    });

    // 绑定常规操作按钮到 Python 端
    document.getElementById('add-folder-btn').addEventListener('click', () => {
        callPython('select_folder_dialog').then(res => {
            if (res && res.status === 'success' && res.folders && res.folders.length > 0) {
                callPython('add_folder', res.folders[0]).then(state => handleBackendResponse(state));
            }
        });
    });

    document.getElementById('add-files-btn').addEventListener('click', () => {
        callPython('select_files_dialog').then(res => {
            if (res && res.status === 'success' && res.files && res.files.length > 0) {
                callPython('on_files_dropped', res.files).then(state => handleBackendResponse(state));
            }
        });
    });

    // select-output-btn 已由 Alpine @click 绑定到 selectOutputDir() 函数

    document.getElementById('clear-btn').addEventListener('click', () => {
        callPython('clear_queue').then(res => {
            showToast('队列已清空', 'info');
            handleBackendResponse(res);
        });
    });

    const globalStartBtn = document.getElementById('global-start-btn');
    if (globalStartBtn) {
        globalStartBtn.addEventListener('click', () => {
            const tool = Alpine.store('app').currentTool;
            const outputDir = document.getElementById('global-output-dir-template')?.value || '';
            const outputName = document.getElementById('global-output-name')?.value?.trim() || '';

            if (tool === 'merge') {
                let settings = {
                    output_name_template: outputName,
                    output_dir_template: outputDir,
                    path_depth: parseInt(document.getElementById('global-path-depth')?.value || '0', 10),
                    overwrite: Alpine.store('settings').overwrite,
                    delete_source: Alpine.store('settings').deleteSource,
                    output_format: Alpine.store('settings').outputFormat,
                    concurrency: Alpine.store('settings').concurrency
                };
                callPython('start_merging', 'merge', settings).then(res => {
                    if (res && res.status === 'error') {
                        showToast(res.message, 'warning');
                    } else {
                        showToast('后台合并任务已拉起！', 'success');
                    }
                }).catch(err => {
                    showToast('启动合并任务失败', 'error');
                });
            } else {
                const checkedCount = document.querySelectorAll(`#${tool}-tbody .tool-row-cb:checked`).length;
                const selCount = checkedCount || window.toolFiles[tool].length;
                const nameForBatch = selCount === 1 ? outputName : '';

                if (window.toolFiles[tool].length === 0) {
                    showToast('当前队列中没有文件', 'warning');
                    return;
                }

                if (tool === 'convert') {
                    const format = document.getElementById('convert-format')?.value || 'mp4';
                    const mode = document.getElementById('convert-mode')?.value || 'copy';
                    runToolTask('convert', (file) => {
                        return window.pywebview.api.convert_file(file.filepath, format, mode, outputDir, nameForBatch);
                    });
                } else if (tool === 'extract') {
                    const format = document.getElementById('extract-format')?.value || 'mp3';
                    const volume = document.getElementById('extract-volume')?.value || 'original';
                    runToolTask('extract', (file) => {
                        return window.pywebview.api.extract_audio_api(
                            file.filepath, format, '192k', outputDir, nameForBatch,
                            'original', 'original', 1.0, 'cbr'
                        );
                    });
                } else if (tool === 'compress') {
                    const mode = document.getElementById('compress-mode')?.value || 'crf';
                    const targetSize = document.getElementById('compress-target-size')?.value || '50';
                    const preset = mode === 'twopass' ? `target:${targetSize}` : 'balanced';
                    runToolTask('compress', (file) => {
                        return window.pywebview.api.compress_video_api(file.filepath, preset, '1080p', outputDir, nameForBatch);
                    });
                } else if (tool === 'trim') {
                    const start = document.getElementById('trim-start')?.value || '00:00:00';
                    const end = document.getElementById('trim-end')?.value || '';
                    const accurate = document.getElementById('trim-accurate-mode')?.checked ? 'accurate' : 'fast';
                    runToolTask('trim', (file) => {
                        return window.pywebview.api.trim_video_api(file.filepath, start, end, accurate, outputDir, nameForBatch);
                    });
                }
            }
        });
    }
}

// =====================================================
// DOMContentLoaded — 主初始化入口
// =====================================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initSidebarToggle();
    initTabs();
    initDragAndDrop();
    initMockOrBridge();
    initSettingsListeners();
    initContextMenu();
    bindRowSelectionListeners();
    initToolDropZones();
    initToolStartButtons();
    initTrimTimeline();
    initSettingsPanel();

    // 快捷键
    document.addEventListener('keydown', (e) => {
        // Ctrl+O: 导入文件
        if (e.ctrlKey && e.key === 'o') {
            e.preventDefault();
            const addFilesBtn = document.getElementById('add-files-btn');
            if (addFilesBtn) addFilesBtn.click();
        }
        // Delete: 删除选中任务
        if (e.key === 'Delete' && !e.target.matches('input, textarea, select')) {
            e.preventDefault();
            window.batchDeleteSelected();
        }
        // Escape: 关闭配置面板
        if (e.key === 'Escape') {
            Alpine.store('app').configPanelCollapsed = true;
        }
    });
});

// =====================================================
// window 全局绑定（供 Alpine.js 模板和 HTML onclick 使用）
// =====================================================

window.callPython = callPython;
window.handleBackendResponse = handleBackendResponse;
window.showToast = showToast;
window.showCustomTooltip = showCustomTooltip;
window.hideCustomTooltip = hideCustomTooltip;

// bridge.js
window.syncSettingsFromPython = syncSettingsFromPython;

// ui.js
window.toggleContextMenu = toggleContextMenu;

// merger.js
window.toggleConfigPanel = toggleConfigPanel;
window.selectQueueRow = selectQueueRow;
window.loadPreviewForFile = loadPreviewForFile;
window.hideVideoPreview = hideVideoPreview;
window.loadVideoPreview = loadVideoPreview;
window.editOutputName = editOutputName;
window.updatePathPreview = updatePathPreview;
window.updateTaskProgress = updateTaskProgress;
window.updateTaskStatus = updateTaskStatus;
window.updateMergeStatusBar = updateMergeStatusBar;
window.initDashboardCards = initDashboardCards;
window.toggleSelectAll = toggleSelectAll;
window.toggleSelectAllLocal = toggleSelectAllLocal;
window.batchDeleteSelected = batchDeleteSelected;
window.batchRetryFailed = batchRetryFailed;
window.onTaskDragStart = onTaskDragStart;
window.onTaskDragOver = onTaskDragOver;
window.onTaskDrop = onTaskDrop;
window.deleteTask = deleteTask;
window.resetTaskStatus = resetTaskStatus;
window.cancelMerging = cancelMerging;
window.showBatchRenameDialog = showBatchRenameDialog;
window.deletePendingFile = deletePendingFile;
window.manualMatchPending = manualMatchPending;
window.closeManualMatchModal = closeManualMatchModal;
window.confirmManualMatch = confirmManualMatch;
window.autoMatchPending = autoMatchPending;
window.deleteMuxedFile = deleteMuxedFile;
window.playVideo = playVideo;
window.openFileFolder = openFileFolder;
window.selectOutputDir = selectOutputDir;

// settings.js
window.loadHwAccelInfo = loadHwAccelInfo;
window.loadPlatformStats = loadPlatformStats;
window.exportConfig = exportConfig;
window.importConfig = importConfig;
window.selectSettingsOutputDir = selectSettingsOutputDir;
window.selectToolOutputDir = selectToolOutputDir;
window.applyExtractPreset = applyExtractPreset;
window.exportProfile = exportProfile;
window.importProfile = importProfile;
window.startConfigResize = startConfigResize;
window.startSidebarResize = startSidebarResize;
window.updateToolProgress = updateToolProgress;
window.selectFilesForTool = selectFilesForTool;
window.openToolFile = openToolFile;
window.openToolFileFolder = openToolFileFolder;
window.removeToolFile = removeToolFile;
window.runToolTask = runToolTask;
