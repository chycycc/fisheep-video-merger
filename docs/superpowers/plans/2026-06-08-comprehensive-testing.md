# 全面测试计划

> **Goal:** 对 Fisheep 视频工具箱进行 100% 覆盖的测试，包含后端测试、前端 UI 测试、集成测试、Bug 验证。
> **总计:** 145 个功能点，10 个已知 Bug。

---

## 测试分层

| 层级 | 范围 | 方法 | 覆盖目标 |
|------|------|------|---------|
| L1: 后端单元 | core/ 模块 | Python 直接调用 | 所有核心函数 |
| L2: 服务层集成 | utils/services/ | Python API 调用 | 所有服务方法 |
| L3: 前端 DOM | UI 元素 | Playwright | 所有 ID、选项、按钮 |
| L4: 前端交互 | Tab 切换、参数面板 | Playwright 点击 | 所有交互路径 |
| L5: 联调测试 | 前端→桥接→服务→核心 | Playwright + pywebview | 端到端功能 |
| L6: Bug 验证 | 已知 10 个 Bug | 专项测试 | 全部修复确认 |

---

## Phase 1: 后端单元测试 (L1)

### 1.1 格式转换 core/converter.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.1.1 | 流复制 mp4→mkv | test_video.mp4, mode=copy | 成功，输出 .mkv |
| 1.1.2 | 重编码 h264 | test_video.mp4, mode=h264, crf=28 | 成功，输出 .mp4 |
| 1.1.3 | 重编码 hevc | test_video.mp4, mode=hevc | 成功，输出 .mp4 |
| 1.1.4 | 缩放 720p | test_video.mp4, scale=720p | 成功，分辨率 1280x? |
| 1.1.5 | 帧率修改 | test_video.mp4, fps=30 | 成功 |
| 1.1.6 | NVENC 预设映射 | mode=h264, preset=ultrafast, hw=nvenc | 预设转为 fast |
| 1.1.7 | NVENC CRF→CQ | mode=h264, hw=nvenc | 使用 -cq 代替 -crf |
| 1.1.8 | 不存在的文件 | nonexistent.mp4 | 返回 (False, 错误信息) |
| 1.1.9 | 输出目录不存在 | output_path=/nonexistent/out.mkv | 自动创建目录 |
| 1.1.10 | 进度回调 | 传入 progress_callback | 回调被调用 |

### 1.2 音频提取 core/extractor.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.2.1 | 提取 MP3 | format=mp3, bitrate=128k | 成功，输出 .mp3 |
| 1.2.2 | 提取 AAC | format=aac, bitrate=192k | 成功，输出 .m4a |
| 1.2.3 | 提取 FLAC | format=flac | 成功，输出 .flac |
| 1.2.4 | 提取 WAV | format=wav | 成功，输出 .wav |
| 1.2.5 | 音量调节 | volume=0.5 | 成功，音量降低 |
| 1.2.6 | 音量放大 | volume=2.0 | 成功，音量提高 |
| 1.2.7 | 声道→单声道 | channels=mono | 成功，单声道 |
| 1.2.8 | 声道→立体声 | channels=stereo | 成功，立体声 |
| 1.2.9 | 采样率修改 | sample_rate=44100 | 成功 |
| 1.2.10 | VBR 模式 | bitrate_mode=vbr, format=mp3 | 成功 |
| 1.2.11 | 流复制优化 | 源 aac → 目标 aac，无参数变化 | 流复制（快速） |
| 1.2.12 | 流复制失败回退 | 流复制失败 | 自动回退到重编码 |

### 1.3 视频压缩 core/compressor.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.3.1 | 快速压缩 | preset=fast, resolution=original | 成功，CRF 28 |
| 1.3.2 | 均衡压缩 | preset=balanced, resolution=720p | 成功，CRF 23 |
| 1.3.3 | 高质量压缩 | preset=quality, resolution=original | 成功，CRF 20 |
| 1.3.4 | 分辨率缩放 480p | resolution=480p | 成功，854x? |
| 1.3.5 | NVENC 压缩 | hw_encoder 存在 | 使用 -cq 代替 -crf |
| 1.3.6 | Two-Pass 模式 | target_size_mb=5 | 成功，两遍编码 |

