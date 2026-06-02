import re

with open('src/fisheep_video_merger/ui/web/style.css', 'r', encoding='utf-8', errors='ignore') as f:
    css = f.read()

# Patterns for blocks to remove
blocks = [
    r'\.app-layout\s*\{[^}]*\}',
    r'/\*\s*===\s*4\.\s*左侧科技导航栏\s*\(Sidebar\)\s*===\s*\*/\s*\.sidebar\s*\{[^}]*\}',
    r'\.sidebar-resizer\s*\{[^}]*\}',
    r'\.sidebar-resizer:hover\s*\{[^}]*\}',
    r'\.logo-area\s*\{[^}]*\}',
    r'\.logo-emoji\s*\{[^}]*\}',
    r'\.logo-text\s*\{[^}]*\}',
    r'\.logo-text\s*h1\s*\{[^}]*\}',
    r'\.version-tag\s*\{[^}]*\}',
    r'\.nav-links\s*\{[^}]*\}',
    r'\.nav-btn\s*\{[^}]*\}',
    r'\.nav-btn:hover\s*\{[^}]*\}',
    r'\.nav-btn\.active\s*\{[^}]*\}',
    r'\.nav-icon\s*\{[^}]*\}',
    r'\.nav-text\s*\{[^}]*\}',
    r'\.sidebar-footer\s*\{[^}]*\}',
    r'\.theme-toggle-area\s*\{[^}]*\}',
    r'\.theme-label\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.theme-toggle-area\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.logo-emoji\s*\{[^}]*\}',
    r'\.logo-area:hover\s*\.logo-emoji\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.logo-area:hover\s*\.logo-emoji\s*\{[^}]*\}',
    r'\.icon-toggle\s*\{[^}]*\}',
    r'\.icon-toggle:hover\s*\{[^}]*\}',
    
    # Also remove empty-state from earlier
    r'\.empty-state-row\s*td\s*\{[^}]*\}',
    r'\.data-table\s*tbody\s*tr\.empty-state-row:hover\s*\{[^}]*\}',
    r'\.empty-state\s*\{[^}]*\}',
    r'\.empty-icon\s*\{[^}]*\}',
    r'\.empty-state\s*h3\s*\{[^}]*\}',
    r'\.empty-state\s*p\s*\{[^}]*\}',
    
    # And collapsed states inside media queries
    r'\.sidebar\.collapsed\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.logo-text,\s*\.sidebar\.collapsed\s*\.nav-text,\s*\.sidebar\.collapsed\s*\.theme-label\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.logo-area\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.nav-btn\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.sidebar-footer\s*\.nav-btn\s*\{[^}]*\}',
    r'\.sidebar\.collapsed\s*\.sidebar-footer\s*\.nav-text\s*\{[^}]*\}'
]

for pattern in blocks:
    css = re.sub(pattern, '', css, flags=re.MULTILINE)

# Clean up multiple empty lines
css = re.sub(r'\n\s*\n\s*\n', '\n\n', css)

# Write back in the same encoding
with open('src/fisheep_video_merger/ui/web/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Obsolete CSS blocks removed.")
