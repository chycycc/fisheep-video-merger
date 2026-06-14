# 01 - 删除 app.js 遗留单体

Status: ready-for-agent

## 目标
消除双重 Alpine store 注册，删除 2383 行未使用的遗留代码。

## 涉及文件
- `ui/web/app.js` — 删除
- `index.html` — 确认无引用

## 预期变更
1. 确认 index.html 不引用 app.js
2. git rm app.js

## 验证方式
1. 启动应用
2. 切换所有工具面板（合并/转换/提取/压缩/裁剪/音频转换/音频裁剪/字幕）
3. 拖入文件到任意工具
4. 确认 Alpine store 正确（7个工具设置都有）
