# Day 36：Human-in-the-loop 人工审核节点

> 学习目标：在 Day 35 的 Checkpoint 暂停基础上，实现完整的人工审核决策逻辑——给"高风险"工具（如发送邮件）加审核节点，模拟"批准 / 修改参数 / 拒绝"三条路径，确保拒绝时工具不会被调用
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 36
>
> 🧭 导航：[← Day 35 · 循环终止与 Checkpoint 持久化](day35_checkpoint_and_loop_termination.md) → [Day 37 · 第 5 周复盘](day37_week5_review.md)

---

## 目录

- [一、从"暂停"到"审核"：Day 35 还差什么](#一从暂停到审核day-35-还差什么)
  - [1.1 Day 35 实现了暂停，但没有人工决策](#11-day-35-实现了暂停但没有人工决策)
  - [1.2 哪些操作必须加人工确认](#12-哪些操作必须加人工确认)
  - [1.3 三条审核路径的设计目标](#13-三条审核路径的设计目标)
- [二、三条审核路径的实现原理](#二三条审核路径的实现原理)
  - [2.1 路径 1：批准——invoke(None) 直接继续](#21-路径-1批准invokenone-直接继续)
  - [2.2 路径 2：修改参数后继续——update_state 改工具入参](#22-路径-2修改参数后继续update_state-改工具入参)
  - [2.3 路径 3：拒绝——注入假 ToolMessage 跳过工具执行](#23-路径-3拒绝注入假-toolmessage-跳过工具执行)
- [三、实战：给"发送邮件"工具加人工审核](#三实战给发送邮件工具加人工审核)
  - [3.1 场景设计：为什么选发送邮件](#31-场景设计为什么选发送邮件)
  - [3.2 图结构：审核点插在哪里](#32-图结构审核点插在哪里)
  - [3.3 完整代码](#33-完整代码)
  - [3.4 演示三条路径](#34-演示三条路径)
- [四、高风险操作的判断标准与设计原则](#四高风险操作的判断标准与设计原则)
  - [4.1 哪些操作必须加确认](#41-哪些操作必须加确认)
  - [4.2 粒度选择：按节点 vs 按工具名过滤](#42-粒度选择按节点-vs-按工具名过滤)
  - [4.3 update_state 的 as_node 参数：为什么关键](#43-update_state-的-as_node-参数为什么关键)
- [五、Day 36 知识速查](#五day-36-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、从"暂停"到"审核"：Day 35 还差什么

### 1.1 Day 35 实现了暂停，但没有人工决策

Day 35 用 `interrupt_before=["call_tools"]` 实现了"在调用工具前暂停"，然后用 `invoke(None)` 恢复——但这个流程只有**暂停**和**直接继续**两种选择，没有加入任何人工判断：

```
Day 35 的流程：
  graph.invoke(initial_state, config)   → 暂停在 call_tools 前
  graph.invoke(None, config)            → 直接继续，工具照常执行

Day 36 要加的：
  graph.invoke(initial_state, config)   → 暂停在 call_tools 前
  人工查看工具调用内容 → 判断风险等级
  → 路径 A：批准       → invoke(None)         → 工具正常执行
  → 路径 B：修改参数   → update_state + invoke(None)  → 用修正后的参数执行
  → 路径 C：拒绝       → update_state 注入拒绝结果    → 工具不执行，模型收到拒绝通知
```

Day 36 的核心增量是**路径 B 和路径 C**——这两条路径都依赖 `update_state`：在恢复之前先修改 State，让图从一个"人工干预后的状态"继续，而不是从原始的暂停点继续。

### 1.2 哪些操作必须加人工确认

不是每个工具调用都需要审核——审核本身有成本（延迟 + 人力）。判断标准：**操作是否满足以下任意一条**。

| 判断条件 | 示例 |
|---------|------|
| **不可逆**：执行后无法撤销 | 发送邮件/消息、删除文件、提交订单 |
| **涉及外部副作用**：影响系统边界之外的状态 | 调用第三方 API 写入数据、发布内容 |
| **涉及资金**：任何金额的支付或转账 | 下单、充值、退款 |
| **涉及隐私数据**：读取或传输敏感信息 | 查询用户个人信息、导出数据 |
| **高影响范围**：一个操作影响大量对象 | 批量发送通知、批量修改权限 |

对比：查询天气、汇率、公开数据——这些是**只读、可重复、无副作用**的操作，不需要审核。

### 1.3 三条审核路径的设计目标

| 路径 | 场景 | 工具最终是否执行 |
|-----|------|----------------|
| **批准** | 工具调用内容符合预期，直接放行 | ✅ 执行，参数不变 |
| **修改参数** | 内容可以，但某个参数需要调整（如收件人写错） | ✅ 执行，用修正后的参数 |
| **拒绝** | 操作不合适，不允许执行 | ❌ 不执行，模型收到拒绝通知后给用户合理解释 |

---

## 二、三条审核路径的实现原理

### 2.1 路径 1：批准——invoke(None) 直接继续

这和 Day 35 完全一样，无需改动 State：

```python
# 审核后批准
graph.invoke(None, config=config)
# 图从暂停点继续，call_tools 正常执行
```

### 2.2 路径 2：修改参数后继续——update_state 改工具入参

暂停点的 State 里，最后一条消息是模型的 `AIMessage`，它的 `tool_calls` 字段包含了模型决定调用的工具名和参数。修改参数的核心：**替换掉这条 `AIMessage`，把 `tool_calls` 里的参数改成修正后的值**。

```python
from langchain_core.messages import AIMessage

# 查看当前暂停状态
snapshot = graph.get_state(config)
last_ai_msg = snapshot.values["messages"][-1]   # 模型的决策消息

# 构造修改后的 AIMessage（保持 id 和其他字段不变，只改参数）
corrected_tool_call = {
    **last_ai_msg.tool_calls[0],
    "args": {"to": "correct@example.com", "subject": last_ai_msg.tool_calls[0]["args"]["subject"],
             "body": last_ai_msg.tool_calls[0]["args"]["body"]},
}
corrected_msg = AIMessage(
    content=last_ai_msg.content,
    tool_calls=[corrected_tool_call],
    id=last_ai_msg.id,        # 保持相同 id，update_state 会用新消息替换掉旧的
)

# 更新 State，用修正后的消息替换原始消息
graph.update_state(config, {"messages": [corrected_msg]})

# 继续执行，call_tools 会用修正后的参数
graph.invoke(None, config=config)
```

`add_messages` Reducer 在 `update_state` 时也生效：相同 `id` 的消息会被**替换**（而不是追加），这就是为什么要保持 `id=last_ai_msg.id`——让新消息覆盖旧消息，而不是追加一条新的。

### 2.3 路径 3：拒绝——注入假 ToolMessage 跳过工具执行

拒绝的目标是：**工具不执行，但模型能收到"被拒绝"的通知，进而给用户一个合理解释**。

实现思路：**跳过 `call_tools` 节点，直接注入一条"操作被拒绝"的 ToolMessage**，让图的状态看起来像"call_tools 已经执行完了，结果是拒绝"。这样图会继续去 `call_model`，模型看到拒绝结果后自然会告诉用户操作未被执行。

```python
snapshot = graph.get_state(config)
last_ai_msg = snapshot.values["messages"][-1]

# 为每个待执行的工具调用，构造一条"拒绝"ToolMessage
rejection_messages = [
    ToolMessage(
        content="操作已被人工审核拒绝，工具未执行。请告知用户此操作不被允许。",
        tool_call_id=tc["id"],
    )
    for tc in last_ai_msg.tool_calls
]

# 关键：as_node="call_tools" 告诉 LangGraph 这次更新是"call_tools 节点的输出"
# 这样图知道 call_tools 已经"执行完了"，下一步该去 call_model
graph.update_state(config, {"messages": rejection_messages}, as_node="call_tools")

# 继续执行，从 call_model 开始（不再经过 call_tools）
graph.invoke(None, config=config)
```

**`as_node="call_tools"` 是拒绝路径的关键**：它告诉 Checkpointer 这次 State 更新是"call_tools 节点执行完之后的结果"，让图的下一步正确指向 `call_model`，而不是再次尝试执行 `call_tools`。

---

## 三、实战：给"发送邮件"工具加人工审核

### 3.1 场景设计：为什么选发送邮件

发送邮件是典型的"不可逆 + 外部副作用"操作：发出去就撤不回来，收件人是真实的外部用户。模型可能把收件人地址写错、把内容搞得不礼貌，这些错误如果不审核就直接发出去，后果难以弥补。

演示场景：用户说"帮我给张三发邮件说明天开会推迟"，模型调用 `send_email` 工具，系统在发送前暂停让人工确认收件地址和正文。

### 3.2 图结构：审核点插在哪里

```
START
  ↓
call_model ──should_continue──┬─ end ──→ END
  ↑                           └─ continue ──→ [interrupt] call_tools ──→ call_model
```

`interrupt_before=["call_tools"]` 在每次到达 `call_tools` 前自动暂停。对于天气/汇率这类低风险工具，可以用**工具名过滤**（见第四节），只拦截高风险工具的调用；这里为简洁起见，对所有工具调用都暂停审核。

### 3.3 完整代码

```python
import os
import json
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# ── 1. State ───────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int

# ── 2. 工具（高风险：发送邮件） ─────────────────────────────────────────────────
@tool
def send_email(to: str, subject: str, body: str) -> dict:
    """发送电子邮件。该操作不可逆，发送前需要人工确认。"""
    print(f"\n📧 [模拟发送] 收件人: {to} | 主题: {subject}")
    print(f"   正文: {body}")
    return {"status": "sent", "to": to, "subject": subject}

@tool
def get_contact(name: str) -> dict:
    """查询联系人的邮件地址（只读操作，无需审核）"""
    contacts = {"张三": "zhangsan@example.com", "李四": "lisi@example.com"}
    return contacts.get(name, {"error": f"联系人 {name} 不存在"})

tools = [send_email, get_contact]
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
            ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tc["id"])
        )
    return {"messages": tool_results}

def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if state["iteration"] >= MAX_ITERATIONS:
        return "end"
    if not getattr(last, "tool_calls", None):
        return "end"
    return "continue"

# ── 5. 构建图（含 interrupt_before） ──────────────────────────────────────────
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
    interrupt_before=["call_tools"],
)

# ── 6. 审核辅助函数 ───────────────────────────────────────────────────────────
def show_pending_tool_calls(config: dict) -> list:
    """展示待审核的工具调用，返回 tool_calls 列表"""
    snapshot = graph.get_state(config)
    if not snapshot.next:
        return []
    last_msg = snapshot.values["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", []) or []
    if tool_calls:
        print("\n🔍 待审核的工具调用：")
        for i, tc in enumerate(tool_calls):
            print(f"  [{i}] 工具名: {tc['name']}")
            for k, v in tc["args"].items():
                print(f"      {k}: {v}")
    return tool_calls

def approve(config: dict):
    """路径 A：批准，直接继续"""
    print("✅ 已批准，继续执行...")
    return graph.invoke(None, config=config)

def modify_and_approve(config: dict, tool_index: int, new_args: dict):
    """路径 B：修改参数后批准"""
    snapshot = graph.get_state(config)
    last_ai_msg = snapshot.values["messages"][-1]
    old_tc = last_ai_msg.tool_calls[tool_index]

    corrected_tc = {**old_tc, "args": {**old_tc["args"], **new_args}}
    corrected_msg = AIMessage(
        content=last_ai_msg.content,
        tool_calls=[corrected_tc if i == tool_index else tc
                    for i, tc in enumerate(last_ai_msg.tool_calls)],
        id=last_ai_msg.id,
    )
    graph.update_state(config, {"messages": [corrected_msg]})
    print(f"✏️  已修改参数 {new_args}，继续执行...")
    return graph.invoke(None, config=config)

def reject(config: dict):
    """路径 C：拒绝，注入拒绝结果，工具不执行"""
    snapshot = graph.get_state(config)
    last_ai_msg = snapshot.values["messages"][-1]
    rejection_msgs = [
        ToolMessage(
            content="操作已被人工审核拒绝，工具未执行。请告知用户此次操作不被允许，并询问是否有其他需求。",
            tool_call_id=tc["id"],
        )
        for tc in last_ai_msg.tool_calls
    ]
    graph.update_state(config, {"messages": rejection_msgs}, as_node="call_tools")
    print("❌ 已拒绝，工具调用被取消...")
    return graph.invoke(None, config=config)
```

### 3.4 演示三条路径

**准备初始状态（三条路径共用）：**

```python
initial_state = {
    "messages": [
        SystemMessage(content="你是一个邮件助手，可以查询联系人并发送邮件。"),
        HumanMessage(content="帮我给张三发邮件，告诉他明天的会议推迟到下午3点。"),
    ],
    "iteration": 0,
}
```

**路径 A：批准**

```python
config_a = {"configurable": {"thread_id": "demo-approve"}}
graph.invoke(initial_state, config=config_a)   # 图暂停在 call_tools 前

tool_calls = show_pending_tool_calls(config_a)
# 🔍 待审核的工具调用：
#   [0] 工具名: send_email
#       to: zhangsan@example.com
#       subject: 会议时间调整通知
#       body: 张三，您好。明天的会议推迟到下午3点，请知悉。

result_a = approve(config_a)
# ✅ 已批准，继续执行...
# 📧 [模拟发送] 收件人: zhangsan@example.com | 主题: 会议时间调整通知
print(result_a["messages"][-1].content)
# 邮件已成功发送给张三，告知他明天会议推迟到下午3点。
```

**路径 B：修改收件人后批准**

```python
config_b = {"configurable": {"thread_id": "demo-modify"}}
graph.invoke(initial_state, config=config_b)

show_pending_tool_calls(config_b)
# 发现 to 字段为 zhangsan@example.com，但实际应该是另一个地址

result_b = modify_and_approve(config_b, tool_index=0, new_args={"to": "zhangsan_work@company.com"})
# ✏️ 已修改参数 {'to': 'zhangsan_work@company.com'}，继续执行...
# 📧 [模拟发送] 收件人: zhangsan_work@company.com | 主题: 会议时间调整通知
```

**路径 C：拒绝**

```python
config_c = {"configurable": {"thread_id": "demo-reject"}}
graph.invoke(initial_state, config=config_c)

show_pending_tool_calls(config_c)

result_c = reject(config_c)
# ❌ 已拒绝，工具调用被取消...
print(result_c["messages"][-1].content)
# 很抱歉，此次发送邮件的操作已被取消，邮件未发出。如果您需要其他帮助，请告知。
```

**关键验证**：路径 C 中 `send_email` 工具的 `print(f"📧 [模拟发送]...")` 那行**永远不会打印**——这证明工具真的没有被调用，拒绝路径成功阻止了工具执行。

---

## 四、高风险操作的判断标准与设计原则

### 4.1 哪些操作必须加确认

| 操作类型 | 是否需要审核 | 原因 |
|---------|-----------|------|
| 发送邮件/消息/通知 | ✅ 必须 | 不可逆，影响真实用户 |
| 删除文件/记录 | ✅ 必须 | 不可逆，数据丢失 |
| 支付/转账/下单 | ✅ 必须 | 涉及资金 |
| 修改用户权限 | ✅ 必须 | 安全影响范围广 |
| 查询天气/汇率 | ❌ 不需要 | 只读，无副作用，可重复 |
| 读取文件/数据库 | ❌ 通常不需要 | 只读（涉及隐私数据除外） |
| 调用搜索引擎 | ❌ 不需要 | 只读，无副作用 |

### 4.2 粒度选择：按节点 vs 按工具名过滤

`interrupt_before=["call_tools"]` 会对**所有**工具调用暂停，包括查天气这类低风险操作。生产场景里更精确的做法是在 `call_tools` 内部按工具名过滤：

```python
# 需要人工审核的高风险工具名单
HIGH_RISK_TOOLS = {"send_email", "delete_record", "process_payment"}

def call_tools_with_filter(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    high_risk = [tc for tc in last_message.tool_calls if tc["name"] in HIGH_RISK_TOOLS]
    safe = [tc for tc in last_message.tool_calls if tc["name"] not in HIGH_RISK_TOOLS]

    # 安全工具立即执行
    results = []
    for tc in safe:
        tool_fn = tool_registry[tc["name"]]
        results.append(ToolMessage(content=str(tool_fn.invoke(tc["args"])), tool_call_id=tc["id"]))

    # 高风险工具先存入 State，等待人工审核（结合 interrupt 实现）
    return {"messages": results, "pending_high_risk": high_risk}
```

这种设计让低风险工具（查询类）自动执行，只有高风险工具才触发人工审核——既保证安全，又不让审核流程拖慢正常操作。

### 4.3 update_state 的 as_node 参数：为什么关键

`graph.update_state(config, values, as_node="node_name")` 里的 `as_node` 告诉 LangGraph：**这次 State 更新应该被视为哪个节点执行完毕后的输出**。

```python
# 拒绝时：as_node="call_tools" 让图认为 call_tools 已执行完
# 下一步 → call_model（而不是再次等待 call_tools）
graph.update_state(config, {"messages": rejection_msgs}, as_node="call_tools")

# 修改参数时：不传 as_node，State 还停在 call_tools 执行前
# 下一步 → call_tools（用修正后的参数执行）
graph.update_state(config, {"messages": [corrected_msg]})
```

| 路径 | as_node | 效果 |
|-----|---------|------|
| 批准 | 不调用 update_state | 从 `call_tools` 继续，工具正常执行 |
| 修改参数 | 不传 as_node | State 更新后还在 `call_tools` 前，工具用新参数执行 |
| 拒绝 | `as_node="call_tools"` | 图认为 `call_tools` 已执行完，跳过工具直接去 `call_model` |

---

## 五、Day 36 知识速查

### 三条审核路径速查

```python
# 路径 A：批准
graph.invoke(None, config=config)

# 路径 B：修改参数后批准
graph.update_state(config, {"messages": [corrected_ai_msg]})   # as_node 不传
graph.invoke(None, config=config)

# 路径 C：拒绝
graph.update_state(config, {"messages": rejection_tool_msgs}, as_node="call_tools")
graph.invoke(None, config=config)
```

### update_state 的 as_node 行为对比

| as_node 取值 | 图认为哪个节点刚执行完 | 下一步执行的节点 |
|-------------|-------------------|---------------|
| 不传（None） | 保持当前暂停位置 | 继续从暂停节点（`call_tools`）执行 |
| `"call_tools"` | call_tools 执行完 | 按 call_tools 的出边走（→ call_model） |
| `"call_model"` | call_model 执行完 | 按 call_model 的出边走（→ call_tools 或 END） |

### AIMessage 同 id 替换原理

```python
# add_messages Reducer 的行为：
# - 同 id 的消息：新消息替换旧消息（用于修改参数）
# - 新 id 的消息：追加到列表末尾（用于注入 ToolMessage）
corrected_msg = AIMessage(..., id=last_ai_msg.id)   # 同 id → 替换
graph.update_state(config, {"messages": [corrected_msg]})
```

### 高风险工具判断标准

```
不可逆 → 必须审核
涉及资金 → 必须审核
外部副作用（影响真实用户/系统）→ 必须审核
只读 + 无副作用 + 可重复 → 通常不需要审核
```

---

## 六、实践任务

- [ ] 把 3.3 的完整代码跑通，准备好三个不同 `thread_id` 的 `config`（`demo-approve` / `demo-modify` / `demo-reject`）
- [ ] 演示路径 A：批准后观察 `📧 [模拟发送]` 打印出来，确认工具执行了
- [ ] 演示路径 C：拒绝后确认 `📧 [模拟发送]` **没有**打印，工具未执行；打印模型的最终回答，确认它能理解"被拒绝"并给用户合理解释
- [ ] 演示路径 B：故意把 `to` 改成一个不同的地址，观察发送出去的收件人确实变成了修改后的地址
- [ ] 用 `graph.get_state_history(config)` 打印路径 C 的全部快照，找到注入 `ToolMessage` 那一步，理解 `as_node="call_tools"` 在快照里的体现
- [ ] 尝试去掉拒绝时的 `as_node="call_tools"`，观察图会如何异常（理解 `as_node` 不传时会发生什么）

**产出标准**：三条路径都能正确执行：批准时工具调用；拒绝时工具不调用且模型给出合理解释；修改参数时用修正后的参数调用。能用一句话解释 `as_node="call_tools"` 在拒绝路径里的作用。

---

## 七、下一步预告

Day 37 是**第 5 周复盘**：回顾 Day 31–36 学过的 LangChain LCEL、LangGraph StateGraph / 条件边 / Checkpoint / Human-in-the-loop，梳理"LangChain 和 LangGraph 各自解决了什么问题、两者是替代关系还是互补关系"，以及"什么场景下手写循环仍然够用，不需要引入框架"。今天的 Human-in-the-loop 是 LangGraph 相比手写 `while` 循环最难复现的能力——Day 37 会把它和其他能力放在一起做横向对比，形成一张清晰的"适用边界地图"。