### 1.4 视频裁剪 core/trimmer.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.4.1 | 快速裁剪 | start=0, end=2, mode=copy | 成功 |
| 1.4.2 | 精确裁剪 | start=1, end=3, mode=accurate | 成功 |
| 1.4.3 | 秒数格式 | start=0.5, end=2.5 | 成功 |
| 1.4.4 | MM:SS 格式 | start=00:30, end=01:30 | 成功 |
| 1.4.5 | HH:MM:SS 格式 | start=00:00:30, end=00:01:30 | 成功 |
| 1.4.6 | 结束时间为空 | end='' | 返回错误 |
| 1.4.7 | NVENC 裁剪 | hw_encoder 存在，mode=accurate | 使用硬件编码 |

### 1.5 字幕工具 core/subtitle.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.5.1 | 整体调轴 +2.5s | offset_ms=2500 | 时间戳全部 +2.5s |
| 1.5.2 | 整体调轴 -1s | offset_ms=-1000 | 时间戳全部 -1s |
| 1.5.3 | 调轴为 0 | offset_ms=0 | 不变，成功 |
| 1.5.4 | 按片段调轴 | segments=[{start_ms, end_ms, offset_ms}] | 指定行偏移 |
| 1.5.5 | 片段验证 start>end | segments=[{start:5000, end:1000}] | 返回错误 |
| 1.5.6 | 片段验证缺少字段 | segments=[{start:0}] | 返回错误 |
| 1.5.7 | 合并 top_bottom | layout=top_bottom | A 在下 B 在上 |
| 1.5.8 | 合并 vertical（兼容） | layout=vertical | 同 top_bottom |
| 1.5.9 | 合并 interleave | layout=interleave | 按时间交错 |
| 1.5.10 | 合并不支持的布局 | layout=horizontal | 返回错误 |
| 1.5.11 | 转换 srt→ass | target_format=ass | 输出 .ass |
| 1.5.12 | 转换 srt→vtt | target_format=vtt | 输出 .vtt，含 WEBVTT |
| 1.5.13 | 转换 srt→ssa | target_format=ssa | 输出 .ssa |
| 1.5.14 | 转换输出路径覆盖 | target_format=ass, output_path=x.srt | 输出 .ass（覆盖扩展名） |
| 1.5.15 | 拆分奇偶行 | 无 pattern | 事件 0→A, 1→B, 2→A... |
| 1.5.16 | 拆分正则 | pattern='World' | 匹配行→B，其余→A |
| 1.5.17 | 从视频提取字幕 | stream_index=0 | 成功，输出 .srt |
| 1.5.18 | 不存在的文件 | input=nonexistent.srt | 返回错误 |

### 1.6 集数提取 core/episode.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.6.1 | 阿拉伯数字 | "第01集" | 1 |
| 1.6.2 | 中文数字 | "第三集" | 3 |
| 1.6.3 | EP 前缀 | "EP05" | 5 |
| 1.6.4 | P 前缀 | "P12" | 12 |
| 1.6.5 | Part 前缀 | "Part 3" | 3 |
| 1.6.6 | 无集数 | "random_file" | None |

### 1.7 命名模板 core/naming.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.7.1 | 基本模板 | template="{series}_{ep}", series="Test", ep=1 | "Test_01" |
| 1.7.2 | 零填充 | template="{ep:03d}", ep=5 | "005" |
| 1.7.3 | 空模板 | template="" | 使用默认命名 |
| 1.7.4 | 未知变量 | template="{unknown}" | 保留原样或忽略 |

