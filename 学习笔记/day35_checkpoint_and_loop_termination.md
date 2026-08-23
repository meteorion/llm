# Day 35：循环终止与 Checkpoint 持久化

> 学习目标：掌握 LangGraph 图内循环的规范终止方式（`recursion_limit` + 显式 END 路由），理解 Checkpoint 的概念与 `thread_id` 会话隔离机制；用 `MemorySaver` 接入 Checkpoint，实现"中断 → 查看暂停状态 → 从原状态恢复继续"的完整演示；了解 `SqliteSaver` 让 Checkpoint 跨进程重启存活的接入方式
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 35
>
> 🧭 导航：[← Day 34 · 条件边与分支路由](day34_conditional_edges_routing.md) → [Day 36 · Human-in-the-loop 人工审核节点](day36_human_in_the_loop.md)

---

## 目录

- [一、循环终止：LangGraph 里的终止条件设计](#一循环终止langgraph-里的终止条件设计)
  - [1.1 回顾 Day 33/34 的终止方式：路由函数里的常量比较](#11-回顾-day-3334-的终止方式路由函数里的常量比较)
  - [1.2 LangGraph 内置的 recursion_limit：最后一道防线](#12-langgraph-内置的-recursion_limit最后一道防线)
  - [1.3 终止条件设计原则](#13-终止条件设计原则)
- [二、Checkpoint 是什么：持久化执行快照](#二checkpoint-是什么持久化执行快照)
  - [2.1 为什么需要 Checkpoint](#21-为什么需要-checkpoint)
  - [2.2 Checkpoint vs State：一次图执行 vs 多个历史快照](#22-checkpoint-vs-state一次图执行-vs-多个历史快照)
  - [2.3 thread_id：区分不同会话](#23-thread_id区分不同会话)
- [三、MemorySaver：内存级 Checkpoint 接入](#三memorysaver内存级-checkpoint-接入)
  - [3.1 接入方式：compile 时传 checkpointer](#31-接入方式compile-时传-checkpointer)
  - [3.2 invoke 时传 config](#32-invoke-时传-config)
  - [3.3 get_state 与 get_state_history：查询快照](#33-get_state-与-get_state_history查询快照)
- [四、实战：中断 → 查看暂停状态 → 从原状态恢复](#四实战中断--查看暂停状态--从原状态恢复)
  - [4.1 用 interrupt_before 让图在指定节点前暂停](#41-用-interrupt_before-让图在指定节点前暂停)
  - [4.2 查看暂停位置与当前 State](#42-查看暂停位置与当前-state)
  - [4.3 恢复执行：同一 thread_id 再次 invoke(None)](#43-恢复执行同一-thread_id-再次-invokenone)
  - [4.4 完整演示代码](#44-完整演示代码)
- [五、SqliteSaver：Checkpoint 跨进程重启存活](#五sqlitesaver-checkpoint-跨进程重启存活)
  - [5.1 MemorySaver vs SqliteSaver](#51-memorysaver-vs-sqlitesaver)
  - [5.2 SqliteSaver 接入方式](#52-sqlitesaver-接入方式)
- [六、Day 35 知识速查](#六day-35-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、循环终止：LangGraph 里的终止条件设计

### 1.1 回顾 Day 33/34 的终止方式：路由函数里的常量比较

Day 33/34 里终止循环的方式是在 `should_continue` 路由函数里手动比较计数器：

```python
def should_continue(state: AgentState) -> str:
    if state["iteration"] >= MAX_ITERATIONS:   # 靠手写常量比较
        return "end"
    if not getattr(state["messages"][-1], "tool_calls", None):
        return "end"
    return "continue"
```

这能跑通，但有一个隐患：**如果路由函数或 Node 里存在 bug 导致 `iteration` 没有正确递增，这个检查就会失效，图陷入真正的死循环**。LangGraph 对此有一道内置的保险机制——`recursion_limit`。

### 1.2 LangGraph 内置的 recursion_limit：最后一道防线

`recursion_limit` 是 LangGraph 在运行时计算"图共经历了多少次 Node 执行"的上限。**每执行一个 Node 计数加一，超过上限直接抛 `GraphRecursionError`**，不管路由函数怎么写。

```python
# 在 invoke / stream 时通过 config 传入
config = {
    "recursion_limit": 50,           # 默认值是 25，这里改为 50
    "configurable": {"thread_id": "session-1"},
}
graph.invoke(initial_state, config=config)
```

它和业务层的 `MAX_ITERATIONS` 是**两层不同粒度的保护**：

| 层级 | 实现方式 | 计数单位 | 触发行为 |
|-----|---------|---------|---------|
| 业务层（推荐先加） | `should_continue` 里比较 `iteration` | 模型被调用的轮次 | 走"结束"分支，优雅输出降级回答 |
| 框架层（最后防线） | `recursion_limit` in config | 所有 Node 执行次数之和 | 抛 `GraphRecursionError`，终止图 |

业务层的终止保证**语义正确**（让模型给出"抱歉没查到"而非直接报错），框架层的 `recursion_limit` 保证**系统安全**（防止失控死循环拖垮进程）。

### 1.3 终止条件设计原则

实际工程中，一个 ReAct 类图至少要有**两条**终止路径：

```
终止路径 1（正常）：模型不再调用工具 → should_continue 返回 "end" → END
终止路径 2（超限保护）：iteration >= MAX_ITERATIONS → should_continue 返回 "end"
终止路径 3（兜底）：recursion_limit 超过 → GraphRecursionError（catch 后给用户降级提示）
```

终止类型 3 应该在调用层 `try/except GraphRecursionError` 捕获，而不是让它直接暴露给用户：

```python
from langgraph.errors import GraphRecursionError

try:
    result = graph.invoke(initial_state, config=config)
except GraphRecursionError:
    result = {"messages": [{"content": "抱歉，任务执行超时，请简化问题后重试。"}]}
```

---

## 二、Checkpoint 是什么：持久化执行快照

### 2.1 为什么需要 Checkpoint

Day 33 提到 `while` 循环的状态"随进程死亡"。这带来三个具体问题：

| 问题 | 具体场景 |
|-----|---------|
| **进程崩溃状态丢失** | 执行到第 7 步时服务器断电，重启后从头开始，之前 7 步的工具调用全部浪费 |
| **长任务无法分步** | 一个需要调用 20 个工具的复杂任务，必须一口气跑完，不能中途保存进度 |
| **Human-in-the-loop 无法实现** | Day 36 要让图在高风险操作前暂停等待人工确认——图必须先能"暂停"，才能等待 |

Checkpoint 解决的就是这三个问题：**把图在每一个 Node 执行完之后的完整 State 快照持久化下来**，后续可以从任意一个快照恢复继续执行。

### 2.2 Checkpoint vs State：一次图执行 vs 多个历史快照

| 概念 | 是什么 | 数量 |
|-----|-------|------|
| **State** | 图在某一时刻的完整状态（一个 `TypedDict` 实例） | 运行中只有一份"当前状态" |
| **Checkpoint** | 每次 Node 执行完后对 State 打的快照，含元数据（时间戳、下一节点等） | 一次图执行产生多个历史快照 |
| **Checkpointer** | 负责存储和读取 Checkpoint 的组件（MemorySaver / SqliteSaver / 自定义） | 全局一个 |

一次 ReAct 图执行的快照序列大致如下：

```
快照 0：START → call_model 之前（initial_state）
快照 1：call_model 执行完（iteration=1，messages 里有模型回复）
快照 2：call_tools 执行完（messages 里有 ToolMessage）
快照 3：call_model 执行完（iteration=2）
...
快照 N：END 之前的最终状态
```

每次 `graph.invoke()` 都会生成这个快照序列，只要 `thread_id` 相同，快照就属于同一个"会话"，可以从任意快照恢复。

### 2.3 thread_id：区分不同会话

`thread_id` 是 Checkpointer 用来隔离不同会话的键。同一个图实例里，不同 `thread_id` 的快照完全独立：

```python
# 用户 A 的会话（第 1 轮对话）
config_a = {"configurable": {"thread_id": "user-alice-session-1"}}
graph.invoke(state_a, config=config_a)

# 用户 B 的会话（和 A 互不干扰）
config_b = {"configurable": {"thread_id": "user-bob-session-1"}}
graph.invoke(state_b, config=config_b)

# 用户 A 的第 2 轮对话（沿用同一 thread_id，延续上次状态）
graph.invoke(state_a2, config=config_a)
```

`thread_id` 的命名规范：`{用户标识}-{会话标识}`，保证全局唯一。不需要 UUID，语义化的字符串更好调试。

---

## 三、MemorySaver：内存级 Checkpoint 接入

### 3.1 接入方式：compile 时传 checkpointer

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
#                       ^^^^^^^^^^^^^^^^^^^ 只加这一行
```

仅这一行改动，图的每个 Node 执行完之后就会自动把 State 快照存进 `memory`。**图的 Node 和 Edge 定义完全不需要改动**——Checkpoint 是图编译层的横切关注点，不侵入业务逻辑。

### 3.2 invoke 时传 config

接入 Checkpointer 之后，每次 `invoke` 必须传 `config`，否则 LangGraph 不知道这次执行属于哪个会话：

```python
config = {"configurable": {"thread_id": "demo-session-1"}}

# 第一次执行：从 initial_state 开始
result = graph.invoke(initial_state, config=config)

# 同一会话的第二次执行：LangGraph 自动读取上次的最终 State 作为起点
result2 = graph.invoke({"messages": [HumanMessage(content="第二个问题")]}, config=config)
```

第二次 `invoke` 时，LangGraph 先从 Checkpointer 读取 `thread_id="demo-session-1"` 的最新快照，把它和新传入的 `initial_state` 合并（消息追加进历史），再开始执行——这正是"多轮对话记忆"的底层机制。

### 3.3 get_state 与 get_state_history：查询快照

```python
# 查看当前（最新）State 快照
snapshot = graph.get_state(config)
print(snapshot.values)       # 当前 State 字段的值
print(snapshot.next)         # 下一步要执行的节点（暂停时非空，执行完后为空）
print(snapshot.created_at)   # 快照创建时间

# 查看该 thread_id 的全部历史快照（从新到旧）
for snapshot in graph.get_state_history(config):
    print(snapshot.created_at, snapshot.next)
```

`snapshot.next` 是判断图是否暂停的关键：**如果 `next` 非空，说明图还没执行完，在某个节点前等待**；如果 `next` 为空元组 `()`，说明图已跑完到 `END`。

---

## 四、实战：中断 → 查看暂停状态 → 从原状态恢复

### 4.1 用 interrupt_before 让图在指定节点前暂停

`interrupt_before` 是 `compile` 时传入的参数，指定哪些节点在执行前要暂停：

```python
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["call_tools"],   # 每次准备调用工具前，先暂停等待
)
```

执行流程变成：

```
graph.invoke(initial_state, config)
  → call_model 执行完（模型决定要调工具）
  → 到达 call_tools 前 → 自动暂停 ← 这里 invoke 返回了！（还没调工具）
  → 人工确认 / 修改 / 跳过
  → graph.invoke(None, config) 继续执行
  → call_tools 执行
  → call_model 执行
  → END
```

`invoke` 在暂停点返回的是**暂停时的 State 快照**，而不是最终结果——返回值里可以看到模型想调用什么工具。

### 4.2 查看暂停位置与当前 State

```python
# 第一次 invoke：会在 call_tools 前暂停，而不是跑完
result = graph.invoke(initial_state, config=config)

snapshot = graph.get_state(config)
print("下一步节点：", snapshot.next)     # ('call_tools',)
print("模型想调用：")
last_msg = snapshot.values["messages"][-1]
for tc in last_msg.tool_calls:
    print(f"  工具名: {tc['name']}, 参数: {tc['args']}")
```

这里打印出的就是"模型决定要调用什么工具、传什么参数"——Day 36 的 Human-in-the-loop 就是在这一步加入人工审核逻辑：看到高风险工具调用时，可以拒绝或修改参数。

### 4.3 恢复执行：同一 thread_id 再次 invoke(None)

```python
# 恢复执行：传 None 表示"从上次的 Checkpoint 继续，不注入新的初始状态"
final_result = graph.invoke(None, config=config)
print(final_result["messages"][-1].content)
```

`invoke(None)` 的含义：**不提供新的输入，直接从 Checkpointer 读取最新快照，从 `snapshot.next` 指向的节点继续执行**。这就是"中断 → 恢复"的核心机制。

### 4.4 完整演示代码

```python
import os
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

# ── 1. State ───────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int

# ── 2. 工具 ────────────────────────────────────────────────────────────────────
@tool
def get_weather(city: str) -> dict:
    """查询城市天气（仅支持上海/北京）"""
    data = {"上海": {"temp": 28, "condition": "多云"}, "北京": {"temp": 32, "condition": "晴"}}
    return data.get(city, {"error": f"不支持城市：{city}"})

tools = [get_weather]
tool_registry = {t.name: t for t in tools}

# ── 3. 模型 ────────────────────────────────────────────────────────────────────
llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0,
)
llm_with_tools = llm.bind_tools(tools)

MAX_ITERATIONS = 8

# ── 4. 节点 ────────────────────────────────────────────────────────────────────
def call_model(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response], "iteration": state["iteration"] + 1}

def call_tools(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    tool_results = []
    for tc in last_message.tool_calls:
        tool_fn = tool_registry.get(tc["name"])
        result = tool_fn.invoke(tc["args"]) if tool_fn else {"error": f"未知工具: {tc['name']}"}
        tool_results.append(
            ToolMessage(content=str(result), tool_call_id=tc["id"])
        )
    return {"messages": tool_results}

def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if state["iteration"] >= MAX_ITERATIONS:
        return "end"
    if not getattr(last, "tool_calls", None):
        return "end"
    return "continue"

# ── 5. 构建图（含 Checkpoint 和 interrupt_before） ─────────────────────────────
memory = MemorySaver()

builder = StateGraph(AgentState)
builder.add_node("call_model", call_model)
builder.add_node("call_tools", call_tools)
builder.set_entry_point("call_model")
builder.add_conditional_edges("call_model", should_continue,
                              {"continue": "call_tools", "end": END})
builder.add_edge("call_tools", "call_model")

graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["call_tools"],   # 每次调工具前暂停
)

# ── 6. 演示"中断 → 查看 → 恢复" ───────────────────────────────────────────────
config = {"configurable": {"thread_id": "demo-checkpoint-1"}}

initial_state = {
    "messages": [
        SystemMessage(content="你是一个天气助手。"),
        HumanMessage(content="上海今天天气怎么样？"),
    ],
    "iteration": 0,
}

print("=== 第一次 invoke（会在 call_tools 前暂停）===")
try:
    result = graph.invoke(initial_state, config=config)
except GraphRecursionError:
    print("执行超限")

# 查看暂停位置
snapshot = graph.get_state(config)
print(f"下一步节点：{snapshot.next}")          # ('call_tools',)
if snapshot.next:
    last_msg = snapshot.values["messages"][-1]
    print("模型准备调用：")
    for tc in last_msg.tool_calls:
        print(f"  {tc['name']}({tc['args']})")

print("\n=== 确认后恢复执行 ===")
final_result = graph.invoke(None, config=config)
print("最终回答：", final_result["messages"][-1].content)

# ── 7. 查看历史快照（可选） ──────────────────────────────────────────────────
print("\n=== 历史快照序列（从新到旧）===")
for i, snap in enumerate(graph.get_state_history(config)):
    print(f"  快照 {i}: next={snap.next}, iteration={snap.values.get('iteration', 0)}")
```

**执行输出示例**：

```
=== 第一次 invoke（会在 call_tools 前暂停）===
下一步节点：('call_tools',)
模型准备调用：
  get_weather({'city': '上海'})

=== 确认后恢复执行 ===
最终回答：上海今天天气多云，气温 28°C，出行建议穿薄外套。

=== 历史快照序列（从新到旧）===
  快照 0: next=(), iteration=1
  快照 1: next=('call_tools',), iteration=1
  快照 2: next=('call_model',), iteration=0
  快照 3: next=('call_model',), iteration=0
```

---

## 五、SqliteSaver：Checkpoint 跨进程重启存活

### 5.1 MemorySaver vs SqliteSaver

| 维度 | MemorySaver | SqliteSaver |
|-----|-------------|-------------|
| 存储位置 | 进程内存 | SQLite 文件（磁盘） |
| 进程重启后 | **快照丢失** | **快照保留** |
| 适用场景 | 开发调试、单次会话 | 长任务、跨会话持久化、生产 |
| 接入复杂度 | 极低（一行） | 低（需指定文件路径） |

`MemorySaver` 适合开发阶段快速验证 Checkpoint 逻辑；生产环境或需要跨进程恢复的场景用 `SqliteSaver`（或接入 Redis / PostgreSQL 的自定义 Checkpointer）。

### 5.2 SqliteSaver 接入方式

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# 方式 A：上下文管理器（推荐）
with SqliteSaver.from_conn_string("checkpoints.db") as memory:
    graph = builder.compile(checkpointer=memory)
    # graph 的用法和 MemorySaver 完全一致
    result = graph.invoke(initial_state, config=config)

# 方式 B：手动管理连接
memory = SqliteSaver.from_conn_string("checkpoints.db")
graph = builder.compile(checkpointer=memory)
```

切换 Checkpointer 只改这一处初始化，**图的 Node / Edge / invoke 调用完全不用改**——这正是"Checkpoint 是横切关注点"的体现：持久化策略和业务逻辑彻底解耦。

**跨进程恢复演示**（伪代码）：

```python
# 进程 1：开始执行，在 call_tools 前暂停
graph.invoke(initial_state, config={"configurable": {"thread_id": "task-001"}})
# 此时进程 1 退出，checkpoints.db 里有暂停点的快照

# 进程 2：重启后，从暂停点继续
graph.invoke(None, config={"configurable": {"thread_id": "task-001"}})
# invoke(None) + 同一 thread_id → 从数据库读快照 → 继续执行
```

---

## 六、Day 35 知识速查

### Checkpoint 核心 API

| 操作 | 代码 | 说明 |
|-----|------|------|
| 接入 Checkpointer | `builder.compile(checkpointer=MemorySaver())` | 编译时传入，不改节点逻辑 |
| 执行时指定会话 | `config = {"configurable": {"thread_id": "..."}}` | 必传，否则报错 |
| 设置 recursion_limit | `config = {"recursion_limit": 50, "configurable": {...}}` | 可选，默认 25 |
| 指定中断节点 | `compile(interrupt_before=["node_name"])` | 在该节点执行前自动暂停 |
| 恢复执行 | `graph.invoke(None, config=config)` | 传 None + 同 thread_id |
| 查看当前快照 | `graph.get_state(config)` | 返回 `StateSnapshot` |
| 查看历史快照 | `graph.get_state_history(config)` | 返回快照迭代器，从新到旧 |
| 手动修改状态 | `graph.update_state(config, {"field": value})` | 恢复前可修正 State |

### StateSnapshot 关键字段

```python
snapshot = graph.get_state(config)
snapshot.values        # dict：当前 State 字段值
snapshot.next          # tuple：下一步要执行的节点，() 表示已结束
snapshot.config        # dict：这个快照对应的 config
snapshot.created_at    # str：ISO 格式时间戳
```

### 终止条件双保险

| 层级 | 写法 | 触发行为 |
|-----|------|---------|
| 业务层（首选） | 路由函数里 `if iteration >= MAX_ITERATIONS: return "end"` | 走"结束"分支，优雅降级 |
| 框架层（兜底） | `config = {"recursion_limit": N, ...}` | 抛 `GraphRecursionError`，需 try/except |

---

## 七、实践任务

- [ ] 把 4.4 的完整代码跑通，观察第一次 `invoke` 在 `call_tools` 前暂停、`snapshot.next` 为 `('call_tools',)`
- [ ] 用 `graph.invoke(None, config=config)` 恢复执行，拿到最终天气回答
- [ ] 打印 `graph.get_state_history(config)` 的全部快照序列，数一数有几个快照、`next` 字段各是什么
- [ ] 把 `interrupt_before=["call_tools"]` 去掉重新编译，对比"有中断/无中断"两种图的运行差异
- [ ] 尝试在恢复前调用 `graph.update_state(config, {"iteration": 100})`，看图是否因此提前结束（验证 State 可以在恢复前被修改）
- [ ] 把 `MemorySaver` 换成 `SqliteSaver.from_conn_string("ckpt.db")`，运行一次后用 SQLite 客户端（或 Python `sqlite3`）查看 `checkpoints` 表里的数据

**产出标准**：能演示一次完整的"中断 → 用 `get_state` 确认暂停位置和工具调用参数 → `invoke(None)` 恢复 → 拿到最终回答"过程；能说清 `thread_id`、`interrupt_before`、`invoke(None)` 三者各自负责什么。

---

## 八、下一步预告

Day 36 进入 **Human-in-the-loop 人工审核节点**：今天的 `interrupt_before=["call_tools"]` 只是让图"暂停"，但还没有加入人工决策逻辑——下一步是在暂停点读取模型准备调用的工具和参数，判断是否高风险，然后选择"批准继续 / 修改参数后继续 / 拒绝并告知模型"三条路径之一。`graph.update_state()` 是实现"修改参数后继续"的关键——今天已经演示了它的基本用法，Day 36 会在真实审核场景里把它用起来。
