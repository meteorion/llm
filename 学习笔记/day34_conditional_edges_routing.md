# Day 34：条件边与分支路由

> 学习目标：掌握 `add_conditional_edges` 的用法，理解路由函数如何根据 State 内容动态决定下一个节点；给 Day 33 的 ReAct 图加一条错误处理分支——工具调用失败走"重试节点"、成功走"汇总回答节点"，并能构造失败案例观察图确实走了重试分支而不是崩溃
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 34
>
> 🧭 导航：[← Day 33 · LangGraph 基础：用状态图重写 ReAct](day33_langgraph_basics_react_rewrite.md) → [Day 35 · 循环终止与 Checkpoint 持久化](day35_checkpoint_and_loop_termination.md)

---

## 目录

- [一、从二路到多路：条件边解决什么问题](#一从二路到多路条件边解决什么问题)
  - [1.1 Day 33 的 should_continue 只是最简单的条件边](#11-day-33-的-should_continue-只是最简单的条件边)
  - [1.2 手写 while 里的 if/elif/else 散落在哪里](#12-手写-while-里的-ifelifelse-散落在哪里)
  - [1.3 条件边把分支变成图的一等公民](#13-条件边把分支变成图的一等公民)
- [二、add_conditional_edges 的完整用法](#二add_conditional_edges-的完整用法)
  - [2.1 三个参数：源节点、路由函数、映射表](#21-三个参数源节点路由函数映射表)
  - [2.2 路由函数的签名与三条约束](#22-路由函数的签名与三条约束)
  - [2.3 映射表写法 vs 直接返回节点名](#23-映射表写法-vs-直接返回节点名)
- [三、条件边 vs 固定边：什么时候用哪个](#三条件边-vs-固定边什么时候用哪个)
  - [3.1 判断标准：下一步是否依赖运行时状态](#31-判断标准下一步是否依赖运行时状态)
  - [3.2 常见误区：把该固定的边写成条件边](#32-常见误区把该固定的边写成条件边)
- [四、实战：给 ReAct 图加错误处理分支](#四实战给-react-图加错误处理分支)
  - [4.1 需求与图结构：失败走重试，成功走汇总](#41-需求与图结构失败走重试成功走汇总)
  - [4.2 State 增加两个字段：tool_ok 与 retry_count](#42-state-增加两个字段tool_ok-与-retry_count)
  - [4.3 新增节点与路由函数](#43-新增节点与路由函数)
  - [4.4 完整代码](#44-完整代码)
  - [4.5 构造失败案例：观察图走了重试分支](#45-构造失败案例观察图走了重试分支)
- [五、Day 34 知识速查](#五day-34-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、从二路到多路：条件边解决什么问题

### 1.1 Day 33 的 should_continue 只是最简单的条件边

Day 33 的图里已经用过一次条件边了——`should_continue` 做的是"继续 / 结束"的二选一：

```python
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if state["iteration"] >= MAX_ITERATIONS:
        return "end"
    if not getattr(last_message, "tool_calls", None):
        return "end"
    return "continue"

graph.add_conditional_edges("call_model", should_continue, {"continue": "call_tools", "end": END})
```

这是条件边最基础的形态：**只有两个出口**。今天要把它扩展成三路甚至多路——真正体现出 LangGraph 相比手写 `while` 的表达力提升。

### 1.2 手写 while 里的 if/elif/else 散落在哪里

回想 Day 25 的手写版：一旦工具调用可能失败，错误处理逻辑会以 `if/elif/else` 的形式散落在 `while` 循环体的各个角落：

```python
while iteration < max_iter:
    response = client.chat.completions.create(...)
    msg = response.choices[0].message
    if not msg.tool_calls:
        return msg.content                       # 分支 1：直接回答
    for tc in msg.tool_calls:
        result = execute_tool(tc)
        if "error" in result:                    # 分支 2：工具失败
            if retry_count < MAX_RETRY:
                retry_count += 1
                continue                         # 靠 continue 跳回循环顶
            else:
                messages.append(降级提示)         # 分支 3：重试耗尽
        else:
            messages.append(正常结果)             # 分支 4：工具成功
```

问题不在于"写不出来"，而在于：这些分支**没有名字、无法可视化、出错时不知道当前在哪条分支上**。`continue` 跳到哪、`else` 对应哪种情况，只能靠读代码在脑子里重建控制流。

### 1.3 条件边把分支变成图的一等公民

LangGraph 的做法是：**每个分支目标都是一个有名字的节点，每条分支都是图里一条可命名、可画出来的边**。

```
手写 while 的隐式分支              LangGraph 的显式分支
────────────────────────         ──────────────────────────────
if not tool_calls: return         call_model --end--> END
if error and can_retry: continue  call_tools --retry--> retry_node
if error and exhausted: ...       call_tools --done--> summarize（降级）
else: append(result)              call_tools --done--> summarize（正常）
```

分支一旦变成"命名的边"，`draw_mermaid()` 就能把它画出来，出错时看一眼日志里的边标注就知道图走了哪条路——这是 Day 34 相比 Day 33 的核心增量。

---

## 二、add_conditional_edges 的完整用法

### 2.1 三个参数：源节点、路由函数、映射表

```python
graph.add_conditional_edges(
    "call_tools",        # ① 源节点：从哪个节点执行完之后开始判断
    route_after_tools,   # ② 路由函数：接收 State，返回一个字符串 key
    {                    # ③ 映射表：把 key 映射到目标节点名
        "retry": "retry_node",
        "done": "summarize",
    },
)
```

执行时机：源节点 `call_tools` 执行完、State 更新完之后，LangGraph 立刻调用 `route_after_tools(state)`，拿到返回的 key，再去映射表里查到目标节点跳过去。

### 2.2 路由函数的签名与三条约束

路由函数和 Node 长得像（都接收 `State`），但职责完全不同，有三条硬约束：

| 约束 | 说明 | 违反的后果 |
|-----|------|-----------|
| **只读 State** | 路由函数只做判断，不返回状态更新 | 返回 dict 会被当成 key 找不到而报错 |
| **返回字符串 key** | 返回值必须是映射表里存在的 key | 返回未登记的 key 抛 `ValueError` |
| **不是 Node** | 它不出现在节点列表里，但会出现在 `draw_mermaid()` 的边标注上 | —— |

```python
def route_after_tools(state: AgentState) -> str:
    # ✅ 只读 state，返回字符串
    if state["tool_ok"]:
        return "done"
    if state["retry_count"] < MAX_RETRIES:
        return "retry"
    return "done"    # 重试耗尽，也走 done（带着错误信息交给模型降级汇总）

    # ❌ 错误示范：路由函数里改状态
    # return {"retry_count": state["retry_count"] + 1}   # 这不是 Node，改状态要放到节点里
```

**记忆点：Node 负责"改状态"，路由函数负责"看状态决定去哪"——两者职责严格分离，改状态的活永远交给 Node。**

### 2.3 映射表写法 vs 直接返回节点名

`add_conditional_edges` 支持两种写法，映射表写法更推荐：

```python
# 写法 A（推荐）：路由函数返回抽象 key，映射表决定 key → 节点
graph.add_conditional_edges("call_tools", route_after_tools,
                            {"retry": "retry_node", "done": "summarize"})

# 写法 B：路由函数直接返回节点名（省掉映射表）
def route_after_tools(state) -> str:
    return "retry_node" if not state["tool_ok"] else "summarize"
graph.add_conditional_edges("call_tools", route_after_tools)
```

| 维度 | 写法 A（有映射表） | 写法 B（直接返回节点名） |
|-----|------------------|----------------------|
| 路由逻辑与节点名 | 解耦：改节点名只改映射表 | 耦合：改节点名要动路由函数 |
| 可读性 | key 是语义化的（`retry`/`done`） | 直接是节点名，稍隐晦 |
| `draw_mermaid()` 标注 | 用 key 标注边，更清晰 | 用节点名标注 |

写法 A 的 key（`retry` / `done`）表达的是"业务语义"，节点名（`retry_node` / `summarize`）表达的是"实现"——两者解耦后，重命名节点或调整路由目标都只改一处。

---

## 三、条件边 vs 固定边：什么时候用哪个

### 3.1 判断标准：下一步是否依赖运行时状态

一句话判断标准：**下一步去哪，是不是由 State 的运行时内容决定的？**

| 场景 | 用哪种边 | 原因 |
|-----|---------|------|
| `call_tools` 执行完固定回到 `call_model` | **固定边** | 无论工具结果如何，都要回模型，不看 State |
| `call_model` 后决定"继续调工具 / 结束" | **条件边** | 取决于模型这轮有没有发起 `tool_calls` |
| `call_tools` 后决定"重试 / 汇总" | **条件边** | 取决于工具执行成功还是失败 |
| `retry_node` 执行完固定回到 `call_model` | **固定边** | 重试的动作固定就是"回去让模型重新决策" |

固定边 `add_edge("a", "b")` 表达的是"a 之后**必然**去 b"；条件边表达的是"a 之后**看情况**去 b 或 c"。

### 3.2 常见误区：把该固定的边写成条件边

新手容易犯的错：给每条边都套一个"以防万一"的路由函数。

```python
# ❌ 过度设计：retry 之后其实必然回 call_model，却硬套条件边
def route_after_retry(state) -> str:
    return "back_to_model"   # 永远只返回这一个值
graph.add_conditional_edges("retry_node", route_after_retry, {"back_to_model": "call_model"})

# ✅ 只有一个确定去向，用固定边
graph.add_edge("retry_node", "call_model")
```

判断很简单：**如果路由函数所有分支最终只可能返回一个值，那它就不该是条件边**。条件边的价值在于"有真正的分叉"，没有分叉的地方用固定边，图更干净、`draw_mermaid()` 也不会画出误导性的"假分支"。

---

## 四、实战：给 ReAct 图加错误处理分支

### 4.1 需求与图结构：失败走重试，成功走汇总

在 Day 33 的 ReAct 图基础上，给工具执行加错误处理：

- 工具执行**成功** → 走"汇总回答节点"（`summarize`），让模型基于工具结果给出最终答案
- 工具执行**失败**且还有重试额度 → 走"重试节点"（`retry_node`），回到模型让它修正参数重新调用
- 工具执行**失败**且重试耗尽 → 也走 `summarize`，但带着错误信息让模型给出降级回答（而不是崩溃）

新的图结构（相比 Day 33 多了 `retry_node` 和 `summarize` 两个节点、一条 `route_after_tools` 条件边）：

```
START
  ↓
call_model ──should_continue──┬─ end ──→ END
  ↑                           └─ continue ──→ call_tools
  │                                              ↓
  │                                    route_after_tools
  │                                        ┌─────┴─────┐
  └──────── retry_node ◄── retry ──────────┘         done ──→ summarize ──→ END
```

### 4.2 State 增加两个字段：tool_ok 与 retry_count

对比 Day 33 的 `AgentState`，新增两个字段来支撑分支判断：

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int
    tool_ok: bool        # 新增：上一次 call_tools 是否全部成功
    retry_count: int     # 新增：已经重试了几次（区别于 iteration）
```

`retry_count` 为什么不复用 `iteration`：`iteration` 统计的是"模型被调用了几轮"，`retry_count` 统计的是"因工具失败而重试了几次"——两者语义不同，混用会导致"正常多轮对话"被误判成"重试太多次"。这正是 Day 33 说的"State 字段要各司其职"。

### 4.3 新增节点与路由函数

```python
# call_tools 改造：执行时记录成功/失败到 tool_ok
def call_tools(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    tool_results, all_ok = [], True
    for tc in last_message.tool_calls:
        tool_fn = tool_registry.get(tc["name"])
        if tool_fn:
            result = tool_fn.invoke(tc["args"])
        else:
            result = {"error": f"未知工具: {tc['name']}"}
        if isinstance(result, dict) and "error" in result:   # 约定：工具返回含 error 键即为失败
            all_ok = False
        tool_results.append(
            ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tc["id"])
        )
    return {"messages": tool_results, "tool_ok": all_ok}

# 新增路由函数：只读 state，返回 retry / done
def route_after_tools(state: AgentState) -> str:
    if state["tool_ok"]:
        return "done"
    if state["retry_count"] < MAX_RETRIES:
        return "retry"
    return "done"    # 重试耗尽，降级：带着错误信息去汇总

# 新增重试节点：只负责记账（+1），动作交给固定边回 call_model
def retry_node(state: AgentState) -> dict:
    print(f"⟳ 工具失败，第 {state['retry_count'] + 1} 次重试，回到模型修正参数")
    return {"retry_count": state["retry_count"] + 1}

# 新增汇总节点：让模型基于（成功或失败的）工具结果给出最终回答
def summarize(state: AgentState) -> dict:
    response = llm.invoke(state["messages"] + [
        HumanMessage(content="请基于以上工具返回结果，给用户一个完整、自然的最终回答。"
                             "如果工具返回了错误，就如实说明查询失败并给出你能提供的建议。")
    ])
    return {"messages": [response]}
```

### 4.4 完整代码

```python
import json
import os
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# ── 1. State：在 Day 33 基础上加 tool_ok / retry_count ──────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int
    tool_ok: bool
    retry_count: int

# ── 2. 工具：get_weather 对未知城市返回 error（用来制造失败） ─────────────────────
@tool
def get_weather(city: str) -> dict:
    """查询指定城市的天气。仅支持：上海、北京。"""
    data = {"上海": {"temp": 28, "condition": "多云"}, "北京": {"temp": 32, "condition": "晴"}}
    return data.get(city, {"error": f"没有 {city} 的天气数据，请确认城市名（仅支持上海/北京）"})

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
MAX_RETRIES = 2

# ── 4. 节点 ────────────────────────────────────────────────────────────────────
def call_model(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response], "iteration": state["iteration"] + 1}

def call_tools(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    tool_results, all_ok = [], True
    for tc in last_message.tool_calls:
        tool_fn = tool_registry.get(tc["name"])
        result = tool_fn.invoke(tc["args"]) if tool_fn else {"error": f"未知工具: {tc['name']}"}
        if isinstance(result, dict) and "error" in result:
            all_ok = False
        tool_results.append(
            ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tc["id"])
        )
    return {"messages": tool_results, "tool_ok": all_ok}

def retry_node(state: AgentState) -> dict:
    print(f"⟳ 工具失败，第 {state['retry_count'] + 1} 次重试，回到模型修正参数")
    return {"retry_count": state["retry_count"] + 1}

def summarize(state: AgentState) -> dict:
    response = llm.invoke(state["messages"] + [
        HumanMessage(content="请基于以上工具返回结果，给用户一个完整、自然的最终回答。"
                             "如果工具返回了错误，就如实说明查询失败并给出你能提供的建议。")
    ])
    return {"messages": [response]}

# ── 5. 路由函数（两条条件边） ────────────────────────────────────────────────────
def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if state["iteration"] >= MAX_ITERATIONS:
        return "end"
    if not getattr(last, "tool_calls", None):
        return "end"
    return "continue"

def route_after_tools(state: AgentState) -> str:
    if state["tool_ok"]:
        return "done"
    if state["retry_count"] < MAX_RETRIES:
        return "retry"
    return "done"

# ── 6. 构建图 ──────────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)
builder.add_node("call_model", call_model)
builder.add_node("call_tools", call_tools)
builder.add_node("retry_node", retry_node)
builder.add_node("summarize", summarize)

builder.set_entry_point("call_model")

# 条件边 1：模型之后——继续调工具 / 结束
builder.add_conditional_edges("call_model", should_continue,
                              {"continue": "call_tools", "end": END})
# 条件边 2：工具之后——失败重试 / 完成汇总
builder.add_conditional_edges("call_tools", route_after_tools,
                              {"retry": "retry_node", "done": "summarize"})
# 固定边：重试之后必然回模型；汇总之后必然结束
builder.add_edge("retry_node", "call_model")
builder.add_edge("summarize", END)

graph = builder.compile()

# ── 7. 运行 ────────────────────────────────────────────────────────────────────
def run_agent(user_input: str) -> str:
    initial_state = {
        "messages": [
            SystemMessage(content="你是一个天气助手，可以查询上海和北京的天气。"),
            HumanMessage(content=user_input),
        ],
        "iteration": 0,
        "tool_ok": True,
        "retry_count": 0,
    }
    final_state = graph.invoke(initial_state)
    return final_state["messages"][-1].content
```

### 4.5 构造失败案例：观察图走了重试分支

**成功案例**（城市在支持列表里）：

```python
print(run_agent("上海今天天气怎么样？"))
# 路径：call_model → call_tools(成功, tool_ok=True) → route_after_tools 返回 "done"
#      → summarize → END
# 不打印任何 "⟳ 重试"，直接给出天气回答
```

**失败案例**（城市不在支持列表，触发重试分支）：

```python
print(run_agent("广州今天天气怎么样？"))
# 路径：call_model → call_tools(失败, tool_ok=False)
#      → route_after_tools 返回 "retry" → retry_node（打印 "⟳ 第 1 次重试"）
#      → call_model（模型看到 error 消息，意识到广州不支持）
#      → 模型这次不再调工具，直接回答 → should_continue 返回 "end" → END
# 关键：程序没有崩溃，而是走了 retry 分支，最终给出"广州暂不支持"的降级回答
```

**验证图确实走了重试分支的三种方式**：

```python
# 方式 1：retry_node 里的 print 会打印出来（最直接）
# 方式 2：用 stream 逐节点观察经过了哪些节点
for event in graph.stream(initial_state):
    print(list(event.keys()))   # 依次打印 ['call_model'] ['call_tools'] ['retry_node'] ...

# 方式 3：可视化图结构，确认 retry 边存在
print(graph.get_graph().draw_mermaid())
# call_tools -. retry .-> retry_node
# call_tools -. done .-> summarize
# retry_node --> call_model
```

**这就是 Day 34 的核心产出：能构造一个失败案例，观察到图确实走了 `retry` 分支去到 `retry_node`，而不是像手写版那样抛异常崩溃。**

---

## 五、Day 34 知识速查

### 条件边 API 速查

| 概念 | 代码 | 说明 |
|-----|------|------|
| 添加条件边 | `add_conditional_edges(源, 路由函数, 映射表)` | 源节点执行完后按路由函数结果跳转 |
| 路由函数签名 | `def fn(state) -> str` | 接收 State，返回映射表里的 key |
| 映射表 | `{"retry": "retry_node", "done": "summarize"}` | key → 目标节点名 |
| 省略映射表 | `add_conditional_edges(源, 路由函数)` | 路由函数直接返回节点名 |
| 跳到结束 | 映射表里写 `{"end": END}` | 条件边也能直接连 END |

### 条件边 vs 固定边判断表

| 下一步去向 | 用哪种边 |
|-----------|---------|
| 由 State 运行时内容决定（有真正分叉） | 条件边 `add_conditional_edges` |
| 恒定，不看 State（无分叉） | 固定边 `add_edge` |
| 路由函数所有分支只返回一个值 | 说明该用固定边（过度设计信号） |

### 路由函数的三条约束

```python
def route_after_tools(state: AgentState) -> str:
    # ① 只读 state，不返回状态更新（改状态是 Node 的活）
    # ② 返回值必须是映射表里存在的字符串 key
    # ③ 它不是 Node，但会出现在 draw_mermaid() 的边标注上
    if state["tool_ok"]:
        return "done"
    return "retry" if state["retry_count"] < MAX_RETRIES else "done"
```

### 本次给图新增的元素（相比 Day 33）

| 新增 | 内容 |
|-----|------|
| State 字段 | `tool_ok: bool`、`retry_count: int` |
| 节点 | `retry_node`（记账 +1）、`summarize`（降级/正常汇总） |
| 条件边 | `route_after_tools`：`retry` / `done` 两路 |
| 固定边 | `retry_node → call_model`、`summarize → END` |

---

## 六、实践任务

- [ ] 把 4.4 的完整代码跑通，先用"上海今天天气怎么样？"验证成功路径（不打印重试、直接汇总）
- [ ] 用"广州今天天气怎么样？"触发失败，观察控制台打印出 `⟳ ... 重试`，确认图走了 `retry` 分支而非崩溃
- [ ] 用 `graph.stream(initial_state)` 逐节点打印经过的节点名，画出成功案例和失败案例各自的真实路径
- [ ] 运行 `graph.get_graph().draw_mermaid()`，确认图里有 `call_tools -. retry .-> retry_node` 这条边
- [ ] 把 `MAX_RETRIES` 改成 0，观察失败时图直接走 `done` 去 `summarize`（降级回答），验证重试耗尽的分支
- [ ] 试着把 `retry_node → call_model` 这条固定边误写成条件边（路由函数只返回一个值），对比 `draw_mermaid()` 输出，体会"假分支"的误导性

**产出标准**：一张能同时演示"成功走汇总 / 失败走重试"两条路径的图；能说清 `route_after_tools` 的三个返回值分别对应图里哪条边，以及为什么 `retry_node → call_model` 用固定边而不是条件边。

---

## 七、下一步预告

Day 35 进入**循环终止与 Checkpoint 持久化**：今天的图里 `MAX_ITERATIONS` 和 `MAX_RETRIES` 是靠路由函数里的常量硬编码控制终止的——Day 35 会讲这些终止条件在 LangGraph 里更规范的表达方式，以及用 `MemorySaver` 给图加上 Checkpoint，让一次执行可以中断后从上次的 State 恢复。今天我们把 `retry_count` 显式放进了 State，正是为了 Day 35：只有状态显式化了，"中断—恢复"时才知道上次重试到第几次、该从哪一步继续。
