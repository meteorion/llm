# Day 15：理解 RAG 基本原理

> 学习目标：彻底理解 RAG（检索增强生成）的完整流程和设计动机——搞清楚为什么不能直接把整个知识库塞给模型、文档切分和 Embedding 各自解决什么问题，画出并能解释一张完整的 RAG 架构图
>
> 📚 所属阶段：**第二阶段 · RAG 核心应用架构**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 15
>
> 🧭 导航：[← Day 14 · 第 2 周复盘](day14_week2_review.md) [→ Day 16 · 读取本地文档](day16_document_loader.md)

---

## 目录

- [一、为什么需要 RAG](#一为什么需要-rag)
  - [1.1 大模型的三大知识局限](#11-大模型的三大知识局限)
  - [1.2 为什么不能直接把整个知识库塞给模型](#12-为什么不能直接把整个知识库塞给模型)
  - [1.3 RAG 的核心思想](#13-rag-的核心思想)
- [二、RAG 完整流程](#二rag-完整流程)
  - [2.1 两个阶段：离线构建 + 在线问答](#21-两个阶段离线构建--在线问答)
  - [2.2 文档切分（Chunking）](#22-文档切分chunking)
  - [2.3 Embedding 与向量化](#23-embedding-与向量化)
  - [2.4 向量检索](#24-向量检索)
  - [2.5 上下文增强与生成](#25-上下文增强与生成)
- [三、最小 RAG 实现（纯 Python）](#三最小-rag-实现纯-python)
  - [3.1 准备工作：安装依赖](#31-准备工作安装依赖)
  - [3.2 离线构建：切分 + 向量化 + 存储](#32-离线构建切分--向量化--存储)
  - [3.3 在线问答：检索 + 生成](#33-在线问答检索--生成)
  - [3.4 完整可运行代码](#34-完整可运行代码)
- [四、RAG 的关键参数与常见陷阱](#四rag-的关键参数与常见陷阱)
  - [4.1 Chunk Size 与 Chunk Overlap 的选择](#41-chunk-size-与-chunk-overlap-的选择)
  - [4.2 Top-K 的影响](#42-top-k-的影响)
  - [4.3 成本视角重看 RAG](#43-成本视角重看-rag)
- [五、Day 15 知识速查](#五day-15-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、为什么需要 RAG

### 1.1 大模型的三大知识局限

第 1 周 Day 1 介绍过大模型的局限性，RAG 主要解决其中三个：

```
┌──────────────────────────────────────────────────────────────────────┐
│              大模型的三大知识局限（RAG 的存在动机）                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  局限 1：知识截止（Knowledge Cutoff）                                  │
│  ─────────────────────────────────                                   │
│  训练数据有截止日期，之后发生的事情模型完全不知道                         │
│  例：问 2024 年某公司新产品 → 模型训练于 2023 → 无法回答                │
│                                                                       │
│  局限 2：不知道私有/领域知识                                            │
│  ─────────────────────────────────                                   │
│  公司内部文档、产品手册、合同模板从未出现在训练数据里                     │
│  例：问"我们公司的退货政策是什么" → 模型没见过这份文档 → 只能编造        │
│                                                                       │
│  局限 3：幻觉（Hallucination）                                         │
│  ─────────────────────────────────                                   │
│  模型用"看起来合理"的语言填充不确定的细节                                │
│  例：问某论文的具体数字 → 模型给出了听起来合理的假数字                   │
│                                                                       │
│  RAG 的解法：不依赖"模型记住了什么"，而是每次回答前                      │
│  先从外部知识库检索相关文档，再让模型基于这些文档回答                    │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 为什么不能直接把整个知识库塞给模型

这是 RAG 最常被问到的问题。直觉上，"把所有文档全放进 context，然后问模型"听起来简单粗暴，为什么不行？

**原因一：上下文窗口有限**

即使最大的模型（如 Claude 200K、GPT-4 128K），能塞进去的 Token 数也是有限的。一个中型企业的知识库可能有数千份文档，几千万 Token，根本无法全部塞入。

**原因二：塞满 ≠ 效果好**

大量实验和 OpenAI 的研究（"Lost in the Middle" 论文）发现：当 context 里有太多文本时，模型对位于中间部分的内容关注度会显著下降。"塞得越满，遗忘的越多"。

**原因三：成本爆炸（Day 12 已预警过）**

```
极端例子——塞 10 份 1000 Token 的文档：

  直接塞全文：输入 = 10,000 Token（文档）+ 50 Token（问题）= 10,050 Token
  
  RAG 检索后只喂相关片段（Top-3 × 300 Token）：
             输入 = 900 Token（检索片段）+ 50 Token（问题）= 950 Token

  成本比 = 10.6 倍
  
  在真实场景（1000 份文档，每天问 1000 次）下，这个差距直接影响产品是否可盈利
```

**原因四：不相关内容引发干扰**

无关内容越多，模型越容易被带跑偏——"这份文档里提到了 A，另一份提到了反义，你应该综合一下"——这种隐式的"综合"往往产生幻觉。只给模型"相关的"内容，反而让它更专注、更准确。

### 1.3 RAG 的核心思想

```
RAG = Retrieval（检索）+ Augmented（增强）+ Generation（生成）

核心思想只有一句话：
  问问题时，先"找"再"答"——找到相关文档片段，再让模型基于这些片段回答

vs. 纯模型（没有 RAG）：
  模型直接从参数记忆中回答，不参考任何外部资料
  
vs. 搜索引擎：
  只找，不答——返回链接，用户自己读
  
RAG = 搜索引擎的"找" + 大模型的"答"
```

---

## 二、RAG 完整流程

### 2.1 两个阶段：离线构建 + 在线问答

RAG 系统分为两个完全独立的阶段，理解这一点非常关键——很多初学者会把两个阶段混在一起想，导致理解混乱：

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RAG 完整架构图                                    │
├──────────────────────────┬──────────────────────────────────────────┤
│   【离线构建阶段】          │        【在线问答阶段】                     │
│   （一次性，提前做好）       │        （每次用户提问时触发）                │
│                           │                                          │
│  原始文档（PDF/TXT/MD）    │  用户提问                               │
│       ↓                   │       ↓                                  │
│  文档加载（Day 16）        │  问题 Embedding（同一个向量模型）          │
│       ↓                   │       ↓                                  │
│  文本切分                  │  向量相似度检索（Top-K）                  │
│  （Chunk Size / Overlap）  │       ↓                                  │
│       ↓                   │  取出 Top-K 个文档片段                   │
│  Embedding 向量化          │       ↓                                  │
│  （每个 Chunk → 一个向量）  │  构建增强 Prompt                        │
│       ↓                   │  （问题 + 检索片段）                      │
│  存入向量数据库             │       ↓                                  │
│  （Chroma / FAISS 等）     │  调用 LLM 生成答案                      │
│                           │       ↓                                  │
│  ← 知识库更新时重新触发      │  返回答案（+ 可选引用来源，Day 20）       │
└──────────────────────────┴──────────────────────────────────────────┘
```

**关键理解**：离线构建阶段花的时间和金钱（向量化），换来了在线问答阶段每次只需处理少量相关内容——这是一个典型的"空间换时间"思路，只是"空间"是向量数据库的存储，"时间"是每次生成回答的成本和延迟。

### 2.2 文档切分（Chunking）

原始文档通常很长，需要切分成小块（Chunk）再向量化。原因有两个：

```
为什么要切分：

  原因 1：向量化的粒度问题
  ─────────────────────────────────────────────────────────────────
  整篇 10,000 Token 的文档 → 一个向量 → 这个向量是整篇文章的"平均"语义
  
  用户问"第 3 章的退款流程是什么" → 检索到整篇文档 → 但 10,000 Token 里
  只有几百 Token 是相关的 → 喂给模型 10,000 Token 的噪音
  
  切分成 500 Token 的小块 → 每块有自己的向量 → 检索到相关的那几块
  → 只喂给模型 1,500 Token 的高质量相关内容

  原因 2：上下文窗口限制
  ─────────────────────────────────────────────────────────────────
  Top-5 × 10,000 Token = 50,000 Token 输入，直接超出大多数模型的限制
  Top-5 × 500 Token = 2,500 Token 输入，完全可控
```

**切分的两个关键参数**：

| 参数 | 说明 | 典型值 | 影响 |
|------|------|--------|------|
| Chunk Size | 每块的 Token 数 | 200–500 Token | 太小：每块语义不完整；太大：检索精度低、输入成本高 |
| Chunk Overlap | 相邻块的重叠 Token 数 | Chunk Size 的 10%–20% | 防止关键信息被切断边界两侧各一半 |

```python
def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap   # 每次前进 (chunk_size - overlap) 个词
    return chunks
```

为什么要有 Overlap：

```
假设 chunk_size=300, overlap=0：
  Chunk 1: ... 退款需在购买后 30 天内
  Chunk 2: 提交申请，客服在 3 个工作日...

  "在购买后 30 天内提交申请"这条关键信息被切断！
  检索"退款期限"时，两个 Chunk 都只包含一半信息

加上 overlap=50：
  Chunk 1: ... 退款需在购买后 30 天内
  Chunk 2: 退款需在购买后 30 天内 提交申请，客服在 3 个工作日...
  
  Chunk 2 包含完整的关键信息
```

### 2.3 Embedding 与向量化

Day 1 已经介绍过 Embedding 的概念，这里聚焦 RAG 场景下的实际使用：

```
文本 → Embedding 模型 → 固定维度的浮点数向量

"退款流程是什么"  →  [0.23, -0.41, 0.87, 0.12, ...]  （1536 维）
"申请退货的步骤"  →  [0.25, -0.39, 0.84, 0.15, ...]  （1536 维，语义相近，向量相近）
"今天天气很好"   →  [-0.65, 0.82, -0.23, 0.44, ...]  （语义不同，向量差异大）
```

**在 RAG 中，Embedding 模型有两个关键约束**：

1. **一致性**：文档的 Chunk 和用户的问题必须用**同一个 Embedding 模型**向量化，否则向量不在同一个空间里，相似度比较没有意义
2. **维度固定**：一旦选定模型，维度就固定了（如 text-embedding-3-small 是 1536 维）；换模型就需要重新向量化所有文档

**常用 Embedding 方案对比**：

| 方案 | 适合场景 | 成本 | 隐私 |
|------|---------|------|------|
| OpenAI text-embedding-3-small | 效果好、接入简单 | 按 Token 付费 | 数据出境 |
| DeepSeek Embedding（如果支持） | 中文优化 | 按 Token 付费 | 数据出境 |
| 本地模型（如 `sentence-transformers`） | 数据敏感场景 | 仅推理硬件成本 | 数据不出境 |

Day 15 先用**本地的 `sentence-transformers`** 跑通流程（不需要 API Key，成本零），Day 18 再深入 Embedding API 的选型。

### 2.4 向量检索

向量数据库存储了所有 Chunk 的（文本 + 向量），检索时：

```
检索流程：

  用户问题 ──→ Embedding 模型 ──→ 问题向量 q
  
  向量数据库里有 N 个 Chunk 向量：v1, v2, ..., vN
  
  计算相似度（余弦相似度）：
    sim(q, v1) = cos(q, v1) = (q · v1) / (|q| × |v1|)
    sim(q, v2) = ...
    ...
  
  取相似度最高的 Top-K 个 Chunk
  返回这 K 个 Chunk 的原始文本
```

**余弦相似度的直觉**：两个向量夹角越小（方向越接近），相似度越高。值在 [-1, 1] 之间，实践中相关内容通常在 0.7 以上，不相关内容通常低于 0.5。

```python
import numpy as np

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    a, b = np.array(v1), np.array(v2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### 2.5 上下文增强与生成

检索到 Top-K 个相关 Chunk 后，把它们拼接进 Prompt，构成"增强后的上下文"：

```python
SYSTEM_PROMPT = "你是文档问答助手，只根据提供的参考资料回答问题，资料中没有的内容请明确说明无法回答。"

def build_rag_prompt(question: str, chunks: list[str]) -> list[dict]:
    context = "\n\n---\n\n".join(
        f"[片段 {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)
    )
    user_content = f"""参考资料：

{context}

---

问题：{question}"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
```

**"只根据参考资料回答"这条指令的重要性**：没有这条约束，模型会把检索到的内容和自己的"参数记忆"混合在一起回答，引入幻觉。加上这条约束，模型被迫只从给定文本里找答案——答不了就说答不了，而不是编造一个"听起来对"的回答。

---

## 三、最小 RAG 实现（纯 Python）

### 3.1 准备工作：安装依赖

```bash
pip install sentence-transformers numpy openai python-dotenv
```

`sentence-transformers` 提供本地运行的高质量 Embedding 模型，不需要 API Key，第一次运行会自动下载模型文件（约 90MB）。

### 3.2 离线构建：切分 + 向量化 + 存储

```python
import numpy as np
from sentence_transformers import SentenceTransformer

# 第一次运行会下载模型，后续使用缓存
embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + chunk_size]))
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def build_index(documents: list[str]) -> dict:
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_text(doc))

    vectors = embedding_model.encode(all_chunks, show_progress_bar=False)
    return {"chunks": all_chunks, "vectors": vectors}
```

### 3.3 在线问答：检索 + 生成

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")


def retrieve(query: str, index: dict, top_k: int = 3) -> list[str]:
    query_vector = embedding_model.encode([query])[0]
    scores = [
        float(np.dot(query_vector, v) / (np.linalg.norm(query_vector) * np.linalg.norm(v)))
        for v in index["vectors"]
    ]
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [index["chunks"][i] for i in top_indices]


def answer(question: str, chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(f"[片段 {i+1}]\n{c}" for i, c in enumerate(chunks))
    messages = [
        {
            "role": "system",
            "content": "你是文档问答助手，只根据提供的参考资料回答问题，资料中没有的内容请明确说明无法回答。",
        },
        {
            "role": "user",
            "content": f"参考资料：\n\n{context}\n\n---\n\n问题：{question}",
        },
    ]
    response = client.chat.completions.create(
        model="deepseek-chat", messages=messages, temperature=0.1
    )
    return response.choices[0].message.content
```

### 3.4 完整可运行代码

```python
"""
day15_rag_demo.py — 最小可用 RAG 演示

运行前准备：
  1. pip install sentence-transformers numpy openai python-dotenv
  2. .env 文件中配置 DEEPSEEK_API_KEY
"""

import os
import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")
embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# ─── 示例知识库（替换为真实文档即可）──────────────────────────────────────────

KNOWLEDGE_BASE = [
    """退款政策：购买后 30 天内可申请退款。退款需满足以下条件：
    商品未拆封使用；退款申请需通过官网客服提交；审核通过后 3-5 个工作日原路退回。
    以下情况不支持退款：虚拟商品、定制商品、促销期间购买的商品。""",

    """配送说明：标准配送通常在 3-7 个工作日内到达。加急配送（额外收费）1-2 个工作日到达。
    偏远地区配送时间可能延长至 10-15 个工作日。配送状态可通过订单页面实时查询。
    如超时未收到，请联系客服提供订单号进行查询。""",

    """会员等级：普通会员（无门槛）、银牌会员（累计消费满 1000 元）、
    金牌会员（累计消费满 5000 元）、钻石会员（累计消费满 20000 元）。
    各等级享有不同折扣：普通 9.8 折、银牌 9.5 折、金牌 9 折、钻石 8.5 折。
    会员积分可兑换优惠券，100 积分 = 1 元优惠券。""",
]


def chunk_text(text: str, chunk_size: int = 100, overlap: int = 20) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + chunk_size]))
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def build_index(documents: list[str]) -> dict:
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_text(doc))
    vectors = embedding_model.encode(all_chunks, show_progress_bar=False)
    return {"chunks": all_chunks, "vectors": vectors}


def retrieve(query: str, index: dict, top_k: int = 3) -> list[tuple[str, float]]:
    q_vec = embedding_model.encode([query])[0]
    scores = []
    for v in index["vectors"]:
        sim = float(np.dot(q_vec, v) / (np.linalg.norm(q_vec) * np.linalg.norm(v)))
        scores.append(sim)
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [(index["chunks"][i], scores[i]) for i in top_idx]


def answer_with_rag(question: str, index: dict) -> dict:
    retrieved = retrieve(question, index, top_k=3)
    context = "\n\n---\n\n".join(
        f"[片段 {i+1}（相似度 {score:.3f}）]\n{chunk}"
        for i, (chunk, score) in enumerate(retrieved)
    )
    messages = [
        {
            "role": "system",
            "content": "你是文档问答助手，只根据提供的参考资料回答问题，资料中没有的内容请明确说明无法回答。",
        },
        {
            "role": "user",
            "content": f"参考资料：\n\n{context}\n\n---\n\n问题：{question}",
        },
    ]
    response = client.chat.completions.create(
        model="deepseek-chat", messages=messages, temperature=0.1
    )
    return {
        "question": question,
        "answer": response.choices[0].message.content,
        "retrieved_chunks": [chunk for chunk, _ in retrieved],
        "top_scores": [score for _, score in retrieved],
    }


if __name__ == "__main__":
    print("正在构建向量索引...")
    index = build_index(KNOWLEDGE_BASE)
    print(f"索引完成：{len(index['chunks'])} 个 Chunk\n")

    questions = [
        "退款需要多少天才能到账？",
        "金牌会员有什么折扣？",
        "配送一般要多久？",
        "能不能在网上修改订单地址？",  # 知识库里没有这个答案，测试拒答效果
    ]

    for q in questions:
        result = answer_with_rag(q, index)
        print(f"问：{result['question']}")
        print(f"答：{result['answer']}")
        print(f"（最高相似度：{result['top_scores'][0]:.3f}）")
        print()
```

---

## 四、RAG 的关键参数与常见陷阱

### 4.1 Chunk Size 与 Chunk Overlap 的选择

```
┌─────────────────────────────────────────────────────────────────────┐
│              Chunk Size 的"甜蜜区间"                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  太小（< 100 Token）：                                               │
│  ✗ 每块语义不完整，一句话被切成两半                                    │
│  ✗ 检索到的片段缺乏上下文，模型无法基于片段给出完整回答                 │
│  ✓ 检索精度高，不相关内容少                                           │
│                                                                      │
│  合适（200-500 Token）：                                             │
│  ✓ 每块包含 1-3 个完整语义段落                                        │
│  ✓ 检索到相关内容时，这块内容通常足够支撑一个回答                      │
│  ✓ Top-3 × 300 Token = 900 Token 输入，成本可控                      │
│                                                                      │
│  太大（> 1000 Token）：                                              │
│  ✗ 检索精度下降（一块包含多个话题，向量是"混合语义"）                   │
│  ✗ 输入成本增加，Top-3 × 1000 = 3000 Token 输入                      │
│  ✓ 上下文完整性好                                                    │
│                                                                      │
│  经验法则：先用 300 Token / 10%–15% Overlap 试跑，                    │
│  根据实际问答质量再调整                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Top-K 的影响

| Top-K | 优点 | 缺点 | 适用场景 |
|-------|------|------|---------|
| 1 | 输入 Token 最少，成本最低 | 一旦最相关的那块被漏掉，答案直接失效 | 知识库质量极高、Chunk 切分精确 |
| 3 | 平衡点，通常的默认值 | — | **大多数场景推荐** |
| 5 | 召回率更高，漏掉的可能性低 | 更多不相关内容输入模型，可能引入噪音 | 知识库组织较散乱 |
| ≥ 10 | 几乎不会漏 | 输入成本高，不相关干扰大 | 不建议，改进 Embedding 更有效 |

### 4.3 成本视角重看 RAG

Day 12 预警过"RAG 场景输入 Token 大头在检索片段"，现在可以算清楚：

```
典型 RAG 请求的 Token 构成：

  system prompt：           100 Token  （固定）
  用户问题：                  30 Token  （固定，通常很短）
  Top-3 检索片段 × 300 Token：900 Token  （主要成本来源）
  
  总输入：约 1030 Token
  
  对比：普通问答请求的输入通常只有 30-100 Token
  
  结论：RAG 把每次请求的输入成本提高了约 10-30 倍
  这就是为什么 Chunk Size 和 Top-K 的选择不仅是"效果问题"，也是"成本问题"
```

---

## 五、Day 15 知识速查

### RAG 流程速查

```
离线构建：原始文档 → 切分（Chunk Size/Overlap）→ Embedding → 向量数据库
在线问答：问题 → Embedding → 向量检索（Top-K）→ 增强 Prompt → LLM 生成
```

### 关键参数参考值

| 参数 | 默认参考值 | 调整方向 |
|------|-----------|---------|
| Chunk Size | 300 Token | 问答质量低 → 减小；输入成本高 → 减小 |
| Chunk Overlap | 10%–15% | 跨 Chunk 边界遗漏 → 增大 |
| Top-K | 3 | 漏召回 → 增大；输入成本高 → 减小 |
| Temperature（生成） | 0.1 | 事实问答保持低值，减少随机性 |

### 最小代码模板

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

def build_index(docs):
    chunks = [c for doc in docs for c in chunk_text(doc)]
    return {"chunks": chunks, "vectors": model.encode(chunks)}

def retrieve(query, index, top_k=3):
    q = model.encode([query])[0]
    scores = [float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v)))
              for v in index["vectors"]]
    return [index["chunks"][i] for i in sorted(range(len(scores)),
            key=lambda i: scores[i], reverse=True)[:top_k]]
```

---

## 六、实践任务

- [ ] 画出一张完整的 RAG 架构图（离线构建 + 在线问答两个阶段均需体现），并用自己的话注释每个环节
- [ ] 用自己的话写 100 字，回答"为什么不能直接把整个知识库塞给模型"
- [ ] 安装 `sentence-transformers`，运行 `day15_rag_demo.py`，观察 4 个问题的回答——特别注意第 4 个（知识库里没有答案的问题）是否正确拒答
- [ ] 修改 Chunk Size（分别试 50 / 100 / 300），观察切分数量和检索相似度的变化
- [ ] 替换知识库内容为任意一份你自己的文档（txt 格式即可），运行问答效果

**产出标准**：

- 一张清晰的 RAG 流程图（ASCII 或手绘均可）
- `day15_rag_demo.py` 成功运行，4 个测试问题均有回答，第 4 个问题正确拒答

---

## 七、下一步预告

**Day 16：读取本地文档**

Day 15 的知识库是硬编码在代码里的字符串，Day 16 要从真实的本地文件读取内容：

- `txt` 和 `md` 文件的读取（Python 内置，最简单）
- `pdf` 文件的读取（`PyPDF2` 或 `pdfplumber`，有坑需要处理）
- 文件编码问题（Windows 和 macOS 的默认编码不同）
- 文档加载后直接接入 Day 15 的切分 + 向量化流程

核心问题：同样是"读取文件"，为什么 PDF 比 TXT 难得多？答案在 Day 16。