### 1.8 FFmpeg 执行器 core/ffmpeg_runner.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.8.1 | 正常执行 | 有效 FFmpeg 命令 | (True, None) |
| 1.8.2 | 无效命令 | 错误参数 | (False, 错误信息) |
| 1.8.3 | 进度解析 | FFmpeg 输出含 (50.0%) | 回调收到 50.0 |
| 1.8.4 | 硬件加速检测 | get_hw_encoder() | 返回 None 或编码器名 |
| 1.8.5 | ensure_output_dir | 目录不存在 | 自动创建 |

### 1.9 B站元数据 core/bilibili.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.9.1 | 读取 entry.json | 有效 B站缓存目录 | 返回元数据 dict |
| 1.9.2 | 无效目录 | 非 B站目录 | 返回 None 或空 |

### 1.10 批处理 core/batch.py

| # | 用例 | 输入 | 预期输出 |
|---|------|------|---------|
| 1.10.1 | 创建批次 | folders=["/path"] | Batch 对象 |
| 1.10.2 | 扫描批次 | batch_id | tasks 列表 |
| 1.10.3 | 命名预览 | batch_id, template | 预览列表 |
| 1.10.4 | 删除批次 | batch_id | 成功 |
| 1.10.5 | 扫描失败容错 | 一个文件夹不存在 | 其他文件夹正常扫描 |

---

## Phase 2: 服务层集成测试 (L2)

### 2.1 ToolService API

| # | 方法 | 用例 | 预期 |
|---|------|------|------|
| 2.1.1 | convert_file | 正常转换 | status=success |
| 2.1.2 | convert_file | 文件不存在 | status=error |
| 2.1.3 | convert_file | 文件名冲突 | 自动 _1 后缀 |
| 2.1.4 | extract_audio_api | MP3 提取 | status=success |
| 2.1.5 | extract_audio_api | AAC 提取 | 输出 .m4a |
| 2.1.6 | compress_video_api | 快速压缩 | status=success |
| 2.1.7 | compress_video_api | 自动后缀 _compressed | 输出文件名正确 |
| 2.1.8 | trim_video_api(copy) | 快速裁剪 | status=success |
| 2.1.9 | trim_video_api(recode) | 精确裁剪 | status=success |
| 2.1.10 | trim_video_api | 自动后缀 _trimmed | 输出文件名正确 |
| 2.1.11 | subtitle_adjust_api | 正常调轴 | status=success |
| 2.1.12 | subtitle_convert_api | 格式转换 | status=success |
| 2.1.13 | subtitle_merge_api | 合并 | status=success |
| 2.1.14 | subtitle_merge_api | 文件 B 不存在 | status=error |
| 2.1.15 | subtitle_split_api | 拆分 | 输出两个文件 |
| 2.1.16 | subtitle_extract_api | 从视频提取 | status=success |
| 2.1.17 | get_video_preview | 有效视频 | 返回截图+元数据 |
| 2.1.18 | get_file_info | 有效音频 | 返回 codec/bitrate/channels |
| 2.1.19 | get_hw_accel_info | 有 GPU | 返回 GPU 信息 |
| 2.1.20 | _resolve_conflict | 文件已存在 | 返回 _1 路径 |
| 2.1.21 | _resolve_conflict | 文件不存在 | 返回原路径 |

### 2.2 MergeControllerService

| # | 方法 | 用例 | 预期 |
|---|------|------|------|
| 2.2.1 | start_merge | 1 个任务 | 成功合并 |
| 2.2.2 | start_merge | 2 个任务，并发=2 | 并行执行 |
| 2.2.3 | cancel_merge | 正在合并时取消 | 所有进程终止 |
| 2.2.4 | get_merge_estimate | 2 个任务 | 返回时间估算 |
| 2.2.5 | 冲突处理 | overwrite=false，文件已存在 | 自动 _1 |
| 2.2.6 | 路径镜像 | path_depth=1 | 输出目录结构正确 |

### 2.3 TaskManagerService

