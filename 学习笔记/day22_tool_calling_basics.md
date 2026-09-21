# Day 22：理解 Tool Calling

> 学习目标：理解 Tool Calling 的完整交互流程，搞清楚"回答问题"和"调用工具做事"的本质区别，实现一个从工具定义到结果反馈的最小可运行 Demo
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 22
>
> 🧭 导航：[← Day 21 · 第 3 周复盘](day21_week3_review.md) [→ Day 23 · 定义第一个工具](day23_define_first_tool.md)

---

## 目录

- [一、Tool Calling 的核心概念](#一tool-calling-的核心概念)
  - [1.1 什么是 Tool Calling](#11-什么是-tool-calling)
  - [1.2 "回答问题"和"调用工具做事"的本质区别](#12-回答问题和调用工具做事的本质区别)
  - [1.3 模型何时决定调用工具](#13-模型何时决定调用工具)
- [二、Tool Calling 完整交互流程](#二tool-calling-完整交互流程)
  - [2.1 完整流程图](#21-完整流程图)
  - [2.2 工具定义的结构（Function Schema）](#22-工具定义的结构function-schema)
  - [2.3 模型返回的 tool_calls 结构](#23-模型返回的-tool_calls-结构)
  - [2.4 工具结果的传入方式](#24-工具结果的传入方式)
- [三、最小 Tool Calling 实现](#三最小-tool-calling-实现)
  - [3.1 定义工具并注册给模型](#31-定义工具并注册给模型)
  - [3.2 处理 tool_calls 响应](#32-处理-tool_calls-响应)
  - [3.3 完整可运行代码](#33-完整可运行代码)
- [四、Tool Calling vs RAG vs 普通对话](#四tool-calling-vs-rag-vs-普通对话)
  - [4.1 三种交互模式对比](#41-三种交互模式对比)
  - [4.2 Tool Calling 与 Agent 的关系](#42-tool-calling-与-agent-的关系)
- [五、Day 22 知识速查](#五day-22-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、Tool Calling 的核心概念

### 1.1 什么是 Tool Calling

Tool Calling（工具调用，也叫 Function Calling）是一种让 LLM **主动触发外部函数执行**的机制。开发者提前告诉模型"你有哪些工具可以用"，模型在对话过程中根据用户意图自动判断"是否要调用工具"以及"调用哪个工具、传什么参数"。

**关键认知**：模型本身不执行工具，它只负责**决策和参数填充**。工具的实际执行发生在你的代码里。

```
Tool Calling 的两个核心问题：

  Q1：模型"调用"的是什么？
  A：不是真正执行函数，而是输出一个结构化的"调用请求"，
     格式类似 {"name": "get_weather", "arguments": {"city": "北京"}}
     你的代码看到这个请求 → 执行真正的 Python 函数 → 把结果传回模型

  Q2：为什么需要这个机制？
  A：模型只能处理文本，但现实世界需要"实时数据"和"执行操作"：
     - 查天气：模型不知道今天天气，但可以调用天气 API
     - 查数据库：模型没有你的业务数据，但可以调用查询函数
     - 发邮件：模型不能直接发送，但可以调用邮件 API
```

### 1.2 "回答问题"和"调用工具做事"的本质区别

这是 Day 22 最核心的概念，也是理解 Agent 的基础。

```
┌─────────────────────────────────────────────────────────────────────┐
│                    两种交互模式的本质对比                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  普通对话（回答问题）：                                               │
│  ─────────────────────────────────────────────────────────          │
│  用户："今天北京天气怎么样？"                                         │
│  模型：根据训练数据生成文字回答                                        │
│        "北京的天气因季节而异，春季通常..."（来自训练数据，不是实时）    │
│                                                                      │
│  Tool Calling（调用工具做事）：                                       │
│  ─────────────────────────────────────────────────────────          │
│  用户："今天北京天气怎么样？"                                         │
│  模型：识别出需要实时数据 → 生成工具调用请求                           │
│        {"name": "get_weather", "arguments": {"city": "北京"}}       │
│  代码：执行 get_weather("北京") → 返回实时数据给模型                  │
│  模型：基于实时数据生成回答                                            │
│        "今天北京晴，25°C，东南风 3 级..."（真实数据）                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**三个本质差异**：

| 维度 | 普通对话 | Tool Calling |
|------|---------|-------------|
| 数据来源 | 训练时冻结的知识 | 运行时获取的实时数据 |
| 是否有副作用 | 无（只生成文字） | 有（可以写数据库、发邮件、调 API） |
| 回答依据 | 模型"记忆" | 外部系统的确定性返回值 |

**一个直觉类比**：普通对话的模型像一本百科全书——只能告诉你书里写的内容；Tool Calling 的模型像一个带手机的顾问——可以实时搜索、打电话、订餐，告诉你现在的真实情况。

### 1.3 模型何时决定调用工具

模型不是随机调用工具，而是基于**意图识别**主动判断。影响决策的两个关键因素：

**因素一：用户意图是否需要外部信息或操作**

```
不调用工具的意图（已有知识够用）：
  "什么是 HTTP 协议？" → 概念解释，训练知识足够
  "Python 如何读取文件？" → 代码示例，无需实时数据

调用工具的意图（需要外部数据或操作）：
  "今天北京天气怎么样？" → 需要实时数据
  "帮我查一下张三的订单状态" → 需要访问数据库
  "给李四发一封邮件" → 需要执行操作
```

**因素二：工具描述是否写得清晰**

工具的 `description` 字段是模型判断"是否该调用这个工具"的核心依据。描述不清楚，模型会猜错。

```python
# 描述太模糊 → 模型不知道何时用
{"name": "get_data", "description": "获取数据"}

# 描述清晰 → 模型能准确判断
{"name": "get_weather", "description": "获取指定城市的当前实时天气信息，包括温度、天气状况和风速。仅用于查询当前天气，不用于历史天气或预报。"}
```

---

## 二、Tool Calling 完整交互流程

### 2.1 完整流程图

```
用户输入："今天上海天气怎么样？"
      │
      ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1：把工具定义 + 对话历史一起发给模型                     │
│                                                              │
│  messages = [{"role": "user", "content": "今天上海天气怎么样？"}]
│  tools = [{"type": "function", "function": {                 │
│              "name": "get_weather",                          │
│              "description": "获取城市实时天气",               │
│              "parameters": {...}                             │
│           }}]                                                │
└─────────────────────────────────────────────────────────────┘
      │
      ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2：模型返回 tool_calls（不是普通文本回答）               │
│                                                              │
│  response.choices[0].message.tool_calls = [{                 │
│      "id": "call_abc123",                                    │
│      "type": "function",                                     │
│      "function": {                                           │
│          "name": "get_weather",                              │
│          "arguments": '{"city": "上海"}'                     │
│      }                                                       │
│  }]                                                          │
└─────────────────────────────────────────────────────────────┘
      │
      ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3：你的代码执行工具，得到结果                            │
│                                                              │
│  result = get_weather("上海")                                │
│  # → {"city": "上海", "temp": 28, "condition": "晴", ...}   │
└─────────────────────────────────────────────────────────────┘
      │
      ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4：把工具结果追加进消息历史，再次发给模型                 │
│                                                              │
│  messages.append(response.choices[0].message)  # assistant  │
│  messages.append({                                           │
│      "role": "tool",                                         │
│      "tool_call_id": "call_abc123",                          │
│      "content": json.dumps(result)                           │
│  })                                                          │
└─────────────────────────────────────────────────────────────┘
      │
      ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5：模型基于工具结果生成最终自然语言回答                   │
│                                                              │
│  "上海今天晴，气温 28°C，东南风 2 级，体感舒适。"              │
└─────────────────────────────────────────────────────────────┘
      │
      ↓
最终回答展示给用户
```

**关键点**：这是一个**两次 API 调用**的过程——第一次问模型"该调什么工具"，第二次问模型"基于工具结果怎么回答用户"。中间的工具执行在你的代码里完成。

### 2.2 工具定义的结构（Function Schema）

工具定义遵循 OpenAI 兼容格式，本质是告诉模型"这个工具能做什么、需要什么参数"：

```python
tool_definition = {
    "type": "function",         # 固定值，目前只有 function 类型
    "function": {
        "name": "get_weather",  # 工具名，模型调用时填在 tool_calls.name 里
        "description": (        # 关键：模型靠这段文字决定是否调用
            "获取指定城市的当前实时天气，返回温度（摄氏度）、天气状况和风速。"
            "仅适用于查询当前天气，不支持历史数据和未来预报。"
        ),
        "parameters": {         # 描述函数的参数（JSON Schema 格式）
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，例如'北京'、'上海'、'广州'"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位，默认 celsius（摄氏度）"
                }
            },
            "required": ["city"]  # 必填参数
        }
    }
}
```

**description 写作原则**：

| 要写的 | 示例 |
|--------|------|
| 工具能做什么 | "获取指定城市的当前实时天气" |
| 返回什么格式 | "返回温度（摄氏度）、天气状况和风速" |
| 适用边界 | "仅适用于查询当前天气，不支持历史数据" |
| 不写的内容 | 技术实现细节（如"调用 OpenWeather API"） |

### 2.3 模型返回的 tool_calls 结构

当模型判断需要调用工具时，`message.content` 为空，`message.tool_calls` 包含调用信息：

```python
# 模型返回结构（简化版）
response.choices[0].message = {
    "role": "assistant",
    "content": None,            # 普通文字回答为空
    "tool_calls": [
        {
            "id": "call_abc123",        # 唯一 ID，后续传工具结果时需要匹配
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"city": "上海", "unit": "celsius"}'
                # arguments 是 JSON 字符串，需要 json.loads() 解析
            }
        }
    ]
}
```

**处理多工具调用**：一次请求模型可能返回多个 `tool_calls`（如同时查天气和查新闻），每个都需要独立执行并传回结果。

### 2.4 工具结果的传入方式

工具结果用 `role: "tool"` 的特殊消息类型传回：

```python
# 执行工具
tool_call = response.choices[0].message.tool_calls[0]
func_name = tool_call.function.name
func_args = json.loads(tool_call.function.arguments)

# 执行实际函数
result = dispatch_tool(func_name, func_args)  # 见完整实现

# 传回结果（必须按格式，tool_call_id 要匹配）
messages.append(response.choices[0].message)  # assistant 的 tool_calls 消息
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,      # 必须和上面的 id 对应
    "content": json.dumps(result, ensure_ascii=False),  # 序列化为字符串
})
```

**`tool_call_id` 的作用**：当模型返回多个 `tool_calls` 时，每个工具结果通过 `id` 对应到具体的调用请求，模型知道哪个结果对应哪个工具。

---

## 三、最小 Tool Calling 实现

### 3.1 定义工具并注册给模型

```python
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

# ── 工具定义 ──────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前实时天气，返回温度（摄氏度）、天气状况和风速。仅适用于当前天气查询。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如'北京'、'上海'"
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算，支持加减乘除和幂运算。用于需要精确数值计算的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如'2 + 3 * 4'、'100 / 7'"
                    }
                },
                "required": ["expression"],
            },
        },
    },
]
```

### 3.2 处理 tool_calls 响应

```python
# ── 工具实现（模拟，真实场景调外部 API）─────────────────────────────────────

def get_weather(city: str) -> dict:
    mock_data = {
        "北京": {"temp": 22, "condition": "晴", "wind": "东北风 3 级"},
        "上海": {"temp": 28, "condition": "多云", "wind": "东南风 2 级"},
        "广州": {"temp": 32, "condition": "阵雨", "wind": "南风 4 级"},
    }
    if city in mock_data:
        return {"city": city, **mock_data[city]}
    return {"city": city, "error": f"未找到 {city} 的天气数据"}


def calculate(expression: str) -> dict:
    try:
        # 只允许安全的数学操作，不执行任意代码
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return {"error": "表达式包含不允许的字符"}
        result = eval(expression, {"__builtins__": {}})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}


# ── 工具分发器 ─────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
}

def dispatch_tool(name: str, args: dict) -> dict:
    if name not in TOOL_FUNCTIONS:
        return {"error": f"未知工具：{name}"}
    return TOOL_FUNCTIONS[name](**args)
```

### 3.3 完整可运行代码

```python
# ── 主对话函数 ─────────────────────────────────────────────────────────────

def chat_with_tools(user_input: str) -> str:
    messages = [{"role": "user", "content": user_input}]

    # Step 1：第一次调用，让模型决定是否使用工具
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",   # auto：让模型自己决定；none：禁用工具；required：强制调用
    )
    msg = response.choices[0].message

    # Step 2：检查模型是否要调用工具
    if not msg.tool_calls:
        return msg.content   # 模型直接回答，不需要工具

    # Step 3：执行所有工具调用
    messages.append(msg)     # 把带 tool_calls 的 assistant 消息加入历史

    for tool_call in msg.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        result = dispatch_tool(name, args)

        print(f"  [工具调用] {name}({args}) → {result}")

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    # Step 4：把工具结果传回模型，获取最终回答
    final_response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=TOOLS,
    )
    return final_response.choices[0].message.content


# ── 运行示例 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_questions = [
        "今天北京天气怎么样？",
        "上海和广州今天哪个城市更热？",   # 可能同时调用两次工具
        "123 乘以 456 等于多少？",
        "Python 中怎么读取文件？",        # 不需要工具，模型直接回答
    ]

    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"问题：{q}")
        print("-" * 40)
        answer = chat_with_tools(q)
        print(f"回答：{answer}")
