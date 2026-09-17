# Day 27：整合成完整作品

> 学习目标：把 Day 1–26 学到的核心能力整合成一个结构完整、可稳定演示的项目，掌握项目整合的思路、目录结构规范和 README 工程化写法，产出一个能放到 GitHub 展示的作品
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 27
>
> 🧭 导航：[← Day 26 · 添加简单界面](day26_simple_ui.md) [→ Day 28 · 补工程细节](day28_engineering_details.md)

---

## 目录

- [一、整合日的核心任务](#一整合日的核心任务)
  - [1.1 三选一：项目方向](#11-三选一项目方向)
  - [1.2 整合 vs 重写：正确的姿势](#12-整合-vs-重写正确的姿势)
  - [1.3 功能边界：砍掉做不完的部分](#13-功能边界砍掉做不完的部分)
- [二、标准项目目录结构](#二标准项目目录结构)
  - [2.1 推荐目录布局](#21-推荐目录布局)
  - [2.2 各目录的职责说明](#22-各目录的职责说明)
  - [2.3 必须有的四个文件](#23-必须有的四个文件)
- [三、可调用工具的个人助理（完整实现）](#三可调用工具的个人助理完整实现)
  - [3.1 功能设计](#31-功能设计)
  - [3.2 核心模块实现](#32-核心模块实现)
  - [3.3 完整入口与 Gradio 界面](#33-完整入口与-gradio-界面)
- [四、README 工程化写法](#四readme-工程化写法)
  - [4.1 README 的必要章节](#41-readme-的必要章节)
  - [4.2 快速启动指南](#42-快速启动指南)
  - [4.3 让别人 5 分钟跑起来的关键](#43-让别人-5-分钟跑起来的关键)
- [五、Day 27 知识速查](#五day-27-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、整合日的核心任务

### 1.1 三选一：项目方向

30 天路线推荐的三个方向，对应不同的能力侧重：

```
方向 A：本地文档问答助手
  核心能力：RAG（Day 15–20）+ 简单界面（Day 26）
  典型场景：上传 PDF / TXT，问文档里的问题
  技术亮点：文档加载 → 切分 → 向量检索 → 引用来源
  适合展示：RAG 全流程 + 引用溯源

方向 B：企业知识库客服助手
  核心能力：RAG + 工具调用 + 多轮对话
  典型场景：知识库固定，用户多轮问答，自动引用条款
  技术亮点：RAG + Tool Calling 融合，引用可追溯
  适合展示：工程完整度更高

方向 C：可调用工具的个人助理          ← 本笔记主要展示方向
  核心能力：Tool Calling（Day 22–25）+ 界面（Day 26）
  典型场景：问天气、查汇率、搜知识库，一个助手全能回答
  技术亮点：多步工作流 + 工具调用链可视化
  适合展示：Day 22–26 工作成果的完整闭环
```

**如何选择**：

| 你的学习重点 | 推荐方向 |
|------------|---------|
| RAG 更扎实，Day 15–20 全做完 | 方向 A 或 B |
| Tool Calling 更熟悉，Day 22–26 全做完 | 方向 C |
| 想展示两者结合 | 方向 B（难度较高，需要时间） |
| 时间不够，追求快速完成 | 方向 C（技术栈最集中） |

### 1.2 整合 vs 重写：正确的姿势

整合日不是"重新写一遍"，而是**把已有 Demo 代码拼接成有结构的项目**：

```
错误做法：
  把 day22_*.py、day23_*.py 的代码全部复制粘贴到一个文件
  → 代码重复、无法维护、命名冲突

正确做法：
  提取各 Day Demo 的核心模块，按职责放进目录结构
  → tools/ 目录复用 day23 的工具定义
  → core/workflow.py 复用 day25 的多步工作流
  → app.py 复用 day26 的 Gradio 界面代码
```

**整合的四个步骤**：

```
Step 1：识别可复用模块
  哪些代码是"业务逻辑"（工具定义、工作流）？ → 放进 core/ 和 tools/
  哪些是"胶水代码"（UI 绑定）？ → 放进 app.py

Step 2：统一配置入口
  把所有 os.getenv("DEEPSEEK_API_KEY") 改为从 core/config.py 读取
  不同模块之间不应该各自读环境变量，应该共享一个配置对象

Step 3：统一日志
  主入口初始化 logging 一次，子模块 getLogger(__name__) 继承

Step 4：写 README 和 requirements.txt
  requirements.txt 锁定依赖版本；README 写清楚"如何 5 分钟跑起来"
```

### 1.3 功能边界：砍掉做不完的部分

整合日常见的陷阱：想做完美，越做越多，最后什么都没做完。

**功能边界原则**：

```
核心功能（必须有）：
  ✓ 天气查询
  ✓ 汇率换算
  ✓ 基础对话（无工具时直接回答）
  ✓ 工具调用链展示（右侧面板）

增强功能（有时间再加）：
  ○ 流式输出
  ○ 对话历史导出
  ○ 更多工具（新闻、日历、计算器）

坚决不做（今天不值得）：
  ✗ 用户认证
  ✗ 数据库持久化
  ✗ 多用户并发优化
  ✗ 完整的错误监控
```

---

## 二、标准项目目录结构

### 2.1 推荐目录布局

```
tool-assistant/                 ← 项目根目录
├── README.md                   ← 项目说明（必须有）
├── requirements.txt            ← 依赖列表（必须有）
├── .env.example                ← 环境变量模板（必须有，不提交真实值）
├── .gitignore                  ← 忽略 .env、__pycache__ 等
│
├── app.py                      ← 入口文件，启动 Gradio 界面
│
├── core/                       ← 核心业务逻辑
│   ├── __init__.py
│   ├── config.py               ← 配置管理（读 .env，暴露配置对象）
│   ├── client.py               ← LLM 客户端（封装 OpenAI SDK）
│   └── workflow.py             ← 多步工作流（复用 day25 逻辑）
│
├── tools/                      ← 工具定义与实现（复用 day23）
│   ├── __init__.py             ← ALL_TOOLS、TOOL_REGISTRY、dispatch()
│   ├── weather.py              ← get_weather + WEATHER_SCHEMA
│   └── exchange_rate.py        ← get_exchange_rate + EXCHANGE_SCHEMA
│
└── tests/                      ← 工具独立测试（可选但推荐）
    └── test_tools.py
```

### 2.2 各目录的职责说明

| 目录/文件 | 职责 | 对应 Day |
|---------|------|---------|
| `tools/` | 工具定义 + 实现，可独立运行测试 | Day 23 |
| `core/workflow.py` | 多步工作流主逻辑（while 循环 + max_iter） | Day 25 |
| `core/config.py` | 统一读取环境变量，暴露配置对象 | Day 13 |
| `core/client.py` | 封装 `OpenAI` 客户端，复用 API 调用 | Day 3 |
| `app.py` | Gradio 界面，只做 UI 绑定，不含业务逻辑 | Day 26 |

**关键原则**：`app.py` 只负责 UI，业务逻辑全部在 `core/` 和 `tools/`。测试时可以直接 `python core/workflow.py` 跑通，无需启动 UI。

### 2.3 必须有的四个文件

**`.env.example`**（不提交真实 key，只提交模板）：

```bash
# .env.example
# 复制本文件为 .env，填入真实值
DEEPSEEK_API_KEY=your_api_key_here
```

**`.gitignore`**：

```
.env
__pycache__/
*.pyc
.DS_Store
*.egg-info/
dist/
```

**`requirements.txt`**（锁定版本）：

```
openai>=1.0.0
gradio>=4.0.0
python-dotenv>=1.0.0
```

**`README.md`**：见第四节。

---

## 三、可调用工具的个人助理（完整实现）

### 3.1 功能设计

```
┌──────────────────────────────────────────────────────────────┐
│                   可调用工具的个人助理                          │
│                                                              │
│  支持能力：                                                    │
│  ✓ 实时天气查询（北京/上海/广州/成都/哈尔滨）                    │
│  ✓ 货币汇率换算（CNY/USD/EUR/JPY）                            │
│  ✓ 纯知识问答（不调工具，直接回答）                             │
│  ✓ 多步推理（先查天气，再查汇率，综合给建议）                    │
│  ✓ 调用链可视化（右侧面板实时展示每步工具调用）                  │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块实现

**`core/config.py`**：

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    model: str
    max_iterations: int
    temperature: float

CFG = Config(
    api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat",
    max_iterations=6,
    temperature=0.0,
)

if not CFG.api_key:
    raise ValueError("未设置 DEEPSEEK_API_KEY，请在 .env 文件中配置")
```

**`core/client.py`**：

```python
from openai import OpenAI
from .config import CFG

_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=CFG.api_key, base_url=CFG.base_url)
    return _client
```

**`tools/__init__.py`**（统一入口）：

```python
import json
from .weather import get_weather, WEATHER_SCHEMA
from .exchange_rate import get_exchange_rate, EXCHANGE_SCHEMA

ALL_TOOLS = [WEATHER_SCHEMA, EXCHANGE_SCHEMA]

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "get_exchange_rate": get_exchange_rate,
}

def dispatch(name: str, args: dict) -> dict:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": True, "message": f"未知工具：{name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": True, "message": f"工具参数错误：{e}"}
```

**`tools/weather.py`**：

```python
WEATHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取指定城市的当前天气，包括温度、状况和着装建议。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如'北京'"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    },
}

_MOCK = {
    "北京": (22, "晴", "东北风 3 级"),
    "上海": (28, "多云", "东南风 2 级"),
    "广州": (33, "阵雨", "南风 4 级"),
    "成都": (19, "阴", "微风"),
    "哈尔滨": (8, "小雨", "北风 5 级"),
}

def get_weather(city: str, unit: str = "celsius") -> dict:
    if city not in _MOCK:
        return {"error": True, "message": f"暂无 '{city}' 的数据，支持：{'、'.join(_MOCK)}"}
    temp, cond, wind = _MOCK[city]
    if unit == "fahrenheit":
        temp = round(temp * 9 / 5 + 32, 1)
        unit_s = "°F"
    else:
        unit_s = "°C"
    wear = ("短袖" if _MOCK[city][0] >= 28 else "薄外套" if _MOCK[city][0] >= 18
            else "厚外套" if _MOCK[city][0] >= 10 else "羽绒服")
    return {"city": city, "temperature": temp, "unit": unit_s,
            "condition": cond, "wind": wind, "wear_advice": wear,
            "summary": f"{city}现在{cond}，{temp}{unit_s}，{wind}，建议穿{wear}"}
```

**`tools/exchange_rate.py`**：

```python
EXCHANGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_exchange_rate",
        "description": "获取两种货币之间的实时汇率，可选传入金额换算。支持 CNY/USD/EUR/JPY。",
        "parameters": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string"},
                "to_currency": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["from_currency", "to_currency"],
        },
    },
}

_RATES = {
    ("CNY", "USD"): 0.138, ("USD", "CNY"): 7.245,
    ("CNY", "EUR"): 0.128, ("EUR", "CNY"): 7.85,
    ("USD", "EUR"): 0.923, ("EUR", "USD"): 1.083,
    ("CNY", "JPY"): 20.3,  ("JPY", "CNY"): 0.049,
    ("USD", "JPY"): 151.2, ("JPY", "USD"): 0.0066,
}

def get_exchange_rate(from_currency: str, to_currency: str, amount: float = None) -> dict:
    f, t = from_currency.upper(), to_currency.upper()
    rate = 1.0 if f == t else _RATES.get((f, t))
    if rate is None:
        return {"error": True, "message": f"不支持 {f}→{t}，支持 CNY/USD/EUR/JPY 互转"}
    result = {"from": f, "to": t, "rate": rate}
    if amount is not None:
        converted = round(amount * rate, 2)
        result.update({"amount": amount, "converted": converted,
                       "summary": f"{amount} {f} = {converted} {t}（汇率 {rate}）"})
    else:
        result["summary"] = f"1 {f} = {rate} {t}"
    return result
```

**`core/workflow.py`**（多步工作流，复用 Day 25 逻辑）：

```python
import json
import logging
import time
from dataclasses import dataclass, field
from .config import CFG
from .client import get_client
from tools import ALL_TOOLS, dispatch

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一个智能个人助理，可以查询实时天气和货币汇率。\n"
    "当用户询问天气时，调用 get_weather 工具。\n"
    "当用户询问货币换算时，调用 get_exchange_rate 工具。\n"
    "如果问题不需要工具，直接回答。回答要简洁、包含具体数据。"
)


@dataclass
class ToolStep:
    name: str
    args: dict
    result: dict
    elapsed: float = 0.0


@dataclass
class WorkflowResult:
    final_answer: str = ""
    steps: list = field(default_factory=list)
    terminated_by: str = "model_done"


def run(user_input: str, messages: list) -> tuple[WorkflowResult, list]:
    client = get_client()
    wf = WorkflowResult()
    messages = messages + [{"role": "user", "content": user_input}]
    
    for _ in range(CFG.max_iterations):
        msg = client.chat.completions.create(
            model=CFG.model, messages=messages,
            tools=ALL_TOOLS, tool_choice="auto",
            temperature=CFG.temperature,
        ).choices[0].message
        
        if not msg.tool_calls:
            wf.final_answer = msg.content
            messages.append({"role": "assistant", "content": msg.content})
            break
        
        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            logger.info("调用工具 %s，参数 %s", name, args)
            
            t = time.monotonic()
            result = dispatch(name, args)
            elapsed = time.monotonic() - t
            
            logger.info("工具返回（%.3fs）：%s", elapsed,
                        result.get("summary") or result.get("message", ""))
            wf.steps.append(ToolStep(name=name, args=args, result=result, elapsed=elapsed))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    else:
        wf.terminated_by = "max_iterations"
        final = client.chat.completions.create(
            model=CFG.model, messages=messages, temperature=CFG.temperature,
        )
        wf.final_answer = final.choices[0].message.content
        messages.append({"role": "assistant", "content": wf.final_answer})
    
    return wf, messages


def format_chain(steps: list) -> str:
    if not steps:
        return "_本次无工具调用_"
    lines = []
    for i, s in enumerate(steps, 1):
        icon = "❌" if s.result.get("error") else "✅"
        summary = s.result.get("summary") or s.result.get("message", str(s.result)[:50])
        lines.append(f"**{i}. {icon} `{s.name}`**")
        lines.append(f"   参数：`{json.dumps(s.args, ensure_ascii=False)}`")
        lines.append(f"   结果：{summary}  _{s.elapsed:.3f}s_")
    return "\n\n".join(lines)
```

### 3.3 完整入口与 Gradio 界面

**`app.py`**（完整入口，约 60 行）：

```python
import logging
import gradio as gr
from core.workflow import run, format_chain, SYSTEM_PROMPT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
    datefmt="%H:%M:%S",
)


def respond(user_msg: str, chat_history: list, messages_state: list, chain_state: str):
    if not user_msg.strip():
        return "", chat_history, messages_state, chain_state
    
    if not messages_state:
        messages_state = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    result, messages_state = run(user_msg, messages_state)
    
    chat_history.append({"role": "user", "content": user_msg})
    chat_history.append({"role": "assistant", "content": result.final_answer})
    
    round_num = len(chat_history) // 2
    chain_block = f"### 第 {round_num} 轮\n\n{format_chain(result.steps)}"
    chain_state = (chain_state or "") + "\n\n---\n\n" + chain_block
    
    return "", chat_history, messages_state, chain_state


def clear_all():
    return [], None, ""


with gr.Blocks(title="个人助理 Demo", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🤖 可调用工具的个人助理\n基于 DeepSeek API + Tool Calling 的多步工作流 Demo")
    
    messages_state = gr.State(value=None)
    chain_state = gr.State(value="")
    
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话", height=480, type="messages",
                                  bubble_full_width=False)
            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="试试：北京今天天气怎么样？/ 500美元换多少人民币？/ 去上海出差带多少钱合适？",
                    label="", scale=5,
                )
                send_btn = gr.Button("发送", variant="primary", scale=1)
        
        with gr.Column(scale=2):
            chain_display = gr.Markdown(value="_等待第一次对话..._",
                                         label="🔧 工具调用链")
    
    gr.Markdown("**支持工具**：天气（北京/上海/广州/成都/哈尔滨）| 汇率（CNY/USD/EUR/JPY）")
    clear_btn = gr.Button("清空对话", variant="secondary")
    
    inputs = [msg_input, chatbot, messages_state, chain_state]
    outputs = [msg_input, chatbot, messages_state, chain_state]
    
    msg_input.submit(respond, inputs, outputs)
    send_btn.click(respond, inputs, outputs)
    clear_btn.click(clear_all, [], [chatbot, messages_state, chain_state])
    chain_state.change(lambda x: x, chain_state, chain_display)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
```

**运行方式**：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 启动
python app.py
# 访问 http://localhost:7860
```

---

## 四、README 工程化写法

### 4.1 README 的必要章节

```markdown
# 项目名称

一句话描述这个项目是做什么的。

## 功能

- ✅ 功能 1
- ✅ 功能 2

## 快速开始

（见下方）

## 技术栈

- Python 3.10+
- DeepSeek API（OpenAI 兼容）
- Gradio 4.x

## 项目结构

（目录树 + 简单说明）

## 示例截图

（至少一张运行截图，面试时很有用）
```

### 4.2 快速启动指南

快速启动是 README 最重要的部分，让别人能在 5 分钟内跑起来：

```markdown
## 快速开始

### 环境要求
- Python 3.10+
- DeepSeek API Key（在 [platform.deepseek.com](https://platform.deepseek.com) 申请）

### 安装与运行

```bash
# 克隆项目
git clone https://github.com/yourname/tool-assistant.git
cd tool-assistant

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 用编辑器打开 .env，填入你的 DEEPSEEK_API_KEY

# 启动
python app.py
```

打开浏览器访问 http://localhost:7860

### 支持的问题示例
- "北京今天天气怎么样？"
- "500 美元能换多少人民币？"
- "我去上海出差，带 500 美元够用吗？天气怎么样？"
```

### 4.3 让别人 5 分钟跑起来的关键

| 容易忘的问题 | 解决方法 |
|------------|---------|
| 没有 `.env.example` | 别人不知道要设置什么环境变量 |
| `requirements.txt` 没有锁版本 | 安装到不兼容的版本 |
| Python 版本依赖没说明 | f-string / dataclass / 类型注解语法报错 |
| 没有运行示例 | 别人不知道输入什么能看到效果 |
| 没有截图 | 面试时展示效果需要临时运行，风险大 |

---

## 五、Day 27 知识速查

### 整合日检查清单

```
目录结构
  [ ] tools/ 中有 __init__.py（统一 ALL_TOOLS、TOOL_REGISTRY、dispatch）
  [ ] core/ 中有 config.py（统一配置）、client.py（单例客户端）
  [ ] app.py 只做 UI 绑定，无业务逻辑

必要文件
  [ ] README.md（含快速启动指南）
  [ ] requirements.txt（含版本号）
  [ ] .env.example（不含真实 key）
  [ ] .gitignore（排除 .env）

可运行性
  [ ] python tools/weather.py 可独立运行（工具独立测试）
  [ ] python core/workflow.py 可独立运行（无需 UI）
  [ ] python app.py 可启动，浏览器可访问

展示准备
  [ ] 准备 3 个演示问题（0 步工具、1 步工具、2 步工具各一个）
  [ ] 截一张运行截图存到 README
```

### 项目模块调用关系

```
app.py
  ↓ import
core/workflow.py (run, format_chain)
  ↓ import                    ↓ import
tools/__init__.py           core/config.py
(ALL_TOOLS, dispatch)       (CFG)
  ↓ import                    ↓ import
tools/weather.py            core/client.py
tools/exchange_rate.py      (get_client)
```

---

## 六、实践任务

- [ ] 按第二节的目录结构创建项目，把 Day 23–26 的代码迁移到对应模块
- [ ] 确认模块间调用关系正确：`python core/workflow.py` 可独立运行（命令行测试 3 个问题）
- [ ] 确认 UI：`python app.py` 启动后，在浏览器测试 3 种场景（无工具/1 步工具/2 步工具）
- [ ] 写 README：完成"快速开始"章节（安装 → 配置 → 运行三步），让别人能照着跑起来
- [ ] 创建 `.env.example`（只含注释和变量名，不含真实 key），确认 `.gitignore` 排除了 `.env`
- [ ] 截一张运行截图（浏览器 + 工具调用链可见），保存为 `screenshots/demo.png`，添加到 README

**产出标准**：

- `python app.py` 可启动，3 类测试问题（0/1/2 步工具调用）均输出正确答案
- README 让一个没有看过代码的人能在 5 分钟内跑起来

---

## 七、下一步预告

**Day 28：补工程细节**

Day 27 做出了能运行的完整项目，Day 28 专注于**工程质量**——让项目不只"能跑"，还要"稳定跑"：

- **异常处理覆盖**：API 超时、工具错误、模型返回异常各种情况的 graceful degradation
- **日志完善**：请求日志（耗时 + Token）、错误日志（异常链路 + 上下文）、启动日志
- **配置验证**：启动时检查 API Key 是否存在、模型名称是否正确，fail-fast 而不是运行中崩溃
- **输出校验**：工具返回结果格式校验（必要字段是否存在）、模型输出的基本合法性检查
- **参数安全**：工具调用时的参数类型验证，防止模型传入非法参数导致函数崩溃

Day 28 的产出：在 Day 27 完整项目的基础上，补全工程细节后的健壮版本，面试时能自信说"这个项目考虑了 X、Y、Z 种异常情况"。