| # | 方法 | 用例 | 预期 |
|---|------|------|------|
| 2.3.1 | add_task | 添加任务 | 任务列表长度+1 |
| 2.3.2 | rename_task | 重命名 | 名称更新 |
| 2.3.3 | reset_task | 重置已完成任务 | 状态变 pending |
| 2.3.4 | batch_rename | 批量重命名 | 所有名称更新 |
| 2.3.5 | reorder_tasks | 移动任务位置 | 顺序正确 |
| 2.3.6 | delete_task | 删除任务 | 任务列表长度-1 |
| 2.3.7 | clear_completed | 清除已完成 | 只剩 pending/failed |
| 2.3.8 | clear_all | 清除全部 | 列表为空 |
| 2.3.9 | preserve_status | 重新扫描 | 已完成状态保留 |

### 2.4 StatePersistenceService

| # | 方法 | 用例 | 预期 |
|---|------|------|------|
| 2.4.1 | save_debounced | 保存状态 | 文件写入 |
| 2.4.2 | load | 加载状态 | 状态恢复 |
| 2.4.3 | 防抖 | 连续调用 3 次 | 只写入 1 次 |
| 2.4.4 | 路径 | sys.frozen=True | 使用 sys.executable 路径 |
| 2.4.5 | 路径 | sys.frozen=False | 使用 LOCALAPPDATA |

### 2.5 DialogService

| # | 方法 | 用例 | 预期 |
|---|------|------|------|
| 2.5.1 | select_folder_dialog | 调用 | 返回路径列表 |
| 2.5.2 | select_files_dialog | 调用 | 返回文件路径列表 |
| 2.5.3 | select_tool_files | 调用 | 返回工具文件列表 |
| 2.5.4 | 文件类型过滤 | .m4s 文件 | 在 merge 对话框中可见 |
| 2.5.5 | 文件类型过滤 | .wmv 文件 | 在 tool 对话框中可见 |

---

## Phase 3: 前端 DOM 测试 (L3)

### 3.1 全局

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.1.1 | 页面标题 | title | 包含 Fisheep |
| 3.1.2 | Alpine.js 加载 | typeof Alpine | 非 undefined |
| 3.1.3 | pywebview mock | window.pywebview | 存在 |

### 3.2 侧栏

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.2.1 | merge 按钮 | button[data-tool="merge"] | 存在 |
| 3.2.2 | convert 按钮 | button[data-tool="convert"] | 存在 |
| 3.2.3 | extract 按钮 | button[data-tool="extract"] | 存在 |
| 3.2.4 | compress 按钮 | button[data-tool="compress"] | 存在 |
| 3.2.5 | trim 按钮 | button[data-tool="trim"] | 存在 |
| 3.2.6 | subtitle 按钮 | button[data-tool="subtitle"] | 存在 |
| 3.2.7 | settings 按钮 | button[data-tool="settings"] | 存在 |
| 3.2.8 | 主题切换 | #theme-switch-btn | 存在 |

### 3.3 格式转换面板

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.3.1 | 面板存在 | #tool-convert | 存在 |
| 3.3.2 | 目标格式 | #convert-format | 有 mp4/mkv/webm/avi |
| 3.3.3 | 转换模式 | #convert-mode | 有 copy/recode |
| 3.3.4 | 输出目录 | #convert-output-dir | 存在 |
| 3.3.5 | 输出文件名 | #convert-output-name | 存在 |
| 3.3.6 | 添加文件按钮 | button 包含"添加文件" | 存在 |
| 3.3.7 | 任务列表 | task-list 组件 | 存在 |
| 3.3.8 | 操作按钮 | action-bar 组件 | 存在 |

### 3.4 提取音频面板

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.4.1 | 面板存在 | #tool-extract | 存在 |
| 3.4.2 | 音频格式 | #extract-format | 有 mp3/aac/flac/wav |
| 3.4.3 | 码率模式 | #extract-bitrate-mode | 有 cbr/vbr |
| 3.4.4 | 码率 | #extract-bitrate | 有 64k-320k |
| 3.4.5 | 声道 | #extract-channels | 有 original/stereo/mono |
| 3.4.6 | 采样率 | #extract-sample-rate | 有 original/8000-48000 |
| 3.4.7 | 音量滑块 | #extract-volume | 存在 |
| 3.4.8 | 预设按钮 | high/medium/low | 存在 |
| 3.4.9 | 输出目录 | #extract-output-dir | 存在 |
| 3.4.10 | 输出文件名 | #extract-output-name | 存在 |

