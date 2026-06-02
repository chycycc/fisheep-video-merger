import re

with open('src/fisheep_video_merger/ui/web/style.css', 'r', encoding='utf-8', errors='ignore') as f:
    css = f.read()

# Patterns for blocks to remove
blocks = [
    r'\.checkbox-group\s*\{[^}]*\}',
    r'\.checkbox-container\s*\{[^}]*\}',
    r'\.checkbox-container\s*input\s*\{[^}]*\}',
    r'\.checkmark\s*\{[^}]*\}',
    r'\.checkbox-container:hover\s*input\s*~\s*\.checkmark\s*\{[^}]*\}',
    r'\.checkbox-container\s*input:checked\s*~\s*\.checkmark\s*\{[^}]*\}',
    r'\.checkmark:after\s*\{[^}]*\}',
    r'\.checkbox-container\s*input:checked\s*~\s*\.checkmark:after\s*\{[^}]*\}',
    r'\.checkbox-container\s*\.checkmark:after\s*\{[^}]*\}'
]

for pattern in blocks:
    css = re.sub(pattern, '', css, flags=re.MULTILINE)

# Clean up multiple empty lines
css = re.sub(r'\n\s*\n\s*\n', '\n\n', css)

# Write back in the same encoding
with open('src/fisheep_video_merger/ui/web/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Obsolete Checkbox CSS blocks removed.")
