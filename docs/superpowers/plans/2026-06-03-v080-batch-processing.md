# v0.8.0 批量处理体系 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现批量处理能力，支持多文件夹导入、自动配对、序号命名、工具并行处理。

**Architecture:** 后端新建 `BatchProcessor` 管理批次生命周期，扩展命名模板引擎支持 `{ep:03d}`，前端新增批次分组展示面板，通过 Bridge 结构化消息通信。

**Tech Stack:** Python (core/batch.py, core/naming.py), JavaScript ES Modules (merger.js), Alpine.js, pywebview Bridge

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `core/batch.py` | 新建 | 批次数据模型、批量扫描配对 |
| `core/naming.py` | 修改 | 扩展 `{ep:03d}` 格式支持 |
| `utils/bridge.py` | 修改 | 添加 batch_import/preview/merge API |
| `ui/web/js/merger.js` | 修改 | 批次 UI 逻辑 |
| `ui/web/js/settings.js` | 修改 | 工具并行处理 |
| `ui/web/index.html` | 修改 | 批次面板 HTML |
| `ui/web/components/batch_panel.html` | 新建 | 批次分组展示组件 |

---

## Task 1: 命名模板扩展

**Files:**
- Modify: `src/fisheep_video_merger/core/naming.py`

- [ ] **Step 1: 读取现有 naming.py，理解 apply_naming_template 函数**

```bash
cat src/fisheep_video_merger/core/naming.py
```

- [ ] **Step 2: 扩展 apply_naming_template 支持 `{ep:03d}` 格式**

在 `apply_naming_template` 函数中，将 `{ep}` 替换逻辑改为支持格式化：

```python
import re

def apply_naming_template(template: str, video_filepath: str, source_dir: str, root_path: str, index: int = 0) -> str:
    """应用命名模板生成输出文件名"""
    # ... 现有逻辑 ...

    # 替换 {ep} 和 {ep:0Nd} 格式
    def replace_ep(match):
        fmt = match.group(1)
        if fmt:
            return format(index + 1, fmt)
        return str(index + 1)

    result = re.sub(r'\{ep(?::([^}]+))?\}', replace_ep, result)

    # ... 现有替换逻辑 ...
```

- [ ] **Step 3: 验证命名模板**

```bash
cd D:/dev-java/tools/fisheep-video-merger
PYTHONPATH=src python -c "
from fisheep_video_merger.core.naming import apply_naming_template
# 测试基础 {ep}
r1 = apply_naming_template('{series}_{ep}', 'test.mp4', '/dir', '/root', 0)
print(f'基础: {r1}')
# 测试 {ep:03d}
r2 = apply_naming_template('{series}_{ep:03d}', 'test.mp4', '/dir', '/root', 0)
print(f'三位: {r2}')
# 测试 {ep:02d}
r3 = apply_naming_template('{series}_{ep:02d}', 'test.mp4', '/dir', '/root', 4)
print(f'两位: {r3}')
"
```

Expected: 基础输出含 `1`，三位输出含 `001`，两位输出含 `05`

- [ ] **Step 4: 提交**

```bash
git add src/fisheep_video_merger/core/naming.py
git commit -m "feat(naming): 命名模板扩展支持 {ep:03d} 格式"
```

---

## Task 2: BatchProcessor 后端

**Files:**
- Create: `src/fisheep_video_merger/core/batch.py`

- [ ] **Step 1: 创建 batch.py 数据模型**