```

**预期输出**：

```
============================================================
问题：今天北京天气怎么样？
----------------------------------------
  [工具调用] get_weather({'city': '北京'}) → {'city': '北京', 'temp': 22, 'condition': '晴', 'wind': '东北风 3 级'}
回答：今天北京天气晴好，气温 22°C，东北风 3 级，是个不错的天气！

============================================================
问题：123 乘以 456 等于多少？
----------------------------------------
  [工具调用] calculate({'expression': '123 * 456'}) → {'expression': '123 * 456', 'result': 56088}
回答：123 乘以 456 等于 56088。

============================================================
问题：Python 中怎么读取文件？
----------------------------------------
回答：在 Python 中，可以使用 open() 函数读取文件...（直接回答，未调用工具）
```

---

## 四、Tool Calling vs RAG vs 普通对话

### 4.1 三种交互模式对比

理解三种模式的差异，是正确选型的基础：

```
三种模式的数据流对比：

  普通对话：
    用户输入 ──→ LLM（训练知识） ──→ 文字回答
    
  RAG：
    用户输入 ──→ 向量检索（私有文档） ──→ 相关 Chunks ──→ LLM ──→ 文字回答
    （文档内容是静态的，提前索引，问答时检索）
    
  Tool Calling：
    用户输入 ──→ LLM（决策） ──→ 工具调用请求 ──→ 外部系统（实时执行） ──→ LLM（整合） ──→ 文字回答
    （数据是动态的，每次实时获取；可以有写操作副作用）
