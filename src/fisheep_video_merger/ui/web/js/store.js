// 使用 Web Components 注册通用 UI 模块
export async function registerComponents() {
    try {
        // 并行拉取组件 HTML
        const [dropRes, listRes, actionRes, batchRes] = await Promise.all([
            fetch('components/file_drop_area.html'),
            fetch('components/task_list.html'),
            fetch('components/action_bar.html'),
            fetch('components/batch_panel.html')
        ]);

        const dropHtml = dropRes.ok ? await dropRes.text() : '';
        const listHtml = listRes.ok ? await listRes.text() : '';
        const actionHtml = actionRes.ok ? await actionRes.text() : '';
        const batchHtml = batchRes.ok ? await batchRes.text() : '';

        // 定义 Web Components
        class FileDropArea extends HTMLElement {
            connectedCallback() { this.innerHTML = dropHtml; }
        }
        class TaskList extends HTMLElement {
            connectedCallback() { this.innerHTML = listHtml; }
        }
        class ActionBar extends HTMLElement {
            connectedCallback() { this.innerHTML = actionHtml; }
        }
        class BatchPanel extends HTMLElement {
            connectedCallback() { this.innerHTML = batchHtml; }
        }

        customElements.define('file-drop-area', FileDropArea);
        customElements.define('task-list', TaskList);
        customElements.define('action-bar', ActionBar);
        customElements.define('batch-panel', BatchPanel);
        
        console.log("[Fisheep] Web Components 注册完成!");
    } catch (e) {
        console.error("组件加载失败", e);
    }
}
