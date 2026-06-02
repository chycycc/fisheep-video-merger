import re

with open('src/fisheep_video_merger/ui/web/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

css = re.sub(r'\.data-table \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table th \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table td \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table tbody tr \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table tbody tr:nth-child\(even\) \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\[data-theme="dark"\] \.data-table tbody tr:nth-child\(even\) \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table tbody tr:hover \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table tbody tr\.selected \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'\.data-table tbody tr\.active-row \{.*?\n\}', '', css, flags=re.DOTALL)
css = re.sub(r'/\* 表格空状态 \(Empty State\) \*/', '', css)

with open('src/fisheep_video_merger/ui/web/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Removed individual .data-table rules!")