```

| 维度 | 普通对话 | RAG | Tool Calling |
|------|---------|-----|-------------|
| 数据新鲜度 | 训练时冻结 | 索引时冻结（可定期更新） | 每次调用实时获取 |
| 私有数据支持 | 否 | 是（文档） | 是（API/数据库） |
| 副作用 | 无 | 无（只读） | 有（可写、可触发操作） |
| 延迟 | 最低（只 1 次 LLM） | 中（检索 + LLM） | 最高（LLM + 工具 + LLM） |
| 典型场景 | 知识问答、写作辅助 | 文档问答、企业知识库 | 查实时数据、执行操作 |

**选型判断**：

```
用户问题需要什么？
  │
  ├── 只需要通用知识 → 普通对话
  │
  ├── 需要我的私有文档内容（静态） → RAG
  │
  └── 需要实时数据 或 需要执行操作 → Tool Calling
       ├── 查天气、股价、航班 → Tool Calling（实时 API）
       ├── 查业务数据库 → Tool Calling（数据库查询工具）
       └── 发邮件、下单、写文件 → Tool Calling（带副作用的工具）
```

### 4.2 Tool Calling 与 Agent 的关系

Tool Calling 是 Agent 的核心基础能力，但两者不是同一个概念：

```
Tool Calling（单步）：
  用户输入 → 模型决策（调哪个工具）→ 执行一次 → 最终回答
  
  例："上海今天天气怎么样？" → 调一次 get_weather → 回答
  
