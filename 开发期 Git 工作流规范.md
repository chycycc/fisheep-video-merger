开发时的 Git 规范，指的是在日常编码过程中，如何管理分支、提交代码、同步更新以及合并代码的一系列约定。下面我整理一份实用的 **开发期 Git 工作流规范**，帮助团队高效协作、避免历史混乱。

---

## 一、分支管理

### 1. 主分支保护
- **`master` / `main`** 始终保持稳定，**禁止直接提交**。  
- 所有开发都在分支上进行，通过合并请求（MR/PR）合并到主分支。

### 2. 分支命名
- **功能分支**：`feat/功能描述`（如 `feat/major-management`）  
- **修复分支**：`fix/问题描述`（如 `fix/login-error`）  
- **热修复分支**：`hotfix/紧急问题`（从主分支拉出，修复后合并回主分支和开发分支）  
- **命名规则**：全小写，单词用短横线 `-` 分隔，描述简洁明确。

### 3. 分支生命周期
- 从最新的主分支创建功能分支。
- 开发完成后，通过 MR/PR 合并回主分支，**合并后删除功能分支**（本地 + 远程）。

---

## 二、代码提交规范

### 1. 提交频率
- **完成一个逻辑单元即可提交**，不要攒一大堆代码再提交。  
- 建议 **每天至少提交一次**，保持进度可追溯。

### 2. 提交颗粒度
- 每次提交只做一件事：一个功能点、一个 Bug 修复、一次重构。  
- 避免在同一个提交中混杂多种无关改动。

### 3. 提交前检查
- **本地自测通过**（编译、单元测试）。  
- 使用 `git status` 确认没有误提交临时文件（如 `.idea`、`node_modules`）。  
- 使用 `git diff --cached` 检查即将提交的变更是否符合预期。

### 4. 提交消息
按之前整理的 **Conventional Commits** 规范填写，便于生成 Changelog 和追溯。

---

## 三、同步规范

### 1. 开始新功能前
```bash
git checkout master
git pull origin master
git checkout -b feat/xxx
```

### 2. 开发过程中
- **定期拉取主分支更新**，避免最终合并时冲突过大：  
  ```bash
  git checkout master
  git pull origin master
  git checkout feat/xxx
  git merge master   # 或 git rebase master
  ```
- 推荐使用 `git merge master`，保持历史清晰，避免 `rebase` 带来的风险（尤其是分支已推送远程）。

### 3. 推送分支
- 功能开发完成后，推送分支到远程：  
  ```bash
  git push origin feat/xxx
  ```

---

## 四、合并规范

### 1. 创建合并请求（MR/PR）
- 在平台上创建 MR/PR，目标分支为 `master`。  
- 填写清晰的标题和描述（包含改动内容、测试方式、影响范围）。  
- 指定至少一名审查者。

### 2. 代码审查
- 审查者检查代码质量、规范、逻辑正确性。  
- 如有修改意见，作者在功能分支上继续提交，MR/PR 会自动更新。

### 3. 合并方式
- **推荐使用 “Merge commit”**（保留完整分支历史），避免使用 “Squash and merge”（除非团队约定）。  
- 合并时**可修改合并提交消息**，让历史更清晰（如 `feat(major): 合并专业管理功能`）。

### 4. 合并后操作
```bash
git checkout master
git pull origin master
git branch -d feat/xxx               # 删除本地分支
git push origin --delete feat/xxx    # 删除远程分支
```

---

## 五、禁止事项

| 禁止操作                       | 原因                                                         |
| ------------------------------ | ------------------------------------------------------------ |
| **直接向 `master` 提交**       | 绕过审查，破坏稳定性                                         |
| **使用 `git push --force`**    | 覆盖远程历史，导致协作者丢失提交（除非是个人分支且明确需要） |
| **长期不拉取主分支更新**       | 合并时冲突爆炸，难以解决                                     |
| **一次提交包含多个不相关功能** | 回滚困难，审查复杂                                           |
| **提交未测试的代码**           | 引入 Bug，影响团队                                           |

---

## 六、工具辅助建议

- **Pre-commit 钩子**：使用 `husky` + `lint-staged` 在提交前自动格式化代码、运行测试。  
- **Commitizen**：用 `git cz` 替代 `git commit`，交互式生成规范消息。  
- **IDEA 集成**：在 IDEA 中配置 Git 操作快捷键，使用可视化 Merge 工具解决冲突。

---

## 七、常见场景流程示例

### 场景：开始一个新功能
```bash
git checkout master
git pull origin master
git checkout -b feat/major-crud
# 开发...
git add .
git commit -m "feat(major): 添加专业列表查询"
# 继续开发...
git push origin feat/major-crud
# 创建 MR，等待审查
```

