"""
共享常量
消除 core 模块间的重复定义
"""

# 音频格式 → FFmpeg 编码器映射
FORMAT_AUDIO_CODEC = {
    "mp3": "libmp3lame",
    "aac": "aac",
    "flac": "flac",
    "wav": "pcm_s16le",
    "opus": "libopus",
    "ogg": "libvorbis",
    "m4a": "aac",
    "wma": "wmav2",
}