Agent（多步循环）：
  用户输入 → 模型决策 → 执行工具 → 观察结果 → 再决策 → 执行工具 → ...→ 最终回答
  
  例："帮我订明天上午去上海的最便宜机票"
    Step 1：调 search_flights(from="北京", to="上海", date="明天") → 返回多条航班
    Step 2：调 get_price(flight_id="CA1234") → 比较价格
    Step 3：调 book_flight(flight_id="CA1234", passenger=...) → 确认预订
    → "已为您预订 CA1234 航班，明天 07:30 出发，票价 ¥680"
```

**关系总结**：Tool Calling = Agent 的"手"（执行单步操作）；Agent = Tool Calling + 循环推理 + 记忆 + 规划（多步自主完成目标）。没有 Tool Calling 基础就无法构建 Agent，但会了 Tool Calling 还需要学 ReAct 模式才能做 Agent。

---

## 五、Day 22 知识速查

### Tool Calling 流程速查（5 步）

```
Step 1：定义工具（JSON Schema）—— 写好 description 是关键
Step 2：发起请求时带上 tools 参数 —— model + messages + tools + tool_choice
Step 3：检查响应是否有 tool_calls —— msg.tool_calls is not None
Step 4：执行工具，传回 role="tool" 消息 —— 注意 tool_call_id 要匹配
Step 5：再次调用模型获取最终回答 —— 第二次 create() 调用
```

### 关键参数速查

| 参数 | 位置 | 作用 | 常用值 |
|------|------|------|-------|
| `tools` | create() | 注册可用工具列表 | `[{"type": "function", "function": {...}}]` |
| `tool_choice` | create() | 控制是否调用工具 | `"auto"`（自动）/ `"none"`（禁用）/ `"required"`（强制） |
| `role: "tool"` | messages | 传工具结果 | 固定值，专用于传工具执行结果 |
| `tool_call_id` | tool 消息 | 匹配工具结果与调用请求 | 来自 `tool_calls[i].id` |

### 最小代码模板

```python
# 1. 发起带工具的请求
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=TOOLS,
    tool_choice="auto",
)
msg = response.choices[0].message

