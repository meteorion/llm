# Day 40：跨对话长期记忆

> 学习目标：理解短期上下文（当前会话 messages）与长期记忆（跨会话持久化）的分层设计；实现一个"记住用户偏好"的记忆模块，验证程序重启后模型仍能使用之前记住的偏好；了解向量存储记忆和 mem0 的分层设计思路，掌握防止记忆无限增长的常见策略
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 40
>
> 🧭 导航：[← Day 39 · 开发一个最小 MCP Server](day39_minimal_mcp_server.md) → [Day 41 · 多 Agent 协作模式](day41_multi_agent_collaboration.md)

---

## 目录

- [一、为什么需要长期记忆：短期上下文的局限](#一为什么需要长期记忆短期上下文的局限)
  - [1.1 现在的"记忆"是什么样的](#11-现在的记忆是什么样的)
  - [1.2 用户体验问题](#12-用户体验问题)
- [二、记忆分层设计](#二记忆分层设计)
  - [2.1 三层记忆结构](#21-三层记忆结构)
  - [2.2 长期记忆的三类内容](#22-长期记忆的三类内容)
- [三、最简实现：JSON 文件存储用户偏好](#三最简实现json-文件存储用户偏好)
  - [3.1 记忆读写模块](#31-记忆读写模块)
  - [3.2 记忆工具：让模型能主动写入记忆](#32-记忆工具让模型能主动写入记忆)
  - [3.3 把记忆注入 System Prompt](#33-把记忆注入-system-prompt)
  - [3.4 完整 Agent 骨架](#34-完整-agent-骨架)
- [四、进阶：向量存储记忆](#四进阶向量存储记忆)
  - [4.1 为什么 KV 存储不够](#41-为什么-kv-存储不够)
  - [4.2 向量化记忆的写入与检索](#42-向量化记忆的写入与检索)
- [五、记忆增长控制：防止无限膨胀](#五记忆增长控制防止无限膨胀)
  - [5.1 记忆去重与更新（覆盖旧偏好）](#51-记忆去重与更新覆盖旧偏好)
  - [5.2 摘要压缩（对话历史合并）](#52-摘要压缩对话历史合并)
  - [5.3 LRU 淘汰（条数上限）](#53-lru-淘汰条数上限)
- [六、mem0 参考实现](#六mem0-参考实现)
  - [6.1 mem0 的三个核心接口](#61-mem0-的三个核心接口)
  - [6.2 mem0 的分层设计思路](#62-mem0-的分层设计思路)
  - [6.3 何时引入 mem0，何时手写](#63-何时引入-mem0何时手写)
- [七、扩展：作为 MCP 工具暴露记忆能力](#七扩展作为-mcp-工具暴露记忆能力)
- [八、Day 40 知识速查](#八day-40-知识速查)
- [九、实践任务](#九实践任务)
- [十、下一步预告](#十下一步预告)

---

## 一、为什么需要长期记忆：短期上下文的局限

### 1.1 现在的"记忆"是什么样的

Day 4 的多轮对话、Day 33-36 的 LangGraph Agent，"记忆"都是同一件事：把当前会话的 `messages` 列表传给模型，模型靠读历史消息来"记住"上文。

这是**短期上下文记忆**——它只存在于当前进程的内存里，程序重启即消失。

```python
# 当前的"记忆"：存在内存里的消息列表
messages = [
    {"role": "user", "content": "我在北京"},
    {"role": "assistant", "content": "好的，我记住了"},
    {"role": "user", "content": "天气怎么样？"},  # 模型知道"北京"因为上面有历史
]
# ↑ 进程重启后 messages = []，"我在北京"消失
```

### 1.2 用户体验问题

短期记忆带来两个用户体验问题：

**问题 1：每次重启都要重复说偏好**
- 用户第一次："我常用的城市是北京，货币对是 USD→CNY"
- 程序重启后，用户再问："天气怎么样？"——模型不知道是哪个城市，还得重新问

**问题 2：上下文窗口有限**
- 长会话里历史消息越来越多，最终超出上下文窗口，早期的"我在北京"被截断丢失
- 即使没超窗口，把几十轮历史全传给模型也浪费 Token

**长期记忆解决的问题**：把用户告诉过模型的偏好、事实持久化到外部存储（文件 / 数据库 / 向量库），每次会话开始时加载，让模型"记得"之前的对话，不受进程重启影响。

---

## 二、记忆分层设计

### 2.1 三层记忆结构

```
┌─────────────────────────────────────────────────────┐
│  Layer 1：工作记忆（Working Memory）                  │
│  = 当前会话的 messages 列表                           │
│  存储：Python 进程内存                                │
│  生命周期：当前会话结束即消失                           │
│  容量：受上下文窗口限制（通常 8k–128k tokens）          │
├─────────────────────────────────────────────────────┤
│  Layer 2：情节记忆（Episodic Memory）                 │
│  = 历史会话的摘要 / 关键事件                           │
│  存储：文件 / 数据库（持久化）                          │
│  生命周期：长期保留，可定期清理                          │
│  容量：压缩后注入 System Prompt，保持在 1-2k tokens     │
├─────────────────────────────────────────────────────┤
│  Layer 3：语义记忆（Semantic Memory）                 │
│  = 用户偏好、常用事实、技能偏好                          │
│  存储：KV 文件 / 向量数据库（持久化）                   │
│  生命周期：永久保留，可按用户更新                        │
│  容量：按需检索，不全量注入                              │
└─────────────────────────────────────────────────────┘
```

今天的实践聚焦 **Layer 3（语义记忆）**：用户偏好的持久化，这是最容易实现、收益最直观的部分。

### 2.2 长期记忆的三类内容

| 类型 | 例子 | 存储结构 | 检索方式 |
|-----|------|---------|---------|
| **用户偏好** | "常用城市：北京"、"货币对：USD→CNY" | KV 对（key: 偏好名, value: 值） | 全量注入 / 按 key 查找 |
| **事实** | "用户名叫小明"、"职业是产品经理" | KV 对 或 向量化条目 | 全量注入 / 语义检索 |
| **历史摘要** | "上周讨论过北京的旅行计划" | 自由文本 + 时间戳 | 语义检索 |

---

## 三、最简实现：JSON 文件存储用户偏好

### 3.1 记忆读写模块

```python
# memory.py
import json
from pathlib import Path

MEMORY_FILE = Path("user_memory.json")


def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return {}
    return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))


def save_memory(memories: dict) -> None:
    MEMORY_FILE.write_text(
        json.dumps(memories, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def set_preference(key: str, value: str) -> None:
    memories = load_memory()
    memories[key] = value
    save_memory(memories)


def get_preference(key: str) -> str | None:
    return load_memory().get(key)


def get_all_preferences() -> dict:
    return load_memory()
```

`user_memory.json` 的格式（程序重启后持久存在）：

```json
{
  "常用城市": "北京",
  "货币对": "USD→CNY",
  "用户名": "小明"
}
```

### 3.2 记忆工具：让模型能主动写入记忆

光有读写函数还不够——需要把记忆操作做成**工具**，让模型在对话中判断何时该"记住"某件事，并主动调用工具写入：

```python
# tools/memory_tools.py
from memory import set_preference, get_preference, get_all_preferences


def remember_preference(key: str, value: str) -> str:
    """
    记住用户的偏好或常用信息，供未来会话使用。
    
    当用户告诉你"我常用的城市是 X"、"我习惯用 Y 货币"、"我叫 Z"等个人信息时调用。
    key 是信息的类别（如"常用城市"、"用户名"），value 是具体内容。
    """
    set_preference(key, value)
    return f"已记住：{key} = {value}（下次重启后依然有效）"


def recall_preference(key: str) -> str:
    """
    查询之前记住的用户偏好。
    
    当你不确定是否记住过某项信息时调用，避免重复询问用户。
    """
    value = get_preference(key)
    if value is None:
        return f"没有关于「{key}」的记忆"
    return f"{key}：{value}"
```

**Prompt 引导是关键**：工具再好，模型也不会自动知道"何时该记"。System Prompt 里要明确告诉模型记忆写入的时机：

```
当用户提到个人偏好（如"我在北京"、"我常用美元"、"我叫小明"）时，
立即调用 remember_preference 工具记下来，不要等用户要求。
下次用户问相关问题时，优先用已记住的偏好，不要重复询问。
```

### 3.3 把记忆注入 System Prompt

每次会话开始时，从文件加载所有记忆，拼入 System Prompt，让模型在对话一开始就"知道"用户的偏好：

```python
BASE_SYSTEM_PROMPT = """你是一个天气和汇率助手。你有两个工具：
- get_weather(city)：查询城市天气
- get_exchange_rate(from_currency, to_currency)：查询汇率

当用户提到个人偏好（如常用城市、货币对、用户名）时，立即调用
remember_preference 工具记下来。下次使用已记住的偏好，不重复询问。"""


def build_system_prompt() -> str:
    preferences = get_all_preferences()
    if not preferences:
        return BASE_SYSTEM_PROMPT
    
    pref_lines = "\n".join(f"- {k}：{v}" for k, v in preferences.items())
    return f"""{BASE_SYSTEM_PROMPT}

【已知用户偏好（无需重复询问）】
{pref_lines}"""
```

### 3.4 完整 Agent 骨架

```python
# agent.py
from openai import OpenAI
from memory import get_all_preferences
from tools.weather_tools import get_weather, get_exchange_rate
from tools.memory_tools import remember_preference, recall_preference

client = OpenAI(api_key="...", base_url="https://api.deepseek.com")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_preference",
            "description": "记住用户的偏好或常用信息，如常用城市、货币对",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "信息类别，如'常用城市'"},
                    "value": {"type": "string", "description": "具体内容"},
                },
                "required": ["key", "value"],
            },
        },
    },
    # ... get_exchange_rate, recall_preference 同理
]

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "get_exchange_rate": get_exchange_rate,
    "remember_preference": remember_preference,
    "recall_preference": recall_preference,
}


def chat(user_input: str, history: list) -> tuple[str, list]:
    # 每轮对话用最新记忆重建 system prompt
    system_prompt = build_system_prompt()
    messages = [{"role": "system", "content": system_prompt}] + history
    messages.append({"role": "user", "content": user_input})

    while True:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
        )
        msg = response.choices[0].message
        messages.append(msg)

        if response.choices[0].finish_reason == "tool_calls":
            for tc in msg.tool_calls:
                import json
                args = json.loads(tc.function.arguments)
                result = TOOL_REGISTRY[tc.function.name](**args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                })
        else:
            # 只把 user/assistant 消息返回给调用方保存到 history
            history = [m for m in messages[1:] if isinstance(m, dict)]
            return msg.content, history
```

**跨会话验证流程**：

```
会话 1：
  用户：我常用的城市是北京
  模型：[调用 remember_preference("常用城市", "北京")]
       好的，已记住北京。
  （写入 user_memory.json: {"常用城市": "北京"}）

--- 程序重启 ---

会话 2：
  build_system_prompt() 读到 {"常用城市": "北京"}，注入 System Prompt
  用户：今天天气怎么样？
  模型：[调用 get_weather("北京")]  ← 没有问"哪个城市"
       北京：晴，22°C，湿度 45%
```

---

## 四、进阶：向量存储记忆

### 4.1 为什么 KV 存储不够

JSON 文件的 KV 存储适合**结构化偏好**（key 固定、数量少）。当记忆条数多了、内容自由（用户说过的任意一句话），按 key 检索就不够用了：

- 用户说过"喜欢喝拿铁"，后来说"给我推荐个下午可以去的地方"
- KV 里没有"喜欢喝拿铁"这个 key，也不知道该查什么
- 需要**语义检索**：把"下午去哪里"和"喜欢咖啡"关联起来

向量存储记忆的做法：把每条记忆 Embedding 向量化，检索时把当前问题也向量化，找最相似的记忆条目注入上下文。

### 4.2 向量化记忆的写入与检索

```python
# 伪代码，说明思路（实际用 Chroma / FAISS 等向量库）
import numpy as np
from embedding_model import embed  # Day 18 的 Embedding 方法

class VectorMemory:
    def __init__(self):
        self.entries = []       # [(text, vector), ...]
    
    def add(self, text: str) -> None:
        vector = embed(text)
        self.entries.append((text, vector))
    
    def search(self, query: str, top_k: int = 3) -> list[str]:
        if not self.entries:
            return []
        query_vec = embed(query)
        # 余弦相似度排序
        scores = [
            cosine_similarity(query_vec, vec)
            for _, vec in self.entries
        ]
        top_indices = np.argsort(scores)[-top_k:][::-1]
        return [self.entries[i][0] for i in top_indices]

# 使用
memory = VectorMemory()
memory.add("用户喜欢喝拿铁")
memory.add("用户在北京工作")
memory.add("用户对价格敏感，偏好实惠选择")

relevant = memory.search("下午去哪里坐坐")
# → ["用户喜欢喝拿铁", "用户在北京工作"]  （和价格关系弱，排后面）
```

**KV 存储 vs 向量存储的选型**：

| | KV 存储（JSON 文件） | 向量存储 |
|--|--|--|
| **适合内容** | 结构化偏好（城市/货币对/用户名） | 自由文本（任意说过的话） |
| **检索方式** | 按 key 精确查找 | 语义相似度检索 |
| **实现复杂度** | 极简（标准库即可） | 需要 Embedding 模型 + 向量库 |
| **注入方式** | 全量注入 System Prompt | 按相关性 top-k 注入 |

对于"用户偏好"这个具体场景，KV 存储完全够用——只有当记忆条数超过几十条、内容是自由文本时，才需要向量存储。

---

## 五、记忆增长控制：防止无限膨胀

长期记忆如果不加控制，会无限增长，最终注入的记忆超过上下文窗口，或者充斥大量陈旧无用信息。三种常用控制策略：

### 5.1 记忆去重与更新（覆盖旧偏好）

同一个 key 的新值覆盖旧值——用户说"我搬到上海了"，`常用城市` 从`北京`变成`上海`，不是追加一条：

```python
def set_preference(key: str, value: str) -> None:
    memories = load_memory()
    memories[key] = value   # dict 赋值天然覆盖，无需额外判断
    save_memory(memories)
```

这是 KV 存储的天然优势：不会产生重复条目。

### 5.2 摘要压缩（对话历史合并）

对于 Layer 2（情节记忆，即历史对话摘要），定期用模型把多条旧摘要合并成一条：

```python
def compress_memory_if_needed(summaries: list[str], max_entries: int = 10) -> list[str]:
    if len(summaries) <= max_entries:
        return summaries
    
    # 把最旧的 N 条合并成一条
    to_compress = summaries[:max_entries // 2]
    compressed = llm_summarize("\n".join(to_compress))
    return [compressed] + summaries[max_entries // 2:]
```

### 5.3 LRU 淘汰（条数上限）

为记忆条目加时间戳，超过上限时淘汰最久未被访问的：

```python
import time

def set_preference_with_lru(key: str, value: str, max_entries: int = 50) -> None:
    memories = load_memory()  # 返回 {key: {"value": v, "last_used": ts}}
    memories[key] = {"value": value, "last_used": time.time()}
    
    if len(memories) > max_entries:
        # 按 last_used 升序排，淘汰最旧的
        oldest_key = min(memories, key=lambda k: memories[k]["last_used"])
        del memories[oldest_key]
    
    save_memory(memories)
```

对于"用户偏好"这个场景，LRU 通常不必要（偏好条数不多）。**摘要压缩是最有用的策略**，主要针对 Layer 2（历史对话摘要）。

---

## 六、mem0 参考实现

### 6.1 mem0 的三个核心接口

[mem0](https://github.com/mem0ai/mem0) 是一个轻量级 LLM 记忆框架，核心接口极简：

```python
from mem0 import Memory

m = Memory()

# add：把一段对话或文本加入记忆（自动提取关键信息、向量化存储）
m.add("用户更喜欢简洁的回答，不喜欢长段落", user_id="user_001")

# search：语义检索相关记忆（返回 top-k 条）
results = m.search("用户对输出格式的偏好", user_id="user_001")
# → [{"memory": "用户更喜欢简洁的回答...", "score": 0.92}]

# update：更新特定记忆条目
m.update(memory_id="...", data="用户更喜欢带代码示例的回答")
```

`add` 内部会调用 LLM 提取对话里的关键信息（而不是把整段文本存进去），再向量化写入向量数据库——这是它和"直接存消息文本"的核心区别。

### 6.2 mem0 的分层设计思路

```
用户输入对话
    │
    ▼
LLM 提取关键信息
（"用户在北京" → "location: Beijing"）
    │
    ▼
向量化 + 写入向量数据库
（每条记忆独立存储）
    │
    ▼ 检索时
语义检索（query → top-k 记忆）
    │
    ▼
注入 System Prompt
```

mem0 解决了手写方案里最繁琐的部分：**从自由文本对话里自动提取结构化记忆**。手写方案里这一步需要模型主动调用 `remember_preference` 工具——如果模型判断失误，偏好就没被记住。mem0 在 `add` 时自动做这件事，更可靠。

### 6.3 何时引入 mem0，何时手写

| 场景 | 推荐方案 |
|-----|---------|
| 用户偏好条数少（< 20 条）、内容结构化 | 手写 KV JSON 存储（今天的方案） |
| 记忆条目多、内容自由文本、需要语义检索 | 向量存储（Chroma + 自写） |
| 需要自动从对话中提取记忆、多用户隔离 | mem0 |
| 生产环境、团队使用、需要记忆管理 UI | mem0 或商业方案 |

---

## 七、扩展：作为 MCP 工具暴露记忆能力

Day 39 的 MCP Server 是个好的扩展点——可以在 `weather_mcp_server.py` 里直接加上记忆工具，让任何连接这个 Server 的 MCP Client 都能使用记忆能力：

```python
# 在 weather_mcp_server.py 里追加

from memory import set_preference, get_preference, get_all_preferences

@mcp.tool()
def save_user_preference(key: str, value: str) -> str:
    """
    记住用户的偏好，如常用城市、货币对、姓名等，供未来会话使用。
    当用户提及个人习惯或偏好时主动调用，无需等用户要求。
    key: 偏好类别（如"常用城市"），value: 具体内容（如"北京"）
    """
    set_preference(key, value)
    return f"已记住：{key} = {value}"

@mcp.tool()
def get_user_preference(key: str) -> str:
    """
    查询之前记住的用户偏好。不确定是否记住某项信息时调用，避免重复询问。
    """
    value = get_preference(key)
    return f"{key}：{value}" if value else f"没有关于「{key}」的记忆"

@mcp.tool()
def list_all_preferences() -> str:
    """
    列出所有已记住的用户偏好。
    """
    prefs = get_all_preferences()
    if not prefs:
        return "目前没有保存任何用户偏好"
    return "\n".join(f"- {k}：{v}" for k, v in prefs.items())
```

把记忆做成 MCP 工具的好处：Claude Code 或其他 MCP Client 连接后，记忆能力不需要任何额外配置就自动可用，记忆文件在 Server 进程的工作目录里持久存储。

---

## 八、Day 40 知识速查

### 三层记忆结构速查

```
工作记忆   → 当前 messages 列表，进程内存，重启即消失
情节记忆   → 历史对话摘要，文件持久化，定期压缩
语义记忆   → 用户偏好/事实，KV 文件或向量库，长期保留
```

### 记忆注入 System Prompt 的模式

```python
def build_system_prompt() -> str:
    prefs = get_all_preferences()
    if not prefs:
        return BASE_PROMPT
    pref_text = "\n".join(f"- {k}：{v}" for k, v in prefs.items())
    return f"{BASE_PROMPT}\n\n【已知用户偏好】\n{pref_text}"
```

### 让模型主动写入记忆的两种方式

| 方式 | 原理 | 可靠性 |
|-----|------|-------|
| **记忆工具 + Prompt 引导** | 模型判断何时调用 `remember_preference` | 依赖模型判断，偶发遗漏 |
| **mem0 自动提取** | `m.add(conversation)` 自动从对话里提取 | 更可靠，但引入外部依赖 |

### 防止记忆无限增长

```
KV 偏好   → dict 赋值天然覆盖，无需额外处理
对话摘要  → 超过 N 条时用 LLM 合并压缩
向量记忆  → 超过 N 条时 LRU 淘汰最旧条目
```

---

## 九、实践任务

- [ ] 实现 `memory.py` 模块（见第三节），用 Python 交互式终端验证 `set_preference` / `get_preference` / `load_memory` 的读写行为，确认 `user_memory.json` 正确生成和更新
- [ ] 把 `remember_preference` 和 `recall_preference` 加为工具，配合 `build_system_prompt()`，实现"会话 1 记住北京 → 重启程序 → 会话 2 直接查北京天气"的完整跨会话验证
- [ ] 对比验证：把 System Prompt 里的已知偏好块注释掉，重启后问"天气怎么样"——模型应该重新询问城市，确认记忆注入是否生效
- [ ] 扩展：把记忆工具加到 Day 39 的 MCP Server 里（见第七节），重启 Claude Code 验证 Claude 能通过对话记住你的偏好并在下次用到

**产出标准**：两次重启实验日志——重启前"天气怎么样"→ 模型答"哪个城市"；重启后（记忆注入生效）"天气怎么样"→ 模型直接查已知城市，不再询问。

---

## 十、下一步预告

Day 41 进入**多 Agent 协作模式**：Planner + Executor + Critic 三角色分工——Planner 拆任务、Executor 逐个执行、Critic 检查结果是否满足原始要求。今天实现的记忆模块是 Executor Agent 的天然扩展——Executor 执行任务时可以把结果摘要写进记忆，Critic 检查失败时可以把"这种失败原因"也写进记忆，让 Planner 下次避开同样的坑。Day 41 还会引入 A2A 协议的设计思路，讨论如果三个角色是独立服务，A2A 的 Task 生命周期状态机如何解决今天 Demo 里的工程问题。