```python
"""
批量处理模块
管理批次的完整生命周期：导入 → 扫描 → 配对 → 命名 → 合并
"""

import os
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from fisheep_video_merger.core.scanner import scan_directory
from fisheep_video_merger.core.matcher import auto_match
from fisheep_video_merger.core.naming import apply_naming_template
from fisheep_video_merger.utils.logger import get_logger

logger = get_logger()


@dataclass
class Batch:
    """批次数据模型"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    folders: List[str] = field(default_factory=list)
    tasks: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    muxed: list = field(default_factory=list)
    status: str = "pending"  # pending/processing/completed/failed
    naming_template: str = "{series}_{ep:03d}"
    series_name: str = ""


class BatchProcessor:
    """批量处理器"""

    def __init__(self):
        self.batches: Dict[str, Batch] = {}

    def create_batch(self, folders: List[str], series_name: str = "") -> Batch:
        """创建批次，触发扫描"""
        batch = Batch(folders=folders, series_name=series_name)
        self.batches[batch.id] = batch
        return batch

    def scan_batch(self, batch_id: str) -> Batch:
        """扫描批次内所有文件夹"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"批次不存在: {batch_id}")

        batch.status = "processing"
        all_stream_infos = []
        root_paths = []

        for folder in batch.folders:
            try:
                result = scan_directory(folder)
                all_stream_infos.extend(result.stream_infos)
                root_paths.append(folder)
            except Exception as e:
                logger.error(f"扫描文件夹失败 {folder}: {e}")

        # 自动配对
        match_result = auto_match(all_stream_infos, root_paths)
        batch.tasks = match_result.auto_tasks
        batch.pending = match_result.pending_videos + match_result.pending_audios
        batch.muxed = match_result.muxed_files

        # 应用命名模板
        if batch.series_name:
            for i, task in enumerate(batch.tasks):
                task.output_name = apply_naming_template(
                    batch.naming_template,
                    task.video_file or task.audio_file,
                    task.source_dir,
                    root_paths[0] if root_paths else "",
                    index=i
                )

        batch.status = "completed" if batch.tasks else "pending"
        return batch

    def preview_names(self, batch_id: str, template: str) -> List[Dict]:
        """预览命名结果"""
        batch = self.batches.get(batch_id)
        if not batch:
            return []

        previews = []
        for i, task in enumerate(batch.tasks):
            name = apply_naming_template(
                template,
                task.video_file or task.audio_file,
                task.source_dir,
                batch.folders[0] if batch.folders else "",
                index=i
            )
            previews.append({
                "index": i,
                "original": task.output_name,
                "preview": name,
                "video": os.path.basename(task.video_file) if task.video_file else "",
                "audio": os.path.basename(task.audio_file) if task.audio_file else "",
            })
        return previews

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        """获取批次"""
        return self.batches.get(batch_id)

    def remove_batch(self, batch_id: str):
        """删除批次"""
        self.batches.pop(batch_id, None)
```

- [ ] **Step 2: 验证 BatchProcessor 基本功能**

```bash
cd D:/dev-java/tools/fisheep-video-merger
PYTHONPATH=src python -c "
from fisheep_video_merger.core.batch import BatchProcessor, Batch
bp = BatchProcessor()
batch = bp.create_batch(['/tmp/test'], '测试系列')
print(f'批次ID: {batch.id}')
print(f'状态: {batch.status}')
print(f'文件夹: {batch.folders}')
"
```

Expected: 批次创建成功，状态为 pending

- [ ] **Step 3: 提交**

```bash
git add src/fisheep_video_merger/core/batch.py
git commit -m "feat(batch): 新建 BatchProcessor 批量处理器"
```

---

## Task 3: Bridge API 扩展

**Files:**
- Modify: `src/fisheep_video_merger/utils/bridge.py`

- [ ] **Step 1: 在 bridge.py 中导入 BatchProcessor**

在文件顶部添加导入：

```python
from fisheep_video_merger.core.batch import BatchProcessor
```

在 `__init__` 中初始化：

```python
self._batch_proc = BatchProcessor()
```

- [ ] **Step 2: 添加 batch_import 方法**