# 2. 检查并处理 tool_calls
if msg.tool_calls:
    messages.append(msg)
    for tc in msg.tool_calls:
        result = dispatch_tool(tc.function.name, json.loads(tc.function.arguments))
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result, ensure_ascii=False)})
    # 3. 第二次请求获取最终回答
    final = client.chat.completions.create(model="deepseek-chat", messages=messages, tools=TOOLS)
    answer = final.choices[0].message.content
else:
    answer = msg.content
```

---

## 六、实践任务

- [ ] 理解流程：能不看文档地画出 Tool Calling 的完整交互图（5 步）
- [ ] 运行示例：跑通 `day22_tool_calling_basics.py`，观察日志中"[工具调用]"的输出
- [ ] 验证边界：测试"Python 中怎么读取文件？"——确认模型跳过工具直接回答
- [ ] 验证多工具：测试"上海和广州今天哪个城市更热？"——确认模型连续调用两次 `get_weather`
- [ ] 理解 tool_choice：把 `tool_choice="none"` 传给第一个问题，看模型如何在没有工具时回答"北京今天天气怎么样？"
- [ ] 用自己的话写出："`role: tool` 消息和 `role: assistant` 消息的关键区别是什么？为什么 `tool_call_id` 不能省略？"

**产出标准**：

- 一份工具调用原理笔记（即本文）
- `day22_tool_calling_basics.py` 可运行，4 个测试问题均有正确输出（含工具调用日志）

---

## 七、下一步预告

**Day 23：定义第一个工具**

Day 22 建立了 Tool Calling 的概念框架，Day 23 深入到**工具设计层面**——如何定义一个"好用的工具"：

- **参数设计原则**：必填 vs 可选、类型约束、`description` 写到什么程度才够
- **输入输出定义**：工具函数的返回格式如何设计才对模型友好
- **真实场景工具**：从"模拟天气"升级到"真正调用外部 API"（如查汇率、查 IP 归属地）
- **工具的错误处理**：工具执行失败时，应该返回什么格式让模型优雅地告知用户

Day 23 的产出：一个可独立运行的工具函数库（`tools/weather.py`、`tools/calculator.py`），能被任意 LLM 对话程序复用。
