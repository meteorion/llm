# Day 58：混合检索（向量 + BM25）

> 学习目标：理解稠密检索（向量相似度）和稀疏检索（BM25 关键词匹配）各自擅长什么、为什么互补；给 Day 18 的向量检索加一路 BM25 检索；用 RRF（Reciprocal Rank Fusion）把两路结果融合成一个排名；对比"纯向量"和"混合检索"在含专有名词/术语类问题上的召回差异
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 58
>
> 🧭 导航：[← Day 57 · 阶段项目整合 + 第 9 周复盘](day57_route_c_integration_review.md) → [Day 59 · Reranker 重排序](day59_reranker.md)

---

## 目录

- [一、稠密检索 vs 稀疏检索](#一稠密检索-vs-稀疏检索)
  - [1.1 向量检索（稠密）擅长什么](#11-向量检索稠密擅长什么)
  - [1.2 BM25（稀疏）擅长什么](#12-bm25稀疏擅长什么)
  - [1.3 为什么两者互补而不是二选一](#13-为什么两者互补而不是二选一)
- [二、BM25 算法原理与实现](#二bm25-算法原理与实现)
  - [2.1 从 TF-IDF 到 BM25：解决了什么问题](#21-从-tf-idf-到-bm25解决了什么问题)
  - [2.2 用 rank_bm25 实现关键词检索](#22-用-rank_bm25-实现关键词检索)
- [三、给 Day 18 向量检索加一路 BM25 检索](#三给-day-18-向量检索加一路-bm25-检索)
  - [3.1 构建 BM25 索引](#31-构建-bm25-索引)
  - [3.2 两路检索并行执行](#32-两路检索并行执行)
- [四、融合排序：把两路结果合并成一个排名](#四融合排序把两路结果合并成一个排名)
  - [4.1 简单加权融合的坑：分数量纲不同](#41-简单加权融合的坑分数量纲不同)
  - [4.2 RRF（Reciprocal Rank Fusion）：只依赖排名，不依赖分数](#42-rrfreciprocal-rank-fusion只依赖排名不依赖分数)
- [五、对比实验：纯向量 vs 混合检索](#五对比实验纯向量-vs-混合检索)
- [六、Day 58 知识速查](#六day-58-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、稠密检索 vs 稀疏检索

### 1.1 向量检索（稠密）擅长什么

Day 18 实现的向量检索本质是**语义相似度匹配**——把文本编码成稠密向量，向量空间里距离近的文本语义相近，即使措辞完全不同：

```
查询："公司如何处理员工离职"
向量检索能命中："员工解除劳动合同的流程说明"（措辞不同，语义相近）
```

**擅长场景**：查询和文档措辞不同但语义相关、同义词/近义词、跨语言（如果用多语言 Embedding 模型）。

### 1.2 BM25（稀疏）擅长什么

BM25 是关键词匹配算法，本质是**精确词汇匹配 + 词频统计**，不理解语义，只看词是否出现：

```
查询："产品型号 XJ-2024 的保修期是多久"
BM25 能精确命中包含 "XJ-2024" 字符串的文档
向量检索可能因为 "XJ-2024" 是稀有 token，Embedding 没有学到它的准确语义而检索不准
```

**擅长场景**：专有名词、产品型号、错误代码、人名地名、缩写这类**必须精确匹配**、语义模型未必学得好的内容。

### 1.3 为什么两者互补而不是二选一

| 维度 | 向量检索（稠密） | BM25（稀疏） |
|-----|----------------|-------------|
| 匹配方式 | 语义相似度 | 关键词精确匹配 |
| 擅长 | 同义改写、跨表达方式的语义关联 | 专有名词、编号、精确术语 |
| 弱点 | 对生僻词/专有名词的向量表示不够精确，容易检索不到 | 无法理解"离职"和"解除劳动合同"是同一件事 |
| 计算方式 | 向量相似度（余弦/内积） | 词频统计 + 逆文档频率加权 |

**一句话总结**：向量检索负责"意思一样但说法不同"，BM25 负责"必须原文精确出现"——真实业务场景里这两类查询同时存在，只用一种检索方式必然在另一类查询上表现差，这正是"混合检索"要解决的问题。

---

## 二、BM25 算法原理与实现

### 2.1 从 TF-IDF 到 BM25：解决了什么问题

TF-IDF 的核心思想是"词在这篇文档里出现得越多、在所有文档里出现得越少，就越重要"，但有一个缺陷：**词频的重要性是无上限线性增长的**——一个词出现 100 次不该被认为比出现 10 次重要 10 倍。BM25 在 TF-IDF 基础上做了两个关键改进：

```
词频饱和（Term Frequency Saturation）：
  词频对得分的贡献存在上限，出现次数超过一定阈值后，继续增加不再显著提升得分

文档长度归一化：
  长文档天然包含更多词，容易"意外命中"更多查询词
  BM25 用文档长度相对平均长度的比例做归一化，避免长文档unfair地占优
```

BM25 公式（了解思路即可，不需要手推）：

```
score(D, Q) = Σ IDF(qi) × [f(qi, D) × (k1 + 1)] / [f(qi, D) + k1 × (1 - b + b × |D|/avgdl)]

f(qi, D)  : 词 qi 在文档 D 中的词频
|D|       : 文档 D 的长度，avgdl 是所有文档的平均长度
k1        : 控制词频饱和速度的参数（通常取 1.2-2.0）
b         : 控制文档长度归一化强度的参数（通常取 0.75）
```

### 2.2 用 rank_bm25 实现关键词检索

```python
# retrieval/bm25_retriever.py
from rank_bm25 import BM25Okapi
import jieba

def tokenize(text: str) -> list[str]:
    """中文需要先分词，BM25 本身只处理词元序列"""
    return list(jieba.cut(text))

class BM25Retriever:
    def __init__(self, documents: list[str]):
        self.documents = documents
        self.tokenized_corpus = [tokenize(doc) for doc in documents]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [{"text": self.documents[i], "score": scores[i]} for i in ranked_idx]
```

```python
retriever = BM25Retriever(documents=chunks)
results = retriever.search("产品型号 XJ-2024 的保修期是多久")
for r in results:
    print(f"score={r['score']:.2f}  {r['text'][:50]}")
```

---

## 三、给 Day 18 向量检索加一路 BM25 检索

### 3.1 构建 BM25 索引

复用 Day 17 切分好的 chunk 列表，构建一个和向量索引平行的 BM25 索引：

```python
# retrieval/hybrid_retriever.py
from retrieval.bm25_retriever import BM25Retriever
# vector_store 是 Day 18 已经构建好的 Chroma/FAISS 检索器

class HybridRetriever:
    def __init__(self, chunks: list[str], vector_store):
        self.vector_store = vector_store       # Day 18 的向量检索
        self.bm25_retriever = BM25Retriever(chunks)   # 今天新加的关键词检索
```

**关键点**：两路检索基于**同一批 chunk**建索引，保证融合时引用的是同一个文档集合，不会出现"向量库有但 BM25 库没有"的不一致。

### 3.2 两路检索并行执行

```python
def dual_search(self, query: str, top_k: int = 10) -> tuple[list[dict], list[dict]]:
    vector_results = self.vector_store.search(query, top_k=top_k)   # 稠密检索结果（按相似度排序）
    bm25_results = self.bm25_retriever.search(query, top_k=top_k)   # 稀疏检索结果（按 BM25 分数排序）
    return vector_results, bm25_results
```

两路检索互相独立，谁也不依赖谁的结果，可以并行执行（如果是远程向量库，可以用 `asyncio.gather` 并发发起两个请求，复用 Day 46 批处理的并发思路）。

---

## 四、融合排序：把两路结果合并成一个排名

### 4.1 简单加权融合的坑：分数量纲不同

最直接的想法是把两路分数加权相加：`final_score = 0.5 * vector_score + 0.5 * bm25_score`，但这样做有一个根本问题：**向量相似度分数（通常 0-1 之间）和 BM25 分数（理论上无上限，取决于词频和文档集合规模）完全不是同一个量纲**，直接相加会导致其中一路分数系统性地主导融合结果，而不是真正意义上的"各占一半权重"。

```
向量相似度: 0.82, 0.79, 0.75 ...（天然落在 0-1 区间）
BM25 分数:  12.3, 8.7, 5.2 ...（数值范围完全不同，且随语料库变化）

直接相加：0.5×0.82 + 0.5×12.3 = 6.56 —— BM25 分数把向量分数的影响完全淹没了
```

### 4.2 RRF（Reciprocal Rank Fusion）：只依赖排名，不依赖分数

RRF 的思路是**抛弃原始分数，只用排名**——不管两路检索的分数量纲差多远，只看"这篇文档在各自结果里排第几名"：

```
RRF_score(d) = Σ 1 / (k + rank_i(d))

d       : 某篇候选文档
rank_i(d): 文档 d 在第 i 路检索结果里的排名（从 1 开始，未出现则不计入该路）
k       : 平滑常数，通常取 60（经验值，避免排名靠前的文档分数过度陡峭）
```

```python
# retrieval/rrf_fusion.py
def reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """result_lists: 多路检索结果，每路已按相关度降序排列，dict 至少包含 'text' 字段"""
    scores: dict[str, float] = {}
    doc_lookup: dict[str, dict] = {}

    for results in result_lists:
        for rank, doc in enumerate(results, start=1):
            key = doc["text"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            doc_lookup[key] = doc

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{"text": text, "rrf_score": score, **{k_: v for k_, v in doc_lookup[text].items() if k_ != "text"}}
             for text, score in fused]
```

```python
vector_results, bm25_results = hybrid_retriever.dual_search("产品型号 XJ-2024 的保修期是多久")
fused_results = reciprocal_rank_fusion([vector_results, bm25_results], k=60)
top_docs = fused_results[:5]
```

**为什么 RRF 是更稳妥的默认选择**：它不需要对两路分数做归一化、不需要调权重比例，只要每一路检索结果内部排序合理，融合结果就是合理的——这是混合检索里最简单也最鲁棒的融合方式，工业界（如 Elasticsearch 8.x 的 RRF 支持）也采用同样的思路。

---

## 五、对比实验：纯向量 vs 混合检索

```python
# experiments/compare_retrieval.py
TEST_QUERIES = [
    {"query": "员工离职需要办理哪些手续", "type": "semantic"},          # 语义类：向量检索应该更擅长
    {"query": "产品型号 XJ-2024 的保修期是多久", "type": "exact_term"}, # 精确术语类：BM25 应该更擅长
    {"query": "错误代码 E-4021 是什么意思", "type": "exact_term"},
    {"query": "公司对加班怎么规定的", "type": "semantic"},
]

def compare(hybrid_retriever, queries: list[dict]):
    for q in queries:
        vector_only = hybrid_retriever.vector_store.search(q["query"], top_k=3)
        vec_res, bm25_res = hybrid_retriever.dual_search(q["query"], top_k=10)
        hybrid = reciprocal_rank_fusion([vec_res, bm25_res], k=60)[:3]

        print(f"\n查询: {q['query']} ({q['type']})")
        print(f"  纯向量 Top3: {[r['text'][:20] for r in vector_only]}")
        print(f"  混合检索 Top3: {[r['text'][:20] for r in hybrid]}")
```

**典型结果模式**：

| 查询类型 | 纯向量检索表现 | 混合检索表现 |
|---------|--------------|-------------|
| 语义类（"员工离职需要办理哪些手续"） | 通常已经能命中相关文档 | 和纯向量结果基本一致，提升不明显 |
| 精确术语类（"产品型号 XJ-2024"） | 容易检索不到包含准确型号的文档（Embedding 对稀有 token 表示不够精确） | BM25 那一路能精确命中包含 "XJ-2024" 字符串的文档，融合后排名靠前 |

**结论**：混合检索的价值主要体现在**包含专有名词、型号、错误代码、编号这类精确匹配需求**的查询上；对纯语义类查询，混合检索不会带来明显提升（甚至因为 BM25 那一路噪音可能轻微拉低融合排名），这也是为什么"要不要上混合检索"要看业务里这类精确匹配查询的比例。

---

## 六、Day 58 知识速查

### 稠密 vs 稀疏检索对比

```
向量检索（稠密）：语义相似度匹配，擅长同义改写/跨表达方式
BM25（稀疏）：关键词精确匹配，擅长专有名词/型号/错误代码/编号
```

### BM25 相比 TF-IDF 的两个改进

```
词频饱和：词频对得分的贡献有上限，不是无限线性增长
文档长度归一化：用 |D|/avgdl 调整，避免长文档天然占优
```

### 融合排序选型

| 方式 | 优点 | 缺点 |
|-----|------|------|
| 加权分数融合 | 直观 | 两路分数量纲不同，需要归一化，调参麻烦 |
| RRF | 只依赖排名，不需要归一化，鲁棒性好 | 丢失了原始分数的绝对差异信息 |

**默认选择 RRF**，除非有明确理由需要保留分数的绝对量级信息。

---

## 七、实践任务

- [ ] 用 `rank_bm25` 给 Day 17 的 chunk 列表建一个 BM25 索引，跑几个包含专有名词的查询，观察命中效果
- [ ] 实现 `HybridRetriever.dual_search()`，验证向量检索和 BM25 检索能分别独立返回结果
- [ ] 实现 `reciprocal_rank_fusion()`，用两路假结果验证融合排序的正确性（手算一个小例子核对）
- [ ] 构造至少 4 个测试查询（2 个语义类 + 2 个精确术语类），对比"纯向量" vs "混合检索"的 Top3 结果
- [ ] 记录一份对比数据表：哪些查询混合检索明显更好，哪些没有明显差异，形成"什么时候该上混合检索"的判断依据

**产出标准**：一份对比数据，明确指出混合检索在含专有名词/精确术语的问题上相比纯向量检索的提升，以及在纯语义类问题上两者差异不大的结论。

---

## 八、下一步预告

Day 59 进入**Reranker 重排序**：今天的混合检索解决的是"召回阶段"的问题——尽量把相关文档从大量候选里捞出来；但召回阶段为了效率通常牺牲了精度（向量相似度和 BM25 分数都是"粗排"）。Day 59 要在这批粗排候选之上加一层 Cross-Encoder 精排，用更贵但更准的模型对 Top-N 候选重新打分排序，这是"先粗召回、再精排"两阶段检索设计的第二步。
