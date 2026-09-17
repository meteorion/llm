# Day 66：阶段项目整合（RAG 深化版）

> 学习目标：把 Day 58–65 积累的混合检索、Reranker、评估体系整合进 Day 20 的带引用 RAG 系统；理解 Agentic RAG 相比传统固定流程 RAG 的核心区别——用 LangGraph 条件边让 Agent 自主判断"是否需要检索、检索结果是否足够好、是否需要换查询词重试"；实现一个能演示"检索不够好 → 自动改写查询 → 再次检索 → 生成"完整循环的 LangGraph 图，并用 Day 64 的评估脚本对比整合前后的指标变化
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 66
>
> 🧭 导航：[← Day 65 · PDF / 表格 / 扫描件解析进阶](day65_advanced_document_parsing.md) → [Day 67 · 第 11 周复盘 + 深化阶段总结](day67_week11_review_and_deepening_summary.md)

---

## 目录

- [一、整合目标：Day 20 系统需要补齐什么](#一整合目标day-20-系统需要补齐什么)
  - [1.1 Day 20 原系统回顾](#11-day-20-原系统回顾)
  - [1.2 需要整合的能力清单](#12-需要整合的能力清单)
- [二、传统 RAG vs Agentic RAG](#二传统-rag-vs-agentic-rag)
  - [2.1 传统 RAG 的固定流程局限](#21-传统-rag-的固定流程局限)
  - [2.2 Agentic RAG 的核心思路](#22-agentic-rag-的核心思路)
- [三、Agentic RAG 的 LangGraph 设计](#三agentic-rag-的-langgraph-设计)
  - [3.1 节点设计](#31-节点设计)
  - [3.2 State 设计](#32-state-设计)
  - [3.3 grade_docs：判断检索结果是否合格](#33-grade_docs判断检索结果是否合格)
  - [3.4 循环终止条件](#34-循环终止条件)
  - [3.5 完整 LangGraph 代码实现](#35-完整-langgraph-代码实现)
- [四、把混合检索 + Reranker 整合进 retrieve 节点](#四把混合检索--reranker-整合进-retrieve-节点)
- [五、整合前后指标对比](#五整合前后指标对比)
- [六、升级版系统完整架构图](#六升级版系统完整架构图)
- [七、Day 66 知识速查](#七day-66-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、整合目标：Day 20 系统需要补齐什么

### 1.1 Day 20 原系统回顾

Day 20 的带引用 RAG 系统实现了"检索 → 生成 JSON 答案 → 引用校验 → 格式化展示"的完整链路，但检索环节还停留在 Day 18 的基础水平：**只用纯向量检索，固定检索一次，不管结果好不好都直接送进生成阶段**。

### 1.2 需要整合的能力清单

| 能力 | 对应 Day | 整合到系统的哪个环节 |
|-----|---------|-------------------|
| 混合检索（向量+BM25+RRF） | 58 | 替换 `retrieve` 节点的检索方式 |
| Reranker 精排 | 59 | `retrieve` 节点内部，粗召回后加一次精排 |
| RAGAS 评估体系 | 63–64 | 整合前后分别跑一次评估脚本，量化对比 |
| Agentic RAG 编排 | 66（今天） | 用 LangGraph 把检索环节从"固定一次"升级为"自主判断、按需重试" |

---

## 二、传统 RAG vs Agentic RAG

### 2.1 传统 RAG 的固定流程局限

```
用户问题 → 检索（固定一次）→ 生成答案

问题：不管这一次检索结果质量如何，都直接拿去生成
     如果检索到的文档根本不相关，模型要么被迫在不相关资料上"勉强回答"，
     要么触发 Day 19 的拒答机制——但拒答之前，其实还有机会"换个角度再查一次"
```

### 2.2 Agentic RAG 的核心思路

Agentic RAG 把检索这一步从"固定发生一次的机械步骤"，变成"Agent 可以自主判断、动态决策的环节"：

```
用户问题 → retrieve（检索）→ grade_docs（判断检索结果是否合格）
                                    │
                        合格 ────────┼──────── 不合格
                          │                        │
                      generate                rewrite_query
                     （生成答案）                    │
                                                  retrieve（用改写后的查询再检索一次）
                                                     │
                                              （回到 grade_docs 判断）
```

**核心设计**：`retrieve → grade_docs`（判断相关性）→ 若不足则 `rewrite_query → retrieve` 再试，达标则 `generate`——这是一个带条件边的循环图，复用了 Day 33-34 的 StateGraph 条件边路由能力，以及 Day 61 的 Query Rewriting 技术。

---

## 三、Agentic RAG 的 LangGraph 设计

### 3.1 节点设计

| 节点 | 职责 |
|-----|------|
| `retrieve` | 用混合检索+Reranker（Day 58-59）执行一次检索，返回候选文档 |
| `grade_docs` | 判断检索到的文档是否足够回答问题（不是路由函数，是一个真正执行判断逻辑的节点） |
| `rewrite_query` | 检索结果不合格时，用 Day 61 的 Query Rewriting 改写查询 |
| `generate` | 检索结果合格时，基于文档生成带引用的答案（复用 Day 20 的生成逻辑） |
| `route_after_grading`（条件边路由函数） | 根据 `grade_docs` 的判断结果，决定走 `generate` 还是 `rewrite_query` |

### 3.2 State 设计

```python
from typing import TypedDict

class AgenticRAGState(TypedDict):
    question: str              # 原始问题（不变）
    current_query: str         # 当前用于检索的查询（可能被改写过）
    retrieved_docs: list[dict] # 当前这一轮检索到的文档
    is_relevant: bool          # grade_docs 的判断结果
    retry_count: int           # 已重试次数，用于终止条件
    answer: str                # 最终生成的答案
```

### 3.3 grade_docs：判断检索结果是否合格

```python
GRADE_PROMPT = """判断下面这些检索到的文档片段，是否包含足够信息回答用户的问题。
只输出 JSON：{{"is_relevant": true/false, "reason": "..."}}

问题：{question}
检索到的文档：
{docs}
"""

def grade_docs(state: AgenticRAGState) -> dict:
    docs_text = "\n---\n".join(d["text"] for d in state["retrieved_docs"])
    prompt = GRADE_PROMPT.format(question=state["question"], docs=docs_text)
    result = json.loads(call_llm(prompt, temperature=0))
    return {"is_relevant": result["is_relevant"]}
```

**关键设计**：`grade_docs` 不是简单看"有没有检索到文档"，而是让 LLM 判断"检索到的内容能不能支撑回答这个具体问题"——即使检索到了 5 篇文档，如果都不相关，也应该判定为不合格，触发重试。

### 3.4 循环终止条件

和 Day 35 的双层终止保护思路一致，避免"改写-检索"陷入死循环：

```python
MAX_RETRY = 2

def route_after_grading(state: AgenticRAGState) -> str:
    if state["is_relevant"]:
        return "generate"
    if state["retry_count"] >= MAX_RETRY:
        return "generate"   # 达到重试上限，仍然生成（会触发 Day 19 的拒答机制）
    return "rewrite_query"
```

**关键点**：即使重试次数用完仍然不合格，也不是抛异常终止，而是照样进入 `generate`——因为 Day 20 的生成阶段本身已经有"资料不足则拒答"的机制，两层设计互相配合，不需要在图层面单独处理"彻底找不到"的情况。

### 3.5 完整 LangGraph 代码实现

```python
# agentic_rag/graph.py
from langgraph.graph import StateGraph, END

def retrieve(state: AgenticRAGState) -> dict:
    query = state["current_query"]
    docs = hybrid_retrieve_with_rerank(query, top_k=5)   # 见第四节，整合混合检索+Reranker
    return {"retrieved_docs": docs}

def rewrite_query(state: AgenticRAGState) -> dict:
    new_query = rewrite_for_retry(state["question"], state["current_query"], state["retrieved_docs"])
    return {"current_query": new_query, "retry_count": state["retry_count"] + 1}

def generate(state: AgenticRAGState) -> dict:
    answer = generate_answer_with_citation(state["question"], state["retrieved_docs"])   # 复用 Day 20
    return {"answer": answer}

builder = StateGraph(AgenticRAGState)
builder.add_node("retrieve", retrieve)
builder.add_node("grade_docs", grade_docs)
builder.add_node("rewrite_query", rewrite_query)
builder.add_node("generate", generate)

builder.set_entry_point("retrieve")
builder.add_edge("retrieve", "grade_docs")
builder.add_conditional_edges("grade_docs", route_after_grading,
                               {"generate": "generate", "rewrite_query": "rewrite_query"})
builder.add_edge("rewrite_query", "retrieve")   # 改写后回到检索，形成循环
builder.add_edge("generate", END)

graph = builder.compile()
```

```python
initial_state = {
    "question": "那个多久能到账",   # 故意用一个模糊问题触发重试
    "current_query": "那个多久能到账",
    "retrieved_docs": [],
    "is_relevant": False,
    "retry_count": 0,
    "answer": "",
}
result = graph.invoke(initial_state)
print(result["answer"])
```

**日志可观察性**：每次 `grade_docs` 和 `rewrite_query` 节点执行时打印判断结果和改写前后的查询，能在日志里清楚看到"第一次检索→判定不合格→改写为'退款到账时间说明'→第二次检索→判定合格→生成答案"的完整决策路径，这正是产出标准要求的"可观察的路由决策"。

---

## 四、把混合检索 + Reranker 整合进 retrieve 节点

```python
# agentic_rag/retrieval.py
def hybrid_retrieve_with_rerank(query: str, top_k: int = 5) -> list[dict]:
    # Day 58：混合检索粗召回
    vector_results = hybrid_retriever.vector_store.search(query, top_k=50)
    bm25_results = hybrid_retriever.bm25_retriever.search(query, top_k=50)
    fused = reciprocal_rank_fusion([vector_results, bm25_results], k=60)[:50]

    # Day 59：Reranker 精排
    reranked = reranker.rerank(query, fused, top_k=top_k)
    return reranked
```

**整合方式**：`retrieve` 节点内部就是 Day 58-59 已经实现好的两阶段检索流程，不需要重新设计，只是把它包装成 LangGraph 的一个 Node 函数——这体现了"框架负责编排，具体能力模块保持独立复用"的设计原则。

---

## 五、整合前后指标对比

用 Day 64 的评估脚本，分别对"Day 20 原系统（纯向量检索+固定单次检索）"和"今天的升级版（混合检索+Reranker+Agentic 重试）"跑一次评估：

```python
report_before = run_full_evaluation(day20_rag_system, EVAL_SET)
report_after = run_full_evaluation(agentic_rag_system, EVAL_SET)

for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
    before = report_before["ragas_scores"][metric]
    after = report_after["ragas_scores"][metric]
    print(f"{metric}: {before:.3f} → {after:.3f} ({after - before:+.3f})")
```

**预期对比结果**：

| 指标 | 整合前（Day 20） | 整合后（今天） | 变化 |
|-----|-----------------|--------------|------|
| Faithfulness | 0.85 | 0.90 | +0.05 |
| Answer Relevancy | 0.80 | 0.87 | +0.07 |
| Context Precision | 0.68 | 0.79 | +0.11 |
| Context Recall | 0.62 | 0.81 | +0.19 |

**结果解读**：检索环节两个指标（Context Precision / Context Recall）提升幅度明显大于生成环节两个指标——这符合预期，因为今天的整合主要动作是升级检索方式（混合检索+Reranker+Agentic重试），并没有改动生成阶段的 Prompt；生成环节指标的提升是**检索质量提升的间接结果**（喂给模型的资料更准确、更全，生成的答案自然更忠实、更切题）。

---

## 六、升级版系统完整架构图

```
用户问题
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              Agentic RAG（LangGraph）                 │
│                                                       │
│   retrieve ──► grade_docs ──合格──► generate ──► END  │
│      ▲              │                                │
│      │           不合格                               │
│      │              ▼                                │
│      └────── rewrite_query（Day 61 Query Rewriting）  │
│                                                       │
│   retrieve 内部：混合检索(Day58) + Reranker精排(Day59)  │
│   generate 内部：Day 20 带引用生成 + 校验               │
└─────────────────────────────────────────────────────┘
    │
    ▼
评估体系（Day 63-64 RAGAS + 评估集）持续验证整合效果
```

---

## 七、Day 66 知识速查

### 传统 RAG vs Agentic RAG

```
传统 RAG：检索固定发生一次，不管质量好坏直接送去生成
Agentic RAG：retrieve → grade_docs 判断 → 不合格则 rewrite_query → retrieve 循环，合格才 generate
```

### Agentic RAG 图节点速查

| 节点 | 职责 |
|-----|------|
| retrieve | 混合检索+Reranker 执行一次检索 |
| grade_docs | LLM 判断检索结果是否足够回答问题 |
| rewrite_query | 不合格时改写查询（复用 Day 61） |
| generate | 合格后生成带引用答案（复用 Day 20） |

### 终止条件设计

```
MAX_RETRY 上限 + 达到上限仍不合格也照常进入 generate
（依赖 Day 20 生成阶段自身的拒答机制兜底，图层面不需要单独处理"彻底找不到"的情况）
```

---

## 八、实践任务

- [ ] 把 Day 20 系统的检索环节替换成 Day 58-59 的混合检索+Reranker 两阶段检索
- [ ] 实现 `AgenticRAGState` 和四个节点函数，用 LangGraph 把它们编排成带条件边的循环图
- [ ] 用一个故意模糊的问题（如"那个多久能到账"）跑一次，验证图能演示"检索不合格→改写→再检索→生成"的完整循环
- [ ] 打印每个节点的执行日志，确认能清楚看到路由决策路径
- [ ] 用 Day 64 的评估脚本，分别对整合前（Day 20 原系统）和整合后跑一次评估，记录四个指标的变化

**产出标准**：一个升级版 RAG 系统 + 整合前后的 RAGAS 指标对比；一个 Agentic RAG 的 LangGraph 图，能演示"检索结果不够好 → 自动改写查询 → 再次检索 → 生成"的完整循环，并在日志里可观察到每次的路由决策。

---

## 九、下一步预告

Day 67 是**第 11 周复盘 + 深化阶段总结**：回顾整个深化阶段（Day 31-66）走过的 A（LangChain/LangGraph/Agent）→ C（生产部署）→ B（RAG 优化）三条路线，评估哪条路线对当前项目提升最明显，并对整个 37 天的深化阶段做一次收尾总结，为后续继续深入（第四阶段：部署与模型定制）或转向新方向做准备。
