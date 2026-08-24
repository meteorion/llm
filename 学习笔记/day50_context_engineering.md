# Day 50：上下文工程（Context Engineering）

> 学习目标：理解上下文窗口是 LLM 应用的稀缺资源，不是"往里塞越多越好"；掌握分区组装策略（固定顺序 + 每分区 Token 预算 + 超限裁剪规则），让每次请求的上下文既完整又不浪费
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 50
>
> 🧭 导航：[← Day 49 · 限流与配额：应用层实现](day49_rate_limiting.md) → Day 51（待更新）

---

## 目录

- [一、上下文工程 ≠ Prompt 工程](#一上下文工程--prompt-工程)
  - [1.1 从"写好 Prompt"到"管好上下文"](#11-从写好-prompt-到管好上下文)
  - [1.2 上下文窗口的稀缺性](#12-上下文窗口的稀缺性)
- [二、上下文的五类组成部分](#二上下文的五类组成部分)
  - [2.1 各分区的内容与特性](#21-各分区的内容与特性)
  - [2.2 为什么需要固定顺序](#22-为什么需要固定顺序)
- [三、分区 Token 预算设计](#三分区-token-预算设计)
  - [3.1 Token 估算](#31-token-估算)
  - [3.2 预算分配策略](#32-预算分配策略)
- [四、超限时的裁剪规则](#四超限时的裁剪规则)
  - [4.1 裁剪优先级](#41-裁剪优先级)
  - [4.2 历史消息裁剪策略](#42-历史消息裁剪策略)
  - [4.3 RAG 结果裁剪策略](#43-rag-结果裁剪策略)
- [五、ContextBuilder 实现](#五-contextbuilder-实现)
  - [5.1 核心数据结构](#51-核心数据结构)
  - [5.2 组装逻辑](#52-组装逻辑)
  - [5.3 与网关层集成](#53-与网关层集成)
- [六、上下文质量的常见问题](#六上下文质量的常见问题)
- [七、Day 50 知识速查](#七day-50-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、上下文工程 ≠ Prompt 工程

### 1.1 从"写好 Prompt"到"管好上下文"

**Prompt 工程**关注"怎么写 System Prompt"，是一次性的文本设计问题。

**上下文工程（Context Engineering）**关注"每次请求的上下文窗口里装什么、装多少、怎么裁剪"，是一个动态的资源分配问题。

| | Prompt 工程 | 上下文工程 |
|--|-----------|----------|
| **核心问题** | 怎么写出好的指令 | 每次请求往窗口里装什么 |
| **时间维度** | 一次性设计 | 每次请求都要计算 |
| **输入变量** | 静态（一次写好） | 动态（RAG 结果/历史/工具返回都在变） |
| **约束** | 表达清晰 | Token 预算有限，超限直接报错 |

一个 System Prompt 写得再好，如果上下文窗口被无关历史消息塞满、RAG 检索到的内容和问题不匹配，模型仍然会给出糟糕的输出。

### 1.2 上下文窗口的稀缺性

主流模型的上下文窗口（以 Token 计）：

| 模型 | 上下文窗口 | 输入成本 |
|-----|-----------|---------|
| GPT-4o | 128k | 高 |
| Claude 3.5 Sonnet | 200k | 中高 |
| DeepSeek-V3 | 128k | 低 |
| GPT-4o-mini | 128k | 低 |

**窗口大不代表可以随便用**：
- 长上下文的"Lost in the Middle"效应：模型对位于中间的内容关注度下降，关键信息放在开头或结尾更容易被利用
- 输入 Token 直接计费，塞满没有价值的内容 = 烧钱
- 超出窗口会直接报错，不是"截断后继续"

---

## 二、上下文的五类组成部分

### 2.1 各分区的内容与特性

每次向模型发请求时，上下文由以下五类内容组成：

| 分区 | 内容 | 动态/静态 | 可裁剪性 |
|-----|------|---------|---------|
| **① System Prompt** | 角色定义、行为规则、输出格式要求 | 静态（每次一样） | 不可裁剪 |
| **② RAG 检索结果** | 从知识库检索到的相关文档片段 | 动态（随查询变化） | 可按相关度裁剪 |
| **③ 工具返回结果** | 已执行工具的返回内容（天气、搜索结果等） | 动态（随工具调用变化） | 可摘要压缩 |
| **④ 对话历史** | 之前的 user/assistant 消息轮次 | 动态（随对话增长） | 可按轮次或摘要裁剪 |
| **⑤ 当前用户消息** | 本次用户输入 | 动态（每轮不同） | 不可裁剪 |

### 2.2 为什么需要固定顺序

固定分区顺序不是偏好，而是有具体原因：

```
System Prompt（最前）
  → 模型在开始处理时就建立"角色框架"，后续内容都在这个框架里解读

RAG 检索结果（紧跟 System Prompt）
  → 作为"参考资料"，在历史对话之前呈现，避免被历史消息淹没

工具返回结果（RAG 之后）
  → 任务上下文，模型需要在看到历史对话之前先了解"当前掌握的事实"

对话历史（倒数第二）
  → 提供对话语境，但历史越老越不重要，放在后面便于裁剪

当前用户消息（最后）
  → 最接近生成位置，"Lost in the Middle"效应对最后内容影响最小
```

---

## 三、分区 Token 预算设计

### 3.1 Token 估算

精确计算 Token 需要使用 tokenizer（如 `tiktoken`），但应用层常用近似估算：

```python
def estimate_tokens(text: str) -> int:
    """粗略估算：英文约 4 字符/token，中文约 1.5 字符/token"""
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)

def messages_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4  # role + 格式化 overhead
    return total + 2  # 对话起始符
```

**精确计算**（需要 `tiktoken`）：

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))
```

### 3.2 预算分配策略

假设模型上下文窗口 = 128k Token，预留输出 = 4k：

```
可用输入预算 = 128k - 4k = 124k Token

典型分配比例：
  ① System Prompt：固定，通常 500–2000 Token（不压缩）
  ② RAG 检索结果：最多 40k Token（约 30%）
  ③ 工具返回结果：最多 10k Token（约 8%）
  ④ 对话历史：最多 60k Token（约 48%）
  ⑤ 当前消息：剩余 Token（保留，不裁剪）
```

**实际使用滚动预算**：先分配①⑤（固定/不可裁），剩余预算按优先级分配给②③④。

```python
@dataclass
class ContextBudget:
    total_tokens: int = 120_000       # 上下文可用总预算
    system_prompt_reserve: int = 2_000
    current_message_reserve: int = 1_000
    rag_max: int = 40_000
    tools_max: int = 10_000
    history_max: int = 60_000

    @property
    def dynamic_budget(self) -> int:
        return self.total_tokens - self.system_prompt_reserve - self.current_message_reserve
```

---

## 四、超限时的裁剪规则

### 4.1 裁剪优先级

当动态内容超出预算时，按以下顺序裁剪（越靠前越先被削减）：

```
1. 对话历史（最老的轮次先删）  ← 最先裁剪
2. RAG 检索结果（相关度低的先删）
3. 工具返回结果（非关键字段先删）
4. 对话历史摘要替换（删掉原始历史，替换为压缩摘要）
5. RAG 结果摘要替换

绝不裁剪：System Prompt、当前用户消息
```

**判断依据**：历史消息越老越不重要；RAG 文档相关度越低越可以丢弃；工具结果通常较短，优先尝试字段级压缩而非整体删除。

### 4.2 历史消息裁剪策略

```python
def trim_history(
    history: list[dict],
    max_tokens: int,
    token_fn=estimate_tokens,
) -> list[dict]:
    """从最老的消息开始丢弃，保留最近的对话"""
    result = list(history)
    while result and messages_tokens(result) > max_tokens:
        # 成对删除（保证 user/assistant 配对完整）
        if len(result) >= 2:
            result = result[2:]   # 删掉最老的 user + assistant 一轮
        else:
            result = result[1:]   # 只剩一条时直接删
    return result

def summarize_history(
    history: list[dict],
    max_tokens: int,
    llm_call,
) -> list[dict]:
    """超出预算时，将旧历史压缩为一条摘要消息"""
    if messages_tokens(history) <= max_tokens:
        return history

    # 取前半段做摘要，保留后半段原样
    midpoint = len(history) // 2
    to_summarize = history[:midpoint]
    to_keep = history[midpoint:]

    summary_text = llm_call(
        messages=[
            {"role": "system", "content": "用 3-5 句话总结以下对话的核心信息，保留关键事实和决策。"},
            {"role": "user", "content": str(to_summarize)},
        ]
    )
    summary_msg = {"role": "system", "content": f"[早期对话摘要] {summary_text}"}
    return [summary_msg] + to_keep
```

### 4.3 RAG 结果裁剪策略

```python
def trim_rag_results(
    docs: list[dict],   # 每个 doc: {"content": str, "score": float}
    max_tokens: int,
    token_fn=estimate_tokens,
) -> list[dict]:
    """按相关度从高到低保留，超出预算的文档直接丢弃"""
    # 先按相关度排序（score 越高越相关）
    sorted_docs = sorted(docs, key=lambda d: d["score"], reverse=True)
    result = []
    used = 0
    for doc in sorted_docs:
        doc_tokens = token_fn(doc["content"])
        if used + doc_tokens > max_tokens:
            break   # 后续文档相关度更低，直接停止
        result.append(doc)
        used += doc_tokens
    return result
```

---

## 五、ContextBuilder 实现

### 5.1 核心数据结构

```python
# context/types.py
from dataclasses import dataclass, field

@dataclass
class ContextInput:
    system_prompt: str
    current_message: str
    history: list[dict] = field(default_factory=list)
    rag_docs: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    user_id: str = ""

@dataclass
class BuiltContext:
    messages: list[dict]
    token_estimate: int
    dropped_history_turns: int    # 丢弃了多少轮历史
    dropped_rag_docs: int         # 丢弃了多少篇文档
    used_history_summary: bool    # 是否使用了历史摘要
```

### 5.2 组装逻辑

```python
# context/builder.py
from .types import ContextInput, BuiltContext, ContextBudget

class ContextBuilder:
    def __init__(self, budget: ContextBudget | None = None):
        self.budget = budget or ContextBudget()

    def build(self, ctx: ContextInput) -> BuiltContext:
        # ① System Prompt（不裁剪）
        system_content = ctx.system_prompt

        # ② RAG 检索结果（按预算裁剪）
        original_rag_count = len(ctx.rag_docs)
        trimmed_rag = trim_rag_results(ctx.rag_docs, self.budget.rag_max)
        if trimmed_rag:
            rag_block = "\n\n".join(
                f"[参考文档 {i+1}]\n{doc['content']}"
                for i, doc in enumerate(trimmed_rag)
            )
            system_content += f"\n\n## 参考资料\n{rag_block}"

        # ③ 工具返回结果
        if ctx.tool_results:
            tool_block = "\n".join(
                f"[{r['tool']}] {r['result']}" for r in ctx.tool_results
            )
            system_content += f"\n\n## 当前已知信息\n{tool_block}"

        # ④ 对话历史（按剩余预算裁剪）
        original_history_len = len(ctx.history)
        trimmed_history = trim_history(ctx.history, self.budget.history_max)

        # ⑤ 拼接最终 messages
        messages = [{"role": "system", "content": system_content}]
        messages.extend(trimmed_history)
        messages.append({"role": "user", "content": ctx.current_message})

        token_est = messages_tokens(messages)
        return BuiltContext(
            messages=messages,
            token_estimate=token_est,
            dropped_history_turns=(original_history_len - len(trimmed_history)) // 2,
            dropped_rag_docs=original_rag_count - len(trimmed_rag),
            used_history_summary=False,
        )
```

### 5.3 与网关层集成

```python
# 在 gateway/gateway.py 的 complete() 中，接入 ContextBuilder
from context.builder import ContextBuilder
from context.types import ContextInput

builder = ContextBuilder()

class ModelGateway:
    def complete_with_context(
        self,
        system_prompt: str,
        current_message: str,
        history: list[dict] = None,
        rag_docs: list[dict] = None,
        tool_results: list[dict] = None,
        user_id: str = "",
        user_tier: str = "free",
    ) -> GatewayResponse:
        # 限流检查（Day 49）
        rl = rate_limiter.check(user_id or "anonymous", user_tier)
        if not rl.allowed:
            return GatewayResponse(status="rate_limited", error=...)

        # 上下文组装（Day 50）
        ctx_input = ContextInput(
            system_prompt=system_prompt,
            current_message=current_message,
            history=history or [],
            rag_docs=rag_docs or [],
            tool_results=tool_results or [],
        )
        built = builder.build(ctx_input)

        # 路由（Day 47）+ 网关调用（Day 48）
        req = GatewayRequest(messages=built.messages, user_id=user_id)
        resp = self.complete(req)

        # 附加上下文元数据到响应
        resp.context_meta = {
            "token_estimate": built.token_estimate,
            "dropped_history_turns": built.dropped_history_turns,
            "dropped_rag_docs": built.dropped_rag_docs,
        }
        return resp
```

这样，Day 43–50 的各模块形成一条完整的处理链：

```
用户请求
  → [Day 49] 限流检查（是否允许请求通过）
  → [Day 50] 上下文组装（组装 messages，管理 Token 预算）
  → [Day 47] 模型路由（选择哪个档位的模型）
  → [Day 48] 网关调用（统一接口，切换 Provider）
  → [Day 43/44] 可观测性（记录 Trace、结构化日志）
  → [Day 45] 缓存（命中则直接返回，不调用 LLM）
模型响应
```

---

## 六、上下文质量的常见问题

| 问题 | 表现 | 根本原因 | 修复方向 |
|-----|------|---------|---------|
| **上下文爆炸** | 请求报 token limit 错误 | 历史或 RAG 无限增长，没有预算管理 | 加 `trim_history()` 和 `trim_rag_results()` |
| **Lost in the Middle** | 模型忽略了关键 RAG 文档 | 关键内容塞在历史消息中间 | 调整分区顺序，关键内容靠近头尾 |
| **历史泄露** | 多用户系统中历史错混 | 用 user_id 区分历史，但漏了隔离 | 每个 user_id 维护独立的历史队列 |
| **RAG 噪音** | 检索到的文档和问题无关 | 相关度阈值太低，什么都拿来放 | 设置最低相关度阈值（如 0.7）才放入上下文 |
| **工具结果过大** | 搜索/爬虫返回了几万字的原始内容 | 工具结果未经压缩直接塞入 | 工具层做摘要（前 N 段 / top-K 句子）再写入 |
| **System Prompt 重复** | 相同规则反复出现在 system 和 history 中 | System Prompt 没有和历史严格隔离 | System Prompt 只出现在 `role="system"` 的第一条 |

---

## 七、Day 50 知识速查

### 五分区组装顺序（记忆口诀）

```
系统（固定规则）→ 资料（RAG 文档）→ 事实（工具结果）→ 历史（对话记录）→ 当前（用户输入）
  ①                ②                  ③                  ④                  ⑤
不可裁             按相关度裁           按字段压缩           按时间裁            不可裁
```

### 裁剪优先级

```
最先裁剪 → 最老的历史轮次（先删一轮，再删一轮）
次要裁剪 → 相关度低的 RAG 文档（从低分到高分丢弃）
最后手段 → 历史摘要替换（把旧历史压缩成一条系统消息）
绝不裁剪 → System Prompt 和当前用户消息
```

### Token 预算配比（128k 窗口参考）

```
System Prompt：≤ 2k（静态，精炼不堆砌）
RAG 结果：    ≤ 40k（动态，按分数过滤）
工具结果：    ≤ 10k（动态，摘要后写入）
对话历史：    ≤ 60k（动态，老轮次先删）
当前消息：    剩余（保留，不裁剪）
输出预留：    ≥ 4k
```

---

## 八、实践任务

- [ ] 实现 `estimate_tokens()` 和 `messages_tokens()`；构造一段 100 轮的对话历史，验证 `trim_history()` 正确裁剪最老的轮次，且返回的消息数 × 平均 Token ≤ max_tokens
- [ ] 实现 `trim_rag_results()`；准备 10 篇相关度不同的文档（score 0.5–1.0），验证裁剪后保留的都是高分文档
- [ ] 实现 `ContextBuilder.build()`；构造一个超出预算的 `ContextInput`（历史 + RAG 都超限），验证 `BuiltContext.token_estimate ≤ budget.total_tokens`，`dropped_history_turns > 0`
- [ ] 把 `ContextBuilder` 接入 `ModelGateway.complete_with_context()`，打一次真实请求，在日志里观察 `context_meta` 里的 `token_estimate` 和 `dropped_*` 字段
- [ ] （进阶）给超出 RAG 预算的场景加历史摘要路径：当 `trim_history()` 删到只剩 4 轮仍超限时，调用 `summarize_history()` 替换

**产出标准**：无论 history / rag_docs 多长，`ContextBuilder.build()` 的输出 `token_estimate` 都不超过 `budget.total_tokens`；关键分区（system_prompt、current_message）永远完整保留；`dropped_*` 字段正确反映实际裁剪量。

---

## 九、下一步预告

Day 51 进入**状态管理（会话/任务状态的持久化与恢复设计）**：今天的上下文工程解决了"单次请求往窗口里装什么"，但 LLM 应用通常跨越多次请求——用户可能关掉页面再回来，Agent 任务可能运行几分钟。Day 51 要设计一套状态持久化方案：区分会话级状态（对话历史）和任务级状态（Agent 执行进度、工具结果缓存），让应用在任意时刻崩溃后都能从断点恢复，而不是重头再来。
