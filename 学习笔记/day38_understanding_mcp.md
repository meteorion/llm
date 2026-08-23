# Day 38：理解 MCP（Model Context Protocol）

> 学习目标：理解 MCP 的三种核心能力（Resources / Tools / Prompts）和 Server / Client 架构，能说清 MCP 与 function calling 的定位差异（两者不是替代关系）、以及 MCP 与 A2A 各自解决哪层连接问题；形成一份原理笔记，为 Day 39 实现最小 MCP Server 打好基础
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 38
>
> 🧭 导航：[← Day 37 · 第 5 周复盘](day37_week5_review.md) → Day 39 · 开发一个最小 MCP Server（待更新）

---

## 目录

- [一、为什么需要 MCP：工具集成的碎片化问题](#一为什么需要-mcp工具集成的碎片化问题)
  - [1.1 现在的工具集成是什么样的](#11-现在的工具集成是什么样的)
  - [1.2 碎片化带来的三个问题](#12-碎片化带来的三个问题)
  - [1.3 MCP 的核心主张：标准化工具服务器](#13-mcp-的核心主张标准化工具服务器)
- [二、MCP 的三种核心能力](#二mcp-的三种核心能力)
  - [2.1 Tools：模型可以调用的函数](#21-tools模型可以调用的函数)
  - [2.2 Resources：模型可以读取的数据](#22-resources模型可以读取的数据)
  - [2.3 Prompts：可复用的提示词模板](#23-prompts可复用的提示词模板)
- [三、Server / Client 架构与交互流程](#三server--client-架构与交互流程)
  - [3.1 角色划分：谁做什么](#31-角色划分谁做什么)
  - [3.2 MCP Client ↔ Server 交互流程图](#32-mcp-client--server-交互流程图)
  - [3.3 独立进程 + 跨语言：MCP 的关键架构决策](#33-独立进程--跨语言mcp-的关键架构决策)
- [四、MCP vs Function Calling：不同层的协议](#四mcp-vs-function-calling不同层的协议)
  - [4.1 Function Calling 是"模型层"约定](#41-function-calling-是模型层约定)
  - [4.2 MCP 是"连接层"协议](#42-mcp-是连接层协议)
  - [4.3 两者的关系：MCP Server 通过 Function Calling 把工具暴露给模型](#43-两者的关系mcp-server-通过-function-calling-把工具暴露给模型)
- [五、MCP vs A2A：两个协议解决不同层的问题](#五mcp-vs-a2a两个协议解决不同层的问题)
  - [5.1 MCP 管"模型与工具/数据的连接"](#51-mcp-管模型与工具数据的连接)
  - [5.2 A2A 管"Agent 与 Agent 的任务委派"](#52-a2a-管agent-与-agent-的任务委派)
  - [5.3 两层协议对比图](#53-两层协议对比图)
- [六、为什么 MCP 成为 2026 年的事实标准](#六为什么-mcp-成为-2026-年的事实标准)
- [七、Day 38 知识速查](#七day-38-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、为什么需要 MCP：工具集成的碎片化问题

### 1.1 现在的工具集成是什么样的

Day 23–25 写过工具调用：把 `get_weather` / `get_exchange_rate` 定义成函数，注册给模型，模型决定何时调用。这是**最简单的工具集成方式**，完全够用——但只在一个应用内。

现实场景更复杂：

- 一个公司里有十个 AI 产品，每个产品的开发者都需要"查数据库"这个工具
- 这十个开发者会分别写十份几乎相同的"数据库查询"代码，各自维护各自的版本
- 其中一个开发者用 Python，另一个用 Node.js，各自写各自的集成代码
- 工具的认证方式、错误处理、参数格式，十个版本各不相同

这是**工具集成的碎片化**：每个 AI 应用各自写一套工具集成代码，工具无法跨应用复用。

### 1.2 碎片化带来的三个问题

| 问题 | 具体表现 |
|-----|---------|
| **重复开发** | "查数据库"这个工具，N 个团队各写一遍，逻辑相同但实现各异 |
| **无法复用** | 团队 A 写好的"查 Jira 工单"工具，团队 B 想用但无法直接接入 |
| **语言绑定** | Python 写的工具不能给 Node.js 的 AI 应用直接用，必须重写 |

如果有一个标准协议：工具开发者按协议规范写一次"数据库查询服务器"，任何遵循协议的 AI 应用都能直接接入——碎片化问题就解决了。这正是 MCP 做的事。

### 1.3 MCP 的核心主张：标准化工具服务器

MCP（Model Context Protocol）是 Anthropic 在 2024 年底发布的开放协议，核心主张是：

> **把工具（Tools）、数据（Resources）、提示词（Prompts）打包成一个标准化的"MCP Server"，任何遵循 MCP 协议的 AI 应用（MCP Client）都可以发现并使用这个 Server 暴露的能力，不受编程语言限制。**

类比：MCP 之于 AI 工具，就像 USB-C 之于设备充电——充电器（工具服务器）和设备（AI 应用）之间用统一的接口，换设备不需要换充电器。

---

## 二、MCP 的三种核心能力

MCP Server 可以暴露三类能力，对应 AI 应用里最常见的三种需求：

### 2.1 Tools：模型可以调用的函数

**定义**：Server 暴露的可执行操作，模型决定何时调用、传什么参数。

```
类比：函数调用
MCP Tools ≈ Day 23–25 手写的 @tool 函数，但通过协议标准化、独立运行
```

典型例子：
- `search_web(query)` — 网络搜索
- `query_database(sql)` — 数据库查询
- `send_email(to, subject, body)` — 发送邮件
- `execute_code(code, language)` — 代码执行

Tools 是 MCP 最常用的能力，也是和 Function Calling 关系最紧密的部分（见第四节）。

### 2.2 Resources：模型可以读取的数据

**定义**：Server 暴露的数据源，Client 可以主动拉取，通常是结构化数据或文件。

```
类比：文件系统 / API 端点
MCP Resources ≈ 一个能被模型读取的"数据文件"或"实时数据流"
```

典型例子：
- 项目文档（Markdown 文件、代码文件）
- 数据库查询结果（只读视图）
- 实时监控数据（服务器 CPU/内存指标）
- 用户的日历事件列表

Resources 和 Tools 的核心区别：**Resources 是"读数据"（Client 主动拉取），Tools 是"执行操作"（模型触发调用）**。Resources 通常不产生副作用，Tools 可能会（如发送邮件）。

### 2.3 Prompts：可复用的提示词模板

**定义**：Server 暴露的提示词模板，Client 可以请求特定模板并填入参数。

```
类比：函数库里的提示词
MCP Prompts ≈ 把常用的、经过调优的 System Prompt / Few-shot 示例打包成可复用单元
```

典型例子：
- "代码审查"提示词模板（接受代码语言和代码内容作为参数）
- "数据分析"提示词模板（接受数据格式描述）
- "翻译"提示词模板（接受源语言、目标语言、文本）

Prompts 是三种能力里使用最少的，但对于"提示词工程是核心资产"的团队很有价值——把调优好的提示词集中管理在 Server 里，所有 AI 应用共享同一份。

---

## 三、Server / Client 架构与交互流程

### 3.1 角色划分：谁做什么

| 角色 | 职责 | 例子 |
|-----|------|-----|
| **MCP Server** | 暴露 Tools / Resources / Prompts，响应 Client 的请求 | 一个运行着"数据库查询工具"的独立进程 |
| **MCP Client** | 发现并调用 Server 的能力，把工具结果传给模型 | Claude Code、你自己写的 AI 应用、LangGraph 图 |
| **Host**（可选） | 管理 Client 的生命周期，处理用户界面 | VS Code 插件、桌面应用 |

**关键区别**：Server 是独立进程，不是 Client 代码里的一个函数。Server 可以用任何语言写（Python / TypeScript / Go），只要遵循 MCP 协议，Client 就能发现并调用它。

### 3.2 MCP Client ↔ Server 交互流程图

```
┌──────────────────────────────────────────────────────────────┐
│                       MCP Client（AI 应用）                   │
│                                                              │
│   1. 启动时：连接 MCP Server，拉取工具/数据/模板列表           │
│      ┌─────────────────────────────────────────────────┐    │
│      │  list_tools()      → [{name, description, ...}] │    │
│      │  list_resources()  → [{uri, name, ...}]         │    │
│      │  list_prompts()    → [{name, arguments, ...}]   │    │
│      └─────────────────────────────────────────────────┘    │
│                                                              │
│   2. 用户提问 → 把工具列表注册给模型 → 模型决定调用哪个工具    │
│      ┌─────────────────────────────────────────────────┐    │
│      │  [模型] → 决定调用 search_web(query="天气")      │    │
│      └─────────────────────────────────────────────────┘    │
│                                                              │
│   3. Client 把模型的工具调用转发给 Server                    │
│      ┌─────────────────────────────────────────────────┐    │
│      │  call_tool("search_web", {"query": "天气"})      │    │
│      └─────────────────────────────────────────────────┘    │
└─────────────────────────┬────────────────────────────────────┘
                          │ MCP 协议（JSON-RPC over stdio/HTTP）
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                       MCP Server（工具服务器）                 │
│                                                              │
│   接收 call_tool 请求 → 执行工具逻辑 → 返回结果               │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  Tools:     search_web / query_db / send_email      │   │
│   │  Resources: /docs/api.md / /data/metrics.json       │   │
│   │  Prompts:   code_review_template / translate_tpl    │   │
│   └─────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**关键流程**：
1. Client 启动时调用 Server 的 `list_tools()` 拿到工具列表
2. Client 把工具列表转成 Function Calling 格式注册给模型
3. 模型决定调用某个工具，Client 把请求转发给 Server 的 `call_tool()`
4. Server 执行工具逻辑，返回结果给 Client，Client 再把结果传给模型

### 3.3 独立进程 + 跨语言：MCP 的关键架构决策

把工具服务器做成独立进程是 MCP 最重要的架构决策，带来三个收益：

| 收益 | 说明 |
|-----|------|
| **语言无关** | Server 可以用 Python / TypeScript / Go / Rust 写，Client 不关心实现语言 |
| **可复用** | 一个"数据库查询 Server"可以被多个 AI 应用同时连接使用 |
| **进程隔离** | Server 崩溃不影响 Client（AI 应用）；Server 的权限和 Client 的权限可以分别控制 |

对比：Day 23–25 的手写 `@tool` 函数是"工具和应用代码在同一个进程里"，切换 AI 应用就要把工具代码复制过去。MCP Server 把工具做成独立服务，AI 应用只需要"连接"而不是"复制"。

---

## 四、MCP vs Function Calling：不同层的协议

### 4.1 Function Calling 是"模型层"约定

Function Calling 是大模型 API 的功能：在调用模型时，把工具定义（函数名、参数 JSON Schema、描述）一起传给模型，模型决定什么时候触发某个工具调用，并返回结构化的工具调用请求。

```python
# Function Calling：在 API 调用时传工具定义
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询城市天气",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}
        }
    }]
)
```

Function Calling 解决的问题：**让模型知道有哪些工具可以用，并用结构化格式表达"我要调用哪个工具、传什么参数"**。

Function Calling 不解决的问题：工具代码在哪里运行、谁来执行工具调用、工具能不能跨应用复用。

### 4.2 MCP 是"连接层"协议

MCP 解决的是工具服务器和 AI 应用之间的**连接问题**：

- 工具服务器怎么声明自己有哪些能力（`list_tools` / `list_resources` / `list_prompts`）
- AI 应用怎么发现并连接工具服务器
- 工具调用请求怎么在 Client 和 Server 之间传递
- 多个 AI 应用怎么共享同一个工具服务器

MCP 不定义"模型怎么决定调用工具"——这仍然是 Function Calling 的职责。

### 4.3 两者的关系：MCP Server 通过 Function Calling 把工具暴露给模型

```
┌────────────────────────────────────────────────────────┐
│  完整的工具调用链路                                       │
│                                                        │
│  MCP Server                                            │
│    │ 暴露工具列表（通过 list_tools）                     │
│    ▼                                                   │
│  MCP Client（AI 应用）                                  │
│    │ 把工具列表转成 Function Calling 格式                │
│    │ 注册给模型                                         │
│    ▼                                                   │
│  模型（Function Calling）                               │
│    │ 决定调用哪个工具，返回结构化工具调用请求              │
│    ▼                                                   │
│  MCP Client                                            │
│    │ 把工具调用请求转发给 MCP Server                     │
│    ▼                                                   │
│  MCP Server 执行工具，返回结果                           │
└────────────────────────────────────────────────────────┘
```

**总结**：MCP 不是 Function Calling 的替代品，而是在它之上的一层：MCP 解决"工具服务器怎么被发现和连接"，Function Calling 解决"模型怎么决定调用工具"。两层各司其职，MCP Server 内部通过 Function Calling 把工具暴露给模型。

| | Function Calling | MCP |
|---|---|---|
| **层次** | 模型 API 层 | 工具服务连接层 |
| **解决的问题** | 模型如何表达工具调用意图 | 工具服务器如何被标准化、复用 |
| **定义方** | 各 LLM 厂商（OpenAI、Anthropic、DeepSeek 等） | Anthropic（开放协议） |
| **跨语言** | 不涉及（只是 API 协议） | ✅（Server 和 Client 可以用不同语言） |
| **工具复用** | ❌（工具代码和应用绑定） | ✅（Server 可被多个 Client 共享） |
| **是否替代关系** | — | ❌ 互补，MCP 在上层包装了 Function Calling |

---

## 五、MCP vs A2A：两个协议解决不同层的问题

### 5.1 MCP 管"模型与工具/数据的连接"

MCP 的连接方向是：**模型（通过 Client）↔ 工具/数据（Server）**。

它回答的问题是："模型怎么找到并调用外部工具？外部数据怎么被模型读取？"

MCP 不关心：调用这个工具的是一个 Agent 还是另一个 Agent，工具调用背后是谁在"指挥"。

### 5.2 A2A 管"Agent 与 Agent 的任务委派"

A2A（Agent-to-Agent）是 Google DeepMind 在 2025 年发布的协议，连接方向是：**Agent ↔ Agent**。

它回答的问题是："一个 Agent 怎么把子任务委派给另一个 Agent？两个 Agent 之间怎么同步任务状态？"

A2A 的核心概念：
- **Task 对象**：任务有明确的生命周期状态（`submitted` → `working` → `completed` / `failed`）
- **Agent Card**：每个 Agent 声明自己能做什么（类比 MCP 的 `list_tools`，但声明的是 Agent 的整体能力，不是单个工具）
- **流式状态更新（Push）**：委派出去的任务通过 Streaming 推送进度，不需要轮询

### 5.3 两层协议对比图

```
┌────────────────────────────────────────────────────────────────┐
│                      Agent 系统的协议层次                        │
│                                                                │
│  ┌──────────────┐   A2A 协议    ┌──────────────┐              │
│  │  Planner     │ ──────────► │  Executor    │              │
│  │  Agent       │  委派任务     │  Agent       │              │
│  └──────┬───────┘             └──────┬───────┘              │
│         │                           │                        │
│      MCP 协议                    MCP 协议                      │
│         │                           │                        │
│         ▼                           ▼                        │
│  ┌──────────────┐           ┌──────────────┐                │
│  │  MCP Server  │           │  MCP Server  │                │
│  │  (搜索工具)  │           │  (代码执行)  │                │
│  └──────────────┘           └──────────────┘                │
│                                                                │
│  MCP：每个 Agent 怎么连接它需要的工具和数据                      │
│  A2A：Agent 之间怎么协作、委派任务、同步状态                     │
└────────────────────────────────────────────────────────────────┘
```

**类比**：
- MCP 像"插座标准"——工具（插头）和 Agent（设备）之间的接口规范
- A2A 像"快递协议"——Agent 之间怎么"寄任务"、"查进度"、"收结果"

两者互补：MCP 让每个 Agent 能连接工具，A2A 让多个 Agent 能协作完成更大的任务。Day 41 会用到 A2A，今天先建立边界感——遇到"Agent 怎么用工具"想到 MCP，遇到"Agent 怎么和另一个 Agent 协作"想到 A2A。

---

## 六、为什么 MCP 成为 2026 年的事实标准

MCP 在 2024 年底发布后，迅速成为 AI 工具集成领域的事实标准，原因有四：

**1. 开放协议，厂商中立**：MCP 不是某个 AI 公司的私有协议——任何 AI 应用都可以实现 MCP Client，任何工具服务都可以实现 MCP Server，不被任何厂商绑定。

**2. 生态快速积累**：大量常用工具已经有了开源的 MCP Server 实现（GitHub、Slack、Google Drive、数据库、浏览器等），AI 应用接入后立刻拥有这些工具，不需要自己写集成代码。

**3. 工具复用解决了真实痛点**：企业里同样的工具被不同团队重复开发的问题非常普遍，MCP 提供了"写一次工具服务器、全公司 AI 应用共用"的标准方案。

**4. 被主流 AI 应用和框架采纳**：Claude Code、Claude Desktop、Cursor、LangChain、LangGraph 都原生支持 MCP，用户直接在这些工具里配置 MCP Server 就能使用，无需额外集成代码。

**与 OpenAI Plugin（失败的先例）的区别**：早期的 ChatGPT Plugin 也想做类似的事，但它是闭源的、绑定 ChatGPT 的、工具定义复杂——没有解决"跨 AI 应用复用"的问题。MCP 从设计上就是开放的、轻量的、跨语言的，这是它成功的关键。

---

## 七、Day 38 知识速查

### MCP 三种能力对比

| 能力 | 方向 | 是否产生副作用 | 典型用途 |
|-----|------|-------------|---------|
| **Tools** | Client 调用 → Server 执行 | 可能有（如发邮件） | 搜索、查数据库、执行操作 |
| **Resources** | Client 主动拉取 | 通常无（只读） | 读文档、读实时数据 |
| **Prompts** | Client 请求模板 | 无 | 获取调优好的提示词 |

### MCP vs Function Calling vs A2A

| 协议 | 连接的是 | 解决的问题 |
|-----|---------|----------|
| **Function Calling** | 模型 ↔ 工具调用意图 | 模型如何表达"我要调用哪个工具" |
| **MCP** | AI 应用（Client）↔ 工具服务器（Server） | 工具服务如何被标准化、跨应用复用 |
| **A2A** | Agent ↔ Agent | Agent 间如何委派任务、同步状态 |

三者不是替代关系：一个完整的多 Agent 系统里，三者可以同时存在——Agent 内部用 MCP 调用工具，Agent 之间用 A2A 协作，底层用 Function Calling 让模型表达工具调用意图。

### MCP 的独立进程架构收益

```
独立进程 → 语言无关（Server 可以是任何语言）
         → 可复用（多个 Client 共享一个 Server）
         → 进程隔离（Server 崩溃不影响 Client）
         → 权限隔离（Server 的系统权限和 Client 独立控制）
```

---

## 八、实践任务

- [ ] 阅读 MCP 官方文档的"Core Architecture"部分（[modelcontextprotocol.io](https://modelcontextprotocol.io)），确认本节对 Client/Server 角色和三种能力的理解是否准确
- [ ] 浏览 MCP 官方仓库里的示例 Server（如 `filesystem` Server），找到 `list_tools` 和 `call_tool` 两个关键接口的实现，对照本节的交互流程图理解代码结构
- [ ] 在 Claude Code 的 MCP 配置文件（`~/.claude/claude_desktop_config.json` 或项目设置）里查看是否已经配置了任何 MCP Server，理解配置格式
- [ ] 用自己的话回答：**如果没有 MCP，你现在写的 Day 23–25 工具调用代码有什么局限？MCP 具体解决了哪一个局限？**（写进笔记，不用交，但这道题的答案是 Day 39 的起点）

**产出标准**：能向不了解 MCP 的人用两分钟解释清楚：MCP 是什么、解决了什么问题、和 Function Calling 是什么关系。不需要会写代码，Day 39 再实现。

---

## 九、下一步预告

Day 39 进入**动手实现**：把 Day 23 定义的天气 / 汇率工具包装成一个真实的 MCP Server，用 MCP 官方 Python SDK（`mcp`）实现，让 Claude Code 或任意 MCP Client 能列出并调用这个 Server 暴露的工具。今天理解的 `list_tools` / `call_tool` 交互流程，明天会在代码里一一对应——Server 需要实现 `list_tools` 返回工具描述，实现 `call_tool` 执行工具逻辑，这两个 handler 就是今天流程图里 Server 侧的全部核心代码。
