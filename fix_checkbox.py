import re

with open('src/fisheep_video_merger/ui/web/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Current pattern
# <label class="relative pl-[26px] cursor-pointer text-xs font-medium text-gray-800 dark:text-gray-200 leading-[18px] inline-block group mb-0">
#     <input type="checkbox" class="peer absolute opacity-0 cursor-pointer h-0 w-0" x-model="$store.settings.overwrite">
#     <span class="absolute top-0 left-0 h-[18px] w-[18px] bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded transition-all duration-200 peer-checked:bg-primary-500 peer-checked:border-primary-500 group-hover:border-primary-500 flex items-center justify-center"><span class="hidden peer-checked:block w-2 h-2 rounded-sm bg-gray-50 dark:bg-gray-800"></span></span>自动覆盖同名文件
# </label>

pattern = r'<label class="relative pl-\[26px\] cursor-pointer text-xs font-medium text-gray-800 dark:text-gray-200 leading-\[18px\] inline-block group mb-0">\s*<input([^>]*?)>\s*<span class="absolute top-0 left-0[^"]*"><span[^>]*></span></span>([^<]*)\s*</label>'

replacement = r'''<label class="flex items-center gap-2 cursor-pointer group">
    <div class="relative w-[18px] h-[18px] flex-shrink-0">
        <input\1>
        <span class="absolute inset-0 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded transition-all duration-200 peer-checked:bg-primary-500 peer-checked:border-primary-500 group-hover:border-primary-500 flex items-center justify-center">
            <span class="hidden peer-checked:block w-2 h-2 rounded-sm bg-gray-50 dark:bg-gray-800"></span>
        </span>
    </div>
    <span class="text-xs font-medium text-gray-800 dark:text-gray-200 leading-[18px]">\2</span>
</label>'''

html = re.sub(pattern, replacement, html)

with open('src/fisheep_video_merger/ui/web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
