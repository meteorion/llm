# Day 19：把检索结果喂给模型回答

> 学习目标：掌握 RAG 问答生成阶段的核心技术——学会将检索到的 Chunk 拼接成有效的上下文 Prompt，用"只根据资料回答"约束防止模型脑补，实现无相关文档时的诚实拒答逻辑，完成 RAG 流程的"最后一公里"
>
> 📚 所属阶段：**第二阶段 · RAG 核心应用架构**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 19
>
> 🧭 导航：[← Day 18 · Embedding 与向量检索](day18_embedding_and_retrieval.md) [→ Day 20 · 给回答加引用](day20_answer_citation.md)

---

## 目录

- [一、上下文拼接策略](#一上下文拼接策略)
  - [1.1 上下文拼接的基本格式](#11-上下文拼接的基本格式)
  - [1.2 多个 Chunk 的排列策略](#12-多个-chunk-的排列策略)
  - [1.3 上下文长度控制与 Token 预算](#13-上下文长度控制与-token-预算)
- [二、"只根据资料回答"约束](#二只根据资料回答约束)
  - [2.1 为什么需要这个约束](#21-为什么需要这个约束)
  - [2.2 约束 Prompt 的写法与强度](#22-约束-prompt-的写法与强度)
  - [2.3 约束强度与回答完整性的权衡](#23-约束强度与回答完整性的权衡)
- [三、无相关文档时的拒答逻辑](#三无相关文档时的拒答逻辑)
  - [3.1 为什么拒答比猜测更有价值](#31-为什么拒答比猜测更有价值)
  - [3.2 拒答的两种实现路径](#32-拒答的两种实现路径)
- [四、完整实现：RAG 问答生成器](#四完整实现rag-问答生成器)
- [五、RAG Prompt 模板对比实验](#五rag-prompt-模板对比实验)
  - [5.1 三版 RAG Prompt 设计](#51-三版-rag-prompt-设计)
  - [5.2 回答质量对比](#52-回答质量对比)
- [六、Day 19 知识速查](#六day-19-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、上下文拼接策略

### 1.1 上下文拼接的基本格式

Day 18 完成了"根据问题找到相关 Chunk"，Day 19 要做的是把检索结果组织成 Prompt，送给模型生成最终答案。

```
RAG 问答 Prompt 的基本结构：

┌─────────────────────────────────────────────────────────────────────┐
│  System Prompt（角色 + 行为约束）                                      │
│  "你是一个文档问答助手，只根据提供的参考资料回答问题。"                     │
│                                                                      │
│  User Prompt（资料 + 问题）                                            │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  参考资料：                                                      │  │
│  │  [1] 退款政策：购买后 30 天内可申请全额退款。超过 30 天...          │  │
│  │  [2] 联系客服：工作日 9:00–18:00，电话 400-888-8888...          │  │
│  │  ...                                                           │  │
│  │                                                                │  │
│  │  问题：我昨天买的东西能退款吗？                                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         ↓
  模型根据 [1] 回答："根据退款政策，购买后 30 天内可申请全额退款..."
```

最简单的拼接实现：

```python
def build_rag_prompt(query: str, contexts: list[str]) -> str:
    context_block = "\n\n".join(
        f"[{i+1}] {ctx}" for i, ctx in enumerate(contexts)
    )
    return f"""参考资料：

{context_block}

问题：{query}

请根据以上参考资料回答问题。如果参考资料中没有相关信息，请明确说明无法回答。"""
```

### 1.2 多个 Chunk 的排列策略

检索返回多个 Chunk 时，排列顺序会影响模型的注意力分配：

```
"Lost in the Middle" 效应（斯坦福 2023 年研究）：

模型的注意力分布：
  开头 ████████████████████ （高注意力）
  中间 ████░░░░░░░░░░░░░░░░ （注意力下降）
  末尾 ████████████████     （注意力恢复）

实验结论：
  - 最相关的 Chunk 放在开头或末尾，回答质量更高
  - 放在中间的 Chunk 容易被模型"忽视"
  - Top-3 检索结果中，相关度最高的放末尾效果往往最好
```
    
排列策略对比：

| 策略 | 做法 | 适用场景 |
|------|------|---------|
| 相关度降序（默认） | score 最高的排第一 | 简单问答，Chunk 较少（≤3） |
| 相关度"三明治" | 最相关放末尾，其余按降序排前面 | 有明显的最佳命中 Chunk |
| 时间/逻辑顺序 | 按文档原始顺序，不按 score | 需要前后文连贯（如叙述性文档） |

```python
def sort_contexts_for_llm(results: list[dict], strategy: str = "descending") -> list[str]:
    if strategy == "descending":
        return [r["text"] for r in results]   # 已按 score 降序
    elif strategy == "sandwich":
        # 最相关的放最后（利用 "recency bias"）
        if len(results) <= 1:
            return [r["text"] for r in results]
        return [r["text"] for r in results[1:]] + [results[0]["text"]]
    elif strategy == "original":
        # 按元数据中的 chunk_idx 重排（保留原文顺序）
        return [r["text"] for r in sorted(results, key=lambda x: x["metadata"].get("chunk_idx", 0))]
    return [r["text"] for r in results]
```

### 1.3 上下文长度控制与 Token 预算

将检索结果放入 Prompt 时，需要控制总 Token 数不超过模型限制，同时给回答留出足够空间：

```
Token 预算分配示意：

Context 窗口（如 8192 Token）
├── System Prompt      ~200 Token   （约 2.5%）
├── 参考资料（Chunks）  ~2000 Token  （约 25%）
├── 用户问题           ~100 Token   （约 1%）
├── 回答空间           ~1500 Token  （约 18%）
└── 缓冲              保留余量

→ 合理的参考资料上限：Context 窗口的 25–40%
```

```python
def truncate_contexts_to_budget(
    contexts: list[str],
    max_context_chars: int = 3000,   # 粗估：1 中文字 ≈ 1.5 Token
) -> list[str]:
    selected, total = [], 0
    for ctx in contexts:
        if total + len(ctx) > max_context_chars:
            remaining = max_context_chars - total
            if remaining > 200:   # 剩余空间还够放有意义的内容
                selected.append(ctx[:remaining] + "...")
            break
        selected.append(ctx)
        total += len(ctx)
    return selected
```

---

## 二、"只根据资料回答"约束

### 2.1 为什么需要这个约束

大模型有一个根深蒂固的倾向：**当回答不确定时，宁愿给出"听起来合理"的答案，也不愿说"不知道"**——这就是幻觉。RAG 场景中，如果不加约束，模型会把检索到的资料和自己"知道"的知识混合使用：

```
场景：知识库里只有产品 A 的退款政策，没有产品 B 的任何信息

用户问题："产品 B 能退款吗？"
检索结果：[产品 A 的退款条款]（相似度 0.62，勉强超过阈值）

无约束的模型回答：
  "根据一般退款政策，您的产品 B 应该可以在 30 天内退款。"
  → 模型把资料 A 的内容混入了对 B 的"推断"，产生了幻觉

有约束的模型回答：
  "根据提供的资料，我只找到了产品 A 的退款政策。关于产品 B 的退款条款，
   资料中没有明确说明，建议直接联系客服确认。"
  → 诚实地反映了资料的局限性
```

### 2.2 约束 Prompt 的写法与强度

几种约束写法，强度从低到高：

```python
# 强度 1：温和建议（容易被模型忽视）
WEAK_CONSTRAINT = "请尽量根据参考资料回答。"

# 强度 2：明确要求（常用，效果较好）
MEDIUM_CONSTRAINT = """请只根据以下参考资料回答问题。
如果参考资料中没有足够信息，请说明"根据现有资料无法回答"。"""

# 强度 3：严格指令（适合精确性要求高的场景）
STRONG_CONSTRAINT = """你是文档问答助手，遵守以下规则：
1. 只能使用下方"参考资料"中的内容回答问题
2. 不得引入参考资料之外的知识或进行推断
3. 如果参考资料中找不到答案，必须回答："根据现有资料，无法回答该问题。"
4. 禁止使用"一般来说"、"通常"等暗示推断的措辞"""
```

**System Prompt vs User Prompt 的放置策略**：

```
约束指令放哪里？

System Prompt（推荐放置核心规则）：
  优点：整个对话都生效，模型把它当作"身份设定"的一部分，更难被覆盖
  缺点：占用 System Prompt 篇幅

User Prompt（每次请求时附带）：
  优点：可以针对每次请求微调约束强度
  缺点：模型对 User Prompt 末尾的指令响应更好，但中间的约束容易被"遗忘"

最佳实践：核心约束放 System，具体指令（如"参考以下资料"）放 User
```

### 2.3 约束强度与回答完整性的权衡

约束不是越强越好——过强会导致模型拒绝回答本可以回答的问题：

```
问题："DeepSeek 是什么公司的产品？"
知识库：全是关于退款政策的文档

强约束模型：
  "根据现有资料，无法回答该问题。" ← 正确的拒答

问题："如果我在 30 天内购买后发现商品损坏，可以退款吗？"
知识库：[退款政策：购买后 30 天内可申请全额退款]（资料里没有"损坏"这个词）

强约束模型：
  "根据现有资料，无法回答该问题。" ← 过于保守，实际上可以推理回答

最佳约束强度：
  允许根据资料进行合理推理，但明确区分"资料明确说明"和"基于资料推断"
```

---

## 三、无相关文档时的拒答逻辑

### 3.1 为什么拒答比猜测更有价值

```
RAG 系统的可信度来源于两个方面：
  1. 回答得准 —— 有资料时给出正确答案
  2. 知道边界 —— 没资料时诚实说不知道

用户更能接受的体验：
  "很抱歉，关于这个问题，我目前的知识库中没有相关信息。
   建议您联系客服获取最新答案。"
  ↑ 清晰、有帮助、不产生误导

用户无法接受的体验：
  "根据一般情况，您的问题答案是..."（然后说错了）
  ↑ 不如不答，会破坏对系统的信任
```

### 3.2 拒答的两种实现路径

**路径一：在检索层过滤（推荐）**

Day 18 的 `min_score` 阈值就是检索层拒答的实现：

```python
results = retriever.retrieve(query, top_k=3, min_score=0.6)

if not results:
    return "根据当前知识库，未找到与您问题相关的信息，无法回答。"

# 有结果才进入生成阶段
answer = generate_answer(query, results)
```

**路径二：让模型自判断（作为补充）**

即使检索到了 Chunk，模型本身也可能判断相关度不足：

```python
SYSTEM_PROMPT = """你是文档问答助手。
规则：
- 根据参考资料回答用户问题
- 如果参考资料与问题完全无关，回答："当前资料无法回答此问题，请联系客服。"
- 不得凭空捏造资料中未出现的信息"""

# 在 Prompt 末尾加"自检"指令
USER_PROMPT_SUFFIX = """
在回答前，请先判断参考资料是否真正与问题相关。如果不相关，直接说明无法回答。"""
```

**两路径的协同**：

```
检索层（硬拒绝）           模型层（软拒绝）
      ↓                         ↓
score < 0.6 → 直接返回    score ≥ 0.6 但模型判断
"无相关资料"              资料与问题实际无关 →
不进入 LLM              模型自行说明无法回答

双重保险：检索层避免浪费 API 成本；模型层处理检索层漏过的边界情况
```

---

## 四、完整实现：RAG 问答生成器

整合 Day 16（文档加载）、Day 17（文本切分）、Day 18（向量检索）和本天（生成回答）：

```python
"""
rag_qa.py — Day 19 完整实现
端到端 RAG 问答：加载 → 切分 → 向量化 → 检索 → 生成
"""
from __future__ import annotations

import os
import json
import time
import numpy as np
from dataclasses import dataclass, field
from openai import OpenAI
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

# ──────────────────────────────────────────────
# 复用 Day 18 的向量检索组件（精简版）
# ──────────────────────────────────────────────

_local_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _local_model.encode(texts)]


@dataclass
class VectorStore:
    texts: list[str] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)
    metadatas: list[dict] = field(default_factory=list)

    def add(self, texts, embeddings, metadatas=None):
        self.texts.extend(texts)
        self.embeddings.extend(embeddings)
        self.metadatas.extend(metadatas or [{}] * len(texts))

    def search(self, q_vec: list[float], top_k=3, min_score=0.5) -> list[dict]:
        if not self.embeddings:
            return []
        q = np.array(q_vec)
        q = q / (np.linalg.norm(q) + 1e-10)
        matrix = np.array(self.embeddings)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
        scores = (matrix / norms) @ q
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [
            {"text": self.texts[i], "score": float(scores[i]), "metadata": self.metadatas[i]}
            for i in top_idx if float(scores[i]) >= min_score
        ]


# ──────────────────────────────────────────────
# RAG Prompt 构建
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个知识库问答助手，专门根据提供的参考资料回答问题。

行为规则：
1. 只根据"参考资料"中的内容回答，不引入外部知识
2. 如果参考资料与问题无关或信息不足，明确说"根据现有资料无法回答，建议联系人工客服"
3. 回答时可以合理推理，但要区分"资料明确说明"和"基于资料推断"
4. 回答简洁、准确，不重复资料原文"""


def build_user_prompt(query: str, contexts: list[dict]) -> str:
    if not contexts:
        return f"问题：{query}"

    context_block = "\n\n".join(
        f"[资料{i+1}]（相关度 {r['score']:.2f}）\n{r['text']}"
        for i, r in enumerate(contexts)
    )
    return f"""参考资料：

{context_block}

---
问题：{query}

请根据以上参考资料回答问题。"""


# ──────────────────────────────────────────────
# 生成器
# ──────────────────────────────────────────────

class RAGAnswerGenerator:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )

    def generate(
        self,
        query: str,
        contexts: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str:
        user_prompt = build_user_prompt(query, contexts)
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()


# ──────────────────────────────────────────────
# 完整 RAG 流程
# ──────────────────────────────────────────────

class RAGPipeline:
    def __init__(self):
        self.store = VectorStore()
        self.generator = RAGAnswerGenerator()

    def build(self, documents: list[str], metadatas: list[dict] | None = None) -> None:
        print(f"构建索引：{len(documents)} 个文档片段...")
        vecs = embed(documents)
        self.store.add(documents, vecs, metadatas)
        print("索引就绪。")

    def ask(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.55,
        verbose: bool = False,
    ) -> str:
        # 1. 检索
        q_vec = embed([query])[0]
        results = self.store.search(q_vec, top_k=top_k, min_score=min_score)

        if verbose:
            print(f"\n[检索结果] 找到 {len(results)} 条相关资料")
            for r in results:
                print(f"  score={r['score']:.3f} | {r['text'][:50]}...")

        # 2. 无相关资料时直接拒答，不进入 LLM
        if not results:
            return "根据当前知识库，未找到与您问题相关的信息，无法回答。建议联系人工客服。"

        # 3. 生成回答
        answer = self.generator.generate(query, results)
        return answer


# ──────────────────────────────────────────────
# 主程序演示
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # 示例知识库
    knowledge_base = [
        "退款政策：购买后 30 天内可申请全额退款。超过 30 天不支持退款，但可申请换货。退款申请通过后，款项将在 3–5 个工作日内原路返回。",
        "联系客服：工作日 9:00–18:00 可拨打客服热线 400-888-8888，或发送邮件至 support@example.com。节假日不受理电话，但邮件 48 小时内回复。",
        "商品质保：所有商品享有一年质保。质保期内非人为损坏可免费维修或换货。人为损坏、进水、改装不在质保范围内。",
        "配送说明：订单确认后 24 小时内发货（周末顺延至周一），预计 3–5 个工作日送达。偏远地区（西藏、新疆等）可能需要 7–10 个工作日。",
        "会员积分规则：每消费 1 元获得 1 积分，积分有效期为自获得之日起 2 年。1000 积分可抵扣 10 元，每笔订单最多使用 5000 积分。",
    ]

    pipeline = RAGPipeline()
    pipeline.build(knowledge_base)

    test_questions = [
        ("我三周前买的东西可以退货吗？", True),
        ("周末能打客服电话吗？", True),
        ("手机进水了还能保修吗？", True),
        ("积分可以换礼品吗？", True),
        ("今天股市涨了吗？", True),   # 完全无关的问题
    ]

    print("\n" + "="*60)
    for question, verbose in test_questions:
        print(f"\n问：{question}")
        answer = pipeline.ask(question, verbose=verbose)
        print(f"答：{answer}")
        print("-" * 40)
```

---

## 五、RAG Prompt 模板对比实验

### 5.1 三版 RAG Prompt 设计

以"我三周前买的东西能退款吗"这个问题为例，对比不同 Prompt 的效果：

```python
def prompt_v1(query: str, contexts: list[str]) -> str:
    """V1：最简版，没有明确约束"""
    ctx = "\n".join(contexts)
    return f"参考资料：\n{ctx}\n\n问题：{query}"


def prompt_v2(query: str, contexts: list[str]) -> str:
    """V2：加入基本约束 + 格式化资料"""
    ctx = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    return f"""参考资料：

{ctx}

请只根据以上资料回答：{query}
如果资料中没有明确答案，说明无法回答。"""


def prompt_v3(query: str, contexts: list[str]) -> str:
    """V3：结构化约束 + 引导引用来源（为 Day 20 铺垫）"""
    ctx = "\n\n".join(f"[资料{i+1}] {c}" for i, c in enumerate(contexts))
    return f"""参考资料：

{ctx}

---
用户问题：{query}

回答要求：
- 只根据参考资料中的信息作答
- 指出你的答案来自哪条资料（如"根据[资料1]"）
- 如果资料不足以回答，明确说明"""
```

### 5.2 回答质量对比

知识库 Chunk：`"退款政策：购买后 30 天内可申请全额退款..."`

问题：`"我三周前买的东西能退款吗？"`（21 天，在 30 天内）

```
V1 典型输出：
  "您三周前购买的商品可以退款。"
  ↑ 简洁但没有引用依据，用户无法核实

V2 典型输出：
  "根据参考资料，购买后 30 天内可申请全额退款。三周（21天）在此范围内，
   所以您的商品可以申请退款。"
  ↑ 有推理过程，可信度更高

V3 典型输出：
  "根据[资料1]，购买后 30 天内可申请全额退款。您三周前（21天）购买的商品
   在此范围内，因此可以申请退款。建议前往官网或拨打客服热线办理。"
  ↑ 明确引用来源 + 建议行动，最有帮助
```

| 维度 | V1 | V2 | V3 |
|------|----|----|-----|
| 是否有推理过程 | ✗ | ✓ | ✓ |
| 是否指出来源 | ✗ | 隐式 | 显式（为 Day 20 准备）|
| 是否处理"拒答" | ✗ | ✓ | ✓ |
| Prompt 复杂度 | 低 | 中 | 高 |
| 推荐场景 | 原型测试 | 通用问答 | 需要可溯源的场景 |

**结论**：V2 是大多数 RAG 场景的推荐起点；V3 为 Day 20 的"引用来源"功能打下基础。

---

## 六、Day 19 知识速查

### RAG 生成阶段核心流程

```
检索结果（list[dict]）
    ↓
过滤：results = [r for r in results if r["score"] >= min_score]
    ↓
空列表？→ 直接返回拒答文案（不进入 LLM）
    ↓
build_user_prompt(query, results) → 拼接上下文 Prompt
    ↓
LLM 生成（temperature=0.1, max_tokens=800）
    ↓
返回回答字符串
```

### System Prompt 模板

```
你是一个知识库问答助手，专门根据提供的参考资料回答问题。

行为规则：
1. 只根据"参考资料"中的内容回答，不引入外部知识
2. 如果参考资料与问题无关或信息不足，明确说明无法回答
3. 回答时可以合理推理，但要区分"资料明确说明"和"基于资料推断"
4. 回答简洁、准确，不重复资料原文
```

### 关键参数速查

| 参数 | 推荐值 | 说明 |
|------|-------|------|
| `temperature` | 0.0–0.1 | RAG 回答追求准确，不需要随机性 |
| `max_tokens` | 500–1000 | 根据预期回答长度设置上限 |
| `min_score` | 0.55–0.65 | 过低会引入噪音，过高会导致误拒 |
| `top_k` | 3 | 检索 3 个 Chunk 通常足够，更多会占用 Token |

### 上下文拼接最小模板

```python
SYSTEM = "你是文档问答助手，只根据参考资料回答，资料不足时说明无法回答。"

def rag_answer(query: str, chunks: list[str]) -> str:
    if not chunks:
        return "根据现有资料，无法回答该问题。"
    ctx = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(chunks))
    user = f"参考资料：\n{ctx}\n\n问题：{query}"
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.1, max_tokens=800,
    )
    return resp.choices[0].message.content.strip()
```

---

## 七、实践任务

- [ ] 将 Day 18 的 `RAGRetriever` 接入 LLM 生成：调用 DeepSeek API，传入检索结果，获得最终回答
- [ ] 用 5 个问题测试：3 个知识库内的问题 + 1 个边界问题（资料中有但需要推理）+ 1 个完全无关的问题
- [ ] 对比 V1/V2/V3 三版 Prompt 在同一问题上的输出差异，记录哪个版本的回答最可信
- [ ] 实现 `min_score` 阈值拒答：用"今天天气怎么样"测试，确认系统不进入 LLM 直接返回拒答文案
- [ ] 调整 `temperature`（0.0 vs 0.5 vs 1.0），观察 RAG 场景下温度对回答的影响

**产出标准**：

- 一个端到端可运行的 RAG 问答脚本，能接受用户输入并返回基于知识库的回答
- 对完全无关的问题返回拒答文案，而不是胡乱关联

---

## 八、下一步预告

**Day 20：给回答加引用**

Day 19 的 V3 Prompt 已经引导模型说"根据[资料1]"，Day 20 要把这个"引用"变得更工程化：

- **结构化引用输出**：让模型用 JSON 格式输出 `{"answer": "...", "sources": [1, 3]}` 而不是在自然语言里混入引用
- **引用溯源显示**：根据 `sources` 列表，把对应的原文 Chunk 附在回答后面展示给用户
- **引用准确性验证**：检测模型是否"虚构了引用"（声称引用了[资料2]，但[资料2]里根本没有这个信息）
- **完整 RAG Demo**：Day 15 原理 → Day 16 加载 → Day 17 切分 → Day 18 检索 → Day 19 生成 → Day 20 引用，完整 RAG Demo 即将完工
