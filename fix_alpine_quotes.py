import re

with open('src/fisheep_video_merger/ui/web/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix the escaped quotes
html = html.replace("\\'bg-white", "'bg-white")
html = html.replace("\\':", "':")
html = html.replace("=== \\'", "=== '")
html = html.replace("\\' }", "' }")

with open('src/fisheep_video_merger/ui/web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
