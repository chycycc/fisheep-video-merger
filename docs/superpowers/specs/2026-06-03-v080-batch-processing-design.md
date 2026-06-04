# v0.8.0 设计文档：批量处理体系

## 1. 概述

### 目标
为 Fisheep Video Merger 实现批量处理能力，支持：
- 一次拖入多个文件夹，各自独立扫描匹配
- 一个大文件夹内混合文件的自动配对
- 批量合并时自动生成序号命名（`{series}_{ep:03d}`）
- 转换/提取/压缩/裁剪工具的并行批处理

### 非目标（v0.8.0 不做）
- `{date}`、`{resolution}`、`{source}` 等扩展变量（后续版本）
- 正则替换功能
- 批次优先级排序

---

## 2. 架构设计

### 方案：前端批量 UI + 后端批量处理器

```
┌─────────────────────────────────────────────┐
│  前端 (index.html + JS 模块)                │
│  ├─ 多文件夹选择/拖入                        │
│  ├─ 批次分组展示（按文件夹分组）               │
│  └─ 批量命名预览                             │
└─────────────────┬───────────────────────────┘
                  │ Bridge API
┌─────────────────▼───────────────────────────┐
│  后端 (Python)                               │
│  ├─ BatchProcessor（批次生命周期管理）         │
│  ├─ 命名模板引擎（{series}_{ep:03d}）         │
│  └─ 合并控制器（复用现有 MergeController）      │
└─────────────────────────────────────────────┘
```

### 前后端分离原则
- 前端只负责 UI 展示和用户交互
- 后端负责所有业务逻辑（扫描、配对、命名、合并）
- 通过 Bridge 结构化消息通信（复用 v0.7.0 的 `_send_message` 机制）

---

## 3. 核心组件

### 3.1 BatchProcessor（后端新建）

**职责**：管理批次的完整生命周期

```
导入 → 扫描 → 配对 → 命名 → 合并
```

**数据模型**：
```python
class Batch:
    id: str                    # 批次 ID
    folders: List[str]         # 文件夹路径列表
    tasks: List[MergeTask]     # 已配对的任务
    pending: List[StreamInfo]  # 未配对的文件
    status: str                # pending/processing/completed/failed
    naming_template: str       # 命名模板
```

**方法**：
- `create_batch(folders)` — 创建批次，触发扫描
- `preview_names(template)` — 预览命名结果
- `start_merge(settings)` — 启动批量合并
- `get_status()` — 获取批次状态

### 3.2 命名模板引擎（扩展现有）

**现有变量**：
- `{series}` — 系列名
- `{ep}` — 集数
- `{original}` — 原始文件名

**新增格式**：
- `{ep:03d}` — 三位数序号（001, 002, 003...）
- `{ep:02d}` — 两位数序号（01, 02, 03...）

**实现**：扩展现有 `naming.py` 的 `apply_naming_template` 函数

### 3.3 前端批次 UI

**新增组件**：
- `batch_panel.html` — 批次分组展示面板
- 批次列表：每个批次显示文件夹名、配对状态、任务数
- 命名预览：实时显示输出文件名

**交互流程**：
1. 用户拖入多个文件夹（或选择多个文件夹）
2. 前端调用 `batch_import(folders)` 
3. 后端扫描并返回批次数据
4. 前端展示批次分组和配对状态
5. 用户确认命名模板
6. 点击"批量合并"开始处理

---

## 4. Bridge API 设计

### 新增接口

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `batch_import` | `folders: List[str]` | `Batch` | 批量导入多个文件夹 |
| `batch_preview` | `batch_id: str, template: str` | `List[PreviewItem]` | 预览批量命名结果 |
| `batch_merge` | `batch_id: str, settings: Dict` | `Dict` | 启动批量合并 |

### 消息类型（Python→JS）

| 类型 | 数据 | 说明 |
|------|------|------|
| `batch_progress` | `{batch_id, completed, total, current_file}` | 批次进度 |
| `batch_status` | `{batch_id, status, error}` | 批次状态变更 |
| `batch_complete` | `{batch_id, completed, failed}` | 批次完成 |

---

## 5. 用户场景

### 场景 1：多个文件夹（每集一个文件夹）
```
输入：
  进击的巨人/
    第1集/
      video.m4s
      audio.m4s
    第2集/
      video.m4s
      audio.m4s
    ...

输出：
  进击的巨人_001.mp4
  进击的巨人_002.mp4
  ...
```

### 场景 2：一个大文件夹（混合文件）
```
输入：
  进击的巨人/
    video_001.m4s
    audio_001.m4s
    video_002.m4s
    audio_002.m4s
    ...

输出：
  进击的巨人_001.mp4
  进击的巨人_002.mp4
  ...
```

### 场景 3：命名模板预览
```
模板：{series}_{ep:03d}
预览：
  进击的巨人_001.mp4
  进击的巨人_002.mp4
  进击的巨人_003.mp4
```

---

## 6. 并发控制

### 合并并发
- 复用现有 `MergeController` 的 `ThreadPoolExecutor`
- 并发数由用户设置（1-8）
- 批次内所有任务共享同一个线程池

### 工具并发（转换/提取/压缩/裁剪）
- 当前是串行处理（`processNext` 递归）
- 改为并发处理：使用 `Promise.all` 或有限并发池
- 并发数由用户设置

---

## 7. 错误处理

### 批次级错误
- 扫描失败：记录错误，继续处理其他文件夹
- 配对失败：未配对文件移入"待整理"队列
- 合并失败：标记任务为 failed，不阻塞其他任务

### 任务级错误
- 单个任务失败：重试一次（音频重编码降级）
- 重试仍失败：标记为 failed，继续下一个

---

## 8. 实现计划

### 阶段 1：后端 BatchProcessor
- 新建 `core/batch.py`
- 实现批次数据模型
- 实现批量扫描和配对

### 阶段 2：命名模板扩展
- 扩展 `core/naming.py`
- 支持 `{ep:03d}` 格式
- 添加命名预览功能

### 阶段 3：Bridge API
- 扩展 `bridge.py`
- 添加 `batch_import`、`batch_preview`、`batch_merge`
- 添加批次进度消息

### 阶段 4：前端 UI
- 新建 `components/batch_panel.html`
- 扩展 `merger.js` 添加批次逻辑
- 批次分组展示和命名预览

### 阶段 5：工具并行处理
- 修改 `settings.js` 的 `runToolTask`
- 实现并发处理池
- 添加并发数控制

---

## 9. 验证计划

1. **批量导入**：拖入 3 个文件夹，各自扫描匹配
2. **混合文件**：一个文件夹内 6 个文件（3 组配对），自动配对
3. **命名预览**：模板 `{series}_{ep:03d}`，预览显示正确序号
4. **批量合并**：3 个任务并行合并，输出文件名正确
5. **错误处理**：故意放入不匹配文件，验证错误提示
6. **并发控制**：设置并发数为 2，验证同时只有 2 个任务在合并
