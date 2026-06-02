import re

with open('src/fisheep_video_merger/ui/web/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Replace `<main class="flex-1 flex flex-col min-w-0 h-full overflow-hidden transition-all duration-300"...>`
# Add px-6 py-6 so that we don't need .center-workspace padding.
html = re.sub(
    r'<main class="flex-1 flex flex-col min-w-0 h-full overflow-hidden transition-all duration-300"',
    r'<main class="flex-1 flex flex-col min-w-0 h-full overflow-hidden transition-all duration-300 p-6"',
    html
)

# 2. Replace `<div class="tool-panel" id="([^"]+)" :class="\{ 'active': ([^\}]+) \}">`
# Notice we want to use flex-col for active, hidden otherwise.
def replace_tool_panel(match):
    id_val = match.group(1)
    cond = match.group(2).strip()
    return f'<div id="{id_val}" class="h-full w-full relative" :class="{cond} ? \'flex flex-col overflow-y-auto\' : \'hidden\'">'

html = re.sub(r'<div class="tool-panel"\s+id="([^"]+)"\s+:class="\{\s*\'active\':\s*([^\}]+)\s*\}">', replace_tool_panel, html)

# 3. Replace `<header class="tool-header">`
html = html.replace('<header class="tool-header">', '<header class="flex justify-between items-center mb-6 flex-wrap gap-4">')

# 4. Replace `<h2>` inside tool-header (we can just replace all `<h2>` that come after `<header...`)
# Better yet, regex replace `<h2>` and `<p class="subtitle">`
html = re.sub(r'<h2>(.*?)</h2>', r'<h2 class="font-[\'Outfit\'] text-2xl font-bold text-gray-900 dark:text-white">\1</h2>', html)
html = re.sub(r'<p class="subtitle">(.*?)</p>', r'<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">\1</p>', html)

# 5. Replace `<div class="header-actions">`
html = html.replace('<div class="header-actions">', '<div class="flex gap-3 flex-wrap">')

# 6. Global Config Panel
# <aside class="global-config-panel"
global_panel_classes = "bg-gray-50 dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-row relative transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
html = html.replace('<aside class="global-config-panel"', f'<aside class="{global_panel_classes}"')

with open('src/fisheep_video_merger/ui/web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("tool-panel, tool-header, and global-config-panel refactored.")
