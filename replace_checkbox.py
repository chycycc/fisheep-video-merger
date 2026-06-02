import re

with open('src/fisheep_video_merger/ui/web/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace checkboxes
checkbox_container = "relative pl-[26px] cursor-pointer text-xs font-medium text-gray-800 dark:text-gray-200 leading-[18px] inline-block group mb-0"
input_checkbox = "peer absolute opacity-0 cursor-pointer h-0 w-0"
checkmark_span = "absolute top-0 left-0 h-[18px] w-[18px] bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded transition-all duration-200 peer-checked:bg-primary-500 peer-checked:border-primary-500 group-hover:border-primary-500 flex items-center justify-center"
inner_dot = '<span class="hidden peer-checked:block w-2 h-2 rounded-sm bg-gray-50 dark:bg-gray-800"></span>'

html = html.replace('class="checkbox-container"', f'class="{checkbox_container}"')
html = re.sub(r'<input([^>]*?)type="checkbox"([^>]*?)>', r'<input\1type="checkbox" class="' + input_checkbox + r'"\2>', html)
html = html.replace('<span class="checkmark"></span>', f'<span class="{checkmark_span}">{inner_dot}</span>')

# Let's also fix config-item
html = html.replace('class="config-item"', 'class="flex flex-col gap-2"')

with open('src/fisheep_video_merger/ui/web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Checkboxes rewritten!")