### 3.5 视频压缩面板

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.5.1 | 面板存在 | #tool-compress | 存在 |
| 3.5.2 | 压缩预设 | #compress-preset | 有 fast/balanced/quality |
| 3.5.3 | 分辨率 | #compress-resolution | 有 original/1080p/720p/480p |
| 3.5.4 | 输出目录 | #compress-output-dir | 存在 |
| 3.5.5 | 输出文件名 | #compress-output-name | 存在 |

### 3.6 视频裁剪面板

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.6.1 | 面板存在 | #tool-trim | 存在 |
| 3.6.2 | 开始时间 | #trim-start | 存在 |
| 3.6.3 | 结束时间 | #trim-end | 存在 |
| 3.6.4 | 裁剪模式 | #trim-mode | 有 copy/recode |
| 3.6.5 | 时间线 | #trim-timeline | 存在 |
| 3.6.6 | 输出目录 | #trim-output-dir | 存在 |
| 3.6.7 | 输出文件名 | #trim-output-name | 存在 |

### 3.7 字幕工具面板

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.7.1 | 面板存在 | #tool-subtitle | 存在 |
| 3.7.2 | 6 个子 Tab | .subtab-bar button | 6 个 |
| 3.7.3 | 调轴-偏移量 | #subtitle-adjust-offset | 存在 |
| 3.7.4 | 调轴-输出目录 | #subtitle-adjust-output-dir | 存在 |
| 3.7.5 | 调轴-输出文件名 | #subtitle-adjust-output-name | 存在 |
| 3.7.6 | 合并-文件 A | #subtitle-merge-file-a | 存在 |
| 3.7.7 | 合并-文件 B | #subtitle-merge-file-b | 存在 |
| 3.7.8 | 合并-布局 | #subtitle-merge-layout | 有选项 |
| 3.7.9 | 合并-输出目录 | #subtitle-merge-output-dir | 存在 |
| 3.7.10 | 转换-格式 | #subtitle-convert-format | 有 srt/ass/ssa/vtt/sub |
| 3.7.11 | 转换-输出目录 | #subtitle-convert-output-dir | 存在 |
| 3.7.12 | 拆分-规则 | #subtitle-split-rule | 有选项 |
| 3.7.13 | 拆分-正则 | #subtitle-split-regex | 存在 |
| 3.7.14 | 拆分-输出目录 | #subtitle-split-output-dir | 存在 |
| 3.7.15 | 提取-字幕流 | #subtitle-extract-stream | 存在 |
| 3.7.16 | 提取-格式 | #subtitle-extract-format | 有 srt/ass/vtt |
| 3.7.17 | 提取-输出目录 | #subtitle-extract-output-dir | 存在 |
| 3.7.18 | 批量-操作 | #subtitle-batch-operation | 有选项 |
| 3.7.19 | 批量-输出目录 | #subtitle-batch-output-dir | 存在 |

### 3.8 合并面板

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.8.1 | 面板存在 | #tool-merge | 存在 |
| 3.8.2 | 导入文件夹 | #add-folder-btn | 存在 |
| 3.8.3 | 导入文件 | #add-files-btn | 存在 |
| 3.8.4 | 清空列表 | #clear-btn | 存在 |
| 3.8.5 | 输出目录 | #global-output-dir | 存在 |
| 3.8.6 | 输出格式 | #merge-format | 有 mp4/mkv |
| 3.8.7 | 并发数 | #merge-concurrency | 存在 |
| 3.8.8 | 开始按钮 | #global-start-btn | 存在 |
| 3.8.9 | 子标签 | .subtab-bar[data-parent="merge"] | >=3 个 |

### 3.9 设置面板

