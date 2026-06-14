# 架构重构计划

## Problem Statement

项目存在三个核心架构问题：
1. **app.js 遗留单体（2383行）仍被加载**，与新模块化文件双重注册 Alpine store，导致潜在 UI 状态 bug
2. **UIBridge 是上帝对象（1002行、60+方法）**，混合状态持有、业务逻辑和薄委托，违反深模块原则
3. **settings.js 是厨房水槽（1245行）**，混合 5 个不相关职责

最终目标：每个模块接口简单、功能强大（深模块原则）。

## Solution

分三阶段重构，每阶段独立可验证，每步 5-10 分钟。

---

## Phase 1: 清理遗留代码（可并行）

### Commit 1.1: 删除 app.js
- **目标**：消除双重 Alpine store 注册
- **文件**：`ui/web/app.js`（删除）、`index.html`（确认不引用）
- **变更**：git rm app.js；检查 index.html 无 `<script src="app.js">`
- **验证**：启动应用，所有工具面板正常加载，Alpine store 正确（7个工具设置）

### Commit 1.2: 删除 utils/theme.py
- **目标**：移除未使用的 PySide6 遗留代码
- **文件**：`utils/theme.py`（删除）
- **变更**：git rm theme.py；确认无其他模块引用
- **验证**：`python -c "from fisheep_video_merger.utils.bridge import UIBridge"` 不报错

---

## Phase 2: 拆分 UIBridge（串行）

### Commit 2.1: 提取 ImportService
- **目标**：把文件导入逻辑从 bridge.py 移到独立 service
- **文件**：新建 `utils/services/import_service.py`、修改 `utils/bridge.py`
- **变更**：
  - 新建 ImportService，包含 scan_and_match()、add_files() 方法
  - 移入 _add_folders() 和 _add_files() 的扫描/匹配/状态管理逻辑
  - UIBridge 的 on_files_dropped/add_folder 改为委托到 ImportService
- **验证**：拖入文件夹，队列正确显示任务

### Commit 2.2: 提取 ViewModelBuilder
- **目标**：把视图模型构建逻辑从 bridge.py 移出
- **文件**：修改 `utils/services/task_manager.py`、修改 `utils/bridge.py`
- **变更**：
  - _get_queue_data() 移入 TaskManagerService.get_queue_view_model()
  - UIBridge.get_current_state() 改为委托
- **验证**：启动应用，队列数据正确显示

### Commit 2.3: 清理 bridge.py 直接导入
- **目标**：UIBridge 不再直接导入 core 模块符号
- **文件**：`utils/bridge.py`
- **变更**：
    - 移除顶层 `from core.matcher import auto_match, create_manual_task, suggest_output_name, apply_naming_template`
    - 这些调用通过 service 层间接访问
- **验证**：手动配对、智能配对、命名模板功能正常

### Commit 2.4: 状态移入 AppState
- **目标**：UIBridge 不再持有业务状态
- **文件**：新建 `utils/app_state.py`、修改 `utils/bridge.py`
- **变更**：
  - 新建 AppState 类，持有 root_paths、all_stream_infos、muxed_files、pending_*、settings
  - UIBridge 持有 AppState 引用，service 通过 AppState 访问状态
- **验证**：启动应用，工作区状态正确加载/保存

---

## Phase 3: 拆分 settings.js（可并行）

### Commit 3.1: 提取 tool-files.js
- **目标**：工具文件管理独立模块
- **文件**：新建 `ui/web/js/tool-files.js`、修改 `settings.js`、`main.js`
- **变更**：
  - 移入：toolFiles、addFilesToTool、renderToolTable、selectToolRow、renderConvertResult、openToolResultFile/Folder、initToolDropZones、selectFilesForTool
  - settings.js 只保留设置面板逻辑
  - main.js 从 tool-files.js 导入
- **验证**：拖入文件到各工具面板，表格正确显示

### Commit 3.2: 提取 tool-runner.js
- **目标**：工具任务执行独立模块
- **文件**：新建 `ui/web/js/tool-runner.js`、修改 `settings.js`、`main.js`
- **变更**：
  - 移入：runToolTask、getSelectedFiles、initToolStartButtons、updateToolProgress
  - main.js 从 tool-runner.js 导入
