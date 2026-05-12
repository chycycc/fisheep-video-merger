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

这套规范覆盖了开发全流程，与之前聊的提交消息、分支命名、合并方式一脉相承。建议团队在 `CONTRIBUTING.md` 中固化，并逐步形成习惯。如果有特殊需求（如版本发布分支、持续集成等），可以在此基础上扩展。