# Bug 修复记录

## 2026-06-12 修复批次

### Bug 1: ffprobe 命令构造错误导致时长识别失败
- **现象**：所有工具拖入文件后无法识别时长，显示"未知"
- **根因**：`_probe_file` 在 Windows 上构造命令时 `-i` 后面紧跟 `-show_format` 而非文件路径，ffprobe 解析失败返回 None
- **修复**：所有输出选项放前面，`-i <filepath>` 统一放最后
- **文件**：`ffprobe.py`

### Bug 2: get_file_info NoneType 比较报错
- **现象**：提取音频/视频压缩报 `'>' not supported between instances of 'NoneType' and 'int'`
- **根因**：ffprobe 返回的 duration 字段可能是 None（不是 0），`float()` 转换后与 `> 0` 比较崩溃；无流数据时 result 缺少必要字段
- **修复**：`duration = 0.0`；`float()` 包裹 try/except；`data.get("streams") or []` 防御 None；result dict 增加默认字段
- **文件**：`tool_service.py`

### Bug 3: 音频转换/裁剪工具无法识别文件
- **现象**：audio-convert 和 audio-trim 工具拖入或选择文件后无反应
- **根因**：`window.toolFiles` 缺少 `audio-convert` 和 `audio-trim` 键；`initToolDropZones` 未遍历这两个工具；`addFilesToTool` 未给 audio-convert 添加音频扩展名支持
- **修复**：toolFiles 增加键；drop zones 遍历增加；扩展名条件增加 `audio-convert`
- **文件**：`settings.js`

### Bug 4: 文件选择对话框不显示音频文件
- **现象**：点击"添加文件"时看不到 mp3/flac/wav 等音频文件
- **根因**：`select_tool_files` 的 file_types 只包含视频格式
- **修复**：file_types 增加 mp3/aac/flac/wav/opus/ogg/m4a/wma
- **文件**：`dialog_service.py`