| # | 用例 | 选择器 | 预期 |
|---|------|--------|------|
| 3.9.1 | 面板存在 | #tool-settings | 存在 |
| 3.9.2 | 主题选择 | #settings-theme | 有 auto/dark/light |
| 3.9.3 | FFmpeg 状态 | #settings-ffmpeg-status | 存在 |
| 3.9.4 | 平台统计 | #platform-stats | 存在 |
| 3.9.5 | 硬件加速 | #hw-accel-info | 存在 |

### 3.10 JS ID 一致性

| # | 用例 | 检查点 | 预期 |
|---|------|--------|------|
| 3.10.1 | subtitle.js ID | 所有 getElementById 调用 | 与 HTML ID 一致 |
| 3.10.2 | bridge.js ID | syncSettingsFromPython 中的 ID | 与 HTML ID 一致 |
| 3.10.3 | settings.js ID | initToolStartButtons 中的 ID | 与 HTML ID 一致 |
| 3.10.4 | 无残留旧 ID | subtitle-offset, subtitle-format 等 | 不存在 |

---

## Phase 4: 前端交互测试 (L4)

### 4.1 面板切换

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 4.1.1 | 切换到 convert | 点击侧栏按钮 | #tool-convert 有 active class |
| 4.1.2 | 切换到 extract | 点击侧栏按钮 | #tool-extract 有 active class |
| 4.1.3 | 切换到 compress | 点击侧栏按钮 | #tool-compress 有 active class |
| 4.1.4 | 切换到 trim | 点击侧栏按钮 | #tool-trim 有 active class |
| 4.1.5 | 切换到 subtitle | 点击侧栏按钮 | #tool-subtitle 有 active class |
| 4.1.6 | 切换到 merge | 点击侧栏按钮 | #tool-merge 有 active class |
| 4.1.7 | 切换到 settings | 点击侧栏按钮 | #tool-settings 有 active class |

### 4.2 字幕工具子 Tab 切换

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 4.2.1 | 切换到合并 Tab | 点击"合并"按钮 | 合并参数面板可见 |
| 4.2.2 | 切换到转换 Tab | 点击"转换"按钮 | 转换参数面板可见 |
| 4.2.3 | 切换到拆分 Tab | 点击"拆分"按钮 | 拆分参数面板可见 |
| 4.2.4 | 切换到提取 Tab | 点击"提取"按钮 | 提取参数面板可见 |
| 4.2.5 | 切换到批量 Tab | 点击"批量"按钮 | 批量参数面板可见 |
| 4.2.6 | 切换回调轴 Tab | 点击"调轴"按钮 | 调轴参数面板可见 |

### 4.3 合并子标签切换

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 4.3.1 | 合并队列 | 点击子标签 | 队列表格可见 |
| 4.3.2 | 待整理 | 点击子标签 | 待整理表格可见 |
| 4.3.3 | 已完整 | 点击子标签 | 已完整表格可见 |
| 4.3.4 | 批量合并 | 点击子标签 | 批量面板可见 |

### 4.4 配置面板交互

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 4.4.1 | 折叠配置面板 | 点击折叠按钮 | 面板隐藏 |
| 4.4.2 | 展开配置面板 | 再次点击 | 面板显示 |
| 4.4.3 | 手风琴切换 | 点击卡片头部 | 卡片展开/折叠 |

---

## Phase 5: 联调测试 (L5)

### 5.1 格式转换联调

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 5.1.1 | 添加文件→转换 | 拖入 mp4，选 mkv，点开始 | 任务完成，输出 .mkv |
| 5.1.2 | 流复制模式 | 选 copy 模式 | 快速完成（秒级） |
| 5.1.3 | 重编码模式 | 选 recode 模式 | 正常完成 |
| 5.1.4 | 进度显示 | 转换过程中 | 进度条更新 |
| 5.1.5 | 完成状态 | 转换完成后 | 状态显示"✅ 完成" |

