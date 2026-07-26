# Day 7：第 1 周复盘

> 学习目标：系统梳理 Day 1–6 的核心知识点，深度理解三个基础问题（Token/成本/Temperature/多轮对话），整理并打磨本周做出的三个 Demo
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 7
>
> 🧭 导航：[← Day 6 · 信息抽取工具](day06_info_extractor.md) → Day 8 · 结构化输出（待更新）

---

## 目录

- [一、本周全景回顾](#一本周全景回顾)
  - [1.1 Day 1–6 知识地图](#11-day-16-知识地图)
  - [1.2 本周三个 Demo 概览](#12-本周三个-demo-概览)
- [二、深度复盘三大问题](#二深度复盘三大问题)
  - [2.1 Token 为什么和成本有关](#21-token-为什么和成本有关)
  - [2.2 Temperature 为什么会影响输出](#22-temperature-为什么会影响输出)
  - [2.3 为什么多轮对话必须传历史消息](#23-为什么多轮对话必须传历史消息)
- [三、三个 Demo 整理与横向对比](#三三个-demo-整理与横向对比)
  - [3.1 CLI 聊天 Demo](#31-cli-聊天-demo)
  - [3.2 文章摘要器](#32-文章摘要器)
  - [3.3 信息抽取工具](#33-信息抽取工具)
  - [3.4 三个 Demo 设计差异对比](#34-三个-demo-设计差异对比)
- [四、第 1 周完整代码骨架](#四第-1-周完整代码骨架)
- [五、Day 7 知识速查](#五day-7-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、本周全景回顾

### 1.1 Day 1–6 知识地图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       第 1 周知识地图（Day 1–6）                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Day 1 · 全景认知                                                        │
│  ─────────────────────────────────────────────────────────────          │
│  LLM 定义 → Transformer 原理 → Prompt/Token/上下文窗口                   │
│  → Embedding → RAG → Tool Calling                                       │
│                           │                                              │
│                           ↓                                              │
│  Day 2 · Python 基础                                                     │
│  ─────────────────────────────────────────────────────────────          │
│  虚拟环境 → 列表/字典/函数/类 → 文件读写 → 异常处理                        │
│                           │                                              │
│                           ↓                                              │
│  Day 3 · API 调用                                                        │
│  ─────────────────────────────────────────────────────────────          │
│  HTTP 请求 → API Key 管理(.env) → SDK 调用 → LLM 客户端封装              │
│                           │                                              │
│                           ↓                                              │
│  Day 4 · 多轮对话                                                        │
│  ─────────────────────────────────────────────────────────────          │
│  system/user/assistant 角色 → 消息历史管理 → 上下文截断 → CLI 聊天 Demo  │
│                           │                                              │
│                           ↓                                              │
│  Day 5 · Prompt 工程                                                     │
│  ─────────────────────────────────────────────────────────────          │
│  任务约束四维度 → 长度控制(软/硬) → 多风格摘要器 → Prompt 版本对比         │
│                           │                                              │
│                           ↓                                              │
│  Day 6 · 结构化抽取                                                      │
│  ─────────────────────────────────────────────────────────────          │
│  JSON 格式约束 → 字段定义规范 → 多场景抽取 → 稳定性提升（Few-shot/校验）  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

这六天构成了**应用开发的最小闭环**：

- 知道模型是什么（Day 1）
- 能写 Python 脚本（Day 2）
- 能调通 API（Day 3）
- 能做多轮对话（Day 4）
- 能写可控 Prompt（Day 5）
- 能输出结构化结果（Day 6）

### 1.2 本周三个 Demo 概览

| Demo | 核心技术 | 输入 | 输出 |
|------|---------|------|------|
| CLI 聊天 | 多轮消息历史 + 角色管理 | 用户连续输入 | 模型多轮回复 |
| 文章摘要器 | Prompt 约束 + 长度控制 | 一段文章文本 | 指定风格/长度的摘要 |
| 信息抽取工具 | JSON 格式约束 + 字段定义 | 非结构化文本 | 稳定的 JSON 字段 |

---

## 二、深度复盘三大问题

### 2.1 Token 为什么和成本有关

**Token 是计费单位**，不是"一个请求一个价格"。理解这一点需要从 Tokenizer 说起。

#### Token 是什么

大模型不处理原始字符，而是先用 Tokenizer 把文本切分为 Token 序列，再在 Token 序列上做计算。Token 的粒度介于字符和单词之间。

```
┌─────────────────────────────────────────────────────────────┐
│                   Tokenizer 切分示例                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  英文："Hello, world!"                                       │
│  Token: ["Hello", ",", " world", "!"]  → 4 tokens           │
│                                                              │
│  中文："你好，世界"                                           │
│  Token: ["你", "好", "，", "世", "界"]  → 约 5 tokens        │
│  （中文通常 1–2 字 = 1 token，取决于模型词表）                 │
│                                                              │
│  代码："def hello():"                                        │
│  Token: ["def", " hello", "():", ]  → 3–4 tokens            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### 成本计算方式

API 费用 = **输入 Token 数 × 输入单价** + **输出 Token 数 × 输出单价**

```python
# 实际成本估算示例（以 DeepSeek 为例，价格仅供参考）
input_tokens  = 500
output_tokens = 200
input_price   = 0.001  # 元/千 token
output_price  = 0.002  # 元/千 token

cost = (input_tokens / 1000) * input_price + (output_tokens / 1000) * output_price
# cost = 0.0005 + 0.0004 = 0.0009 元 ≈ 不到 1 分钱
```

#### 哪里最容易浪费 Token

```
┌────────────────────────────────────────────────────────────────────┐
│                     Token 消耗的四个来源                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ① system prompt    ─── 每次请求都重复计费，越长越贵                 │
│  ② 历史消息          ─── 多轮对话累积，到后期可能占大半输入            │
│  ③ 用户输入          ─── 用户控制，不易压缩                           │
│  ④ 模型输出          ─── 通常比输入单价贵；max_tokens 是上限，不是定值  │
│                                                                     │
│  优化策略：                                                          │
│  - system prompt 精简，去掉冗余说明                                  │
│  - 历史消息定期截断或摘要压缩                                         │
│  - 输入文档先预处理（去空行、去重、去无关段落）                         │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

**关键结论**：Token 和成本挂钩，是因为生成每一个 Token 都需要 GPU 算力，按量计费最公平。输出 Token 比输入贵（计算量更大），长历史 + 长输出 = 成本主要来源。

---

### 2.2 Temperature 为什么会影响输出

Temperature 不是一个神秘的"创意旋钮"，它直接作用于 Softmax 函数的数学计算。

#### 生成下一个 Token 的过程

模型每次只预测**下一个 Token**的概率分布，然后按概率采样：

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Temperature 的数学作用                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  原始 logits（模型打分）:  [天: 3.0,  日: 1.2,  气: 0.5,  情: 0.1]   │
│                                                                      │
│  Softmax(logits / T)：                                               │
│                                                                      │
│  T = 0.1（极低）→  [天: 0.999, 日: 0.001, 气: ≈0, 情: ≈0]           │
│  T = 1.0（默认）→  [天: 0.75,  日: 0.17,  气: 0.06, 情: 0.02]       │
│  T = 2.0（极高）→  [天: 0.45,  日: 0.30,  气: 0.17, 情: 0.08]       │
│                                                                      │
│  T → 0：概率集中在最高分 Token → 输出确定（每次一样）                  │
│  T → ∞：概率趋于均匀 → 输出完全随机                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 实际效果对比

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

prompt = "用一句话描述 Python"

for t in [0.0, 0.7, 1.5]:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=t
    )
    print(f"T={t}: {response.choices[0].message.content}")
```

#### 场景选择速查

| Temperature | 特性 | 典型场景 |
|-------------|------|---------|
| 0.0 | 完全确定，可重复 | 信息抽取、代码生成、格式化输出 |
| 0.1–0.3 | 高度确定，极少偏差 | 文章摘要、事实问答、分类任务 |
| 0.5–0.7 | 平衡准确与多样 | 日常对话、写作辅助、翻译 |
| 1.0 | 明显随机，多样性强 | 内容创作、营销文案 |
| ≥ 1.5 | 高度随机，有时离题 | 头脑风暴、角色扮演（需要人工筛选） |

**关键结论**：Temperature 不是"质量"控制器，而是"确定性"控制器。低 Temperature 适合需要稳定输出的任务，高 Temperature 适合需要多样性的任务。

---

### 2.3 为什么多轮对话必须传历史消息

这是最容易误解的一点：**大模型本身是无状态的**。

#### 无状态模型的本质

```
┌─────────────────────────────────────────────────────────────────────┐
│                   有记忆 vs 无记忆 的直觉差异                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ✗ 错误认知：模型像一个真人，记得每次对话                               │
│                                                                      │
│  用户：我叫张伟                  ← 第 1 次请求                         │
│  模型：你好，张伟！                                                    │
│                                                                      │
│  用户：我叫什么名字？             ← 第 2 次请求（独立发出，不带历史）     │
│  模型：你没有告诉我你的名字...    ← 模型"失忆"了                        │
│                                                                      │
│  ─────────────────────────────────────────────────────────          │
│                                                                      │
│  ✓ 正确做法：每次请求都带完整历史                                       │
│                                                                      │
│  messages = [                                                        │
│    {"role": "user",      "content": "我叫张伟"},                     │
│    {"role": "assistant", "content": "你好，张伟！"},                 │
│    {"role": "user",      "content": "我叫什么名字？"},               │  ← 当前输入
│  ]                                                                   │
│  → 模型回复：你叫张伟。                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 为什么 API 设计成无状态

1. **水平扩展**：无状态服务可以随时增减机器，每台机器处理任何请求
2. **成本合理**：计费精确到 Token，服务方无需维护每个用户的会话状态
3. **灵活性**：应用层可以自由裁剪历史（截断、摘要、过滤），而不是被 API 绑架

#### 历史消息管理的核心规则

```python
class ConversationManager:
    def __init__(self, system_prompt: str):
        self.messages = [{"role": "system", "content": system_prompt}]

    def chat(self, client, user_input: str) -> str:
        # 1. 追加用户消息
        self.messages.append({"role": "user", "content": user_input})

        # 2. 携带完整历史调用 API
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=self.messages
        )
        reply = response.choices[0].message.content

        # 3. 追加模型回复 ← 不能遗漏，否则模型不知道它上一轮说了什么
        self.messages.append({"role": "assistant", "content": reply})

        return reply

    def truncate(self, max_turns: int = 10):
        system = self.messages[:1]
        others = self.messages[1:]
        self.messages = system + others[-(max_turns * 2):]
```

**关键结论**：历史消息是对话的"外部记忆"，模型本身没有记忆，需要应用层维护。每轮都要追加 user + assistant 两条消息，缺一不可。截断时必须保留 system 消息。

---

## 三、三个 Demo 整理与横向对比

### 3.1 CLI 聊天 Demo

**核心设计**：无限输入循环 + 完整历史维护 + 特殊命令处理。

```python
import os
from openai import OpenAI

def run_chat():
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )
    messages = [{"role": "system", "content": "你是一个有帮助的助手。"}]

    print("聊天开始（/quit 退出，/clear 清空历史）")
    while True:
        user_input = input("\n你：").strip()
        if not user_input:
            continue
        if user_input == "/quit":
            break
        if user_input == "/clear":
            messages = [messages[0]]
            print("历史已清空")
            continue

        messages.append({"role": "user", "content": user_input})
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True
        )

        print("助手：", end="", flush=True)
        reply = ""
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                reply += content
                print(content, end="", flush=True)
        print()

        messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    run_chat()
```

**关键点**：
- `stream=True` 逐 token 打印，用户体验更好
- `/clear` 只清空对话历史，保留 `messages[0]`（system 消息）
- `reply` 在所有 chunk 收完后才追加到历史

---

### 3.2 文章摘要器

**核心设计**：任务约束 Prompt + 多风格输出。

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

PROMPTS = {
    "brief": "用不超过 50 字，提炼以下文章的核心结论。只输出摘要，不要说明文字。\n\n{text}",
    "bullets": "从以下文章中提取 3 个关键要点，用编号列表输出，每条不超过 20 字。\n\n{text}",
    "structured": (
        "从以下文章中提取信息，输出 JSON，格式：\n"
        "{\"title\": \"主题\", \"summary\": \"100字以内摘要\", \"keywords\": [\"关键词\"]}\n"
        "只输出 JSON，不要 markdown 代码块。\n\n{text}"
    ),
}

def summarize(text: str, style: str = "brief") -> str:
    prompt = PROMPTS[style].format(text=text)
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    article = "人工智能正在改变各行各业..."
    for style in PROMPTS:
        print(f"\n【{style}】")
        print(summarize(article, style))
```

**关键点**：
- `temperature=0.1`：摘要需要稳定输出，不需要随机性
- `max_tokens=500`：软约束（Prompt 层）+ 硬截断（API 层）配合
- 不同风格用字典管理，扩展只需增加 key

---

### 3.3 信息抽取工具

**核心设计**：字段参数化 + 双重 JSON 约束 + 缺失字段兜底。

```python
import os
import json
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

def extract(text: str, fields: dict) -> dict:
    field_lines = "\n".join(f"- {k}: {v}" for k, v in fields.items())
    prompt = (
        f"从以下文本中抽取信息，以 JSON 格式输出。\n\n"
        f"字段定义：\n{field_lines}\n\n"
        "规则：只提取原文中明确出现的信息；找不到的字段返回 null；"
        "直接输出 JSON 对象，不要说明文字。\n\n"
        f"文本：\n{text}"
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    data = json.loads(response.choices[0].message.content)
    for key in fields:
        data.setdefault(key, None)
    return data

if __name__ == "__main__":
    resume = "张伟，28 岁，曾在字节跳动工作 3 年，擅长 Python 和 Go，邮箱 wei@example.com"
    fields = {
        "name": "姓名（字符串）",
        "age": "年龄（整数）",
        "company": "最近工作公司（字符串）",
        "skills": "技能列表（字符串数组）",
        "email": "邮箱（字符串）",
    }
    result = extract(resume, fields)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

**关键点**：
- `temperature=0.0`：抽取任务要求完全确定性
- `response_format={"type": "json_object"}`：API 层强制 JSON
- `data.setdefault(key, None)`：保证所有预期字段都存在

---

### 3.4 三个 Demo 设计差异对比

```
┌─────────────────┬──────────────┬──────────────┬──────────────────┐
│ 维度            │ CLI 聊天     │ 文章摘要器   │ 信息抽取工具     │
├─────────────────┼──────────────┼──────────────┼──────────────────┤
│ 输入模式        │ 交互式多轮   │ 单次批量     │ 单次批量         │
│ 输出格式        │ 自然语言     │ 自然语言     │ 结构化 JSON      │
│ 消息历史        │ 必须维护     │ 不需要       │ 不需要           │
│ Temperature     │ 0.7          │ 0.1          │ 0.0              │
│ max_tokens      │ 不限         │ 500 (兜底)   │ 不限             │
│ response_format │ 不用         │ 不用         │ json_object      │
│ 核心 Prompt 技术│ system 角色  │ 四维度约束   │ 字段定义 + 规则  │
│ 主要风险        │ Token 超限   │ 软约束失效   │ 格式污染/推断    │
└─────────────────┴──────────────┴──────────────┴──────────────────┘
```

这三个 Demo 其实是**递进的**：聊天是最基础的 API 调用；摘要在输出内容上加了 Prompt 约束；抽取在输出格式上加了结构化约束。第 2 周的任务是在这个基础上继续强化：**结构化输出（Day 8）→ 输出校验（Day 9）→ 分类器（Day 10）→ Prompt 优化（Day 11）**。

---

## 四、第 1 周完整代码骨架

把本周核心代码整合成一个最小可用的"工具箱"：

```python
"""
week1_toolkit.py — 第 1 周成果汇总
包含：聊天 / 摘要 / 抽取 三大功能
"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)


# ── 功能 1：多轮聊天 ─────────────────────────────────────────────────────
class ChatSession:
    def __init__(self, system: str = "你是一个有帮助的助手。"):
        self.messages = [{"role": "system", "content": system}]

    def send(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=self.messages,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def clear(self):
        self.messages = self.messages[:1]


# ── 功能 2：文章摘要 ─────────────────────────────────────────────────────
SUMMARY_STYLES = {
    "brief":  "用不超过 50 字提炼核心结论。只输出摘要。\n\n{text}",
    "bullets": "提取 3 个关键要点，编号列表，每条不超过 20 字。\n\n{text}",
}

def summarize(text: str, style: str = "brief") -> str:
    prompt = SUMMARY_STYLES[style].format(text=text)
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500,
    )
    return response.choices[0].message.content


# ── 功能 3：信息抽取 ─────────────────────────────────────────────────────
def extract(text: str, fields: dict) -> dict:
    field_lines = "\n".join(f"- {k}: {v}" for k, v in fields.items())
    prompt = (
        f"从以下文本中抽取信息，以 JSON 格式输出。\n\n字段：\n{field_lines}\n\n"
        "只提取原文信息，找不到返回 null，只输出 JSON。\n\n"
        f"文本：\n{text}"
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    for key in fields:
        data.setdefault(key, None)
    return data


# ── 演示入口 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 演示聊天
    session = ChatSession()
    print(session.send("你好，我叫张伟"))
    print(session.send("我叫什么名字？"))

    # 演示摘要
    article = "大模型应用开发是近年最热的方向之一，核心是通过 API 调用预训练模型来完成各种任务……"
    print(summarize(article, "bullets"))

    # 演示抽取
    resume = "李明，26 岁，前端工程师，会 Vue 和 React，邮箱 li@example.com"
    result = extract(resume, {
        "name": "姓名（字符串）",
        "age": "年龄（整数）",
        "skills": "技能（字符串数组）",
        "email": "邮箱（字符串）",
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

---

## 五、Day 7 知识速查

### 第 1 周核心公式

| 公式 | 解释 |
|------|------|
| API 费用 = 输入 Token × 输入价 + 输出 Token × 输出价 | Token 是计费最小单位 |
| Softmax(logits / T) | Temperature 通过缩放 logits 控制分布 |
| messages = system + 历史轮次 + 当前输入 | 无状态模型的"记忆"完全在 messages 里 |

### 三个关键参数速查

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `temperature` | 1.0 | 0=确定，>1=随机；抽取用 0，摘要用 0.1，聊天用 0.7 |
| `max_tokens` | 无限制 | 输出 Token 上限，不影响输入；建议摘要设 300–500 兜底 |
| `stream` | False | True 时逐 Token 推送；聊天程序体验更好 |

### 本周三 Demo 最小模板

```
聊天：维护 messages 列表 → 追加 user → API 调用 → 追加 assistant → 循环
摘要：构建 Prompt（任务+约束+文本）→ temperature=0.1 → 直接输出
抽取：构建 Prompt（字段定义+规则+文本）→ temperature=0 + json_object → 解析 + 补全
```

---

## 六、实践任务

- [ ] 用自己的话回答三大问题：Token/成本、Temperature、多轮历史（不看笔记作答）
- [ ] 把本周三个 Demo 整合进 `week1_toolkit.py`，确保都可运行
- [ ] 对 CLI 聊天 Demo 测试：连续对话 5 轮，确认模型记住了前面的内容
- [ ] 对摘要器测试：同一篇文章分别用 temperature=0 和 temperature=1 各运行 3 次，对比输出稳定性
- [ ] 对抽取器测试：故意输入缺少某些字段的文本，确认输出中缺失字段为 `null` 而不是 `KeyError`

**产出标准**：

- 三个 Demo 均可从命令行运行并产出预期输出
- 一份不超过 500 字的周总结（回答路线图中的三大复盘问题）

---

## 七、下一步预告

**Day 8：结构化输出**（第 2 周开始）

Day 6 的信息抽取已经用了 JSON 约束，但还比较"朴素"——只靠 Prompt 和 `response_format` 来约束格式。Day 8 会更系统地学习结构化输出：

- 如何用 JSON Schema 精确描述字段类型和必填规则
- Pydantic 模型与 LLM 输出的集成
- 如何在大规模场景下批量保证输出格式一致

核心问题：当抽取结果要入库、要被前端 API 消费时，"大概像 JSON"不够用，需要字段类型和结构都可验证的输出。