```python
def batch_import(self, folders: list, series_name: str = "") -> Dict:
    """批量导入多个文件夹"""
    try:
        batch = self._batch_proc.create_batch(folders, series_name)
        batch = self._batch_proc.scan_batch(batch.id)
        return {
            "status": "success",
            "batch_id": batch.id,
            "tasks": len(batch.tasks),
            "pending": len(batch.pending),
            "muxed": len(batch.muxed),
            "series_name": batch.series_name,
        }
    except Exception as e:
        logger.error(f"批量导入失败: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 3: 添加 batch_preview 方法**

```python
def batch_preview(self, batch_id: str, template: str) -> Dict:
    """预览批量命名结果"""
    try:
        previews = self._batch_proc.preview_names(batch_id, template)
        return {"status": "success", "previews": previews}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: 添加 batch_merge 方法**

```python
def batch_merge(self, batch_id: str, settings: dict = None) -> Dict:
    """启动批量合并"""
    batch = self._batch_proc.get_batch(batch_id)
    if not batch:
        return {"status": "error", "message": "批次不存在"}

    if not batch.tasks:
        return {"status": "error", "message": "批次无任务"}

    # 将批次任务加入合并队列
    for task in batch.tasks:
        self._task_mgr.add_task(task)

    # 启动合并
    return self.start_merging("merge", settings)
```

- [ ] **Step 5: 提交**

```bash
git add src/fisheep_video_merger/utils/bridge.py
git commit -m "feat(bridge): 添加 batch_import/preview/merge API"
```

---

## Task 4: 前端批次面板

**Files:**
- Create: `src/fisheep_video_merger/ui/web/components/batch_panel.html`
- Modify: `src/fisheep_video_merger/ui/web/index.html`

- [ ] **Step 1: 创建 batch_panel.html 组件**

```html
<!-- 批次面板组件 -->
<div class="batch-panel" x-data="{ batchId: null, previews: [], template: '{series}_{ep:03d}' }">
    <!-- 批次导入区 -->
    <div class="batch-import-area" x-show="!batchId">
        <div class="drop-zone" @drop.prevent="handleBatchDrop($event)" @dragover.prevent>
            <div class="drop-zone-icon">📁</div>
            <div class="drop-zone-text">拖入多个文件夹进行批量合并</div>
            <div class="drop-zone-hint">每个文件夹为一集，自动扫描配对</div>
        </div>
        <div style="margin-top: 12px; display: flex; gap: 8px;">
            <input type="text" x-model="seriesName" placeholder="系列名称（可选）" 
                   style="flex: 1; padding: 8px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--window-bg); color: var(--text-color);">
            <button class="btn btn-secondary" @click="selectBatchFolders()">📂 选择文件夹</button>
        </div>
    </div>

    <!-- 批次信息 -->
    <div x-show="batchId" style="margin-top: 16px;">
        <div class="config-card">
            <h4>📦 批次信息</h4>
            <div style="font-size: 12px; color: var(--text-muted);">
                <div>批次 ID: <span x-text="batchId"></span></div>
                <div>任务数: <span x-text="taskCount"></span></div>
            </div>
        </div>

        <!-- 命名模板 -->
        <div class="config-card" style="margin-top: 12px;">
            <h4>📝 命名模板</h4>
            <input type="text" x-model="template" 
                   style="width: 100%; padding: 8px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--window-bg); color: var(--text-color);"
                   @input="debouncePreview()">
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                变量: {series} 系列名, {ep} 集数, {ep:03d} 三位序号
            </div>
            <button class="btn btn-secondary" style="margin-top: 8px;" @click="refreshPreview()">🔄 刷新预览</button>
        </div>

        <!-- 命名预览 -->
        <div class="config-card" style="margin-top: 12px;" x-show="previews.length > 0">
            <h4>👀 命名预览</h4>
            <div style="max-height: 200px; overflow-y: auto;">
                <template x-for="(p, i) in previews" :key="i">
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; font-size: 12px; border-bottom: 1px solid var(--border-color);">
                        <span x-text="p.video || p.audio" style="color: var(--text-muted);"></span>
                        <span x-text="'→ ' + p.preview" style="color: var(--primary-color); font-weight: 600;"></span>
                    </div>
                </template>
            </div>
        </div>

        <!-- 操作按钮 -->
        <div style="margin-top: 16px; display: flex; gap: 8px;">
            <button class="btn btn-primary" style="flex: 1;" @click="startBatchMerge()">🚀 开始批量合并</button>
            <button class="btn btn-secondary" @click="clearBatch()">🗑️ 清空批次</button>
        </div>
    </div>
</div>
```

