# Day 69：Claude Code Skills 教程

> 学习目标：理解 Claude Code Skills 解决的问题——把重复出现的多步骤任务封装成可复用、可被自动匹配触发的"playbook"；掌握 SKILL.md 的文件结构（frontmatter + 正文 + references 子目录）；以本仓库实际在用的 `day-note-sync` skill 为例拆解真实设计；动手写一个最小 Skill 并验证触发
>
> 📚 所属阶段：**深化阶段 · 补充篇（技能查缺补漏）**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) 第七节 · Day 69
>
> 🧭 导航：[← Day 68 · FastAPI 后端工程](day68_fastapi_backend.md) ｜ 补充篇 · 技能查缺补漏（不计入 Day 31–67 主线，后续按需追加）

---

## 目录

- [一、Claude Code Skills 解决什么问题](#一claude-code-skills-解决什么问题)
  - [1.1 和斜杠命令的区别](#11-和斜杠命令的区别)
  - [1.2 和 CLAUDE.md 的区别](#12-和-claudemd-的区别)
  - [1.3 本仓库的真实例子：day-note-sync](#13-本仓库的真实例子day-note-sync)
- [二、Skill 的文件结构](#二skill-的文件结构)
  - [2.1 SKILL.md 的 frontmatter](#21-skillmd-的-frontmatter)
  - [2.2 description 字段的关键作用](#22-description-字段的关键作用)
  - [2.3 references 子目录：延迟加载的详细文档](#23-references-子目录延迟加载的详细文档)
- [三、Skill 是怎么被触发的](#三skill-是怎么被触发的)
  - [3.1 显式触发：斜杠命令](#31-显式触发斜杠命令)
  - [3.2 隐式匹配：按 description 语义自动调用](#32-隐式匹配按-description-语义自动调用)
  - [3.3 项目级 vs 个人级 Skill](#33-项目级-vs-个人级-skill)
- [四、拆解一个真实 Skill：day-note-sync](#四拆解一个真实-skillday-note-sync)
- [五、动手写一个最小 Skill](#五动手写一个最小-skill)
- [六、Skill vs Subagent vs 普通 Prompt 的选型](#六skill-vs-subagent-vs-普通-prompt-的选型)
- [七、Day 69 知识速查](#七day-69-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步](#九下一步)

---

## 一、Claude Code Skills 解决什么问题

### 1.1 和斜杠命令的区别

Claude Code 里最直接的"复用指令"方式是斜杠命令（如输入 `/day-note-sync`）——这是**显式调用**，用户必须记得命令名并主动敲出来。Skill 在此基础上多了一层能力：**Claude 可以根据对话内容，自己判断某个 Skill 是否适用并主动调用它**，不需要用户记住命令名，只需要正常描述需求（比如说"帮我写 Day51 学习笔记"，Claude 会自己匹配到 `day-note-sync` 这个 Skill）。

```
斜杠命令：用户必须知道并输入 /command-name（显式）
Skill：Claude 根据任务描述和 Skill 的 description 做语义匹配，自主判断是否调用（隐式，也支持显式 /skill-name）
```

### 1.2 和 CLAUDE.md 的区别

CLAUDE.md 是项目级的**全局上下文**——每次对话都会被加载，适合放"这个项目是什么、用什么技术栈、有哪些约定"这类**始终相关**的背景信息。Skill 则是**任务级的可复用流程**，只在匹配到特定任务时才被加载和执行，平时不占用上下文：

| 维度 | CLAUDE.md | Skill |
|-----|-----------|-------|
| 加载时机 | 每次对话开始就加载 | 只在任务匹配时按需加载 |
| 内容性质 | 项目背景、约定、长期有效的规则 | 针对特定重复性任务的多步骤操作流程 |
| 典型内容 | "这个仓库是学习笔记库，用 Day-N 命名" | "写学习笔记时要同步做哪四件事、每件事的具体格式要求" |

### 1.3 本仓库的真实例子：day-note-sync

这个仓库里贯穿整个 Day 51–68 写作过程使用的 `day-note-sync` Skill，就是本教程要拆解的真实案例——它把"新增一天学习笔记时要同步做的四件事"（写笔记、追加面试题、勾选路线图、同步 README）封装成一个固定流程，每次调用都严格按同样的步骤执行，不会因为对话轮次不同而遗漏某一步。

---

## 二、Skill 的文件结构

### 2.1 SKILL.md 的 frontmatter

```markdown
---
name: day-note-sync
description: This skill should be used when the user asks to "写 DayN 学习笔记", ...
---

# Day Note Sync

为本仓库新增一天学习笔记时，同步完成四件事：写笔记、追加面试题、勾选路线图进度、同步 README。
...
```

每个 Skill 是 `.claude/skills/<skill-name>/SKILL.md` 这样一个文件，`name` 是 Skill 的唯一标识，`description` 是 Claude 判断"这个任务该不该用这个 Skill"的核心依据。

### 2.2 description 字段的关键作用

`description` 不是给人看的简介，而是**匹配算法读取的触发条件**——写得越具体、覆盖的措辞越全面，Skill 被正确触发的概率越高：

```yaml
description: This skill should be used when the user asks to "写 DayN 学习笔记",
  "生成学习笔记", "补一篇学习笔记", "更新面试题", "同步面试题", "更新进度", "同步 README",
  or otherwise wants to add a new day's learning note to this repo and keep
  面试题.md / 路线图 / README.md in sync with it.
```

这段 description 列举了多种用户可能的说法（"写学习笔记"/"补笔记"/"更新面试题"），而不是只写一句抽象的"用来管理学习笔记"——**description 覆盖的措辞越具体，越不容易在用户换一种说法提需求时漏掉匹配**，这是设计 Skill 时最容易被忽视但最关键的一步。

### 2.3 references 子目录：延迟加载的详细文档

```
.claude/skills/day-note-sync/
├── SKILL.md                              # 主文件：何时用 + 步骤概览
└── references/
    ├── note-template.md                  # 学习笔记的完整结构模板
    ├── interview-questions-sync.md       # 面试题.md 的同步规则
    └── readme-sync.md                    # README.md 的同步规则
```

`SKILL.md` 本身写得很精简（只有"四步做什么、判断哪个路线图文件"这些概览性内容），真正细致的格式规范（比如"目录锚点怎么生成""表格行怎么写"）都放进了 `references/` 目录，只有当 Skill 真正被触发、执行到具体某一步时才去读取对应的参考文件。**这是控制上下文 Token 消耗的关键设计**：如果把所有细节都写进 `SKILL.md` 本体，每次哪怕只是判断"要不要用这个 Skill"都要把全部细节加载进上下文；拆分成"精简主文件 + 按需加载的参考文件"后，只有真正开始执行时才产生这部分开销。

---

## 三、Skill 是怎么被触发的

### 3.1 显式触发：斜杠命令

用户直接输入 `/day-note-sync 执行day51` 这样的命令，Claude Code 会直接加载并执行对应的 Skill，不需要额外判断——这是最明确、最不会误触发的调用方式。

### 3.2 隐式匹配：按 description 语义自动调用

用户不输入斜杠命令，只是正常描述需求（比如"帮我写一篇 Day70 的学习笔记"），Claude 会把这句话和当前可用的所有 Skill 的 `description`做语义匹配，如果匹配上就主动调用——这正是本教程 1.1 节提到的"Claude 自主判断"能力。

### 3.3 项目级 vs 个人级 Skill

```
项目级 Skill：.claude/skills/<name>/SKILL.md，随仓库提交，团队所有人共享
个人级 Skill：通常在用户主目录下的全局配置里，只对当前用户生效，不会被提交进项目仓库
```

项目级 Skill 适合"这个仓库特有的重复性任务"（比如 `day-note-sync` 只对这个学习笔记仓库有意义）；个人级 Skill 适合"我个人在所有项目里都想用的习惯性流程"，不应该被写进某一个具体项目的仓库里。

---

## 四、拆解一个真实 Skill：day-note-sync

用本仓库实际的 `day-note-sync` Skill 逐层拆解设计思路：

```
① description 覆盖了用户可能的多种表达方式
   ——"写学习笔记""补笔记""更新面试题""同步README"都能命中，而不是要求用户说出固定咒语

② SKILL.md 正文先讲"触发前要确认哪些输入"
   ——Day编号、主题名、知识点列表，如果缺失就先问用户，不凭空编造技术细节
   这是一条"防止 Skill 在信息不全时乱猜"的安全阀

③ 正文按步骤列出"四件事要按顺序整套执行"
   ——写笔记→面试题→路线图→README，每一步都写清楚"在哪个文件、插入到什么位置"
   这保证了每次调用行为一致，不会因为不同对话而随意变动执行顺序

④ 具体格式规范拆进 references/ 三个文件
   ——SKILL.md 本体只有"做什么"，"具体怎么写"的细节按需加载，节省常驻上下文的开销

⑤ 结尾有"完成后自检"清单
   ——四个文件是否都改了、编号是否连续、有没有把未完成的 Day 标记成已完成
   这是执行完毕后的质量门控，防止 Skill 执行到一半漏了某一步却没被发现
```

**这五条设计原则可以迁移到任何新 Skill 的设计上**：明确触发条件、缺信息先问不瞎猜、步骤固定且有序、细节延迟加载、执行完有自检清单。

---

## 五、动手写一个最小 Skill

假设想封装一个"给 Git commit message 生成规范格式"的 Skill：

```markdown
---
name: commit-message-helper
description: This skill should be used when the user asks to "写 commit message",
  "生成提交信息", "帮我写个规范的commit", or wants a properly formatted git commit
  message following Conventional Commits style for changes in this repo.
---

# Commit Message Helper

## 使用时机

用户想要给当前的代码改动生成一条符合 Conventional Commits 规范的提交信息时使用。

## 执行步骤

1. 运行 `git diff --staged` 查看已暂存的改动内容
2. 判断改动类型：新功能用 `feat`，修复用 `fix`，文档用 `docs`，重构用 `refactor`
3. 生成格式：`<type>(<scope>): <一句话描述>`，scope 是改动涉及的模块名
4. 如果改动涉及多个不相关的模块，提示用户考虑拆分成多次提交，而不是硬塞一条 message

## 输出格式

只输出建议的 commit message 文本，不要自动执行 `git commit`——是否提交由用户决定。
```

这个最小示例展示了一个完整 Skill 该有的骨架：**明确的触发条件、清晰的执行步骤、明确的输出边界（不越权自动执行 `git commit`）**——即使是简单任务，也要写清楚"到哪一步为止"，避免 Skill 擅自做超出预期的操作。

---

## 六、Skill vs Subagent vs 普通 Prompt 的选型

| 维度 | 普通 Prompt | Skill | Subagent |
|-----|-----------|-------|---------|
| 复用性 | 一次性，用完即忘 | 可复用，沉淀成文件长期存在 | 可复用，但主要用于隔离上下文的独立任务 |
| 上下文占用 | 直接占用主对话上下文 | 主文件精简，细节按需加载 | 完全独立的上下文，只把最终结果带回主对话 |
| 适合场景 | 临时的、不会重复的需求 | 重复出现的多步骤任务，需要保证执行顺序和格式一致 | 需要大量探索/试错、且不希望污染主对话上下文的子任务 |

**判断标准**：如果一个任务**只做一次**，直接用普通 Prompt 描述需求就够了，不需要封装；如果这个任务**会反复出现**，且每次都需要"按同样的步骤、同样的格式"执行（比如本仓库每次写新的一天学习笔记都要做同样的四件事），封装成 Skill 能保证一致性，不会因为不同对话而遗漏步骤；如果任务需要**大量独立探索**（比如翻遍整个代码库找某个用法），适合用 Subagent 隔离上下文，避免探索过程中的中间结果占满主对话的窗口。

---

## 七、Day 69 知识速查

### Skill 文件结构

```
.claude/skills/<skill-name>/
├── SKILL.md          # frontmatter(name/description) + 正文（触发条件+步骤概览）
└── references/       # 详细格式规范，按需加载，不常驻上下文
```

### 触发方式

```
显式：/skill-name 参数（用户主动敲命令）
隐式：Claude 根据 description 和对话内容自动语义匹配调用
```

### 设计一个 Skill 的五条原则

```
1. description 覆盖用户可能的多种说法，不要求用户说固定咒语
2. 缺信息先问用户，不凭空编造细节
3. 步骤固定有序，写清楚每步在哪个文件、插入到什么位置
4. 细节拆进 references/，主文件保持精简
5. 结尾给一份自检清单，防止执行到一半漏步骤
```

### Skill vs Subagent vs 普通 Prompt

```
一次性需求 → 普通 Prompt
反复出现、需要保证步骤一致 → Skill
需要大量独立探索、避免污染主对话上下文 → Subagent
```

---

## 八、实践任务

- [ ] 打开这个仓库的 `.claude/skills/day-note-sync/SKILL.md`，对照本笔记第四节的五条设计原则，逐条找到对应的段落
- [ ] 挑一个自己重复做过至少 3 次的任务（比如"每次发 PR 前检查 checklist"），写一份最小 SKILL.md
- [ ] 给这份 SKILL.md 写一个覆盖至少 3 种用户说法的 `description`，测试用不同措辞触发它，验证能否被正确匹配
- [ ] 如果这个 Skill 涉及的格式规范比较复杂，尝试把细节拆进 `references/` 子目录，只在 `SKILL.md` 正文里留一句"具体格式见 references/xxx.md"
- [ ] 在自己写的 Skill 结尾加一份"完成后自检"清单，模仿 `day-note-sync` 的做法

**产出标准**：一个能被正确触发（显式命令和自然语言描述都能匹配）的最小 Skill，覆盖一个自己项目里真实存在的重复性任务。

---

## 九、下一步

FastAPI 后端工程（Day 68）和 Claude Code Skills（Day 69）都是深化阶段主线之外的技能查缺补漏——前者补的是"把 LLM 应用暴露成标准后端服务"的工程能力，后者补的是"如何把重复性协作流程封装成可复用资产"的元能力。这份笔记本身就是用 `day-note-sync` Skill 生成的，也算是对本篇内容的一次现场验证。后续如果继续发现类似的技能缺口，仍然按补充篇的方式追加即可。
