import re

with open('src/fisheep_video_merger/ui/web/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Define the new Sidebar HTML
new_sidebar = '''    <div id="app-container" class="grid grid-cols-[auto_1fr_auto] h-screen w-screen relative overflow-hidden text-gray-800 dark:text-gray-100" :class="{ 'sidebar-collapsed': $store.app.sidebarCollapsed }">
        
        <!-- 1. 左侧扁平科技感导航栏 (Sidebar) -->
        <aside class="bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col py-4 transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] z-10 relative" 
               :style="{ width: $store.app.sidebarCollapsed ? '72px' : $store.app.sidebarWidth + 'px', flex: 'none' }"
               :class="{ 'items-center px-0': $store.app.sidebarCollapsed }">
            <!-- 拖拽调整宽度的把手 -->
            <div class="absolute right-[-3px] top-0 bottom-0 w-[6px] cursor-col-resize z-20 hover:bg-primary-500/50 transition-colors opacity-0 hover:opacity-100" @mousedown="window.startSidebarResize($event)"></div>
            
            <div class="flex items-center mb-6 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors rounded-lg mx-3 px-2 py-1" 
                 :class="$store.app.sidebarCollapsed ? 'justify-center mx-0 px-0 w-12 h-12 rounded-full' : ''"
                 title="点击折叠侧栏"
                 @click="$store.app.sidebarCollapsed = !$store.app.sidebarCollapsed">
                <span class="text-2xl transition-transform duration-300 group-hover:scale-110" 
                      :class="$store.app.sidebarCollapsed ? 'mr-0 -scale-x-100' : 'mr-3'">🐑</span>
                <div class="flex flex-col whitespace-nowrap overflow-hidden transition-all duration-300"
                     :class="$store.app.sidebarCollapsed ? 'opacity-0 max-w-0 pointer-events-none' : 'opacity-100 max-w-[150px]'">
                    <h1 class="text-lg font-bold text-gray-900 dark:text-white leading-tight tracking-tight">Fisheep</h1>
                    <span class="text-[10px] bg-primary-500/10 text-primary-600 dark:text-primary-400 px-1.5 py-0.5 rounded uppercase font-semibold w-fit mt-0.5">v0.6.0 工具箱</span>
                </div>
            </div>

            <nav class="flex flex-col flex-1 px-3 space-y-1 overflow-y-auto w-full">
                <template x-for="btn in [
                    { id: 'merge', icon: '🔗', name: '音视频合并' },
                    { id: 'convert', icon: '🔄', name: '格式转换' },
                    { id: 'extract', icon: '🎵', name: '提取音频' },
                    { id: 'compress', icon: '📦', name: '视频压缩' },
                    { id: 'trim', icon: '✂️', name: '视频裁剪' }
                ]" :key="btn.id">
                    <button class="flex items-center w-full px-3 py-2.5 rounded-lg text-sm transition-colors group"
                            :class="[
                                $store.app.currentTool === btn.id ? 'bg-white dark:bg-gray-800 text-primary-600 dark:text-primary-400 font-medium shadow-sm ring-1 ring-gray-200 dark:ring-gray-700' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200',
                                $store.app.sidebarCollapsed ? 'justify-center px-0' : ''
                            ]"
                            @click="$store.app.currentTool = btn.id; window.location.hash = btn.id">
                        <span class="text-xl flex-shrink-0 transition-transform duration-300 group-hover:scale-110" 
                              :class="[
                                  $store.app.currentTool === btn.id ? 'scale-110' : '',
                                  $store.app.sidebarCollapsed ? 'mr-0' : 'mr-3'
                              ]" x-text="btn.icon"></span>
                        <span class="whitespace-nowrap overflow-hidden transition-all duration-300" 
                              :class="$store.app.sidebarCollapsed ? 'opacity-0 max-w-0 pointer-events-none' : 'opacity-100 max-w-[150px]'"
                              x-text="btn.name"></span>
                    </button>
                </template>
            </nav>

            <div class="px-3 py-2 mt-auto w-full border-t border-gray-200 dark:border-gray-800 flex flex-col space-y-1">
                <button class="flex items-center w-full px-3 py-2.5 rounded-lg text-sm transition-colors group text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200"
                        :class="[
                            $store.app.currentTool === 'settings' ? 'bg-white dark:bg-gray-800 text-primary-600 dark:text-primary-400 font-medium shadow-sm ring-1 ring-gray-200 dark:ring-gray-700' : '',
                            $store.app.sidebarCollapsed ? 'justify-center px-0' : ''
                        ]"
                        @click="$store.app.currentTool = 'settings'; window.location.hash = 'settings'">
                    <span class="text-xl flex-shrink-0 transition-transform duration-300 group-hover:scale-110"
                          :class="[
                              $store.app.currentTool === 'settings' ? 'scale-110' : '',
                              $store.app.sidebarCollapsed ? 'mr-0' : 'mr-3'
                          ]">⚙️</span>
                    <span class="whitespace-nowrap overflow-hidden transition-all duration-300" 
                          :class="$store.app.sidebarCollapsed ? 'opacity-0 max-w-0 pointer-events-none' : 'opacity-100 max-w-[150px]'">设置</span>
                </button>
                <div class="flex items-center px-3 py-2 mt-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors w-full"
                     :class="$store.app.sidebarCollapsed ? 'justify-center px-0' : 'justify-between'">
                    <span class="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap overflow-hidden transition-all duration-300"
                          :class="$store.app.sidebarCollapsed ? 'opacity-0 max-w-0 pointer-events-none' : 'opacity-100 max-w-[150px]'">🌓 主题</span>
                    <button id="theme-switch-btn" class="w-8 h-8 rounded-full flex items-center justify-center bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 shadow-sm text-sm hover:scale-105 transition-transform flex-shrink-0">🌙</button>
                </div>
            </div>
        </aside>

        <!-- 2. 右侧主工作区 (Main Work Area) -->
        <div class="flex-1 flex flex-col min-w-0 h-full relative" :class="{ 'panel-collapsed': $store.app.configPanelCollapsed || $store.app.currentTool !== 'merge' }">
            <main class="flex-1 flex flex-col overflow-hidden transition-all duration-300" :style="{ paddingRight: ($store.app.configPanelCollapsed && $store.app.currentTool === 'merge') ? '48px' : '0' }">'''

# We need to replace from `<div id="app-container" ...` to `<main class="center-workspace" ...>`
start_marker = r'<div id="app-container"[^>]*>'
end_marker = r'<main class="center-workspace"[^>]*>'

pattern = re.compile(start_marker + r'.*?' + end_marker, re.DOTALL)
new_html = pattern.sub(new_sidebar, html)

with open('src/fisheep_video_merger/ui/web/index.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print("Sidebar replaced with Tailwind CSS version using Alpine x-for.")
