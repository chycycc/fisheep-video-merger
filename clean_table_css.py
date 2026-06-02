import re

with open('src/fisheep_video_merger/ui/web/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Remove .data-table rules block
css = re.sub(r'/\* 表格样式 \(Data Table\) \*/.*?(?=/\* === 9\. 合并工具工作区与配置面板 === \*/)', '', css, flags=re.DOTALL)

# Remove active row rules
css = re.sub(r'\.data-table tbody tr\.active-row td \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table tbody tr\.active-row td:first-child \{.*?\n\}', '', css, flags=re.DOTALL)

with open('src/fisheep_video_merger/ui/web/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Cleaned up style.css")