- **验证**：各工具开始按钮正常工作，进度正确显示

### Commit 3.3: 提取 trim-timeline.js
- **目标**：裁剪时间轴组件独立模块
- **文件**：新建 `ui/web/js/trim-timeline.js`、修改 `settings.js`、`main.js`
- **变更**：
  - 移入：initTrimTimeline、setTrimDuration、resetTrimTimeline、secToTime、timeToSec、updateVisual
  - main.js 从 trim-timeline.js 导入
- **验证**：裁剪工具时间轴正常拖拽，时长正确显示

### Commit 3.4: 提取 panel-resize.js
- **目标**：面板拖拽调整独立模块
- **文件**：新建 `ui/web/js/panel-resize.js`、修改 `settings.js`、`main.js`
- **变更**：
  - 移入：startConfigResize、startSidebarResize
  - main.js 从 panel-resize.js 导入
- **验证**：右侧配置面板和左侧导航栏拖拽调整正常

---

## Phase 4: 消除层级违规（可并行）

### Commit 4.1: 提取共享常量
- **目标**：消除 _FORMAT_CODEC 重复定义
- **文件**：新建 `core/constants.py`、修改 `core/extractor.py`、`core/audio_converter.py`、`core/audio_trimmer.py`
- **变更**：
  - 新建 constants.py，定义 FORMAT_AUDIO_CODEC、FORMAT_VIDEO_CODEC
  - 三个模块改为从 constants 导入
- **验证**：转换/提取/音频工具正常工作

### Commit 4.2: 修复 ffprobe → ffmpeg_runner 反向依赖
- **目标**：utils 不再导入 core
- **文件**：`utils/ffprobe.py`、`core/ffmpeg_runner.py`
- **变更**：
  - extract_screenshot() 接受 ffmpeg_path 参数，不自己获取
  - 调用方（bridge.py）传入 get_ffmpeg_path()
- **验证**：视频预览截图正常

### Commit 4.3: 修复 extractor → ffprobe 反向依赖
- **目标**：core 不再导入 utils
- **文件**：`core/extractor.py`、`utils/services/tool_service.py`
- **变更**：
  - _can_use_stream_copy() 接受 video_detail 参数
  - ToolService 在调用前获取 video_detail 并传入
- **验证**：提取音频工具正常工作

---

## 并行关系

```
Phase 1 (可并行)
  ├── 1.1 删除 app.js
  └── 1.2 删除 theme.py

Phase 2 (串行)
  ├── 2.1 提取 ImportService
  ├── 2.2 提取 ViewModelBuilder
  ├── 2.3 清理直接导入
  └── 2.4 提取 AppState

Phase 3 (可并行)
  ├── 3.1 提取 tool-files.js
  ├── 3.2 提取 tool-runner.js
  ├── 3.3 提取 trim-timeline.js
  └── 3.4 提取 panel-resize.js

Phase 4 (可并行)
  ├── 4.1 提取共享常量
  ├── 4.2 修复 ffprobe 依赖
  └── 4.3 修复 extractor 依赖
```

Phase 1 可与 Phase 3、Phase 4 并行。Phase 2 必须串行。

---

## Decision Document

- UIBridge 拆分后保留为薄门面，所有业务逻辑下沉到 service
- AppState 作为共享状态容器，service 通过引用访问
- JS 模块拆分后通过 ES module import/export，window.* 绑定集中在 main.js
- 深模块原则：每个模块对外暴露简单接口，内部实现复杂逻辑

## Testing Decisions

- 每步验证：启动应用 → 操作相关功能 → 确认无报错
- Phase 1：全量冒烟测试（所有工具面板切换、拖入文件）
- Phase 2：重点测试文件导入和队列显示
- Phase 3：重点测试各工具的文件管理和任务执行
- Phase 4：重点测试格式转换和音频提取

## Out of Scope

- 不引入正式测试框架（pytest 迁移）
- 不引入依赖注入容器
- 不重构 core/ 模块的内部逻辑
- 不修改 HTML 模板结构
