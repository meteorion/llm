# Day 59：Reranker 重排序

> 学习目标：理解 Cross-Encoder 和普通 Embedding 相似度（Bi-Encoder）的本质区别，掌握"先粗召回、再精排"两阶段检索的设计思路；给 Day 58 的混合检索候选接入一个开源 Reranker 模型做二次排序；对比加 Reranker 前后的 Top-K 命中率
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 59
>
> 🧭 导航：[← Day 58 · 混合检索（向量 + BM25）](day58_hybrid_retrieval.md) → [Day 60 · HyDE（假设文档 Embedding）](day60_hyde.md)

---

## 目录

- [一、Cross-Encoder 和 Bi-Encoder 的本质区别](#一cross-encoder-和-bi-encoder-的本质区别)
  - [1.1 Bi-Encoder：Day 18 向量检索的工作方式](#11-bi-encoderday-18-向量检索的工作方式)
  - [1.2 Cross-Encoder：Reranker 的工作方式](#12-cross-encoderreranker-的工作方式)
  - [1.3 为什么精排更准但更贵](#13-为什么精排更准但更贵)
- [二、两阶段检索：先粗召回再精排](#二两阶段检索先粗召回再精排)
  - [2.1 为什么不能对全量文档直接用 Cross-Encoder](#21-为什么不能对全量文档直接用-cross-encoder)
  - [2.2 粗召回阶段：拿到 Top-N 候选](#22-粗召回阶段拿到-top-n-候选)
  - [2.3 精排阶段：Cross-Encoder 重新打分取 Top-K](#23-精排阶段cross-encoder-重新打分取-top-k)
- [三、接入开源 Reranker 模型](#三接入开源-reranker-模型)
  - [3.1 常见开源 Reranker 选择](#31-常见开源-reranker-选择)
  - [3.2 代码实现](#32-代码实现)
- [四、对比实验：加 Reranker 前后的 Top-K 命中率](#四对比实验加-reranker-前后的-top-k-命中率)
  - [4.1 命中率（Hit Rate）指标回顾](#41-命中率hit-rate指标回顾)
  - [4.2 测试集设计与对比脚本](#42-测试集设计与对比脚本)
  - [4.3 结果分析](#43-结果分析)
- [五、Day 59 知识速查](#五day-59-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、Cross-Encoder 和 Bi-Encoder 的本质区别

### 1.1 Bi-Encoder：Day 18 向量检索的工作方式

Day 18 的向量检索用的是 **Bi-Encoder** 架构——query 和文档**分别独立**编码成向量，检索时只需要计算两个向量的相似度：

```
query  ──► Embedding模型 ──► query向量
                                    │
                                    ▼ 余弦相似度
                                    ▲
doc    ──► Embedding模型 ──► doc向量（可以提前批量算好，存进向量库）
```

**关键特性**：doc 向量可以**离线预计算并存储**，检索时只需要编码 query 一次，然后和向量库里几十万条 doc 向量做一次快速的相似度计算——这是向量检索能做到"毫秒级检索几十万文档"的原因。

### 1.2 Cross-Encoder：Reranker 的工作方式

Cross-Encoder 把 query 和 doc **拼接成一个序列**一起输入模型，让模型在编码过程中就能看到两者的交互信息：

```
[query] [SEP] [doc]  ──► 模型（如 BERT）──► 一个相关性分数（0-1）

query 和 doc 在同一次前向传播里互相"看得见"对方，
注意力机制能捕捉到词与词之间的精细交互（比如 query 里的关键词是否在 doc 里被准确呼应）
```

**关键特性**：**doc 不能被预计算**——每一次打分都需要针对"这一对 query-doc"重新跑一遍完整的模型前向传播，无法像 Bi-Encoder 那样把 doc 向量提前存起来复用。

### 1.3 为什么精排更准但更贵

| 维度 | Bi-Encoder（向量检索） | Cross-Encoder（Reranker） |
|-----|----------------------|--------------------------|
| 编码方式 | query 和 doc 独立编码 | query 和 doc 拼接后一起编码 |
| 交互粒度 | 只在最后比较两个向量的相似度，交互信息被压缩进向量 | 模型内部注意力层直接捕捉 query 和 doc 的词级交互 |
| 准确率 | 较低（向量压缩丢失了部分细粒度信息） | 较高（交互越充分，排序越准） |
| doc 是否可预计算 | 可以，检索前批量算好存库 | 不可以，每次都要重新计算 |
| 检索一批候选的耗时 | 快（向量库检索几十万条也是毫秒级） | 慢（每对 query-doc 都要跑一次完整模型） |

**根本原因**：Cross-Encoder 的"更准"恰恰来自它"不能预计算"这个特性——正是因为它把 query 和 doc 放在一起端到端地算了一遍，才能捕捉到 Bi-Encoder 压缩进两个独立向量后丢失的交互信息；但这也意味着它没法像 Bi-Encoder 一样对海量文档做批量离线索引，只能对**一小批候选**逐一打分。

---

## 二、两阶段检索：先粗召回再精排

### 2.1 为什么不能对全量文档直接用 Cross-Encoder

假设知识库有 10 万条 chunk，如果对每个用户查询都用 Cross-Encoder 给全部 10 万条打分，意味着每次查询要跑 10 万次模型前向传播——这在延迟和算力成本上都是不可接受的。而 Bi-Encoder 的向量检索可以把 10 万条 doc 向量一次性建好索引，之后每次查询只需要一次 query 编码 + 一次向量库检索，是毫秒级的。

### 2.2 粗召回阶段：拿到 Top-N 候选

用 Day 58 的混合检索（向量 + BM25 + RRF 融合）从全量文档里快速捞出一批候选，N 通常设置得比最终需要的 K 大不少（如 N=50，最终只需要 K=3-5）：

```python
# 粗召回：快、便宜，但排序未必最优
coarse_candidates = hybrid_retriever.dual_search(query, top_k=50)
fused_candidates = reciprocal_rank_fusion(coarse_candidates, k=60)[:50]
```

### 2.3 精排阶段：Cross-Encoder 重新打分取 Top-K

对这 50 个候选（而不是全量 10 万条）逐一跑 Cross-Encoder 打分，因为候选数量已经从 10 万降到 50，计算量完全可以接受：

```
用户查询
    │
    ▼
┌─────────────────────────────────┐
│ 粗召回（Day 58 混合检索）          │  快、便宜，Top-N=50
│ 向量检索 + BM25 + RRF 融合         │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 精排（今天的 Reranker）            │  慢、准，只处理 50 条候选
│ Cross-Encoder 对 50 条重新打分      │
└─────────────────────────────────┘
    │
    ▼
Top-K=3-5 送入生成阶段（Day 19 的 RAG 生成链路）
```

**两阶段设计的核心权衡**：粗召回牺牲一部分精度换取速度，覆盖尽量大的候选范围；精排在小范围候选内牺牲一部分速度换取精度，保证最终送进生成阶段的文档质量更高——这和 Day 47 分级路由"简单任务用小模型、复杂任务用大模型"是同一种"用最贵的资源做最关键的判断"的工程思路。

---

## 三、接入开源 Reranker 模型

### 3.1 常见开源 Reranker 选择

| 模型 | 特点 |
|-----|------|
| `BAAI/bge-reranker-base` / `bge-reranker-large` | 中英双语效果好，开源可本地部署，`base` 速度快、`large` 精度更高 |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 英文场景常用，轻量，sentence-transformers 官方维护 |
| Cohere Rerank API | 商业 API，无需自己部署，多语言效果稳定，按调用量计费 |

**选型建议**：中文场景优先 `bge-reranker`（本地部署，无额外 API 成本）；不想自己维护模型、预算允许的场景可以直接用 Cohere Rerank 这类托管服务。

### 3.2 代码实现

```python
# retrieval/reranker.py
from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
        pairs = [[query, c["text"]] for c in candidates]
        scores = self.model.predict(pairs)   # 每一对 (query, doc) 输出一个相关性分数

        for c, score in zip(candidates, scores):
            c["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
        return reranked[:top_k]
```

```python
# 完整两阶段检索流程
def two_stage_retrieve(query: str, hybrid_retriever, reranker: Reranker, coarse_n: int = 50, final_k: int = 5):
    vector_results, bm25_results = hybrid_retriever.dual_search(query, top_k=coarse_n)
    coarse_candidates = reciprocal_rank_fusion([vector_results, bm25_results], k=60)[:coarse_n]

    final_results = reranker.rerank(query, coarse_candidates, top_k=final_k)
    return final_results
```

**关键点**：`rerank()` 只对粗召回返回的 `coarse_n` 条候选打分，不涉及全量文档——这正是两阶段设计把 Cross-Encoder 的计算量控制在可接受范围的地方。

---

## 四、对比实验：加 Reranker 前后的 Top-K 命中率

### 4.1 命中率（Hit Rate）指标回顾

Day 29 提到过 Hit Rate 的定义：对于一批"已知正确答案文档"的测试查询，检索结果的 Top-K 里是否包含了那篇正确文档：

```
Hit Rate@K = 命中的查询数 / 总查询数
（命中 = 正确文档出现在返回的 Top-K 结果里）
```

### 4.2 测试集设计与对比脚本

```python
# experiments/rerank_evaluation.py
EVAL_SET = [
    {"query": "退款需要多长时间到账", "gold_doc_id": "doc_042"},
    {"query": "产品保修期是多久", "gold_doc_id": "doc_017"},
    {"query": "如何修改收货地址", "gold_doc_id": "doc_088"},
    # ... 更多标注好正确文档的测试查询
]

def evaluate_hit_rate(eval_set, retrieve_fn, top_k: int = 5) -> float:
    hits = 0
    for case in eval_set:
        results = retrieve_fn(case["query"], top_k=top_k)
        retrieved_ids = {r["doc_id"] for r in results}
        if case["gold_doc_id"] in retrieved_ids:
            hits += 1
    return hits / len(eval_set)

# 对比：粗召回直接截断 Top-K vs 粗召回 + Reranker 精排后取 Top-K
def coarse_only(query, top_k):
    vector_results, bm25_results = hybrid_retriever.dual_search(query, top_k=50)
    return reciprocal_rank_fusion([vector_results, bm25_results], k=60)[:top_k]

def with_reranker(query, top_k):
    return two_stage_retrieve(query, hybrid_retriever, reranker, coarse_n=50, final_k=top_k)

hit_rate_before = evaluate_hit_rate(EVAL_SET, coarse_only, top_k=5)
hit_rate_after = evaluate_hit_rate(EVAL_SET, with_reranker, top_k=5)
print(f"加 Reranker 前 Hit Rate@5: {hit_rate_before:.2%}")
print(f"加 Reranker 后 Hit Rate@5: {hit_rate_after:.2%}")
```

### 4.3 结果分析

预期输出模式：

```
加 Reranker 前 Hit Rate@5: 68%
加 Reranker 后 Hit Rate@5: 84%
```

**为什么会提升**：粗召回阶段（向量+BM25+RRF）本身已经能把正确文档"捞进"Top-50 候选，但受限于 Bi-Encoder 的向量压缩和 RRF 融合的排名规则，正确文档未必排进最终返回的 Top-5；Reranker 用更精细的交互式打分重新排序这 50 个候选，能把粗召回阶段"排名靠后但其实相关"的正确文档重新拉到前面。**Reranker 提升的不是"能不能找到"，而是"排序准不准"**——如果正确文档在粗召回阶段就没进入 Top-N 候选，Reranker 也无能为力，这也是为什么粗召回阶段的 Top-N 要设置得足够大（覆盖率优先），精排阶段再收窄到最终需要的 Top-K（精度优先）。

---

## 五、Day 59 知识速查

### Bi-Encoder vs Cross-Encoder

```
Bi-Encoder（向量检索）：query/doc 独立编码，doc 可预计算，快但交互信息有损失
Cross-Encoder（Reranker）：query/doc 拼接编码，不可预计算，慢但交互信息充分，排序更准
```

### 两阶段检索设计

```
粗召回（快、便宜）：向量+BM25+RRF，覆盖优先，Top-N（如50）
   ↓
精排（慢、准）：Cross-Encoder 对 N 条候选重新打分，精度优先，Top-K（如5）
```

### Reranker 提升的本质

```
Reranker 解决的是"排序准不准"，不是"能不能找到"
如果正确文档没进粗召回的 Top-N，Reranker 无法挽救
→ 粗召回阶段的 N 要设置得足够大，覆盖率优先于速度
```

---

## 六、实践任务

- [ ] 用 `sentence-transformers` 加载 `BAAI/bge-reranker-base`（或 `cross-encoder/ms-marco-MiniLM-L-6-v2`），对一组 query-doc pair 跑一次打分，观察分数范围
- [ ] 实现 `Reranker.rerank()`，对 Day 58 混合检索返回的 Top-50 候选做二次排序
- [ ] 实现 `two_stage_retrieve()`，验证粗召回 + 精排的完整两阶段流程能跑通
- [ ] 标注至少 10 条测试查询及其"正确文档 ID"，构建 `EVAL_SET`
- [ ] 跑 `evaluate_hit_rate()`，对比"仅粗召回直接截断 Top-K" vs "粗召回+Reranker精排后取 Top-K"的 Hit Rate@K 差异

**产出标准**：一份 Top-K 命中率提升的对比数据（加 Reranker 前后的 Hit Rate@K），能说明 Reranker 在哪些 case 上把原本排名靠后的正确文档拉到了前面。

---

## 七、下一步预告

Day 60 进入**HyDE（假设文档 Embedding）**：今天的 Reranker 解决的是"候选文档排序不够准"的问题，HyDE 要解决的是另一类问题——**用户的查询本身和目标文档在表达方式上差异很大**（比如用户问"东西坏了怎么办"，但知识库文档写的是"产品质量问题处理流程"），这种情况下即使有 Reranker，粗召回阶段可能就已经因为查询和文档语义/措辞差距太大而没能把正确文档捞进候选池。HyDE 的思路是先让模型生成一个"假设的答案文档"，再用这个假设文档去检索，从"用问题找答案"变成"用假设答案找真答案"，缩小检索时的语义鸿沟。