### 场景：主分支有新代码，需要同步到功能分支
```bash
git checkout master
git pull origin master
git checkout feat/major-crud
git merge master
# 解决冲突（若有）
git push origin feat/major-crud
```

### 场景：合并完成，清理分支
```bash
# MR 合并后
git checkout master
git pull origin master
git branch -d feat/major-crud
git push origin --delete feat/major-crud
```

---

## 八、版本与发布管理（轻量级 Git Flow）

针对我们的中小型独立或双人迭代项目，推荐使用轻量级的 **“双主分支 + 质检发布分支”** 模型。这套模型可以完美衔接从 `v0.1.0` 雏形到 `v0.2.0` 成熟期的平滑跃迁。

### 1. 三剑客分支的终身使命

| 分支角色 | 代表场景 | 状态特质 | 什么时候推送/更新？ |
| :--- | :--- | :--- | :--- |
| **`dev`** | **日常施工工地 🚧** | 功能激进但偶有瑕疵 | **高频**。每完成一个打勾小任务，就 push 一次。 |
| **`release/vX.X.X`** | **出厂前总质检车间 📦** | 冻结新功能，仅做捉虫与改号 | **功能封版（Feature Freeze）时**。从 `dev` 拉出来做最后打磨。 |
| **`main` / `master`** | **样板间与交钥匙区 🔑** | 100% 绝对稳定，对外分发 | **版本发布时**。从 `release` 合入，象征着伟大的里程碑。 |

### 2. 版本升华的三大硬核关卡（触发条件）

*   **关卡 A：【创建 release/vX.X.X 的时机】**
    *   **条件**：迭代路线图中的功能已全部开发完毕（如 Phase 8 完成打勾），项目成员达成共识：**本次绝对不再塞入新功能（冻结功能）**。
*   **关卡 B：【合并入 main / master 的时机】**
    *   **条件**：完成了全局链路跑通测试（冒烟测试），证明**无恶性闪退、无破坏性交互逻辑漏洞**。由产品核心决策者下达正式发布指令。
*   **关卡 C：【打上历史丰碑（Version Tag）的时机】**
    *   **条件**：代码刚刚风光大嫁进 `main` 分支，在此刻立刻打上带语义的标签（如 `v0.2.0`），永冻历史状态。

### 3. 实战演习：如何打通 `v0.2.0` 的发布神路（完整命令）

当您觉得我们在 `dev` 上的打磨已经足够，准备向全世界公布 `v0.2.0` 时，按照以下黄金序列，在终端顺序执行命令：

#### 🏃‍♂️ 步骤 1：功能封版，建立质检分支
```bash
# 确保在最新的开发分支上
git checkout dev
git pull origin dev

# 瞬间拉出 v0.2.0 的专职质检车间
git checkout -b release/v0.2.0
```

#### 🧪 步骤 2：进行微调（如果需要）
在此分支下进行最终的界面微调、版本号常量修改。改完后做最后一次提交：
```bash
git add .
git commit -m "chore(release): 升级软件版本文字至 0.2.0 并完成最终修饰"
```

#### 🏆 步骤 3：大兵压境，合流 `main` 分支
```bash
# 1. 如果本地还没有 main 分支，就新建一个（仅限首次）：
git checkout -b main

# 2. 如果本地已经有 main，直接切过去：
git checkout main

# 3. 把完美的质检车间代码彻底融进样板间
git merge release/v0.2.0

# 4. 在 GitHub 远程服务器挂牌营业，推送 main
git push -u origin main
```

#### 🏷️ 步骤 4：雕刻不朽丰碑（打上 Version Tag）
这一步会在 GitHub 的 Releases 页面自动创建一个历史快照点：
```bash
# 本地打上具有里程碑意义的标签
git tag -a v0.2.0 -m "正式发布 v0.2.0: 极速美化、折叠侧栏与全套交互解禁版"

# 将标签神圣地发射上天（GitHub）
git push origin v0.2.0
```

#### 🧹 步骤 5：功成身退，回馈 `dev` 并切回工地
```bash
# 把刚才质检分支顺手修好的 bug 合并回开发分支
git checkout dev
git merge release/v0.2.0
git push origin dev

# 安全铲除功成身退的质检分支
git branch -d release/v0.2.0
```

---

这套规范完美对接了我们从 `dev` 的频繁打磨到 `main` 的高光发布的整套仪式感。建议您把这个文件永久保存在本地，当作您的 Git 工作流手抄本。未来当我们要面向公众交付我们的 `fisheep-video-merger` 大成之作时，这套流程就是我们最坚实的守护神！🛡️🐑