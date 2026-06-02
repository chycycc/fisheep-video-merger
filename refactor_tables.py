import re
import os

TABLE_CLASS = 'w-full border-collapse text-left text-[13px] data-table'
TH_CLASS = 'bg-gray-50 dark:bg-[#1a1b26] text-gray-800 dark:text-gray-200 font-bold px-4 py-3.5 border-b-2 border-gray-200 dark:border-[#23273D] sticky top-0 z-10 whitespace-nowrap'
TD_CLASS = 'px-4 py-3.5 border-b border-gray-100 dark:border-[#23273D] align-middle text-gray-700 dark:text-gray-300 font-medium whitespace-nowrap'
TR_CLASS = 'transition-colors duration-150 ease-in-out hover:bg-white dark:hover:bg-[#151621] even:bg-black/[0.015] dark:even:bg-white/[0.005] group data-table-row'

def process_html_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    # Replace table class
    html = re.sub(r'class="data-table([^"]*)"', f'class="{TABLE_CLASS}\\1"', html)

    # Add th class
    html = re.sub(r'<th(\s|>| width="[^"]*">)', f'<th class="{TH_CLASS}"\\1', html)
    # Fix if there was already a class (edge case)
    # In this app, th don't have classes yet.

    # For tr in thead, just leave them as <tr>
    # For tr in tbody, add TR_CLASS
    
    # We will just inject TR_CLASS to all tr except in thead, or those with empty-state-row
    # We can do a simple replacement for specific known TRs:
    html = re.sub(r'<tr :id="\'queue-row-\' \+ index"', f'<tr :id="\'queue-row-\' + index" class="{TR_CLASS}"', html)
    html = re.sub(r'<tr @click="window.loadPreviewForFile\(item.filepath\)" style="cursor: pointer;">', f'<tr @click="window.loadPreviewForFile(item.filepath)" class="cursor-pointer {TR_CLASS}">', html)

    # For tds:
    # <td ...> -> <td class="TD_CLASS" ...>
    html = re.sub(r'<td([^>]*)>', f'<td class="{TD_CLASS}"\\1>', html)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

def process_js_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        js = f.read()

    # In main.js, tr is generated:
    # <tr class="${file._status === 'processing' ? 'tool-processing' : ''}">
    js = js.replace(
        '''<tr class="${file._status === 'processing' ? 'tool-processing' : ''}">''',
        f'''<tr class="{TR_CLASS} ${{file._status === 'processing' ? 'tool-processing' : ''}}">'''
    )
    # <td ...> -> <td class="TD_CLASS" ...>
    # Wait, we can just replace <td> and <td width/class...>
    # But carefully:
    js = js.replace('<td>', f'<td class="{TD_CLASS}">')
    js = js.replace('<td width="40">', f'<td width="40" class="{TD_CLASS}">')
    js = js.replace('<td style="font-weight: 600; max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"', f'<td class="{TD_CLASS}" style="font-weight: 600; max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"')
    js = js.replace('<td style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"', f'<td class="{TD_CLASS}" style="font-weight: 600; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"')
    js = js.replace('<td class="tool-status">', f'<td class="tool-status {TD_CLASS}">')
    js = js.replace('<td style="white-space: nowrap;">', f'<td class="{TD_CLASS}">') # it already has whitespace-nowrap in TD_CLASS

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(js)

process_html_file('src/fisheep_video_merger/ui/web/index.html')
process_html_file('src/fisheep_video_merger/ui/web/components/task_list.html')
process_js_file('src/fisheep_video_merger/ui/web/js/main.js')

print("Refactored tables to Tailwind!")