- [ ] **Step 2: 在 index.html 的合并工具区添加批次面板**

在合并工具的合适位置添加：

```html
<!-- 批次面板 -->
<div x-show="$store.app.subtab === 'batch'" style="margin-bottom: 16px;">
    <div x-html="await (await fetch('components/batch_panel.html')).text()"></div>
</div>
```

- [ ] **Step 3: 提交**

```bash
git add src/fisheep_video_merger/ui/web/components/batch_panel.html
git add src/fisheep_video_merger/ui/web/index.html
git commit -m "feat(ui): 新增批次面板组件"
```

---

## Task 5: 前端批次逻辑

**Files:**
- Modify: `src/fisheep_video_merger/ui/web/js/merger.js`

- [ ] **Step 1: 在 merger.js 中添加批次相关函数**

```javascript
// === 批量处理 ===

window.handleBatchDrop = function(event) {
    const folders = Array.from(event.dataTransfer.items)
        .filter(item => item.kind === 'file')
        .map(item => item.webkitGetAsEntry())
        .filter(entry => entry && entry.isDirectory);
    
    if (folders.length === 0) {
        showToast('请拖入文件夹', 'warning');
        return;
    }
    
    // 获取文件夹路径
    const paths = folders.map(f => f.fullPath);
    window.batchImport(paths);
};

window.selectBatchFolders = function() {
    callPython('select_folder_dialog').then(res => {
        if (res && res.folders && res.folders.length > 0) {
            window.batchImport(res.folders);
        }
    });
};

window.batchImport = function(folders) {
    const seriesName = document.querySelector('[x-data]')?.__x?.$data?.seriesName || '';
    callPython('batch_import', folders, seriesName).then(res => {
        if (res && res.status === 'success') {
            showToast(`批量导入成功：${res.tasks} 个任务`, 'success');
            // 更新 Alpine 数据
            const panel = document.querySelector('.batch-panel');
            if (panel && panel.__x) {
                panel.__x.$data.batchId = res.batch_id;
                panel.__x.$data.taskCount = res.tasks;
            }
            window.refreshPreview();
        } else {
            showToast(`批量导入失败：${res?.message}`, 'error');
        }
    });
};

window.refreshPreview = function() {
    const panel = document.querySelector('.batch-panel');
    if (!panel || !panel.__x) return;
    const batchId = panel.__x.$data.batchId;
    const template = panel.__x.$data.template;
    if (!batchId) return;
    
    callPython('batch_preview', batchId, template).then(res => {
        if (res && res.status === 'success') {
            panel.__x.$data.previews = res.previews;
        }
    });
};

window.startBatchMerge = function() {
    const panel = document.querySelector('.batch-panel');
    if (!panel || !panel.__x) return;
    const batchId = panel.__x.$data.batchId;
    if (!batchId) {
        showToast('请先导入批次', 'warning');
        return;
    }
    
    const settings = {
        output_format: Alpine.store('settings').outputFormat,
        concurrency: Alpine.store('settings').concurrency,
        overwrite: Alpine.store('settings').overwrite,
    };
    
    callPython('batch_merge', batchId, settings).then(res => {
        if (res && res.status === 'error') {
            showToast(res.message, 'warning');
        } else {
            showToast('批量合并已启动', 'success');
        }
    });
};

window.clearBatch = function() {
    const panel = document.querySelector('.batch-panel');
    if (panel && panel.__x) {
        panel.__x.$data.batchId = null;
        panel.__x.$data.previews = [];
        panel.__x.$data.taskCount = 0;
    }
    showToast('批次已清空', 'info');
};

// 防抖预览
let previewTimer = null;
window.debouncePreview = function() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => window.refreshPreview(), 500);
};
```

