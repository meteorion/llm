# Day 24：单工具调用 Demo

> 学习目标：把 Day 22–23 的工具定义接入真实 LLM 对话，完成完整的"用户提问 → 模型决策 → 工具执行 → 自然语言回答"闭环，理解如何控制触发时机并处理各种边界情况
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 24
>
> 🧭 导航：[← Day 23 · 定义第一个工具](day23_define_first_tool.md) [→ Day 25 · 多步工作流](day25_multi_step_workflow.md)

---

## 目录

- [一、tool_choice 参数深度解析](#一tool_choice-参数深度解析)
  - [1.1 三种模式的行为差异](#11-三种模式的行为差异)
  - [1.2 强制指定工具（指定名称模式）](#12-强制指定工具指定名称模式)
  - [1.3 什么时候用哪种模式](#13-什么时候用哪种模式)
- [二、模型如何决定触发工具](#二模型如何决定触发工具)
  - [2.1 触发决策的影响因素](#21-触发决策的影响因素)
  - [2.2 调整触发边界的实用方法](#22-调整触发边界的实用方法)
  - [2.3 模型不调工具时该怎么办](#23-模型不调工具时该怎么办)
- [三、完整单工具调用 Demo](#三完整单工具调用-demo)
  - [3.1 核心调用逻辑](#31-核心调用逻辑)
  - [3.2 带日志的完整实现](#32-带日志的完整实现)
- [四、多轮对话中的工具调用](#四多轮对话中的工具调用)
  - [4.1 工具调用历史的保存规则](#41-工具调用历史的保存规则)
  - [4.2 跨轮引用工具结果](#42-跨轮引用工具结果)
- [五、Day 24 知识速查](#五day-24-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、tool_choice 参数深度解析

### 1.1 三种模式的行为差异

`tool_choice` 参数控制模型是否以及如何选择工具，共有三种基础模式：

```
┌────────────────────────────────────────────────────────────────────┐
│                     tool_choice 三种模式对比                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  "auto"（默认）                                                     │
│  ─────────────────────────────────────────────────────────         │
│  模型自主判断：觉得需要工具 → tool_calls；觉得不需要 → 直接回答       │
│  用户问"今天天气" → tool_calls ✓                                    │
│  用户问"Python 是什么" → 直接回答 ✓                                 │
│                                                                     │
│  "none"                                                             │
│  ─────────────────────────────────────────────────────────         │
│  禁用所有工具，模型只能用训练知识回答，即使注册了工具也不会调用       │
│  用户问"今天天气" → 给出通用性回答（不是实时数据）                    │
│  用途：测试"没有工具时模型如何回答"/ 对比实验                        │
│                                                                     │
│  "required"                                                         │
│  ─────────────────────────────────────────────────────────         │
│  强制模型必须调用某个工具（至少一个），不允许直接回答                  │
│  用途：ETL 流程、信息抽取、确保必须走工具路径的场景                   │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

**代码示例**：

```python
# auto 模式（最常用）
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=TOOLS,
    tool_choice="auto",
)

# none 模式（禁用工具）
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=TOOLS,
    tool_choice="none",   # 即使有 tools，也不调用
)

# required 模式（必须调用工具）
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=TOOLS,
    tool_choice="required",  # 模型必须在 tool_calls 里填至少一个工具
)
```

### 1.2 强制指定工具（指定名称模式）

除了三种字符串模式，还可以**强制指定调用哪个工具**：

```python
# 强制调用 get_weather，不管用户说什么
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=TOOLS,
    tool_choice={
        "type": "function",
        "function": {"name": "get_weather"}
    },
)
# 此时模型必须调用 get_weather，参数仍由模型填写
```

**适用场景**：

- 流程中的特定步骤必须执行某个工具（无论用户输入什么）
- 批量信息抽取：强制每条输入都调用 `extract_info` 工具，保证输出结构化
- 测试：验证某个特定工具在给定输入下的参数填写是否正确

### 1.3 什么时候用哪种模式

| 场景 | 推荐模式 | 理由 |
|------|---------|------|
| 通用对话助手（用户问任何问题） | `"auto"` | 模型自主判断最合理 |
| 测试"没有工具时的基线" | `"none"` | 对比有无工具时的回答质量 |
| 信息抽取流水线（每条都要抽取） | `"required"` 或指定名称 | 保证输出格式一致 |
| 多工具时强制走特定工具 | 指定名称 | 避免模型选错工具 |
| 生产环境日常使用 | `"auto"` | 灵活性最高，符合用户期望 |

---

## 二、模型如何决定触发工具

### 2.1 触发决策的影响因素

模型不是随机调用工具，触发决策基于三个核心因素：

```
触发决策的三个维度：

  维度 1：用户意图 vs 工具能力的匹配度
  ─────────────────────────────────────
  "今天北京天气" + get_weather → 高匹配 → 触发
  "Python 是啥" + get_weather → 零匹配 → 不触发
  "气温超过 30 度时人容易中暑吗" + get_weather → 低匹配（问的是生理，不是实时天气）→ 不触发

  维度 2：工具 description 的清晰程度
  ─────────────────────────────────────
  模糊描述："获取数据"
    → 模型不知道什么时候用，触发边界不稳定
  
  清晰描述："获取指定城市的当前实时天气，仅适用于当前天气查询"
    → 模型知道"实时"和"当前"才触发，历史天气不触发

  维度 3：模型对自身知识的自信度
  ─────────────────────────────────────
  能直接回答的问题（基础知识、常识）→ 不调工具
  无法确定实时状态的问题（价格、天气、新闻）→ 倾向调工具
```

**一个实验**：同一个问题，用不同措辞，触发率不同：

```
问题                           是否触发 get_weather
─────────────────────────────────────────────
"今天北京天气怎么样？"           ✓ 触发
"北京一般什么季节下雪？"         ✗ 不触发（问的是规律，不是实时）
"北京天气好吗？"                ？ 不稳定（模糊问题，模型有时触发有时不触发）
"帮我查查北京今天的温度"         ✓ 触发
"告诉我北京天气"                ✓ 触发
```

### 2.2 调整触发边界的实用方法

当发现工具触发不准确（该触发的不触发，不该触发的触发了），优先调整工具的 description：

```python
# 问题：用户问"北京有雪吗"（问的是现在），模型不触发
# 原因：description 没有覆盖"有没有下雪"这类问法

# 优化前
"description": "获取指定城市的当前实时天气，包括温度和天气状况"

# 优化后（增加"降水/降雪"的语义）
"description": (
    "获取指定城市的当前实时天气，包括温度、天气状况（晴/多云/雨/雪等）和风速。"
    "适用于查询当前气温、是否下雨、是否下雪等实时天气相关问题。"
)
```

**System Prompt 兜底**：也可以在 system 消息里提示模型何时使用工具：

```python
messages = [
    {
        "role": "system",
        "content": (
            "你是一个智能助手，配备了天气查询工具。"
            "当用户询问任何关于某地当前天气状况的问题时（包括温度、降水、风速等），"
            "必须先调用 get_weather 工具获取实时数据，而不是依赖你的训练知识回答。"
        )
    },
    {"role": "user", "content": user_input}
]
```

### 2.3 模型不调工具时该怎么办

模型在 `auto` 模式下决定不调工具时，有两种情况：

```
情况 A：正确的不调用
  用户："Python 里怎么用 f-string？"
  模型：直接回答，不调 get_weather ✓
  处理：正常使用模型的文字回答

情况 B：错误的不调用（该调却没调）
  用户："上海今天天气怎么样？"
  模型：给出通用回答（如"上海夏季炎热..."）而不调工具
  
  诊断步骤：
    1. 检查工具 description 是否足够清晰
    2. 检查 messages 里是否有 system 提示
    3. 降低 temperature（temperature=0 时触发更稳定）
    4. 改用 tool_choice="required" 强制触发（适合测试，不适合生产）
```

---

## 三、完整单工具调用 Demo

### 3.1 核心调用逻辑

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

# 使用 Day 23 的工具定义
from tools.weather import get_weather, WEATHER_TOOL_SCHEMA
from tools.exchange_rate import get_exchange_rate, EXCHANGE_RATE_TOOL_SCHEMA

TOOLS = [WEATHER_TOOL_SCHEMA, EXCHANGE_RATE_TOOL_SCHEMA]
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "get_exchange_rate": get_exchange_rate,
}


def dispatch(name: str, args: dict) -> dict:
    if name not in TOOL_REGISTRY:
        return {"error": True, "message": f"未知工具：{name}"}
    try:
        return TOOL_REGISTRY[name](**args)
    except TypeError as e:
        return {"error": True, "message": f"工具参数错误：{e}"}


def single_turn(user_input: str, system_prompt: str = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_input})

    # 第一次调用：让模型决定是否使用工具
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0,
    )
    msg = response.choices[0].message

    # 模型直接回答（无工具调用）
    if not msg.tool_calls:
        return msg.content

    # 执行所有工具调用
    messages.append(msg)
    for tc in msg.tool_calls:
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        result = dispatch(name, args)
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    # 第二次调用：基于工具结果生成最终回答
    final = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=TOOLS,
        temperature=0,
    )
    return final.choices[0].message.content
```

### 3.2 带日志的完整实现

```python
import json
import os
import logging
import time
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

# ── 工具定义（内联，不依赖外部文件）────────────────────────────────────────

def get_weather(city: str, unit: str = "celsius") -> dict:
    mock = {
        "北京": {"temp": 22, "condition": "晴", "wind": "东北风 3 级"},
        "上海": {"temp": 28, "condition": "多云", "wind": "东南风 2 级"},
        "广州": {"temp": 33, "condition": "阵雨", "wind": "南风 4 级"},
        "成都": {"temp": 19, "condition": "阴", "wind": "微风"},
    }
    if city not in mock:
        return {"error": True, "message": f"暂无 '{city}' 的天气数据"}
    d = mock[city]
    temp = d["temp"] if unit == "celsius" else round(d["temp"] * 9 / 5 + 32, 1)
    unit_str = "°C" if unit == "celsius" else "°F"
    return {
        "city": city, "temperature": temp, "unit": unit_str,
        "condition": d["condition"], "wind": d["wind"],
        "summary": f"{city}当前{d['condition']}，{temp}{unit_str}，{d['wind']}",
    }


def get_exchange_rate(from_currency: str, to_currency: str, amount: float = None) -> dict:
    rates = {("CNY", "USD"): 0.138, ("USD", "CNY"): 7.245,
             ("EUR", "CNY"): 7.85, ("USD", "EUR"): 0.923, ("USD", "JPY"): 151.2}
    from_c, to_c = from_currency.upper(), to_currency.upper()
    if from_c == to_c:
        rate = 1.0
    else:
        rate = rates.get((from_c, to_c))
        if rate is None:
            return {"error": True, "message": f"不支持 {from_c}→{to_c} 的汇率"}
    result = {"from": from_c, "to": to_c, "rate": rate,
              "description": f"1 {from_c} = {rate} {to_c}"}
    if amount is not None:
        converted = round(amount * rate, 2)
        result["amount"] = amount
        result["converted"] = converted
        result["summary"] = f"{amount} {from_c} ≈ {converted} {to_c}"
    else:
        result["summary"] = f"1 {from_c} = {rate} {to_c}"
    return result


TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "获取指定城市的当前实时天气（温度、天气状况、风速）。仅适用于当前天气查询，不支持预报。",
        "parameters": {"type": "object",
                       "properties": {"city": {"type": "string", "description": "城市名，如'北京'"},
                                      "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
                       "required": ["city"]},
    }},
    {"type": "function", "function": {
        "name": "get_exchange_rate",
        "description": "获取两种货币之间的实时汇率，可选传入金额进行换算。",
        "parameters": {"type": "object",
                       "properties": {"from_currency": {"type": "string", "description": "源货币代码，如'CNY'"},
                                      "to_currency": {"type": "string", "description": "目标货币代码，如'USD'"},
                                      "amount": {"type": "number", "description": "可选，要换算的金额"}},
                       "required": ["from_currency", "to_currency"]},
    }},
]

TOOL_REGISTRY = {"get_weather": get_weather, "get_exchange_rate": get_exchange_rate}

SYSTEM_PROMPT = (
    "你是一个智能助手，可以查询实时天气和货币汇率。"
    "当用户询问某地当前天气或货币兑换时，优先使用对应工具获取实时数据。"
    "回答要简洁、自然，直接给出用户需要的信息。"
)


# ── 核心对话函数 ─────────────────────────────────────────────────────────────

def chat(user_input: str, history: list[dict] = None) -> tuple[str, list[dict]]:
    """
    单轮对话，支持传入历史消息（多轮复用）。
    返回 (最终回答, 更新后的完整消息历史)
    """
    if history is None:
        history = [{"role": "system", "content": SYSTEM_PROMPT}]

    history.append({"role": "user", "content": user_input})
    logger.info("用户：%s", user_input)

    # 第一次调用
    t0 = time.monotonic()
    resp1 = client.chat.completions.create(
        model="deepseek-chat", messages=history,
        tools=TOOLS, tool_choice="auto", temperature=0,
    )
    msg = resp1.choices[0].message
    elapsed1 = time.monotonic() - t0

    if not msg.tool_calls:
        history.append({"role": "assistant", "content": msg.content})
        logger.info("直接回答（%.2fs，无工具调用）", elapsed1)
        return msg.content, history

    logger.info("模型决定调用 %d 个工具（%.2fs）", len(msg.tool_calls), elapsed1)
    history.append(msg)

    # 执行工具
    for tc in msg.tool_calls:
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        logger.info("  → 调用 %s(%s)", name, args)

        t_tool = time.monotonic()
        if name in TOOL_REGISTRY:
            result = TOOL_REGISTRY[name](**args)
        else:
            result = {"error": True, "message": f"未知工具：{name}"}
        elapsed_tool = time.monotonic() - t_tool

        logger.info("  ← 返回（%.3fs）：%s", elapsed_tool,
                    result.get("summary") or result.get("message") or str(result)[:60])

        history.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    # 第二次调用：生成最终回答
    t2 = time.monotonic()
    resp2 = client.chat.completions.create(
        model="deepseek-chat", messages=history,
        tools=TOOLS, temperature=0,
    )
    answer = resp2.choices[0].message.content
    elapsed2 = time.monotonic() - t2

    history.append({"role": "assistant", "content": answer})
    logger.info("最终回答（%.2fs）：%s", elapsed2, answer[:80])
    return answer, history


# ── 运行示例 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        ("今天北京天气怎么样？", "天气查询"),
        ("上海和广州哪个更热？", "多城市对比"),
        ("1000 人民币能换多少美元？", "汇率换算"),
        ("Python 的 GIL 是什么？", "纯知识问答，不触发工具"),
        ("北京天气适合出行吗，顺便告诉我今天人民币对日元汇率", "多工具并行"),
    ]

    history = None
    for user_input, label in test_cases:
        print(f"\n{'='*60}")
        print(f"[{label}]")
        answer, history = chat(user_input, history)
        print(f"回答：{answer}")
```

---

## 四、多轮对话中的工具调用

### 4.1 工具调用历史的保存规则

多轮对话时，工具调用相关的消息必须**完整保留**在历史里，否则模型在下一轮会不知道之前获取了什么数据。

```
完整消息历史结构（含工具调用的轮次）：

  [{"role": "system", "content": "..."}]           ← 系统提示
  [{"role": "user", "content": "北京天气"}]         ← 第 1 轮用户输入
  [{"role": "assistant", "tool_calls": [...]}]      ← 模型的工具调用请求 ← 必须保留
  [{"role": "tool", "tool_call_id": "...", ...}]    ← 工具执行结果 ← 必须保留
  [{"role": "assistant", "content": "北京晴，22°C"}] ← 最终回答
  [{"role": "user", "content": "上海呢？"}]          ← 第 2 轮用户输入
```

**为什么不能只保留最终回答**：如果删除中间的 `tool_calls` 和 `tool` 消息，只保留最终回答，那么在第 2 轮对话时，模型无法知道第 1 轮是通过工具得到了实时天气，可能会认为"北京晴，22°C"只是模型自己说的，而不是真实数据。

### 4.2 跨轮引用工具结果

```python
if __name__ == "__main__":
    print("=== 多轮对话示例（工具结果在轮次间保留）===\n")

    # 初始化共享历史
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 第 1 轮：查天气
    answer1, history = chat("北京今天天气怎么样？", history)
    print(f"[第 1 轮] {answer1}\n")

    # 第 2 轮：基于第 1 轮的信息追问
    answer2, history = chat("那上海呢？两个城市比较哪个更适合户外活动？", history)
    print(f"[第 2 轮] {answer2}\n")

    # 第 3 轮：切换话题（汇率）
    answer3, history = chat("顺便问一下，现在美元对人民币汇率是多少？", history)
    print(f"[第 3 轮] {answer3}\n")

    # 第 4 轮：综合上下文
    answer4, history = chat("如果我计划这周去上海出差，带 500 美元够吗？", history)
    print(f"[第 4 轮] {answer4}\n")

    print(f"消息历史总条数：{len(history)}")
```

**预期行为**：
- 第 2 轮查上海天气时，模型知道第 1 轮已经查了北京，会自动补充上海并进行对比
- 第 4 轮模型能引用第 3 轮的汇率结果，结合上海的物价水平给出建议
- 每次工具调用都会在日志里留下记录

---

## 五、Day 24 知识速查

### tool_choice 模式速查

| 模式 | 写法 | 适用场景 |
|------|------|---------|
| 自动（默认） | `tool_choice="auto"` | 通用对话助手 |
| 禁用工具 | `tool_choice="none"` | 基线测试、调试 |
| 强制调用（任意工具） | `tool_choice="required"` | 信息抽取流水线 |
| 强制调用（指定工具） | `tool_choice={"type":"function","function":{"name":"xxx"}}` | 批量抽取、测试特定工具 |

### 完整 Demo 代码框架（最小版本）

```python
def chat_with_tools(user_input: str) -> str:
    messages = [
        {"role": "system", "content": "你是智能助手..."},
        {"role": "user", "content": user_input},
    ]

    # 第一次：决策
    msg = client.chat.completions.create(
        model="deepseek-chat", messages=messages,
        tools=TOOLS, tool_choice="auto", temperature=0,
    ).choices[0].message

    if not msg.tool_calls:
        return msg.content   # 直接回答

    # 执行工具
    messages.append(msg)
    for tc in msg.tool_calls:
        result = TOOL_REGISTRY.get(tc.function.name, lambda **_: {"error": "未知工具"}) \
                 (**json.loads(tc.function.arguments))
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result, ensure_ascii=False)})

    # 第二次：生成最终回答
    return client.chat.completions.create(
        model="deepseek-chat", messages=messages, tools=TOOLS, temperature=0,
    ).choices[0].message.content
```

### 常见问题排查

| 症状 | 可能原因 | 解决方法 |
|------|---------|---------|
| 该触发工具但没触发 | description 描述不清晰 | 修改 description，加入适用边界 |
| 不该触发却触发了 | description 范围太广 | 在 description 里明确"不适用"场景 |
| 参数填错（如传了中文单位） | 参数 description 没有示例 | 在参数 description 里加 enum 或格式示例 |
| 第二次调用报错 | `tool_call_id` 不匹配 | 检查传 `tool` 消息时的 `tool_call_id` 是否来自 `tc.id` |
| 多轮对话"忘记"工具结果 | 历史消息被截断 | 确保 `msg.tool_calls` 消息和 `tool` 消息都在历史里 |

---

## 六、实践任务

- [ ] 运行完整 Demo（`python day24_single_tool_demo.py`），观察 5 组问题的日志输出，确认哪些触发了工具、哪些没有
- [ ] 测试 `tool_choice="none"`：把天气查询的 `tool_choice` 改为 `"none"`，对比有无工具时的回答差异
- [ ] 复现"触发边界"：把工具 description 中的"仅适用于当前天气查询"去掉，测试"北京一般什么时候最热"是否会误触发工具
- [ ] 跑通多轮对话示例（4.2 小节），确认第 4 轮能引用第 3 轮的汇率结果
- [ ] 主动制造一个工具错误（传入不存在的城市名），确认模型能基于错误 dict 生成友好的用户提示
- [ ] 统计一次完整对话的 Token 消耗：两次 API 调用各消耗了多少 Token？工具结果传入增加了多少输入 Token？

**产出标准**：

- `day24_single_tool_demo.py` 可运行，5 组测试问题均有正确输出（含工具调用日志）
- 能用自己的话解释"为什么多轮对话里 `tool_calls` 消息不能删"

---

## 七、下一步预告

**Day 25：做多步工作流**

Day 24 完成了单工具调用的完整闭环，Day 25 进入**多步工作流**——让模型通过多轮工具调用完成一个需要多步推理的复杂任务：

- **多步推理结构**：模型先调工具 A 获取数据，基于结果决定是否继续调工具 B，最后综合所有结果回答
- **循环调用的终止条件**：何时停止工具调用、何时切换到生成最终回答？
- **调用链可观测性**：记录每步"调用了什么工具→返回了什么→下一步决策"，让整个推理过程透明
- **实际场景**：旅行规划（查天气 → 查机票 → 查酒店 → 综合建议）、数据分析（查数据 → 计算 → 生成报告）

Day 25 的产出：一个"先理解需求 → 调用工具链 → 生成自然语言结果"的多步流程 Demo，工具调用次数可变（由模型自主决定）。
