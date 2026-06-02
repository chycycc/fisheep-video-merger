import re

with open('src/fisheep_video_merger/ui/web/style.css', 'r', encoding='utf-8', errors='ignore') as f:
    css = f.read()

# Patterns for blocks to remove
blocks = [
    r'\.btn\s*\{[^}]*\}',
    r'\.btn-secondary\s*\{[^}]*\}',
    r'\.btn-secondary:hover\s*\{[^}]*\}',
    r'\.btn-secondary\.active\s*\{[^}]*\}',
    r'\.btn-danger\s*\{[^}]*\}',
    r'\.btn-danger:hover\s*\{[^}]*\}',
    r'\.btn-block\s*\{[^}]*\}',
    r'\.btn:active\s*\{[^}]*\}',
    r'\.mini-action-btn\s*\{[^}]*\}',
    r'\.mini-action-btn:hover\s*\{[^}]*\}',
    r'\.subtab-bar\s*\.btn\s*\{[^}]*\}',
    r'\.subtab-bar\s*\.btn:hover\s*\{[^}]*\}',
    r'\.subtab-bar\s*\.btn\.active\s*\{[^}]*\}',
    r'\.form-group\s*\{[^}]*\}',
    r'\.form-group\s*label\s*\{[^}]*\}',
    r'input\[type="text"\],\s*input\[type="number"\],\s*select\s*\{[^}]*\}',
    r'input\[type="text"\]:focus,\s*input\[type="number"\]:focus,\s*select:focus\s*\{[^}]*\}',
    r'\.input-with-action\s*\{[^}]*\}'
]

for pattern in blocks:
    css = re.sub(pattern, '', css, flags=re.MULTILINE)

# Clean up multiple empty lines
css = re.sub(r'\n\s*\n\s*\n', '\n\n', css)

# Write back in the same encoding
with open('src/fisheep_video_merger/ui/web/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Obsolete Button and Form CSS blocks removed.")