- [ ] **Step 2: 提交**

```bash
git add src/fisheep_video_merger/ui/web/js/merger.js
git commit -m "feat(merger): 添加批量处理前端逻辑"
```

---

## Task 6: 工具并行处理

**Files:**
- Modify: `src/fisheep_video_merger/ui/web/js/settings.js`

- [ ] **Step 1: 修改 runToolTask 支持并发**

将 `processNext` 递归改为并发池：

```javascript
export function runToolTask(tool, taskFn) {
    const selectedFiles = getSelectedFiles(tool);
    if (selectedFiles.length === 0) {
        showToast('请先添加文件', 'warning');
        return;
    }

    if (!window.pywebview || !window.pywebview.api) {
        showToast('请在桌面客户端中使用此功能', 'warning');
        return;
    }

    const btn = document.getElementById(`${tool}-start-btn`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ 处理中...';
    }

    let completed = 0;
    let failed = 0;
    const total = selectedFiles.length;
    const concurrency = Alpine.store('settings').concurrency || 2;

    selectedFiles.forEach(file => { file._status = 'waiting'; });
    renderToolTable(tool);

    async function processFile(file) {
        file._status = 'processing';
        renderToolTable(tool);
        try {
            const result = await taskFn(file);
            if (result && result.status === 'success') {
                completed++;
                file._status = 'completed';
            } else {
                failed++;
                file._status = 'failed';
                file._error = result?.error || result?.message || '失败';
            }
        } catch (e) {
            failed++;
            file._status = 'failed';
            file._error = String(e);
        }
        renderToolTable(tool);
    }

    // 并发处理池
    async function runPool() {
        const queue = [...selectedFiles];
        const workers = [];
        for (let i = 0; i < Math.min(concurrency, queue.length); i++) {
            workers.push((async () => {
                while (queue.length > 0) {
                    const file = queue.shift();
                    await processFile(file);
                }
            })());
        }
        await Promise.all(workers);
        
        if (btn) {
            btn.textContent = '🚀 开始处理';
            btn.disabled = false;
        }
        showToast(`处理完成：成功 ${completed}，失败 ${failed}`, failed > 0 ? 'warning' : 'success');
    }

    runPool();
}
```

- [ ] **Step 2: 提交**

```bash
git add src/fisheep_video_merger/ui/web/js/settings.js
git commit -m "feat(tools): 工具处理改为并发池模式"
```

---

## Task 7: 集成测试

- [ ] **Step 1: 启动应用验证批量导入**

```bash
cd D:/dev-java/tools/fisheep-video-merger
PYTHONPATH=src python -m fisheep_video_merger.main_web
```

- [ ] **Step 2: 测试命名模板**

在 Python 控制台验证：
```python
from fisheep_video_merger.core.naming import apply_naming_template
assert apply_naming_template('{series}_{ep:03d}', 't.mp4', '/d', '/r', 0) == '系列_001'
assert apply_naming_template('{series}_{ep:03d}', 't.mp4', '/d', '/r', 9) == '系列_010'
```

- [ ] **Step 3: 测试 BatchProcessor**

```python
from fisheep_video_merger.core.batch import BatchProcessor
bp = BatchProcessor()
batch = bp.create_batch(['/path/to/folder'], '测试')
print(batch.id, batch.status)
```

- [ ] **Step 4: 全量回归**

1. 合并功能正常
2. 转换/提取/压缩/裁剪功能正常
3. 批次面板显示正常
4. 命名预览正常

- [ ] **Step 5: 提交最终版本**

```bash
git add -A
git commit -m "feat: v0.8.0 批量处理体系完成"
```