### 5.2 音频提取联调

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 5.2.1 | 提取 MP3 | 添加视频，选 mp3，点开始 | 输出 .mp3 |
| 5.2.2 | 预设应用 | 点击 high 预设 | 码率/采样率/声道更新 |
| 5.2.3 | 音量调节 | 调整音量滑块 | 输出音量变化 |

### 5.3 视频压缩联调

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 5.3.1 | 快速压缩 | 选 fast 预设，点开始 | 输出 _compressed.mp4 |
| 5.3.2 | 降分辨率 | 选 720p | 输出分辨率 1280x? |

### 5.4 视频裁剪联调

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 5.4.1 | 快速裁剪 | 输入时间，选 copy，点开始 | 输出 _trimmed.mp4 |
| 5.4.2 | 精确裁剪 | 选 recode 模式 | 精确到帧 |

### 5.5 字幕工具联调

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 5.5.1 | 调轴 | 添加 srt，输入 +2.5s，点开始 | 输出时间轴偏移 |
| 5.5.2 | 转换 | 添加 srt，选 ass，点开始 | 输出 .ass |
| 5.5.3 | 合并 | 选两个文件，选布局，点开始 | 输出双语字幕 |
| 5.5.4 | 拆分 | 添加双语 srt，点开始 | 输出两个文件 |
| 5.5.5 | 从视频提取 | 添加含字幕的视频 | 输出 .srt |

### 5.6 设置持久化联调

| # | 用例 | 操作 | 预期 |
|---|------|------|------|
| 5.6.1 | 修改设置→重启 | 改格式为 mkv，重启应用 | 设置保留 mkv |
| 5.6.2 | 工作区状态 | 添加任务，重启 | 任务列表恢复 |
| 5.6.3 | 主题切换 | 切换到亮色，重启 | 主题保留亮色 |

---

## Phase 6: Bug 验证测试 (L6)

| # | Bug | 验证方法 | 预期（修复后） |
|---|-----|---------|--------------|
| 6.1 | Hash 路由缺少 subtitle | 导航到 #subtitle | 面板切换正常 |
| 6.2 | initSettingsPanel 引用不存在的 ID | 检查控制台无报错 | 无 ReferenceError |
| 6.3 | selectOutputDir 重复导出 | 检查 window.selectOutputDir | 函数存在且正常 |
| 6.4 | global-start-btn 读取不存在的 ID | 检查合并启动 | 正常启动 |
| 6.5 | 工具按钮读 DOM 而非 Alpine | 修改 Alpine store 值，点开始 | 使用最新值 |
| 6.6 | action-bar 响应式问题 | 添加/移除文件 | 按钮状态更新 |
| 6.7 | subtitle-adjust-segments 无 JS 调用 | 检查 API 是否可用 | API 存在（可选修复） |
| 6.8 | showToastWithAction 闭包问题 | 传入复杂函数 | 不报错 |
| 6.9 | 裁剪模式 recode 不触发精确 | 选 recode，检查输出 | 精确裁剪 |
| 6.10 | 字幕合并 vertical 不匹配 | 选 vertical 布局 | 同 top_bottom |

---

## 测试文件准备

| 文件 | 用途 | 生成方式 |
|------|------|---------|
| test_video.mp4 | 3 秒测试视频（含音频） | FFmpeg testsrc + sine |
| test_audio.aac | 纯音频文件 | FFmpeg sine |
| test.srt | 测试字幕（2 条） | 手写 |
| test_b.srt | 第二个测试字幕 | 手写 |
| test_dual.srt | 双语字幕（奇偶行不同语言） | 手写 |
| test.mkv | MKV 格式视频 | FFmpeg 生成 |
| test_embedded.mp4 | 含内嵌字幕的视频 | FFmpeg 添加字幕流 |

---

## 执行顺序

1. 生成测试文件
2. Phase 1: 后端单元测试
3. Phase 2: 服务层集成测试
4. 启动应用
5. Phase 3: 前端 DOM 测试
6. Phase 4: 前端交互测试
7. Phase 5: 联调测试
8. Phase 6: Bug 验证测试
9. 生成测试报告
10. 提交
