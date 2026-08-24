# Day 41：多 Agent 协作模式

> 学习目标：实现 Planner + Executor + Critic 三角色协作 Demo，理解 Agent 间的消息传递协议；通过思考题深入 A2A 协议的设计动机（Task 状态机、流式 Push、Agent Card）；形成"MCP 管工具连接、A2A 管 Agent 协作"的完整认知
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 41
>
> 🧭 导航：[← Day 40 · 跨对话长期记忆](day40_cross_session_memory.md) → [Day 42 · 阶段项目整合 + 第 6 周复盘](day42_week6_review_and_integration.md)

---

## 目录

- [一、为什么需要多 Agent 协作](#一为什么需要多-agent-协作)
  - [1.1 单 Agent 的局限](#11-单-agent-的局限)
  - [1.2 分而治之：每个角色聚焦自己的职责](#12-分而治之每个角色聚焦自己的职责)
- [二、Planner / Executor / Critic 三角色设计](#二planner--executor--critic-三角色设计)
  - [2.1 Planner：任务拆解](#21-planner任务拆解)
  - [2.2 Executor：任务执行](#22-executor任务执行)
  - [2.3 Critic：结果验证](#23-critic结果验证)
- [三、Agent 间的消息传递协议](#三agent-间的消息传递协议)
  - [3.1 子任务数据结构](#31-子任务数据结构)
  - [3.2 执行结果数据结构](#32-执行结果数据结构)
  - [3.3 Critic 判断结构](#33-critic-判断结构)
- [四、协作 Demo 实现](#四协作-demo-实现)
  - [4.1 Planner 实现](#41-planner-实现)
  - [4.2 Executor 实现](#42-executor-实现)
  - [4.3 Critic 实现](#43-critic-实现)
  - [4.4 主流程与协作日志](#44-主流程与协作日志)
  - [4.5 运行示例日志](#45-运行示例日志)
- [五、思考题：A2A 协议解决了哪些工程问题](#五思考题a2a-协议解决了哪些工程问题)
  - [5.1 今天 Demo 的三个工程短板](#51-今天-demo-的三个工程短板)
  - [5.2 A2A 的 Task 状态机如何解决短板 1](#52-a2a-的-task-状态机如何解决短板-1)
  - [5.3 流式 Push 如何解决短板 2](#53-流式-push-如何解决短板-2)
  - [5.4 Agent Card 如何解决短板 3](#54-agent-card-如何解决短板-3)
- [六、MCP + A2A：两层连接的完整图景](#六mcp--a2a两层连接的完整图景)
- [七、Day 41 知识速查](#七day-41-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、为什么需要多 Agent 协作

### 1.1 单 Agent 的局限

Day 25 / Day 33-36 的 ReAct Agent 已经可以处理多步工具调用。但当任务变得复杂时，单 Agent 会遇到三个瓶颈：

| 问题 | 表现 |
|-----|------|
| **规划能力弱** | 模型同时要理解任务、拆分子任务、决定工具调用顺序——认知负担大，复杂任务容易漏步或顺序错误 |
| **容错能力差** | Executor 输出错误时，没有独立的"检查"环节——错误直接传给用户 |
| **不可替换** | 拆任务和执行任务耦合在同一个 Agent 里，想换更强的执行模型或更快的规划模型，需要整体替换 |

### 1.2 分而治之：每个角色聚焦自己的职责

多 Agent 协作的核心思想：**把"理解问题"、"执行操作"、"验证结果"三件事分配给三个独立角色**，各自可以用不同的模型、不同的 Prompt、甚至不同的编程语言实现。

```
用户提问
    │
    ▼
Planner Agent ──── 只负责：把复合问题拆成子任务列表
    │ 子任务列表
    ▼
Executor Agent ─── 只负责：逐个执行子任务，调用工具
    │ 执行结果列表
    ▼
Critic Agent ───── 只负责：检查结果是否完整回答原始问题
    │ 通过 / 失败 + 原因
    ▼
用户得到答案（或 Critic 驱动重试）
```

---

## 二、Planner / Executor / Critic 三角色设计

### 2.1 Planner：任务拆解

**职责**：理解用户的复合意图，把它分解成一组可独立执行的子任务，每个子任务对应一个具体工具调用。

**System Prompt 要求**：
- 只输出结构化的子任务列表（JSON），不执行任何工具
- 每个子任务必须包含：任务 ID、描述、要用的工具名、工具参数
- 子任务之间如有依赖（B 需要 A 的结果），用 `depends_on` 字段标注

**Planner 的能力边界**：
- ✅ 理解意图、拆分步骤、输出子任务列表
- ❌ 不调用工具、不执行操作、不验证结果

### 2.2 Executor：任务执行

**职责**：按顺序接收 Planner 给出的子任务列表，逐个执行，对每个子任务调用对应的工具，返回结果。

**System Prompt 要求**：
- 对每个子任务，按照指定的工具和参数执行，不自行判断是否要换工具
- 返回结构化结果：任务 ID + 状态（completed / failed）+ 结果内容
- 遇到工具调用失败时，状态标记为 failed，写明错误原因，继续执行下一个子任务

**Executor 的能力边界**：
- ✅ 工具调用、结果格式化、错误处理
- ❌ 不判断原始问题是否被回答了、不决定是否需要额外步骤

### 2.3 Critic：结果验证

**职责**：对照 Planner 的原始任务意图和 Executor 的结果，判断"用户的问题是否被完整回答了"。

**System Prompt 要求**：
- 对照原始用户问题，检查每个子任务的结果是否满足需求
- 输出 `pass: true/false`，失败时列出缺失或不正确的部分
- 不重复执行任何操作，只做判断

**Critic 的能力边界**：
- ✅ 比对原始意图与实际结果，给出有理有据的通过/失败判断
- ❌ 不执行工具、不修改结果

---

## 三、Agent 间的消息传递协议

三个 Agent 之间传递的数据结构是"协议"的核心——它决定了各角色的输入输出格式，以及如何判断"这一步完成了"。

### 3.1 子任务数据结构

```python
from dataclasses import dataclass, field

@dataclass
class SubTask:
    task_id: str           # 唯一标识，如 "task_1"
    description: str       # 任务描述，供 Executor 理解
    tool_name: str         # 要调用的工具名
    tool_args: dict        # 工具参数
    depends_on: list[str] = field(default_factory=list)  # 依赖的前置任务 ID
```

### 3.2 执行结果数据结构

```python
from enum import Enum

class TaskStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: str            # 成功时的结果文本
    error: str = ""        # 失败时的错误说明
```

**判断"这一步完成了"的标准**：`TaskResult.status == TaskStatus.COMPLETED`。Executor 负责写这个字段，Critic 和 Planner 靠它决定下一步行为。

### 3.3 Critic 判断结构

```python
@dataclass
class CriticVerdict:
    passed: bool
    missing: list[str]     # 未被回答的需求点
    reason: str            # 整体判断理由
    retry_hint: str = ""   # 如果失败，给 Planner 的重试建议
```

---

## 四、协作 Demo 实现

场景：用户问"帮我规划一次北京出发的商务行程，需要知道目的地（上海）天气、美元兑人民币汇率"。

### 4.1 Planner 实现

```python
import json
from openai import OpenAI

client = OpenAI(api_key="...", base_url="https://api.deepseek.com")

PLANNER_SYSTEM = """你是一个任务规划 Agent。
把用户的复合问题拆分成若干独立的子任务，每个子任务对应一个工具调用。
只输出 JSON 格式的子任务列表，不执行任何工具。

可用工具：
- get_weather(city: str)：查询城市天气
- get_exchange_rate(from_currency: str, to_currency: str)：查询汇率

输出格式：
[
  {
    "task_id": "task_1",
    "description": "任务描述",
    "tool_name": "工具名",
    "tool_args": {"参数名": "参数值"},
    "depends_on": []
  }
]"""


def plan(user_request: str) -> list[dict]:
    """Planner：把用户问题拆成子任务列表"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": user_request},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    data = json.loads(raw)
    # 模型可能返回 {"tasks": [...]} 或直接返回列表
    return data if isinstance(data, list) else data.get("tasks", list(data.values())[0])
```

### 4.2 Executor 实现

```python
# 工具注册表（复用 Day 23 / Day 39 的工具实现）
def get_weather(city: str) -> str:
    data = {
        "上海": "多云，26°C，湿度 72%",
        "北京": "晴，22°C，湿度 45%",
        "广州": "小雨，29°C，湿度 85%",
    }
    return data.get(city, f"暂无 {city} 的天气数据")

def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    rates = {("USD", "CNY"): 7.25, ("CNY", "USD"): 0.138}
    key = (from_currency.upper(), to_currency.upper())
    return f"1 {from_currency.upper()} = {rates[key]} {to_currency.upper()}" \
        if key in rates else f"暂不支持 {from_currency}→{to_currency}"

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "get_exchange_rate": get_exchange_rate,
}


def execute(tasks: list[dict]) -> list[dict]:
    """Executor：按顺序执行每个子任务，返回结果列表"""
    results = []
    completed_ids = set()

    for task in tasks:
        task_id = task["task_id"]

        # 检查依赖是否已完成
        unmet = [dep for dep in task.get("depends_on", []) if dep not in completed_ids]
        if unmet:
            results.append({
                "task_id": task_id,
                "status": "failed",
                "result": "",
                "error": f"前置任务未完成：{unmet}",
            })
            continue

        tool_fn = TOOL_REGISTRY.get(task["tool_name"])
        if tool_fn is None:
            results.append({
                "task_id": task_id,
                "status": "failed",
                "result": "",
                "error": f"未知工具：{task['tool_name']}",
            })
            continue

        try:
            result = tool_fn(**task["tool_args"])
            results.append({
                "task_id": task_id,
                "status": "completed",
                "result": result,
                "error": "",
            })
            completed_ids.add(task_id)
        except Exception as e:
            results.append({
                "task_id": task_id,
                "status": "failed",
                "result": "",
                "error": str(e),
            })

    return results
```

### 4.3 Critic 实现

```python
CRITIC_SYSTEM = """你是一个结果验证 Agent。
给定用户的原始问题和各子任务的执行结果，判断用户的问题是否被完整回答。

输出 JSON 格式：
{
  "passed": true 或 false,
  "missing": ["未被回答的需求点1", ...],
  "reason": "整体判断理由",
  "retry_hint": "如果 passed=false，给 Planner 的重试建议"
}"""


def critique(user_request: str, tasks: list[dict], results: list[dict]) -> dict:
    """Critic：检查结果是否完整回答了原始问题"""
    results_text = "\n".join(
        f"[{r['task_id']}] 状态={r['status']} "
        f"结果={r['result'] or '无'} 错误={r['error'] or '无'}"
        for r in results
    )
    prompt = f"""原始问题：{user_request}

子任务执行结果：
{results_text}

请判断用户的问题是否被完整回答。"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
```

### 4.4 主流程与协作日志

```python
def run_multi_agent(user_request: str) -> str:
    print(f"\n{'='*60}")
    print(f"[用户] {user_request}")
    print('='*60)

    # === Planner ===
    print("\n[Planner] 正在拆解任务...")
    tasks = plan(user_request)
    for t in tasks:
        print(f"  → {t['task_id']}: {t['description']} "
              f"（工具: {t['tool_name']}, 参数: {t['tool_args']}）")

    # === Executor ===
    print("\n[Executor] 正在执行子任务...")
    results = execute(tasks)
    for r in results:
        status_icon = "✓" if r["status"] == "completed" else "✗"
        print(f"  {status_icon} {r['task_id']}: {r['result'] or r['error']}")

    # === Critic ===
    print("\n[Critic] 正在验证结果...")
    verdict = critique(user_request, tasks, results)
    if verdict["passed"]:
        print(f"  ✓ 验证通过：{verdict['reason']}")
    else:
        print(f"  ✗ 验证失败：{verdict['reason']}")
        print(f"  缺失：{verdict['missing']}")
        if verdict.get("retry_hint"):
            print(f"  重试建议：{verdict['retry_hint']}")

    # === 汇总回答 ===
    completed = [r for r in results if r["status"] == "completed"]
    answer_lines = [f"• {r['result']}" for r in completed]
    return "\n".join(answer_lines) if verdict["passed"] else \
        "部分信息获取失败，请查看上方日志。"


# 运行
answer = run_multi_agent(
    "帮我规划一次从北京出发的商务行程：需要知道上海的天气，以及美元兑人民币的汇率"
)
print(f"\n[最终回答]\n{answer}")
```

### 4.5 运行示例日志

```
============================================================
[用户] 帮我规划一次从北京出发的商务行程：需要知道上海的天气，以及美元兑人民币的汇率
============================================================

[Planner] 正在拆解任务...
  → task_1: 查询上海的当前天气 （工具: get_weather, 参数: {'city': '上海'}）
  → task_2: 查询美元兑人民币汇率 （工具: get_exchange_rate, 参数: {'from_currency': 'USD', 'to_currency': 'CNY'}）

[Executor] 正在执行子任务...
  ✓ task_1: 多云，26°C，湿度 72%
  ✓ task_2: 1 USD = 7.25 CNY

[Critic] 正在验证结果...
  ✓ 验证通过：用户需要的上海天气和美元汇率均已获取，信息完整

[最终回答]
• 多云，26°C，湿度 72%
• 1 USD = 7.25 CNY
```

这份日志就是产出标准要求的"可观察的协作日志"——每一步谁在做什么、输入输出是什么，一目了然。

---

## 五、思考题：A2A 协议解决了哪些工程问题

今天的 Demo 是"同进程多函数调用"——Planner / Executor / Critic 都在同一个 Python 进程里，用函数返回值传递数据。生产环境里，这三个角色可能是独立的服务（独立部署、独立扩容），这时就需要 A2A 协议。

### 5.1 今天 Demo 的三个工程短板

| 短板 | 表现 |
|-----|------|
| **1. 无任务状态持久化** | 任务状态只在内存里（`results` 列表），进程崩溃全丢；Planner 不知道某个 Executor 是否在工作 |
| **2. 同步阻塞** | Executor 执行完所有子任务后，Planner / Critic 才能继续——长任务会阻塞整个流程 |
| **3. Planner 不知道有哪些 Executor 可用** | 硬编码工具注册表，无法动态发现"有哪些 Executor 服务" |

### 5.2 A2A 的 Task 状态机如何解决短板 1

A2A 定义了标准的 **Task 对象**，每个 Task 有明确的生命周期状态：

```
submitted → working → completed
                   ↘ failed
                   ↘ canceled
```

Planner 向 Executor 服务发送一个 Task（`POST /tasks`），Executor 创建 Task 并立即返回 Task ID（不等执行完成）。Task 的状态持久化在 Executor 服务的存储里，进程崩溃后 Task 状态仍然可查。

这解决了**短板 1**：任务状态不再依赖进程内存，任何时候 Planner 都可以查询 `GET /tasks/{id}` 知道执行进度。

### 5.3 流式 Push 如何解决短板 2

A2A 支持 **Streaming 推送**：Executor 执行长任务时，每完成一个阶段就主动 Push 状态更新给 Planner（通过 SSE / WebSocket），而不是等全部完成再返回。

```
Planner ──── POST /tasks ────► Executor
        ◄─── 202 Accepted ────
        ◄─── SSE: working ─────
        ◄─── SSE: step 1 done ─
        ◄─── SSE: completed ───
```

这解决了**短板 2**：Planner 在等待期间可以同时处理其他事情（如开始 Critic 对已完成步骤的验证），而不是阻塞等全部完成。

### 5.4 Agent Card 如何解决短板 3

A2A 定义了 **Agent Card**：每个 Agent 服务在标准路径（`/.well-known/agent.json`）暴露自己的能力声明，包括名称、描述、支持的输入/输出格式、可处理的任务类型。

```json
{
  "name": "WeatherExecutor",
  "description": "执行天气查询任务",
  "capabilities": {
    "tasks": ["get_weather"],
    "input_format": "SubTask JSON",
    "output_format": "TaskResult JSON"
  }
}
```

Planner 可以动态发现（Discovery）有哪些 Executor 服务，以及各自能处理什么类型的任务——不再硬编码 `TOOL_REGISTRY`。

这解决了**短板 3**：Planner 从"硬编码工具表"升级为"动态发现可用 Agent"，新增一个 Executor 服务只需要发布 Agent Card，Planner 自动感知。

---

## 六、MCP + A2A：两层连接的完整图景

把今天和 Day 38-39 的知识整合成一张图：

```
┌────────────────────────────────────────────────────────────────┐
│                    完整多 Agent 系统的连接层次                    │
│                                                                │
│  ┌──────────────┐   A2A 协议    ┌──────────────┐              │
│  │  Planner     │ ──委派任务──► │  Executor    │              │
│  │  Agent       │ ◄─Push 状态── │  Agent       │              │
│  └──────┬───────┘              └──────┬───────┘              │
│         │                            │                        │
│      MCP 协议                     MCP 协议                     │
│         │                            │                        │
│         ▼                            ▼                        │
│  ┌──────────────┐           ┌──────────────┐                 │
│  │  MCP Server  │           │  MCP Server  │                 │
│  │（记忆工具）   │           │（天气/汇率）  │                 │
│  └──────────────┘           └──────────────┘                 │
│                                                                │
│  A2A 层：解决 "Agent 之间怎么协作、委派任务、同步状态"          │
│  MCP 层：解决 "每个 Agent 怎么连接工具和数据"                   │
│  Function Calling：解决 "模型怎么表达工具调用意图"              │
└────────────────────────────────────────────────────────────────┘
```

**三层协议各司其职**：

| 协议 | 解决的问题 | 跨越的边界 |
|-----|----------|----------|
| Function Calling | 模型如何表达"我要调用哪个工具" | 模型 ↔ 工具调用意图 |
| MCP | 工具服务如何被标准化、跨应用复用 | AI 应用 ↔ 工具服务器 |
| A2A | Agent 如何委派任务、同步状态、动态发现彼此 | Agent ↔ Agent |

三者不是替代关系，是不同层次的互补——今天的 Demo 在同进程里只用到了 Function Calling；引入 MCP 后工具变成了独立服务；引入 A2A 后三个 Agent 角色也变成了独立服务，彼此通过协议通信。

---

## 七、Day 41 知识速查

### 三角色职责边界

```
Planner  → 输入：用户问题 → 输出：SubTask[] （只拆，不执行）
Executor → 输入：SubTask  → 输出：TaskResult（只执行，不判断完整性）
Critic   → 输入：原始问题 + TaskResult[] → 输出：CriticVerdict（只判断，不执行）
```

### Agent 间数据结构速查

```python
SubTask      = {task_id, description, tool_name, tool_args, depends_on}
TaskResult   = {task_id, status("completed"/"failed"), result, error}
CriticVerdict = {passed, missing[], reason, retry_hint}
```

### A2A 三项设计与解决的工程问题

| A2A 设计 | 解决的短板 |
|---------|----------|
| Task 状态机（submitted/working/completed/failed） | 任务状态持久化，进程崩溃不丢失，可随时查询进度 |
| Streaming Push（SSE / WebSocket） | 长任务不阻塞 Planner，边执行边推送状态 |
| Agent Card（能力声明） | Planner 动态发现可用 Executor，无需硬编码工具表 |

---

## 八、实践任务

- [ ] 把第四节的完整代码跑通，查看协作日志，确认 Planner 的拆解结果、Executor 的工具调用、Critic 的验证结论三部分都清晰可见
- [ ] 故意制造失败场景：给 `get_weather` 传一个不支持的城市（如"成都"），观察 Executor 如何处理 failed 状态，Critic 如何判断"用户问题未被完整回答"
- [ ] 给 Planner 换一个更复杂的问题（如"我要去广州出差，帮我查广州天气和欧元兑人民币汇率，还有人民币兑日元"），验证 Planner 是否能正确拆出三个子任务
- [ ] 思考题（写进笔记，不需要实现）：如果 Critic 判断 `passed=false`，主流程应该如何决定是否让 Planner 重新规划？最多重试几次？加一个 `MAX_RETRIES` 保护的话应该放在哪里？

**产出标准**：有一份完整的协作日志打印输出（包含 Planner 拆解、Executor 执行、Critic 验证三节），以及一段关于"Critic 失败如何触发重试"的思考记录。

---

## 九、下一步预告

Day 42 是**阶段项目整合 + 第 6 周复盘**：把 Day 33-41 积累的能力（LangGraph 编排、MCP 工具、长期记忆、多 Agent 协作）整合进 Day 27 的个人助理项目，跑通一个升级版 Agent；同时构造 15-20 个测试 case（用户输入 → 预期工具调用序列 → 预期回答要点），量化 Agent 行为的通过率——这是 Agent 开发从"能跑"到"可度量"的关键一步，也是后续每次改动图结构时的回归基准。
