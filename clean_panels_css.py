import re

with open('src/fisheep_video_merger/ui/web/style.css', 'r', encoding='utf-8', errors='ignore') as f:
    css = f.read()

# Patterns for blocks to remove
blocks = [
    r'\.tool-panel\s*\{[^}]*\}',
    r'\.tool-panel\.active\s*\{[^}]*\}',
    r'\.tool-header\s*\{[^}]*\}',
    r'\.tool-header\s*h2\s*\{[^}]*\}',
    r'\.tool-header\s*\.subtitle\s*\{[^}]*\}',
    r'\.header-actions\s*\{[^}]*\}',
    r'\.global-config-panel\s*\{[^}]*\}',
    r'\.workspace-grid\.panel-collapsed\s*\.global-config-panel\s*\{[^}]*\}',
    r'\.workspace-grid\.panel-collapsed\s*\.center-workspace\s*\{[^}]*\}',
    r'\.workspace-grid\s*\{[^}]*\}',
    r'\.center-workspace\s*\{[^}]*\}'
]

for pattern in blocks:
    css = re.sub(pattern, '', css, flags=re.MULTILINE)

# Clean up multiple empty lines
css = re.sub(r'\n\s*\n\s*\n', '\n\n', css)

# Write back in the same encoding
with open('src/fisheep_video_merger/ui/web/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("More Obsolete CSS blocks removed.")
