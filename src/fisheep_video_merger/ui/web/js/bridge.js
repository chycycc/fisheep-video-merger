/**
 * bridge.js — Python Bridge 封装模块
 * 负责 pywebview 通信就绪检测、安全调用 Python 接口、同步设置与状态响应
 */

// pywebview 就绪 Promise，保证调用时机正确
export let pywebviewReadyPromise = new Promise((resolve) => {
    if (window.pywebview) {
        resolve();
    } else {
        window.addEventListener('pywebviewready', () => resolve());
        // 500ms 后如果没有触发事件，当作是在普通浏览器环境打开（Mock 模式）
        setTimeout(() => resolve(), 500);
    }
});

/**
 * 安全调用 Python 接口，自动等待 pywebview 就绪
 * @param {string} methodName - Python API 方法名
 * @param  {...any} args - 传递给方法的参数
 * @returns {Promise}
 */
export function callPython(methodName, ...args) {
    return pywebviewReadyPromise.then(() => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api[methodName]) {
            return window.pywebview.api[methodName](...args)
                .catch(err => {
                    if (window.showToast) window.showToast(`接口错误: ${err}`, 'error');
                    throw err;
                });
        } else {
            console.warn(`[Mock] 模拟调用 Python 接口: ${methodName}`, args);
            return { status: 'mock' };
        }
    });
}

/**
 * 接收扫描与工作空间状态结果，同步填充三个数据面板
 * @param {object} res - 后端返回的状态对象
 */
export function handleBackendResponse(res) {
    if (!res) return;

    // 同步到 Alpine.store（响应式）
    const store = Alpine.store('app');

    if (res.tasks) {
        store.tasks = res.tasks;
    }

    if (res.pending) {
        store.pending = res.pending;
    }

    if (res.muxed) {
        store.muxed = res.muxed;
    }
}

/**
 * 刷新同步设置参数，从 Python 获取当前设置并更新 UI
 */
export function syncSettingsFromPython() {
    callPython('get_current_settings').then(settings => {
        if (settings) {
            const store = Alpine.store('settings');
            store.outputDir = settings.output_dir || '';
            store.outputFormat = settings.output_format || 'mp4';
            store.concurrency = settings.concurrency || 2;
            store.overwrite = !!settings.overwrite;
            store.deleteSource = !!settings.delete_allowed;

            // 同步命名模板
            const tplInput = document.getElementById('global-output-name');
            if (tplInput) tplInput.value = settings.naming_template || '';

            // 同步输出目录模板
            const dirTplInput = document.getElementById('global-output-dir-template');
            if (dirTplInput) dirTplInput.value = settings.output_dir_template || '';

            // 同步路径层级
            const depthSelect = document.getElementById('global-path-depth');
            if (depthSelect) depthSelect.value = String(settings.path_depth || 0);

            // 同步工具输出目录
            if (settings.tool_output_dirs) {
                Object.assign(store.toolOutputDirs, settings.tool_output_dirs);
                ['convert', 'extract', 'compress', 'trim'].forEach(tool => {
                    const el = document.getElementById(`${tool}-output-dir`);
                    if (el && store.toolOutputDirs[tool]) el.value = store.toolOutputDirs[tool];
                });
            }

            // 同步工具设置
            if (settings.tool_settings) {
                Object.assign(store.toolSettings, settings.tool_settings);
                // 恢复到 DOM 元素
                const ts = settings.tool_settings;
                if (ts.convert) {
                    const fmt = document.getElementById('convert-format');
                    const mode = document.getElementById('convert-mode');
                    if (fmt) fmt.value = ts.convert.format || 'mp4';
                    if (mode) mode.value = ts.convert.mode || 'copy';
                }
                if (ts.extract) {
                    const fmt = document.getElementById('extract-format');
                    const br = document.getElementById('extract-bitrate');
                    if (fmt) fmt.value = ts.extract.format || 'aac';
                    if (br) br.value = ts.extract.bitrate || '192k';
                }
                if (ts.compress) {
                    const pre = document.getElementById('compress-preset');
                    const res = document.getElementById('compress-resolution');
                    if (pre) pre.value = ts.compress.preset || 'medium';
                    if (res) res.value = ts.compress.resolution || '720p';
                }
                if (ts.trim) {
                    const mode = document.getElementById('trim-mode');
                    if (mode) mode.value = ts.trim.mode || 'reencode';
                }
            }

            // 加载平台统计和硬件加速信息
            if (window.loadPlatformStats) window.loadPlatformStats();
            if (window.loadHwAccelInfo) window.loadHwAccelInfo();

            // 同步格式配置
            if (settings.enabled_formats) {
                document.querySelectorAll('.format-cb').forEach(cb => {
                    cb.checked = settings.enabled_formats.includes(cb.dataset.ext);
                });
            }

            // 同步应用从后端载入的界面主题
            if (settings.theme && window.setAppTheme) {
                window.setAppTheme(settings.theme);
            }
        }
    });
}
