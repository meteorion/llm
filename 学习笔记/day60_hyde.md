# Day 60：HyDE（假设文档 Embedding）

> 学习目标：理解用户问题和知识库文档之间的表述鸿沟（query-document mismatch）为什么会拖累检索效果；掌握 HyDE 的核心思路——先让模型生成一段"假设性答案"，再用这段假设答案去检索而非直接用原始问题；实现 HyDE 检索流程，记录几个典型 case 下和直接问题检索的效果差异
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 60
>
> 🧭 导航：[← Day 59 · Reranker 重排序](day59_reranker.md) → [Day 61 · 查询改写与多查询检索](day61_query_rewriting_multi_query.md)

---

## 目录

- [一、问题与文档之间的语义鸿沟](#一问题与文档之间的语义鸿沟)
  - [1.1 为什么用问题去检索有时候效果不好](#11-为什么用问题去检索有时候效果不好)
  - [1.2 HyDE 的核心思路](#12-hyde-的核心思路)
- [二、HyDE 工作流程详解](#二hyde-工作流程详解)
  - [2.1 Step 1：让模型生成一段假设性答案](#21-step-1让模型生成一段假设性答案)
  - [2.2 Step 2：对假设答案做 Embedding](#22-step-2对假设答案做-embedding)
  - [2.3 Step 3：用假设答案向量检索真实文档](#23-step-3用假设答案向量检索真实文档)
  - [2.4 为什么这样做更有效](#24-为什么这样做更有效)
- [三、实现 HyDE 检索流程](#三实现-hyde-检索流程)
  - [3.1 生成假设文档的 Prompt 设计](#31-生成假设文档的-prompt-设计)
  - [3.2 完整代码实现](#32-完整代码实现)
  - [3.3 和两阶段检索的结合方式](#33-和两阶段检索的结合方式)
- [四、HyDE 的适用场景与局限性](#四hyde-的适用场景与局限性)
  - [4.1 明显有效的场景](#41-明显有效的场景)
  - [4.2 局限性](#42-局限性)
- [五、对比实验：HyDE 检索 vs 直接问题检索](#五对比实验hyde-检索-vs-直接问题检索)
- [六、Day 60 知识速查](#六day-60-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、问题与文档之间的语义鸿沟

### 1.1 为什么用问题去检索有时候效果不好

Day 18 起的向量检索一直是**用用户的原始问题去检索知识库文档**，这个做法隐含一个假设：**问题的向量表示和答案文档的向量表示足够接近**。但现实中这个假设经常不成立——问题通常是口语化的疑问句，而知识库文档通常是陈述句、说明文，两者在**语言风格、句式结构、用词习惯**上天然存在差异：

```
用户问题："东西坏了怎么办，能退吗"（口语化疑问句）
知识库文档："产品质量问题处理流程：自购买之日起 7 日内，因质量问题可申请全额退款……"（正式陈述句）

即使这两句话讨论的是同一件事，向量空间里的距离可能没有想象中那么近
——问题的向量表示更像"疑问句的语义"，答案文档的向量表示更像"说明文的语义"
```

这种"问题和答案文体不同导致检索不准"的现象，就是**query-document mismatch**，是纯向量检索（甚至加上 Day 58 的 BM25）都难以彻底解决的结构性问题——不是分词或相似度算法的问题，而是两种文本的**语言风格本身存在差异**。

### 1.2 HyDE 的核心思路

HyDE（Hypothetical Document Embeddings）的思路很反直觉但很有效：**不要直接用问题去检索，而是先让模型针对这个问题生成一段"假设性答案"，再用这段假设答案的 Embedding 去检索**：

```
传统检索：用户问题 ──► Embedding ──► 检索知识库

HyDE 检索：用户问题 ──► LLM 生成假设答案 ──► 对假设答案做 Embedding ──► 检索知识库
                         （不要求真实准确，只要求"像"知识库里的答案文风）
```

**关键认知**：这段"假设答案"完全可能包含模型编造的细节（甚至幻觉），这在 HyDE 里**不是问题**——因为假设答案从来不会被返回给用户，它只是一个"用来检索的中间媒介"，它的价值在于**文体和措辞风格更接近真实文档**，而不在于内容本身是否准确。

---

## 二、HyDE 工作流程详解

### 2.1 Step 1：让模型生成一段假设性答案

```python
HYDE_PROMPT = """请针对下面的问题，写一段简短的假设性回答（100字以内），
就像这段回答会出现在一份正式的产品说明文档或政策文档里一样。
不需要保证内容完全准确，重点是措辞和文体要贴近正式文档的写法。

问题：{question}
"""
```

对于问题"东西坏了怎么办，能退吗"，模型可能生成：

```
"根据产品质量保障政策，若产品在购买后出现非人为损坏的质量问题，
用户可在规定期限内申请退货或换货，具体流程需提交订单信息及问题描述。"
```

这段文字读起来就像知识库里会出现的正式说明文——即使里面的"规定期限"到底是几天并不准确（模型编造的），这不影响后续检索的效果。

### 2.2 Step 2：对假设答案做 Embedding

```python
hypothetical_doc = generate_hypothetical_answer(question)
hyde_embedding = embed(hypothetical_doc)   # 注意：编码的是假设答案，不是原始问题
```

### 2.3 Step 3：用假设答案向量检索真实文档

```python
results = vector_store.search_by_embedding(hyde_embedding, top_k=10)
```

**关键区别**：检索用的向量来自"假设答案"，而不是来自"原始问题"——这正是 HyDE 名字里 "Hypothetical Document" 的含义：把检索的锚点从"问题的向量"换成"假设文档的向量"。

### 2.4 为什么这样做更有效

```
问题的向量表示 —— 语义空间里更像"一个疑问句"
假设答案的向量表示 —— 语义空间里更像"一段说明文"
知识库文档的向量表示 —— 语义空间里也是"一段说明文"

假设答案和知识库文档同属"陈述文体"，
两者在向量空间里的距离，天然比"疑问句 vs 陈述文"的距离更近
```

HyDE 本质上是用一次 LLM 生成，把检索的"锚点"从问题的语义空间搬到了文档的语义空间——牺牲一次额外的模型调用（延迟和成本），换取更贴近目标文档分布的检索向量。

---

## 三、实现 HyDE 检索流程

### 3.1 生成假设文档的 Prompt 设计

```python
HYDE_PROMPT_TEMPLATE = """你是一个专业知识库的内容撰写助手。
请针对下面的问题，写一段可能出现在正式文档里的回答。

要求：
1. 语言风格要正式、陈述式，避免口语化表达
2. 长度控制在 80-150 字
3. 不需要保证内容绝对准确，重点是文体贴近正式说明文档

问题：{question}

假设性回答："""
```

**设计要点**：明确要求"正式陈述文体"而不是"回答用户问题"，这是让生成结果贴近知识库文风的关键——如果 Prompt 写成"请回答这个问题"，模型可能生成的是口语化的助手式回复，反而和知识库文档的文体差异依然很大。

### 3.2 完整代码实现

```python
# retrieval/hyde_retriever.py
def generate_hypothetical_answer(question: str) -> str:
    prompt = HYDE_PROMPT_TEMPLATE.format(question=question)
    return call_llm(prompt, temperature=0.3)   # 保留一点多样性，但不需要太高

class HyDERetriever:
    def __init__(self, vector_store, embed_fn):
        self.vector_store = vector_store
        self.embed_fn = embed_fn

    def search(self, question: str, top_k: int = 10) -> list[dict]:
        hypothetical_doc = generate_hypothetical_answer(question)
        hyde_vector = self.embed_fn(hypothetical_doc)
        results = self.vector_store.search_by_embedding(hyde_vector, top_k=top_k)
        return results

    def search_with_comparison(self, question: str, top_k: int = 10) -> dict:
        """同时跑传统检索和 HyDE 检索，便于对比"""
        direct_vector = self.embed_fn(question)
        direct_results = self.vector_store.search_by_embedding(direct_vector, top_k=top_k)

        hyde_results = self.search(question, top_k=top_k)

        return {"direct": direct_results, "hyde": hyde_results}
```

### 3.3 和两阶段检索的结合方式

HyDE 不是要替代 Day 58/59 的混合检索和 Reranker，而是可以**叠加**在检索流程的最前端——用 HyDE 生成的假设文档向量替代原始问题向量，作为粗召回阶段的检索锚点，后续的 BM25 融合和 Reranker 精排环节保持不变：

```python
def hyde_hybrid_retrieve(question: str, hyde_retriever, hybrid_retriever, reranker):
    hypothetical_doc = generate_hypothetical_answer(question)

    # 向量检索这一路用假设文档做 embedding，BM25 这一路仍然用原始问题做关键词匹配
    # （BM25 依赖关键词精确匹配，用假设文档反而可能引入生成噪音里的无关关键词）
    vector_results = hybrid_retriever.vector_store.search(hypothetical_doc, top_k=50)
    bm25_results = hybrid_retriever.bm25_retriever.search(question, top_k=50)

    fused = reciprocal_rank_fusion([vector_results, bm25_results], k=60)[:50]
    return reranker.rerank(question, fused, top_k=5)   # 精排阶段仍然用原始问题判断相关性
```

**关键设计决策**：只有**向量检索**这一路用假设文档做 Embedding，BM25 那一路和最终的 Reranker 打分依然使用**原始问题**——因为 BM25 依赖精确关键词匹配，假设文档里的编造内容可能引入无关关键词；Reranker 判断"这篇文档是否真的回答了用户的问题"，自然也应该基于原始问题而不是假设答案。

---

## 四、HyDE 的适用场景与局限性

### 4.1 明显有效的场景

| 场景 | 原因 |
|-----|------|
| 用户问题高度口语化，知识库是正式文档 | 文体差异大，HyDE 能有效缩小语义鸿沟 |
| 专业领域知识库（法律、医疗、政策条款） | 用户提问方式和专业文档措辞差异显著 |
| 用户问题信息量少（如"能退吗"） | 假设答案能补全上下文信息，检索锚点更丰富 |

### 4.2 局限性

```
额外成本：每次检索多一次 LLM 调用，增加延迟和 Token 成本
          （不适合对延迟极度敏感的场景，或大幅提高了每次检索成本）

幻觉风险：假设答案如果生成方向完全跑偏（比如误解了问题意图），
          可能让检索走向错误方向，反而不如直接用原始问题准确

对已经写得清楚的问题收益有限：如果用户问题本身已经是"陈述式的完整表达"
          （比如直接输入产品型号），HyDE 的转换步骤价值不大，甚至多此一举
```

**核心权衡**：HyDE 用"一次额外的生成成本"换取"检索锚点文体更贴近目标文档"，只有当"问题和文档的文体/表述差异"是检索效果的主要瓶颈时，这笔额外成本才划算——如果检索效果差的根因是 Chunk 切分不合理或 Embedding 模型选型问题，HyDE 解决不了这些问题。

---

## 五、对比实验：HyDE 检索 vs 直接问题检索

```python
# experiments/hyde_comparison.py
TEST_QUESTIONS = [
    "东西坏了怎么办，能退吗",
    "多久能到账",
    "买贵了能补差价吗",
    "换个尺码麻烦吗",
    "不想要了能取消吗",
]

def run_comparison(hyde_retriever, questions: list[str]):
    for q in questions:
        result = hyde_retriever.search_with_comparison(q, top_k=3)
        print(f"\n问题：{q}")
        print(f"  直接检索 Top3: {[r['text'][:30] for r in result['direct']]}")
        print(f"  HyDE 检索 Top3: {[r['text'][:30] for r in result['hyde']]}")
```

**典型对比记录**：

| 问题 | 直接检索命中 | HyDE 检索命中 |
|-----|-------------|--------------|
| "东西坏了怎么办，能退吗" | 命中了"产品使用说明"（相关性较弱） | 命中了"产品质量问题处理流程"（更准确） |
| "多久能到账" | 命中了"物流配送时效"（跑偏，答非所问） | 命中了"退款到账时间说明"（更准确） |
| "换个尺码麻烦吗" | 命中了"换货政策"（基本相关） | 命中了"换货政策"（结果一致，无明显差异） |

**结论模式**：HyDE 在"问题信息量少、口语化程度高"的 case 上（如"多久能到账"这种缺乏明确主语的短问题）提升明显；在问题本身已经比较清晰、和文档措辞差异不大的 case 上，两种方式的检索结果基本一致，HyDE 的额外成本没有换来明显收益。

---

## 六、Day 60 知识速查

### HyDE 核心流程

```
用户问题 → LLM 生成假设性答案（不要求准确，只要求文体贴近文档）
        → 对假设答案做 Embedding（而不是对原始问题）
        → 用假设答案向量检索知识库
```

### HyDE 生效的原理

```
假设答案和知识库文档同属"陈述文体"，向量空间距离比"疑问句 vs 陈述文"更近
用一次额外的 LLM 生成，把检索锚点从问题的语义空间搬到文档的语义空间
```

### 适用性判断

```
适合：口语化问题 + 正式知识库文档、专业领域术语差异大、问题信息量少
不适合：对延迟/成本极度敏感的场景、问题本身已经很清晰规范的场景
根因排查：如果检索差是 Chunk 切分或 Embedding 模型问题，HyDE 解决不了
```

### 与混合检索/Reranker 的组合方式

```
向量检索这一路 → 用 HyDE 假设文档做 Embedding
BM25 这一路   → 仍用原始问题做关键词匹配
Reranker 精排 → 仍用原始问题判断相关性
```

---

## 七、实践任务

- [ ] 设计 `HYDE_PROMPT_TEMPLATE`，针对 3-5 个口语化问题生成假设性答案，检查生成结果的文体是否贴近知识库文档
- [ ] 实现 `HyDERetriever.search()`，验证能用假设答案的 Embedding 完成检索
- [ ] 实现 `search_with_comparison()`，对同一批问题同时跑直接检索和 HyDE 检索
- [ ] 记录至少 5 个测试问题的对比结果：直接检索 Top3 vs HyDE 检索 Top3，标注哪些 case HyDE 明显更准
- [ ] 尝试把 HyDE 和 Day 58 的混合检索结合（向量路用假设文档，BM25 路用原始问题），验证组合流程能跑通

**产出标准**：几个具体 case 下"直接问题检索"和"HyDE 检索"的效果对比记录，能说明 HyDE 在哪类问题上收益明显、哪类问题上没有明显差异。

---

## 八、下一步预告

Day 61 进入**查询改写与多查询检索**：今天的 HyDE 是针对"一个问题生成一个假设答案"的思路，Day 61 要解决的是另一个相关但不同的问题——**用户的一次提问可能隐含多个检索意图**（比如"退货流程和运费谁承担"实际包含两个子问题），或者用户的表达方式本身有歧义/信息不全。查询改写会把原始问题拆解或重写成多个更明确的检索查询，分别检索后再合并结果——和 HyDE"改变检索锚点的文体"不同，查询改写改变的是"检索查询的数量和颗粒度"。
