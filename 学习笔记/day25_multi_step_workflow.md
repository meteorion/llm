# Day 25：多步工作流

> 学习目标：理解模型如何通过多轮工具调用完成需要多步推理的复杂任务，掌握循环调用的终止条件设计、调用链可观测性，以及如何实现一个完整的多步工作流 Demo
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 25
>
> 🧭 导航：[← Day 24 · 单工具调用 Demo](day24_single_tool_demo.md) [→ Day 26 · 添加简单界面](day26_simple_ui.md)

---

## 目录

- [一、多步工作流的核心概念](#一多步工作流的核心概念)
  - [1.1 单步 vs 多步：本质区别](#11-单步-vs-多步本质区别)
  - [1.2 ReAct 模式：推理 + 行动的循环](#12-react-模式推理--行动的循环)
  - [1.3 调用链的终止条件](#13-调用链的终止条件)
- [二、实现循环调用结构](#二实现循环调用结构)
  - [2.1 基础 while 循环框架](#21-基础-while-循环框架)
  - [2.2 安全限制：最大迭代次数](#22-安全限制最大迭代次数)
  - [2.3 工具调用历史的完整记录](#23-工具调用历史的完整记录)
- [三、可观测性：让推理过程透明](#三可观测性让推理过程透明)
  - [3.1 为什么多步工作流必须可观测](#31-为什么多步工作流必须可观测)
  - [3.2 调用链日志的设计](#32-调用链日志的设计)
  - [3.3 结构化的调用链记录](#33-结构化的调用链记录)
- [四、完整多步工作流 Demo](#四完整多步工作流-demo)
  - [4.1 场景设计：出行规划助手](#41-场景设计出行规划助手)
  - [4.2 完整实现](#42-完整实现)
  - [4.3 典型调用链示例](#43-典型调用链示例)
- [五、Day 25 知识速查](#五day-25-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、多步工作流的核心概念

### 1.1 单步 vs 多步：本质区别

Day 24 实现的单工具调用是**固定两次 API 调用**的结构：第一次决策，第二次生成最终回答。而多步工作流中，工具调用次数由**模型在运行时自主决定**：

```
单步工作流（Day 24）：

  用户 → [API 调用 1：决策] → 工具执行 → [API 调用 2：回答]
          ↑ 最多一次工具调用                ↑ 固定两次 API 调用

  适用：用户问"北京天气" → 调一次 get_weather → 回答


多步工作流（Day 25）：

  用户 → [API 调用 1] → 工具 A → [API 调用 2] → 工具 B → [API 调用 3] → 回答
                        ↑可能有   ↑可能有         ↑可能有    ↑ 工具调用次数 N 由模型决定

  适用：用户问"我下周去上海出差，带500美元够吗，天气适合怎么穿？"
        → 调 get_weather(上海) → 调 get_exchange_rate(USD, CNY) → 综合回答
```

关键差异：单步工作流循环 1 次工具调用；多步工作流循环 N 次，**N 在运行时确定**。

### 1.2 ReAct 模式：推理 + 行动的循环

多步工作流的底层思路来自 ReAct（Reason + Act）模式：模型在每一步先推理当前状态，再决定下一步行动（调用工具或给出最终回答）：

```
ReAct 循环（每次 API 调用）：

  ┌─────────────────────────────────────────┐
  │  当前状态：[system] + [历史消息] + [用户输入]  │
  └───────────────────┬─────────────────────┘
                      │
                      ▼
            模型推理下一步行动
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
    tool_calls 不为空           tool_calls 为空
    (还需要工具数据)             (信息够了，直接回答)
          │                       │
          ▼                       ▼
    执行工具，结果                返回最终文字回答
    追加到历史               ← 退出循环
          │
          ▼
      下一轮循环
```

**模型不是"硬编码"多少步**，而是在每次 API 调用后，根据当前信息判断"还需要什么工具"——这使得相同的代码结构能处理 1 步和 10 步的场景。

### 1.3 调用链的终止条件

循环需要有明确的退出条件，否则会无限执行：

```
退出条件 1（正常）：model_response.tool_calls 为 None 或空列表
  → 模型认为信息已够，直接给出文字回答
  → 返回 message.content

退出条件 2（安全）：已执行工具次数 >= max_iterations（通常 5–10）
  → 防止模型进入无限循环（BUG 或模型行为异常）
  → 返回部分结果或错误提示

退出条件 3（工具错误累积）：连续 N 次工具调用均返回 error: True
  → 工具本身有问题，继续循环无意义
  → 可选实现，根据实际需求决定
```

**安全上限很重要**：没有 `max_iterations` 的多步工作流，在模型 Bug 或工具返回异常时可能产生大量 API 调用和费用。

---

## 二、实现循环调用结构

### 2.1 基础 while 循环框架

```python
def run_workflow(user_input: str, tools: list, tool_registry: dict,
                 system_prompt: str, client, max_iter: int = 8) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    
    iteration = 0
    while iteration < max_iter:
        iteration += 1
        
        # 每一轮都调用 API，让模型决策
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0,
        )
        msg = response.choices[0].message
        
        # 退出条件 1：模型不再调用工具
        if not msg.tool_calls:
            return msg.content
        
        # 执行本轮所有工具调用
        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = tool_registry.get(name, lambda **_: {"error": True, "message": f"未知工具: {name}"})(**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
    
    # 退出条件 2：达到最大迭代次数
    # 强制最后一次调用，让模型基于已有信息生成回答
    final = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages + [{"role": "user", "content": "请基于目前获取到的信息给出你的回答。"}],
        temperature=0,
    )
    return final.choices[0].message.content
```

### 2.2 安全限制：最大迭代次数

`max_iterations` 的取值取决于应用场景：

| 场景 | 推荐值 | 理由 |
|------|--------|------|
| 通用对话助手（工具较少） | 3–5 | 超过 5 步基本是 Bug |
| 信息收集类任务（多数据源） | 5–8 | 可能需要查多个工具 |
| 复杂 Agent（ReAct 规划） | 10–20 | 多阶段规划任务 |
| 生产级别（有成本限制） | 根据预算上限计算 | `max_iter = budget / avg_cost_per_call` |

**为什么不设很大的值**：
- 每次循环 = 一次完整 API 调用（传入全部历史），消耗的 Token 随历史长度**线性增长**
- 第 5 次调用时，消耗 Token ≈ 前 4 次调用结果的总和 + 新内容
- 10 次调用 ≈ 1 次调用的 Token 消耗的 4–5 倍（不是 10 倍，但依然显著）

### 2.3 工具调用历史的完整记录

多步工作流中，每次循环都在历史消息列表里追加内容：

```
循环开始前：
  history = [system, user_input]

第 1 轮（调用 get_weather）：
  history = [system, user_input, assistant(tool_calls), tool(weather结果)]

第 2 轮（调用 get_exchange_rate）：
  history = [system, user_input, assistant(tool_calls₁), tool(weather), assistant(tool_calls₂), tool(exchange)]

第 3 轮（模型直接回答，退出）：
  history = [...上面全部..., assistant(最终回答)]
```

关键规则（同 Day 24）：
- `assistant` 消息（含 `tool_calls`）和对应 `tool` 消息**必须成对保留**
- 不能只保留最终 `assistant.content`，否则模型失去推理链路

---

## 三、可观测性：让推理过程透明

### 3.1 为什么多步工作流必须可观测

单步工作流出错很容易定位（只有一次工具调用）；多步工作流出错时可能是：

```
可能的失败点：

  Step 1: 模型决策错误 → 调了不该调的工具
  Step 2: 工具参数填写错误 → 返回了无用数据
  Step 3: 模型误读了工具结果 → 第二步决策基于错误信息
  Step N: 最终回答基于错误的中间状态 → 结果不可信
```

**没有日志的多步工作流等于黑盒**——结果错了，但不知道错在哪一步。可观测性要覆盖三个层次：

```
层次 1（基础）：知道调用了几次工具、分别是哪些
层次 2（调试）：每次工具调用的入参和出参
层次 3（审计）：每次调用的耗时、Token 消耗、决策链路
```

### 3.2 调用链日志的设计

```python
import logging, time, json

logger = logging.getLogger(__name__)

class WorkflowLogger:
    def __init__(self, name: str = "workflow"):
        self.name = name
        self.steps = []
        self.start_time = time.monotonic()

    def log_decision(self, iteration: int, tool_calls: list):
        tools_called = [tc.function.name for tc in tool_calls] if tool_calls else []
        msg = f"[迭代 {iteration}] 决策：{'调用 ' + ', '.join(tools_called) if tools_called else '直接回答'}"
        logger.info(msg)
        self.steps.append({"iter": iteration, "type": "decision", "tools": tools_called})

    def log_tool_result(self, name: str, args: dict, result: dict, elapsed: float):
        summary = result.get("summary") or result.get("message") or str(result)[:80]
        logger.info("  → %s(%s) → %s（%.3fs）", name, args, summary, elapsed)
        self.steps.append({"type": "tool", "name": name, "args": args,
                           "result_summary": summary, "elapsed": elapsed})

    def log_final(self, answer: str, total_elapsed: float):
        logger.info("[完成] 总耗时 %.2fs，共 %d 步工具调用", total_elapsed,
                    sum(1 for s in self.steps if s["type"] == "tool"))
        self.steps.append({"type": "final", "answer": answer[:100]})

    def summary(self) -> dict:
        tool_steps = [s for s in self.steps if s["type"] == "tool"]
        return {
            "total_steps": len(tool_steps),
            "tools_used": [s["name"] for s in tool_steps],
            "total_elapsed": time.monotonic() - self.start_time,
        }
```

### 3.3 结构化的调用链记录

除了日志，还可以把调用链保存为结构化数据，方便后续分析：

```python
@dataclass
class StepRecord:
    iteration: int
    tool_name: str
    args: dict
    result_summary: str
    elapsed: float

@dataclass
class WorkflowResult:
    user_input: str
    final_answer: str
    steps: list[StepRecord]
    total_iterations: int
    total_elapsed: float
    terminated_by: str  # "model_done" | "max_iterations"
```

---

## 四、完整多步工作流 Demo

### 4.1 场景设计：出行规划助手

选择出行规划场景，因为它天然需要多步推理：
- 查目的地天气（决定着装/活动）
- 查货币汇率（决定预算）
- 综合两个维度给出建议

这个场景可以展示：1 步工具调用（只问天气）和 2 步工具调用（问天气 + 汇率）的情况，以及 0 步（纯知识问答）。

### 4.2 完整实现

```python
import json
import os
import logging
import time
from dataclasses import dataclass, field
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

# ── 工具定义（内联）────────────────────────────────────────────────────────

def get_weather(city: str, unit: str = "celsius") -> dict:
    mock = {
        "北京": {"temp": 22, "condition": "晴", "wind": "东北风 3 级", "humidity": 45},
        "上海": {"temp": 28, "condition": "多云", "wind": "东南风 2 级", "humidity": 72},
        "广州": {"temp": 33, "condition": "阵雨", "wind": "南风 4 级", "humidity": 88},
        "成都": {"temp": 19, "condition": "阴", "wind": "微风", "humidity": 65},
        "哈尔滨": {"temp": 8, "condition": "小雨", "wind": "北风 5 级", "humidity": 80},
    }
    if city not in mock:
        return {"error": True, "message": f"暂无 '{city}' 的天气数据，支持：北京/上海/广州/成都/哈尔滨"}
    d = mock[city]
    temp = d["temp"] if unit == "celsius" else round(d["temp"] * 9 / 5 + 32, 1)
    unit_str = "°C" if unit == "celsius" else "°F"
    wear_advice = (
        "短袖/T恤" if d["temp"] >= 28 else
        "薄外套/长袖" if d["temp"] >= 18 else
        "厚外套/夹克" if d["temp"] >= 10 else "羽绒服/厚棉衣"
    )
    return {
        "city": city, "temperature": temp, "unit": unit_str,
        "condition": d["condition"], "wind": d["wind"], "humidity": d["humidity"],
        "wear_advice": wear_advice,
        "summary": f"{city}当前{d['condition']}，{temp}{unit_str}，{d['wind']}，湿度{d['humidity']}%，建议穿{wear_advice}",
    }


def get_exchange_rate(from_currency: str, to_currency: str, amount: float = None) -> dict:
    rates = {
        ("CNY", "USD"): 0.138, ("USD", "CNY"): 7.245,
        ("CNY", "EUR"): 0.128, ("EUR", "CNY"): 7.85,
        ("USD", "EUR"): 0.923, ("EUR", "USD"): 1.083,
        ("CNY", "JPY"): 20.3, ("JPY", "CNY"): 0.049,
        ("USD", "JPY"): 151.2, ("JPY", "USD"): 0.0066,
    }
    from_c, to_c = from_currency.upper(), to_currency.upper()
    if from_c == to_c:
        rate = 1.0
    else:
        rate = rates.get((from_c, to_c))
        if rate is None:
            return {"error": True, "message": f"不支持 {from_c}→{to_c} 的汇率，支持：CNY/USD/EUR/JPY 互转"}
    result = {"from": from_c, "to": to_c, "rate": rate}
    if amount is not None:
        converted = round(amount * rate, 2)
        result["amount"] = amount
        result["converted"] = converted
        result["summary"] = f"{amount} {from_c} = {converted} {to_c}（汇率 {rate}）"
    else:
        result["summary"] = f"1 {from_c} = {rate} {to_c}"
    return result


TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": (
            "获取指定城市的当前实时天气，包括温度、天气状况、风速、湿度和着装建议。"
            "适用于查询当前天气、是否下雨/下雪、今天适合穿什么等问题。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如'北京'、'上海'"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"],
                         "description": "温度单位，默认摄氏度"},
            },
            "required": ["city"],
        },
    }},
    {"type": "function", "function": {
        "name": "get_exchange_rate",
        "description": "获取两种货币之间的实时汇率，可选传入金额进行换算。支持 CNY/USD/EUR/JPY。",
        "parameters": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string", "description": "源货币代码，如'CNY'、'USD'"},
                "to_currency": {"type": "string", "description": "目标货币代码，如'USD'、'EUR'"},
                "amount": {"type": "number", "description": "可选，要换算的金额"},
            },
            "required": ["from_currency", "to_currency"],
        },
    }},
]

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "get_exchange_rate": get_exchange_rate,
}

SYSTEM_PROMPT = (
    "你是一个智能出行规划助手，可以查询实时天气和货币汇率。\n"
    "规则：\n"
    "1. 当用户询问某地当前天气、着装建议时，调用 get_weather 工具\n"
    "2. 当用户询问货币换算、预算规划时，调用 get_exchange_rate 工具\n"
    "3. 如果一个问题需要天气和汇率两类信息，分别调用两个工具再综合回答\n"
    "4. 回答简洁、直接，包含具体数据，不要泛泛而谈"
)


# ── 调用链记录 ─────────────────────────────────────────────────────────────

@dataclass
class ToolStep:
    name: str
    args: dict
    result: dict
    elapsed: float


@dataclass
class WorkflowResult:
    user_input: str
    final_answer: str
    steps: list = field(default_factory=list)
    total_elapsed: float = 0.0
    terminated_by: str = "model_done"   # "model_done" | "max_iterations"


# ── 多步工作流主函数 ──────────────────────────────────────────────────────────

def run_workflow(user_input: str, max_iter: int = 6) -> WorkflowResult:
    wf = WorkflowResult(user_input=user_input)
    t_start = time.monotonic()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    logger.info("═" * 55)
    logger.info("用户：%s", user_input)

    for iteration in range(1, max_iter + 1):
        # API 调用：让模型决策
        t_call = time.monotonic()
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
        )
        msg = response.choices[0].message
        elapsed_call = time.monotonic() - t_call

        # 退出条件 1：模型直接回答
        if not msg.tool_calls:
            wf.final_answer = msg.content
            wf.terminated_by = "model_done"
            logger.info("[迭代 %d] 模型直接回答（%.2fs）：%s", iteration, elapsed_call,
                        msg.content[:60])
            break

        logger.info("[迭代 %d] 模型调用 %d 个工具（决策 %.2fs）",
                    iteration, len(msg.tool_calls), elapsed_call)
        messages.append(msg)

        # 执行本轮所有工具
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            logger.info("  ↓ 调用 %s  args=%s", name, args)

            t_tool = time.monotonic()
            if name in TOOL_REGISTRY:
                result = TOOL_REGISTRY[name](**args)
            else:
                result = {"error": True, "message": f"未知工具：{name}"}
            elapsed_tool = time.monotonic() - t_tool

            logger.info("  ↑ 返回（%.3fs）：%s", elapsed_tool,
                        result.get("summary") or result.get("message") or str(result)[:60])

            wf.steps.append(ToolStep(name=name, args=args, result=result, elapsed=elapsed_tool))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    else:
        # 达到 max_iter 仍未退出，强制生成回答
        wf.terminated_by = "max_iterations"
        logger.warning("已达最大迭代次数 %d，强制生成最终回答", max_iter)
        messages.append({
            "role": "user",
            "content": "请基于目前获取到的信息，直接给出你的最终回答。"
        })
        final_resp = client.chat.completions.create(
            model="deepseek-chat", messages=messages, temperature=0,
        )
        wf.final_answer = final_resp.choices[0].message.content

    wf.total_elapsed = time.monotonic() - t_start
    logger.info("完成（总 %.2fs，%d 步工具调用，终止原因：%s）",
                wf.total_elapsed, len(wf.steps), wf.terminated_by)
    return wf


# ── 运行示例 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        "北京今天天气怎么样，适合出行吗？",                             # 1 步工具
        "我下周去上海出差，带 500 美元够吗？天气怎么样？",              # 2 步工具
        "广州天气热不热？我想把 2000 人民币换成欧元用于购物。",          # 2 步工具
        "人工智能的发展趋势是什么？",                                    # 0 步工具
        "去哈尔滨旅游，今天天气如何，带 1000 人民币换日元够买礼物吗？",  # 2 步工具
    ]

    for q in test_cases:
        result = run_workflow(q)
        print(f"\n{'─' * 55}")
        print(f"Q: {q}")
        print(f"工具调用链: {' → '.join(s.name for s in result.steps) or '（无）'}")
        print(f"A: {result.final_answer}")
        print(f"（{len(result.steps)} 步工具调用，{result.total_elapsed:.2f}s，{result.terminated_by}）")
```

### 4.3 典型调用链示例

**场景 A：2 步工具调用**

```
用户：我下周去上海出差，带 500 美元够吗？天气怎么样？

═══════════════════════════════════════════════════════
[迭代 1] 模型调用 2 个工具（决策 0.82s）
  ↓ 调用 get_weather  args={'city': '上海'}
  ↑ 返回（0.001s）：上海当前多云，28°C，东南风 2 级，湿度72%，建议穿薄外套/长袖
  ↓ 调用 get_exchange_rate  args={'from_currency': 'USD', 'to_currency': 'CNY', 'amount': 500}
  ↑ 返回（0.001s）：500 USD = 3622.5 CNY（汇率 7.245）
[迭代 2] 模型直接回答（0.74s）：上海今天多云，28°C……
完成（总 1.61s，2 步工具调用，终止原因：model_done）
```

**场景 B：0 步工具调用（纯知识）**

```
用户：人工智能的发展趋势是什么？

[迭代 1] 模型直接回答（0.63s）：AI 的发展趋势……
完成（总 0.65s，0 步工具调用，终止原因：model_done）
```

**场景 C：并行工具调用**（模型一次返回 2 个 `tool_calls`）

```
[迭代 1] 模型调用 2 个工具（决策 0.91s）
  ↓ 调用 get_weather + get_exchange_rate（同一 assistant 消息里）
  ↑ 两个工具依次执行
[迭代 2] 模型直接回答
```

注意：当用户问题明显需要两类数据时，DeepSeek 等模型通常会在**一次 API 调用**里同时返回两个 `tool_calls`，而不是分两轮各调一次。这样总迭代次数只有 2（一次决策 + 两个工具 → 一次生成），比逐步调用效率更高。

---

## 五、Day 25 知识速查

### 多步工作流 vs 单步的关键差异

| 维度 | 单步（Day 24） | 多步（Day 25） |
|------|--------------|--------------|
| 调用结构 | 固定两次 API 调用 | N+1 次（N 由模型决定） |
| 循环结构 | `if msg.tool_calls` | `while iteration < max_iter` |
| 终止条件 | 第二次调用固定回答 | 模型 `tool_calls` 为空，或达到 `max_iterations` |
| 调用链长度 | 最多 1 个工具 | 0 ~ max_iter 个工具 |
| 典型耗时 | ~1.5s | ~1.5s + n × 工具耗时 |

### 最小多步工作流模板

```python
def multi_step(user_input, tools, registry, system_prompt, max_iter=6):
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}]
    
    for _ in range(max_iter):
        msg = client.chat.completions.create(
            model="deepseek-chat", messages=messages,
            tools=tools, tool_choice="auto", temperature=0,
        ).choices[0].message
        
        if not msg.tool_calls:
            return msg.content   # 正常退出
        
        messages.append(msg)
        for tc in msg.tool_calls:
            result = registry.get(tc.function.name, lambda **_: {"error": "未知工具"})(
                **json.loads(tc.function.arguments))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    
    # 超出上限，强制回答
    return client.chat.completions.create(model="deepseek-chat", messages=messages,
                                          temperature=0).choices[0].message.content
```

### 常见问题速查

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 工具被重复调用（调 3 次 get_weather） | 模型每轮重新决策，忘记已调过 | 在 System Prompt 说明"每个工具调用一次即可" |
| 达到 max_iter 仍未回答 | 工具返回了错误，模型想重试 | 检查工具的 error 处理；适当增加 max_iter |
| 模型调用顺序和预期不同 | 模型自主规划调用顺序 | 用 `tool_choice` 指定第一步必须调某工具 |
| Token 消耗迅速增长 | 历史消息随迭代累积 | 对工具结果做摘要（只保留 summary 字段）；限制 max_iter |
| 并行工具只执行了 1 个 | `tool_calls` 列表里有多个，for 循环遍历即可 | 确认 for 循环遍历所有 `msg.tool_calls` |

---

## 六、实践任务

- [ ] 运行完整 Demo（5 组测试问题），对照日志确认每条问题的工具调用步数
- [ ] 验证"并行工具调用"：用一个同时需要天气和汇率的问题测试，确认模型是否在第 1 轮同时返回 2 个 `tool_calls`
- [ ] 测试 `max_iter` 保护：临时把 `max_iter=1`，验证达到上限时是否能正确强制生成最终回答
- [ ] 添加 Token 统计：修改代码，在每次 API 调用后打印 `response.usage.total_tokens`，观察历史累积对 Token 消耗的影响
- [ ] 扩展工具：再添加一个工具（如"查城市简介"），验证工作流能否自动使用新工具
- [ ] 实现 `WorkflowResult` 的 JSON 序列化，把调用链保存为文件，分析哪类问题会触发几步工具调用

**产出标准**：

- `day25_multi_step_workflow.py` 可运行，5 组问题均有正确输出和详细日志
- 能用自己的话解释"为什么需要 max_iterations 上限，而不是让模型无限循环"

---

## 七、下一步预告

**Day 26：给项目添加简单界面**

Day 24–25 完成了工具调用的核心逻辑，Day 26 进入**可展示阶段**——用最小成本给 Demo 加上可交互的界面：

- **Gradio 快速入门**：5 行代码把 Python 函数变成 Web 界面，无需学前端
- **接入多步工作流**：把 Day 25 的 `run_workflow` 函数接入 Gradio，展示实时流式输出
- **展示调用链**：在界面上显示"模型调了哪些工具 → 得到什么结果 → 最终回答"的可视化链路
- **部署思路**：本地运行 vs Gradio 分享链接（临时公网访问），让他人也能体验你的 Demo

Day 26 的产出：一个可以在浏览器里访问、展示完整工具调用链路的 Web Demo，是整个项目最直接的"成果展示"形式。
