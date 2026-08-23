# Day 33：LangGraph 基础：用状态图重写 ReAct

> 学习目标：理解 LangGraph 的 StateGraph / Node / Edge 三个核心概念，把 Day 25 手写的 `while` 循环 ReAct 工作流用 `StateGraph` 重写，感受"显式状态建模"和"隐式状态塞进消息历史"的本质区别
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 33
>
> 🧭 导航：[← Day 32 · 用 LangChain 重新实现结构化输出与 RAG 链](day32_langchain_structured_output_and_rag.md) → [Day 34 · 条件边与分支路由](day34_conditional_edges_routing.md)

---

## 目录

- [一、为什么需要 LangGraph：while 循环的三个隐性问题](#一为什么需要-langgraph-while-循环的三个隐性问题)
  - [1.1 Day 25 手写 ReAct 的状态在哪里](#11-day-25-手写-react-的状态在哪里)
  - [1.2 隐式状态带来的三个问题](#12-隐式状态带来的三个问题)
  - [1.3 LangGraph 的核心主张：把状态显式化](#13-langgraph-的核心主张把状态显式化)
- [二、三个核心概念：StateGraph / Node / Edge](#二三个核心概念stategraph--node--edge)
  - [2.1 State：显式的 Agent 状态快照](#21-state显式的-agent-状态快照)
  - [2.2 Node：处理状态的 Runnable](#22-node处理状态的-runnable)
  - [2.3 Edge：决定执行顺序的连线](#23-edge决定执行顺序的连线)
- [三、State 的设计：TypedDict 与 Reducer](#三state-的设计typeddict-与-reducer)
  - [3.1 用 TypedDict 定义 State](#31-用-typeddict-定义-state)
  - [3.2 Reducer：控制字段如何更新](#32-reducer控制字段如何更新)
  - [3.3 ReAct 场景下 State 需要哪些字段](#33-react-场景下-state-需要哪些字段)
- [四、实战：用 StateGraph 重写 Day 25 的 ReAct 工作流](#四实战用-stategraph-重写-day-25-的-react-工作流)
  - [4.1 Day 25 手写版核心逻辑回顾](#41-day-25-手写版核心逻辑回顾)
  - [4.2 Node 拆分：把 while 循环拆成图节点](#42-node-拆分把-while-循环拆成图节点)
  - [4.3 完整 LangGraph ReAct Demo](#43-完整-langgraph-react-demo)
  - [4.4 两版本对比：手写 while vs StateGraph](#44-两版本对比手写-while-vs-stategraph)
- [五、Day 33 知识速查](#五day-33-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、为什么需要 LangGraph：while 循环的三个隐性问题

### 1.1 Day 25 手写 ReAct 的状态在哪里

Day 25 的多步工作流核心是一个 `while` 循环，状态完全藏在 `messages` 列表里：

```python
def run_workflow(user_input: str, ...) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    iteration = 0
    while iteration < max_iter:
        iteration += 1
        response = client.chat.completions.create(messages=messages, ...)
        msg = response.choices[0].message

        if not msg.tool_calls:       # 状态判断：靠检查 msg.tool_calls 是否为空
            return msg.content

        messages.append(msg)         # 状态更新：把新消息追加到列表
        for tc in msg.tool_calls:
            result = execute_tool(tc)
            messages.append({"role": "tool", ...})   # 继续追加
```

所有"状态"都在 `messages` 这一个变量里：用户输入、工具调用历史、迭代次数（通过 `iteration` 单独维护）、工具结果——混在一起，没有明确的结构。

### 1.2 隐式状态带来的三个问题

| 问题 | 具体表现 |
|-----|---------|
| **不可中断** | 函数执行到一半不能暂停，无法在某步等待人工审批后继续 |
| **不可观测** | 要看"当前迭代用了几个工具"，只能遍历 `messages` 数组数 `tool` 消息的数量 |
| **不可持久化** | `messages` 是进程内 Python 对象，程序重启或崩溃后状态全丢 |

第一个问题在 Day 36 的 Human-in-the-loop 会直接卡死——你无法在 `while` 循环中间"暂停等待用户"，因为函数栈不能被挂起。

### 1.3 LangGraph 的核心主张：把状态显式化

LangGraph 的解法是：**用一个显式的 `State` 对象替代隐式的 `messages` 列表，用图（Graph）结构替代 `while` 循环**。

```
手写 while 循环                    LangGraph StateGraph
─────────────────────              ──────────────────────────────
状态：隐式，藏在 messages 里        状态：显式 TypedDict，字段清晰
流程：while 循环 + if/return        流程：Node + Edge 构成的有向图
中断：不支持                        中断：任意 Node 后可 interrupt
可视化：无                          可视化：.get_graph().draw_mermaid()
持久化：手写，或放弃                  持久化：MemorySaver / 任意 Checkpointer
```

---

## 二、三个核心概念：StateGraph / Node / Edge

### 2.1 State：显式的 Agent 状态快照

`State` 是一个 `TypedDict`，记录图在某一时刻的完整快照。每个 Node 接收当前 `State`，返回更新后的字段（不需要返回完整 `State`，只返回发生变化的字段）。

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # 消息历史，用 add_messages reducer 追加
    iteration: int                             # 当前迭代次数，直接赋值覆盖
```

`State` 的字段设计决定了图的"记忆边界"：只有放进 `State` 的信息才能在 Node 之间传递。

### 2.2 Node：处理状态的 Runnable

Node 本质上是一个函数（或 `Runnable`），签名固定：**接收 `State`，返回更新的字段字典**。

```python
def call_model(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {
        "messages": [response],          # add_messages reducer 会把它追加进去
        "iteration": state["iteration"] + 1,
    }
```

Node 和 Day 31–32 学的 LCEL `Runnable` 是同一套接口——Node 也可以用 `ChatPromptTemplate | llm | parser` 这样的 LCEL 链来实现，LangGraph 把它当 Node 挂进图里就行。

### 2.3 Edge：决定执行顺序的连线

Edge 连接 Node，决定执行完一个 Node 后去哪里：

| Edge 类型 | 代码写法 | 用途 |
|----------|---------|------|
| **固定边** | `graph.add_edge("node_a", "node_b")` | 始终跳到下一个固定节点 |
| **条件边** | `graph.add_conditional_edges("node_a", routing_fn)` | 根据 State 内容动态决定下一步（Day 34 重点） |
| **入口边** | `graph.set_entry_point("node_a")` | 图从哪个 Node 开始 |
| **结束边** | `graph.add_edge("node_a", END)` | 图在哪个 Node 后结束 |

今天用固定边和条件边就能实现完整的 ReAct 循环；条件边的详细用法放到 Day 34。

---

## 三、State 的设计：TypedDict 与 Reducer

### 3.1 用 TypedDict 定义 State

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int
```

`TypedDict` 给 State 加上类型标注，让 IDE 能做自动补全，也让图的接口变得自文档化——看 `AgentState` 就知道这个 Agent 追踪了哪些信息。

### 3.2 Reducer：控制字段如何更新

Node 只返回"发生变化的字段"，LangGraph 需要知道怎么把这个局部更新合并进 State：

| 字段写法 | 合并方式 | 适用场景 |
|---------|---------|---------|
| `field: list` | **直接替换**：新值完全覆盖旧值 | 需要精确控制列表内容 |
| `field: Annotated[list, add_messages]` | **追加**：新消息追加到列表末尾，同 id 消息去重更新 | 消息历史（最常用） |
| `field: int` | **直接替换**：用新值覆盖 | 计数器、状态标志 |

`add_messages` 是 LangGraph 内置的 reducer，专门处理 `AIMessage` / `ToolMessage` / `HumanMessage` 的追加和去重逻辑——它比手写 `messages.append(...)` 更可靠，因为它能处理 `tool_call_id` 重复等边界情况。

### 3.3 ReAct 场景下 State 需要哪些字段

对应 Day 25 手写版里的"状态"，显式映射到 `AgentState` 字段：

| Day 25 手写的隐式状态 | AgentState 的显式字段 |
|---------------------|---------------------|
| `messages` 列表（含 system/user/assistant/tool） | `messages: Annotated[list, add_messages]` |
| `iteration` 计数器 | `iteration: int` |
| 工具调用结果（塞进 messages） | 也在 `messages` 里，ToolMessage 格式 |
| `max_iter` 上限 | 不放进 State，作为图的配置参数（或在 routing 函数里用常量） |

`max_iter` 不放进 State 的原因：它是图的静态配置，不是运行时会变化的数据——放进 State 反而会让每次更新都要传它，增加噪音。

---

## 四、实战：用 StateGraph 重写 Day 25 的 ReAct 工作流

### 4.1 Day 25 手写版核心逻辑回顾

Day 25 的出行规划助手有两个工具：`get_weather`（查天气）和 `get_exchange_rate`（查汇率）。ReAct 循环的逻辑：

```
用户输入
  → 模型推理（决定调用哪个工具）
  → 执行工具
  → 再次推理（决定继续调用还是直接回答）
  → … 直到模型不再调用工具，或达到最大迭代次数
```

### 4.2 Node 拆分：把 while 循环拆成图节点

`while` 循环里的每一个"决策点"对应一个 Node：

```
while 循环里的逻辑          →     LangGraph Node
─────────────────────────       ────────────────────
模型调用（决定下一步）         →     call_model Node
执行工具                      →     call_tools Node
判断是否继续                  →     should_continue 路由函数（条件边）
```

图的结构：

```
START
  ↓
call_model  ←─────────────┐
  ↓                        │
should_continue ──继续──→ call_tools
  ↓
 结束
  ↓
END
```

`should_continue` 是条件边的路由函数，不是 Node——它检查 State 里最后一条消息有没有 `tool_calls`，有就跳到 `call_tools`，没有就跳到 `END`。

### 4.3 完整 LangGraph ReAct Demo

```python
import json
import os
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# ── 1. State 定义 ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int

# ── 2. 工具定义（对应 Day 25 的工具） ──────────────────────────────────────────

@tool
def get_weather(city: str) -> dict:
    """查询指定城市的天气"""
    data = {"上海": {"temp": 28, "condition": "多云"}, "北京": {"temp": 32, "condition": "晴"}}
    return data.get(city, {"error": f"没有 {city} 的天气数据"})

@tool
def get_exchange_rate(from_currency: str, to_currency: str) -> dict:
    """查询汇率"""
    rates = {("USD", "CNY"): 7.25, ("EUR", "CNY"): 7.85}
    rate = rates.get((from_currency, to_currency))
    if rate:
        return {"rate": rate, "from": from_currency, "to": to_currency}
    return {"error": f"没有 {from_currency}/{to_currency} 的汇率数据"}

tools = [get_weather, get_exchange_rate]
tool_registry = {t.name: t for t in tools}

# ── 3. 初始化模型并绑定工具 ────────────────────────────────────────────────────

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0,
)
llm_with_tools = llm.bind_tools(tools)

# ── 4. Node 定义 ──────────────────────────────────────────────────────────────

MAX_ITERATIONS = 8

def call_model(state: AgentState) -> dict:
    """调用模型，让它决定下一步（调工具还是直接回答）"""
    response = llm_with_tools.invoke(state["messages"])
    return {
        "messages": [response],
        "iteration": state["iteration"] + 1,
    }

def call_tools(state: AgentState) -> dict:
    """执行模型请求的所有工具调用"""
    last_message = state["messages"][-1]
    tool_results = []
    for tc in last_message.tool_calls:
        tool_fn = tool_registry.get(tc["name"])
        if tool_fn:
            result = tool_fn.invoke(tc["args"])
        else:
            result = {"error": f"未知工具: {tc['name']}"}
        tool_results.append(
            ToolMessage(
                content=json.dumps(result, ensure_ascii=False),
                tool_call_id=tc["id"],
            )
        )
    return {"messages": tool_results}

# ── 5. 条件边路由函数 ──────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> str:
    """检查是否需要继续调用工具"""
    last_message = state["messages"][-1]
    # 达到最大迭代次数，强制结束
    if state["iteration"] >= MAX_ITERATIONS:
        return "end"
    # 没有工具调用，模型已给出最终回答
    if not getattr(last_message, "tool_calls", None):
        return "end"
    # 有工具调用，继续执行
    return "continue"

# ── 6. 构建图 ─────────────────────────────────────────────────────────────────

graph_builder = StateGraph(AgentState)

graph_builder.add_node("call_model", call_model)
graph_builder.add_node("call_tools", call_tools)

graph_builder.set_entry_point("call_model")

graph_builder.add_conditional_edges(
    "call_model",
    should_continue,
    {
        "continue": "call_tools",
        "end": END,
    },
)
graph_builder.add_edge("call_tools", "call_model")   # 执行完工具，回到模型

graph = graph_builder.compile()

# ── 7. 运行 ──────────────────────────────────────────────────────────────────

from langchain_core.messages import HumanMessage, SystemMessage

def run_agent(user_input: str) -> str:
    initial_state = {
        "messages": [
            SystemMessage(content="你是一个出行规划助手，可以查询天气和汇率。"),
            HumanMessage(content=user_input),
        ],
        "iteration": 0,
    }
    final_state = graph.invoke(initial_state)
    return final_state["messages"][-1].content

# 测试
answer = run_agent("我下周去上海出差，带500美元够吗，上海天气适合怎么穿？")
print(answer)
```

运行后模型会先调 `get_weather("上海")`，再调 `get_exchange_rate("USD", "CNY")`，最后综合两个结果给出回答——行为和 Day 25 的手写版完全一致，但现在状态是显式的，图结构是可视化的。

**可视化图结构**（LangGraph 内置）：

```python
print(graph.get_graph().draw_mermaid())
# 输出：
# graph TD
#     __start__ --> call_model
#     call_model -. continue .-> call_tools
#     call_model -. end .-> __end__
#     call_tools --> call_model
```

### 4.4 两版本对比：手写 while vs StateGraph

| 维度 | 手写 while（Day 25） | LangGraph StateGraph |
|-----|---------------------|---------------------|
| **状态存储** | 隐式，藏在 `messages` 列表里 | 显式 `AgentState`，字段清晰 |
| **流程控制** | `while` + `if/return` | Node + Edge，结构可视化 |
| **迭代计数** | 单独的 `iteration` 局部变量 | `AgentState.iteration` 字段，随状态传递 |
| **可中断** | 不支持 | 在任意 Node 后加 `interrupt_before` 即可 |
| **持久化** | 不支持，重启即丢 | 接入 `MemorySaver` 一行代码 |
| **可观测** | 手动 print | `.get_graph().draw_mermaid()` 可视化 |
| **代码量** | 更少（约 30 行） | 稍多（约 60 行），但结构更清晰 |
| **适用场景** | 简单固定流程、一次性脚本 | 需要中断/持久化/复杂分支/多 Agent |

❌ 误区：LangGraph 不是"更高级"就一定更好——**如果你的 Agent 不需要中断、持久化、复杂分支**，手写 `while` 循环代码更少、调试更直接。引入 LangGraph 的判断标准是：工作流里出现了 `while` 循环解决不了的需求（Day 34 的分支路由、Day 35 的 Checkpoint、Day 36 的 Human-in-the-loop），而不是"我想用新框架"。

✅ LangGraph 的核心价值在于：**状态显式建模之后，中断、持久化、可视化都是自然的副产品**，不需要额外改造代码结构。

---

## 五、Day 33 知识速查

### LangGraph 核心 API 速查

| 概念 | 代码 | 说明 |
|-----|------|------|
| 定义 State | `class S(TypedDict): field: type` | 图的状态结构 |
| 消息追加 Reducer | `Annotated[list, add_messages]` | 自动追加+去重消息 |
| 创建图 | `StateGraph(AgentState)` | 传入 State 类型 |
| 添加节点 | `graph.add_node("name", fn)` | fn 接收 State 返回 dict |
| 固定边 | `graph.add_edge("a", "b")` | a 执行完直接去 b |
| 条件边 | `graph.add_conditional_edges("a", fn, {"k": "node"})` | fn 返回 key，对应跳转 |
| 入口 | `graph.set_entry_point("name")` | 图从哪里开始 |
| 编译 | `graph.compile()` | 生成可执行图 |
| 运行 | `graph.invoke(initial_state)` | 返回最终 State |
| 可视化 | `graph.get_graph().draw_mermaid()` | 打印 Mermaid 图定义 |

### Node 函数的签名规范

```python
# 正确：接收完整 State，返回需要更新的字段字典
def my_node(state: AgentState) -> dict:
    # 只返回发生变化的字段
    return {"messages": [new_message], "iteration": state["iteration"] + 1}

# 返回值里没有的字段，State 保持不变（不是置空，是不动）
```

### 何时用 LangGraph vs 手写 while

| 需求 | 推荐方案 |
|-----|---------|
| 简单线性工作流，不需要分支 | 手写 while，更简洁 |
| 需要条件分支（工具失败走重试） | LangGraph 条件边 |
| 需要等待人工审批（Human-in-the-loop） | LangGraph interrupt |
| 需要跨会话持久化状态 | LangGraph + Checkpointer |
| 需要可视化图结构 | LangGraph |
| 多 Agent 协同 | LangGraph 多图 |

---

## 六、实践任务

- [ ] 把 Day 25 的工具（`get_weather` / `get_exchange_rate`）包装成 `@tool`，用本节代码完整跑通 LangGraph ReAct Demo，验证行为和 Day 25 手写版一致
- [ ] 在 `call_model` 节点加一行 `print(f"迭代 {state['iteration']}: {state['messages'][-1]}")` 打印每步状态，观察 State 在节点间的流转
- [ ] 运行 `graph.get_graph().draw_mermaid()` 打印图结构，理解 Node 和 Edge 的关系
- [ ] 故意传入一个触发工具调用的问题，再传入一个不触发工具的问题，对比两次执行的 `should_continue` 路由逻辑
- [ ] 把 `MAX_ITERATIONS` 改为 1，观察图提前结束时返回的内容是什么（模型来不及得到工具结果就被截断）

**产出标准**：一个能跑通、行为和 Day 25 版本一致的 LangGraph Demo；能说清 `State` 里每个字段的作用、`should_continue` 返回 `"continue"` 和 `"end"` 分别对应图里的哪条边。

---

## 七、下一步预告

Day 34 深入条件边（`add_conditional_edges`）：给今天的图加一条分支——工具调用失败时走"重试节点"，成功则走"汇总回答节点"。今天的 `should_continue` 只做了"继续/结束"的二选一；Day 34 把它扩展成三路甚至多路路由，这是 LangGraph 相比手写 `while` 最大的表达力提升——`while` 循环里的 `if/elif/else` 在图里变成了可以独立命名、可以可视化的边，出错时能立刻定位是哪条分支的问题。
