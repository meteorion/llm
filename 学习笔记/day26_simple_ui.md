# Day 26：添加简单界面

> 学习目标：用最小成本给 LLM Demo 添加可交互的 Web 界面，掌握 Gradio 的核心用法，把 Day 25 的多步工作流接入 UI，实现可在浏览器里访问并展示工具调用链路的完整 Demo
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 26
>
> 🧭 导航：[← Day 25 · 多步工作流](day25_multi_step_workflow.md) [→ Day 27 · 整合成完整作品](day27_complete_project.md)

---

## 目录

- [一、为什么要加界面](#一为什么要加界面)
  - [1.1 命令行 Demo 的瓶颈](#11-命令行-demo-的瓶颈)
  - [1.2 Streamlit vs Gradio：选哪个](#12-streamlit-vs-gradio选哪个)
- [二、Gradio 快速入门](#二gradio-快速入门)
  - [2.1 安装与最小示例](#21-安装与最小示例)
  - [2.2 gr.Interface vs gr.ChatInterface](#22-grinterface-vs-grchatinterface)
  - [2.3 常用组件速查](#23-常用组件速查)
- [三、接入 LLM 的关键技巧](#三接入-llm-的关键技巧)
  - [3.1 流式输出（Streaming）](#31-流式输出streaming)
  - [3.2 在聊天界面展示工具调用链](#32-在聊天界面展示工具调用链)
  - [3.3 状态管理：跨轮保持对话历史](#33-状态管理跨轮保持对话历史)
- [四、完整 Demo：带工具调用链的出行规划助手](#四完整-demo带工具调用链的出行规划助手)
  - [4.1 界面设计](#41-界面设计)
  - [4.2 完整实现](#42-完整实现)
- [五、Day 26 知识速查](#五day-26-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、为什么要加界面

### 1.1 命令行 Demo 的瓶颈

Day 22–25 的 Demo 全部运行在命令行里，对技术同行展示没问题，但有三个瓶颈：

```
瓶颈 1：不可分享
  命令行 Demo 只能在有 Python 环境的机器上运行
  → 无法让产品经理/用户直接体验

瓶颈 2：没有视觉呈现
  工具调用链通过 logging 输出，混在终端里看起来很乱
  → 面试时"展示项目"效果差

瓶颈 3：单次交互
  每次 python main.py "用户输入" 都要重新启动
  → 无法体验多轮对话的连续性
```

**加界面解决的核心问题**：让非技术用户能直接使用，让技术面试时能直观展示项目效果。

### 1.2 Streamlit vs Gradio：选哪个

两者都是把 Python 函数变成 Web 应用的框架，面向不同侧重点：

| 对比维度 | Streamlit | Gradio |
|---------|-----------|--------|
| 定位 | **数据应用**（图表/报表/Dashboard） | **ML/AI 模型 Demo**（输入→推理→输出） |
| 聊天界面 | 需要手动用 `st.chat_message` 搭建 | 内置 `gr.ChatInterface`，5 行代码完成 |
| 组件丰富度 | 更丰富（数据表格、图表、表单） | AI 场景专用组件（Image/Audio/Chatbot） |
| 学习曲线 | 略高（需要理解响应式重渲染机制） | 更低（函数签名即界面） |
| 流式输出 | `st.write_stream()` | `yield` 生成器即可 |
| 最小依赖 | `pip install streamlit` | `pip install gradio` |

**结论**：做 LLM 聊天/工具 Demo → **Gradio**；做数据报表/监控面板 → Streamlit。

---

## 二、Gradio 快速入门

### 2.1 安装与最小示例

```bash
pip install gradio
```

**最小 LLM 聊天示例**（完整可运行，约 15 行）：

```python
import gradio as gr
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")

def chat(message, history):
    # history 是 Gradio 传入的对话历史，格式：[{"role": ..., "content": ...}, ...]
    messages = [{"role": "system", "content": "你是一个有帮助的助手"}]
    messages += history
    messages.append({"role": "user", "content": message})
    
    response = client.chat.completions.create(
        model="deepseek-chat", messages=messages, temperature=0.7,
    )
    return response.choices[0].message.content

gr.ChatInterface(fn=chat, title="LLM 聊天 Demo").launch()
```

运行后在浏览器打开 `http://localhost:7860` 即可使用。

### 2.2 gr.Interface vs gr.ChatInterface

```
gr.Interface（通用：一次性输入→输出）
─────────────────────────────────────
输入组件 → [Python 函数] → 输出组件
示例：文本摘要、情感分析、文本翻译

┌─────────────┐    ┌─────────────┐
│  输入文本框  │ → │   摘要结果   │
│  [提交按钮]  │    │             │
└─────────────┘    └─────────────┘


gr.ChatInterface（对话：多轮聊天）
─────────────────────────────────────
内置对话历史管理，自动渲染气泡式对话

┌──────────────────────────────────┐
│  用户：北京天气怎么样？           │
│  助手：北京今天晴天，22°C……       │
│  用户：上海呢？                   │
│  助手：上海今天多云，28°C……       │
├──────────────────────────────────┤
│  [输入框]              [发送]     │
└──────────────────────────────────┘
```

**如何选择**：

| 场景 | 推荐 |
|------|------|
| 单次文本处理（摘要、翻译、抽取） | `gr.Interface` |
| 多轮对话助手（聊天机器人） | `gr.ChatInterface` |
| 需要展示额外信息（工具调用链） | `gr.Blocks`（自定义布局） |

### 2.3 常用组件速查

```python
import gradio as gr

# 文本类
gr.Textbox(label="输入", placeholder="请输入内容", lines=3)
gr.Markdown("## 标题")         # 富文本展示
gr.Code(language="python")    # 代码高亮展示

# 交互类
gr.Button("提交")
gr.Slider(minimum=0, maximum=1, step=0.1, label="Temperature", value=0.7)
gr.Dropdown(choices=["选项A", "选项B"], label="选择")

# 对话类
gr.Chatbot(height=400)         # 聊天气泡展示区域，独立使用时
gr.ChatInterface(fn=chat_fn)   # 完整聊天界面（自带 Chatbot + 输入框 + 按钮）

# 状态（跨请求保持数据）
gr.State(value=[])             # 存储 Python 对象（如对话历史列表）
```

---

## 三、接入 LLM 的关键技巧

### 3.1 流式输出（Streaming）

没有流式输出时，用户需要等待模型完整回答生成后才看到内容；有流式输出时，文字逐字出现，体验更好。

**Gradio 流式输出**：在函数里用 `yield` 逐步返回内容：

```python
def chat_stream(message, history):
    messages = build_messages(history, message)
    
    # 开启流式模式
    stream = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        stream=True,         # 关键：开启流式
        temperature=0.7,
    )
    
    partial = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            partial += delta
            yield partial   # 每次 yield 都会更新界面显示
```

`gr.ChatInterface` 自动检测函数是否是生成器（有 `yield`），有则开启流式模式，无则等待完整结果。

**流式输出的两种模式对比**：

```
非流式（return）：
  [等待 2 秒]  →  完整回答突然出现

流式（yield）：
  文字逐渐出现，像打字机一样
  → 用户感知的等待时间更短
  → 适合回答较长的场景
```

### 3.2 在聊天界面展示工具调用链

工具调用链如果只是写进 logging，UI 上看不到。可以用以下两种方式展示：

**方式 A：追加到聊天消息里（简单）**

把工具调用过程作为助手消息的一部分，用特殊格式展示：

```python
def chat_with_tools(message, history, state):
    wf_history = state or []
    
    # 在回答前构建"调用链摘要"
    result, wf_history = run_workflow_step(message, wf_history)
    
    # 如果有工具调用，在回答前加上调用链说明
    if result.steps:
        chain_text = "\n".join([f"🔧 `{s.name}` → {s.result.get('summary', '...')}"
                                for s in result.steps])
        full_answer = f"**工具调用链：**\n{chain_text}\n\n---\n\n{result.final_answer}"
    else:
        full_answer = result.final_answer
    
    # 注意：此处 return 返回完整字符串，最终答案为非流式输出。
    # 多步工作流的中间调用（工具选择、工具执行）无法流式推送，
    # 只有最后一次生成可以改为 yield 逐字推送——见实践任务第 3 条。
    return full_answer, wf_history
```

**方式 B：用 `gr.Blocks` 添加独立展示区（专业）**

```
┌──────────────────────┬──────────────────────┐
│                      │  工具调用链            │
│   聊天区域            │  🔧 get_weather        │
│                      │    城市：上海           │
│                      │    结果：28°C，多云     │
│                      │                      │
│                      │  🔧 get_exchange_rate  │
│                      │    500 USD = 3622 CNY │
│                      │                      │
├──────────────────────┴──────────────────────┤
│  [输入框]                        [发送]      │
└─────────────────────────────────────────────┘
```

### 3.3 状态管理：跨轮保持对话历史

Gradio 每次请求都是无状态的（HTTP 请求），需要用 `gr.State` 在用户 Session 内持久化数据：

```python
with gr.Blocks() as demo:
    # 对话历史：每个用户独立的 State
    wf_messages = gr.State(value=None)   # 存储工作流的 messages 列表

    chatbot = gr.Chatbot()
    msg_input = gr.Textbox(placeholder="输入你的问题...")
    
    def respond(user_msg, chat_history, messages_state):
        # messages_state 是跨轮持久化的工作流历史
        result, updated_messages = do_chat(user_msg, messages_state)
        
        # 更新聊天显示历史
        chat_history.append({"role": "user", "content": user_msg})
        chat_history.append({"role": "assistant", "content": result.final_answer})
        
        return "", chat_history, updated_messages
    
    msg_input.submit(respond, [msg_input, chatbot, wf_messages],
                     [msg_input, chatbot, wf_messages])
```

---

## 四、完整 Demo：带工具调用链的出行规划助手

### 4.1 界面设计

```
┌─────────────────────────────────────────────────────────┐
│  🌍 出行规划助手（工具调用 Demo）                           │
├──────────────────────────┬──────────────────────────────┤
│  💬 对话区域               │  🔧 工具调用链                 │
│                          │  ─────────────────────────  │
│  用户：去上海出差，         │  第 1 次问题                   │
│    带500美元够吗？          │  ✓ get_weather(上海)          │
│                          │    28°C，多云，建议穿薄外套     │
│  助手：根据查询结果……       │  ✓ get_exchange_rate          │
│                          │    500 USD = 3622.5 CNY       │
│                          │  ─────────────────────────  │
│                          │  第 2 次问题                   │
│                          │  （无工具调用）                 │
├──────────────────────────┴──────────────────────────────┤
│  [输入你的出行问题...]                        [发送]       │
└─────────────────────────────────────────────────────────┘
```

### 4.2 完整实现

```python
import gradio as gr
import json
import os
import time
from dataclasses import dataclass, field
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")

# ── 工具定义（复用 Day 25）────────────────────────────────────────────────────

def get_weather(city: str, unit: str = "celsius") -> dict:
    mock = {
        "北京": {"temp": 22, "condition": "晴", "wind": "东北风 3 级"},
        "上海": {"temp": 28, "condition": "多云", "wind": "东南风 2 级"},
        "广州": {"temp": 33, "condition": "阵雨", "wind": "南风 4 级"},
        "成都": {"temp": 19, "condition": "阴", "wind": "微风"},
        "哈尔滨": {"temp": 8, "condition": "小雨", "wind": "北风 5 级"},
    }
    if city not in mock:
        return {"error": True, "message": f"暂无 '{city}' 的天气数据"}
    d = mock[city]
    temp = d["temp"] if unit == "celsius" else round(d["temp"] * 9 / 5 + 32, 1)
    unit_str = "°C" if unit == "celsius" else "°F"
    wear = ("短袖" if d["temp"] >= 28 else "薄外套" if d["temp"] >= 18 else
            "厚外套" if d["temp"] >= 10 else "羽绒服")
    return {"city": city, "temperature": temp, "unit": unit_str,
            "condition": d["condition"], "wind": d["wind"],
            "summary": f"{city}现在{d['condition']}，{temp}{unit_str}，{d['wind']}，建议穿{wear}"}


def get_exchange_rate(from_currency: str, to_currency: str, amount: float = None) -> dict:
    rates = {("CNY", "USD"): 0.138, ("USD", "CNY"): 7.245,
             ("CNY", "EUR"): 0.128, ("EUR", "CNY"): 7.85,
             ("USD", "JPY"): 151.2, ("JPY", "USD"): 0.0066,
             ("CNY", "JPY"): 20.3, ("JPY", "CNY"): 0.049}
    f, t = from_currency.upper(), to_currency.upper()
    if f == t:
        rate = 1.0
    else:
        rate = rates.get((f, t))
        if rate is None:
            return {"error": True, "message": f"不支持 {f}→{t} 汇率"}
    result = {"from": f, "to": t, "rate": rate}
    if amount is not None:
        converted = round(amount * rate, 2)
        result.update({"amount": amount, "converted": converted,
                       "summary": f"{amount} {f} = {converted} {t}"})
    else:
        result["summary"] = f"1 {f} = {rate} {t}"
    return result


TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "获取指定城市的当前天气，包括温度、天气状况和着装建议。",
        "parameters": {"type": "object",
                       "properties": {"city": {"type": "string"},
                                      "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
                       "required": ["city"]},
    }},
    {"type": "function", "function": {
        "name": "get_exchange_rate",
        "description": "获取货币实时汇率，可选传入金额换算。支持 CNY/USD/EUR/JPY。",
        "parameters": {"type": "object",
                       "properties": {"from_currency": {"type": "string"},
                                      "to_currency": {"type": "string"},
                                      "amount": {"type": "number"}},
                       "required": ["from_currency", "to_currency"]},
    }},
]

TOOL_REGISTRY = {"get_weather": get_weather, "get_exchange_rate": get_exchange_rate}

SYSTEM_PROMPT = (
    "你是一个智能出行规划助手，可以查询实时天气和货币汇率。"
    "当用户询问天气或货币换算时，优先调用工具获取实时数据，然后给出具体建议。"
)

# ── 多步工作流（复用 Day 25 逻辑）──────────────────────────────────────────────

@dataclass
class ToolStep:
    name: str
    args: dict
    result: dict

@dataclass
class WorkflowResult:
    final_answer: str = ""
    steps: list = field(default_factory=list)


def run_workflow(user_input: str, messages: list, max_iter: int = 5) -> tuple[WorkflowResult, list]:
    """执行多步工作流，返回结果和更新后的消息历史。"""
    wf = WorkflowResult()
    messages = messages + [{"role": "user", "content": user_input}]
    
    for _ in range(max_iter):
        msg = client.chat.completions.create(
            model="deepseek-chat", messages=messages,
            tools=TOOLS, tool_choice="auto", temperature=0,
        ).choices[0].message
        
        if not msg.tool_calls:
            wf.final_answer = msg.content
            messages.append({"role": "assistant", "content": msg.content})
            break
        
        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = TOOL_REGISTRY.get(name, lambda **_: {"error": True, "message": "未知工具"})(**args)
            wf.steps.append(ToolStep(name=name, args=args, result=result))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    else:
        final = client.chat.completions.create(
            model="deepseek-chat", messages=messages, temperature=0,
        )
        wf.final_answer = final.choices[0].message.content
        messages.append({"role": "assistant", "content": wf.final_answer})
    
    return wf, messages


def format_chain(steps: list[ToolStep]) -> str:
    """把工具调用链格式化为 Markdown 展示。"""
    if not steps:
        return "_（本次无工具调用，直接回答）_"
    lines = []
    for i, s in enumerate(steps, 1):
        summary = s.result.get("summary") or s.result.get("message") or str(s.result)[:60]
        icon = "❌" if s.result.get("error") else "✅"
        lines.append(f"**{i}. {icon} `{s.name}`**")
        lines.append(f"   - 参数：`{json.dumps(s.args, ensure_ascii=False)}`")
        lines.append(f"   - 结果：{summary}")
    return "\n".join(lines)


# ── Gradio 界面 ───────────────────────────────────────────────────────────────

def respond(user_msg: str, chat_history: list, messages_state: list, chain_state: str):
    if not user_msg.strip():
        return "", chat_history, messages_state, chain_state
    
    # 初始化工作流消息历史
    if not messages_state:
        messages_state = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 执行多步工作流
    result, updated_messages = run_workflow(user_msg, messages_state)
    
    # 更新聊天显示
    chat_history.append({"role": "user", "content": user_msg})
    chat_history.append({"role": "assistant", "content": result.final_answer})
    
    # 格式化调用链
    chain_md = f"### 第 {len(chat_history) // 2} 次问答\n\n{format_chain(result.steps)}"
    new_chain = (chain_state or "") + "\n\n---\n\n" + chain_md
    
    return "", chat_history, updated_messages, new_chain


def clear_all():
    return [], None, ""


with gr.Blocks(title="出行规划助手 Demo", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌍 出行规划助手\n基于 DeepSeek + Tool Calling 的多步工作流 Demo（Day 26）")
    
    messages_state = gr.State(value=None)
    chain_state = gr.State(value="")
    
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="对话",
                height=450,
                type="messages",
                bubble_full_width=False,
            )
            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="问我天气或货币汇率相关问题，如：去上海出差，带500美元够吗？",
                    label="",
                    scale=5,
                )
                send_btn = gr.Button("发送", variant="primary", scale=1)
        
        with gr.Column(scale=2):
            chain_display = gr.Markdown(
                label="🔧 工具调用链",
                value="_等待第一次问答..._",
                height=450,
            )
    
    with gr.Row():
        clear_btn = gr.Button("清空对话", variant="secondary")
        gr.Markdown("**提示**：可以问天气（北京/上海/广州/成都/哈尔滨）或汇率（CNY/USD/EUR/JPY）")
    
    # 绑定事件
    inputs = [msg_input, chatbot, messages_state, chain_state]
    outputs = [msg_input, chatbot, messages_state, chain_state]
    
    msg_input.submit(respond, inputs, outputs)
    send_btn.click(respond, inputs, outputs)
    clear_btn.click(clear_all, [], [chatbot, messages_state, chain_state])
    
    # 同步 chain_state 到显示组件
    chain_state.change(lambda x: x, chain_state, chain_display)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",   # 局域网可访问
        server_port=7860,
        share=False,             # True 时生成临时公网链接（需要联网）
    )
```

---

## 五、Day 26 知识速查

### Gradio 关键参数速查

| 场景 | 用法 |
|------|------|
| 最快聊天界面 | `gr.ChatInterface(fn=chat_fn).launch()` |
| 流式输出 | 函数用 `yield partial_text` 替代 `return text` |
| 跨轮状态 | `gr.State(value=initial)` + 作为参数传入函数 |
| 自定义布局 | `with gr.Blocks(): with gr.Row(): with gr.Column():` |
| 多输出组件 | 函数返回元组，outputs 是列表 |
| 公网分享 | `demo.launch(share=True)` |
| 局域网访问 | `demo.launch(server_name="0.0.0.0")` |

### 最小 Gradio 聊天界面（含流式）

```python
import gradio as gr

def chat_stream(message, history):
    messages = [{"role": "system", "content": "你是助手"}]
    messages += history
    messages.append({"role": "user", "content": message})
    
    stream = client.chat.completions.create(
        model="deepseek-chat", messages=messages, stream=True,
    )
    partial = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            partial += chunk.choices[0].delta.content
            yield partial

gr.ChatInterface(
    fn=chat_stream,
    title="LLM 聊天",
    type="messages",   # 使用 OpenAI 消息格式
).launch()
```

### 常见报错排查

| 报错 | 原因 | 解决方法 |
|------|------|---------|
| `Port 7860 is already in use` | 上次进程未关闭 | `demo.launch(server_port=7861)` |
| `TypeError: chat() missing argument` | 函数签名与 inputs 不匹配 | 检查 inputs/outputs 列表和函数参数数量 |
| `State` 不更新 | 忘记把新值通过 outputs 返回 | 函数必须 return 新的 state 值 |
| 工具链不显示 | `chain_state.change` 没绑定 | 添加 `chain_state.change(lambda x: x, chain_state, chain_display)` |
| 流式输出停顿 | `yield` 时机太少 | 每个 chunk 都 `yield`，不要攒满后再 yield |

---

## 六、实践任务

- [ ] 安装 gradio：`pip install gradio`，运行最小聊天示例（15 行代码版），确认浏览器可访问
- [ ] 跑通完整 Demo（`python day26_simple_ui.py`），测试天气 + 汇率查询，观察右侧工具调用链实时更新
- [ ] 添加流式输出：把 `run_workflow` 的最终 `final_answer` 改为流式传输给前端，让文字逐步出现
- [ ] 测试 `demo.launch(share=True)`（需要联网），体验 Gradio 生成的临时公网链接，把链接发给一个朋友测试
- [ ] 修改界面布局：在底部添加一个 `gr.Dropdown` 供用户选择要查询的城市，预填充到输入框
- [ ] 体验 Streamlit：用 `pip install streamlit`，用 `st.chat_message` + `st.chat_input` 复现相同功能，感受两个框架的差异

**产出标准**：

- `day26_simple_ui.py` 可运行，浏览器 `http://localhost:7860` 可访问
- 界面上能看到聊天内容和右侧工具调用链
- 能用自己的话解释"Gradio State 的作用是什么，不用它会发生什么"

---

## 七、下一步预告

**Day 27：整合成一个完整作品**

Day 22–26 分别完成了工具定义（Day 23）、单工具调用（Day 24）、多步工作流（Day 25）、Web 界面（Day 26）。Day 27 是**整合日**——把这些零散 Demo 整合成一个有清晰结构、可展示、可分享的完整项目：

- **项目结构规范化**：统一目录结构（`tools/`、`core/`、`app.py`、`requirements.txt`、`README.md`）
- **三选一题目方向**：本地文档问答助手 / 企业知识库客服助手 / 通用工具助理
- **README 工程化**：项目描述 + 功能截图 + 快速启动指南（让别人能在 5 分钟内跑起来）
- **关键工程细节**：`.env.example`、`requirements.txt` 版本锁定、异常提示友好化

Day 27 的产出：一个结构清晰、可以直接放到 GitHub 展示的完整项目，面试或个人作品集时的核心展示内容。
