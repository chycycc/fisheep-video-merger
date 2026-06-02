import re

with open('src/fisheep_video_merger/ui/web/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Button mappings
btn_secondary = "px-4 py-2 rounded-lg text-[13px] font-semibold cursor-pointer inline-flex items-center justify-center gap-2 min-h-[36px] transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] bg-gray-50/75 dark:bg-gray-800/75 border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 hover:border-primary-500 hover:bg-gray-100 dark:hover:bg-gray-800"
btn_danger = "px-4 py-2 rounded-lg text-[13px] font-semibold cursor-pointer inline-flex items-center justify-center gap-2 min-h-[36px] transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] bg-red-500/15 border border-red-500/30 text-red-500 hover:bg-red-500 hover:border-red-500 hover:text-white"
btn_primary = "px-4 py-2 rounded-lg text-[13px] font-semibold cursor-pointer inline-flex items-center justify-center gap-2 min-h-[36px] transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] bg-primary-500 text-white hover:bg-primary-600 shadow-sm border border-primary-600/20"
btn_plain = "px-3.5 py-1.5 rounded-md text-xs text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white transition-colors"

# Subtab buttons need active state
html = re.sub(r'class="btn"\s+data-subtab="([^"]+)"', r'class="' + btn_plain + r'" :class="{ \'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm ring-1 ring-gray-200 dark:ring-gray-700\': $store.app.currentSubtab === \'\1\' }" data-subtab="\1"', html)

# Replace other buttons
html = html.replace('class="btn btn-secondary btn-block"', f'class="{btn_secondary} w-full"')
html = html.replace('class="btn btn-primary btn-block"', f'class="{btn_primary} w-full"')
html = re.sub(r'class="btn btn-secondary\s*(preset-btn)?\s*(active)?"', f'class="{btn_secondary} \\1 \\2"', html)
html = html.replace('class="btn btn-danger"', f'class="{btn_danger}"')

mini_action = "inline-flex items-center justify-center w-[34px] h-[34px] rounded-md bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 cursor-pointer mx-[1px] hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors shadow-sm text-xs"
html = html.replace('class="mini-action-btn"', f'class="{mini_action}"')

# Forms
html = html.replace('class="form-group"', 'class="flex flex-col gap-2 mb-4"')
html = html.replace('class="input-with-action"', 'class="flex gap-2"')

input_class = "w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md px-3 py-2 text-[13px] text-gray-800 dark:text-gray-100 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all"
html = re.sub(r'<input([^>]*?)type="(text|number)"([^>]*?)class="([^"]*)"', r'<input\1type="\2"\3class="\4 ' + input_class + '"', html)
html = re.sub(r'<input([^>]*?)type="(text|number)"((?:(?!class=).)*?)>', r'<input\1type="\2" class="' + input_class + r'"\3>', html)

html = re.sub(r'<select([^>]*?)class="([^"]*)"', r'<select\1class="\2 ' + input_class + '"', html)
html = re.sub(r'<select((?:(?!class=).)*?)>', r'<select class="' + input_class + r'"\1>', html)

with open('src/fisheep_video_merger/ui/web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Buttons and form fields updated!")
