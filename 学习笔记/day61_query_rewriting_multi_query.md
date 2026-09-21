# Day 61：查询改写与多查询检索

> 学习目标：区分 Query Rewriting（把模糊/口语化问题改写成更适合检索的表述）和 Multi-query Fusion（一个问题生成多个变体分别检索再合并）两种技术；给一个缺乏上下文的模糊问题实现查询改写和多查询扩展；对比改写前后的召回结果，说清楚改写解决了什么问题
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 61
>
> 🧭 导航：[← Day 60 · HyDE（假设文档 Embedding）](day60_hyde.md) → [Day 62 · 第 10 周复盘](day62_week10_rag_optimization_review.md)

---

## 目录

- [一、Query Rewriting 与 Multi-query Fusion 解决什么问题](#一query-rewriting-与-multi-query-fusion-解决什么问题)
  - [1.1 模糊问题的三类典型症状](#11-模糊问题的三类典型症状)
  - [1.2 Query Rewriting：改写成更适合检索的表述](#12-query-rewriting改写成更适合检索的表述)
  - [1.3 Multi-query Fusion：一个问题生成多个变体](#13-multi-query-fusion一个问题生成多个变体)
  - [1.4 和 HyDE 的区别](#14-和-hyde-的区别)
- [二、Query Rewriting 实现](#二query-rewriting-实现)
  - [2.1 结合对话历史的指代消解](#21-结合对话历史的指代消解)
  - [2.2 Prompt 设计与代码实现](#22-prompt-设计与代码实现)
- [三、Multi-query Fusion 实现](#三multi-query-fusion-实现)
  - [3.1 生成多个查询变体的 Prompt 设计](#31-生成多个查询变体的-prompt-设计)
  - [3.2 分别检索 + RRF 融合](#32-分别检索--rrf-融合)
- [四、完整实现：给模糊问题做改写 + 多查询扩展](#四完整实现给模糊问题做改写--多查询扩展)
- [五、对比实验：改写前后的召回结果](#五对比实验改写前后的召回结果)
- [六、Day 61 知识速查](#六day-61-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、Query Rewriting 与 Multi-query Fusion 解决什么问题

### 1.1 模糊问题的三类典型症状

真实用户提问经常不是"教科书式"的清晰查询，常见三类症状：

| 症状 | 示例 | 对检索的影响 |
|-----|------|-------------|
| **指代不明** | "那个东西怎么用"（"那个东西"指代什么，需要看对话历史才知道） | 检索系统拿到的是一句缺失主语的话，向量/关键词都无从匹配 |
| **信息不全** | "多久能到"（缺少"到"的是什么——退款？发货？换货？） | 检索锚点信息量太少，容易匹配到多个不相关话题 |
| **歧义/多义** | "费用怎么算"（可能问的是运费、服务费或退款手续费） | 检索结果可能覆盖了错误的费用类型 |

### 1.2 Query Rewriting：改写成更适合检索的表述

Query Rewriting 的思路是**在检索之前，先把原始问题改写成一个信息完整、消除指代和歧义的版本**，通常需要结合对话历史：

```
对话历史：
  用户：我买的这款蓝牙耳机没声音了
  助手：请问是完全没声音，还是只有一边耳机没声音？
  用户：那个东西怎么用           ← 原始问题，指代不明

改写后：
  "蓝牙耳机没声音时应该如何排查和使用"   ← 补全了"那个东西"指代的具体产品和场景
```

改写后的查询才真正携带了足够的信息量去检索知识库，这是**一对一**的转换——一个模糊问题改写成一个更清晰的问题。

### 1.3 Multi-query Fusion：一个问题生成多个变体

Multi-query Fusion 解决的是另一类问题：即使问题本身表述清晰，**单一的检索查询可能只覆盖了知识库文档措辞角度的一部分**，尤其在问题包含多个隐含子意图或可以从不同角度理解时：

```
原始问题："退货流程和运费谁承担"

生成的查询变体（一对多）：
  变体1："退货申请流程是什么"
  变体2："退货运费由谁承担"
  变体3："退货政策中关于运费的规定"
```

每个变体分别检索，再把多路结果用 Day 58 的 RRF 融合成一个排名——这样即使知识库把"退货流程"和"运费规定"分别写在两篇不同的文档里，也能通过不同变体分别命中，而不是被"退货流程和运费谁承担"这一句混合表述稀释掉检索信号。

### 1.4 和 HyDE 的区别

| 维度 | HyDE（Day 60） | Query Rewriting / Multi-query（Day 61） |
|-----|--------------|----------------------------------------|
| 改变的对象 | 检索锚点的**文体**（问题 → 假设答案） | 查询本身的**内容和数量**（模糊 → 清晰，一个 → 多个） |
| 解决的问题 | 问题和文档语言风格不同导致向量距离偏远 | 问题信息不全/指代不明/单一查询覆盖角度有限 |
| 输出形式 | 一段"假设性答案"文本 | 一个改写后的查询 或 多个查询变体 |

三者并不互斥，实际项目里可以叠加使用：先做 Query Rewriting 消除指代和歧义，再对改写后的清晰问题做 Multi-query 生成变体，每个变体也可以再套一层 HyDE——但要意识到每叠加一层都多一次 LLM 调用，需要权衡延迟和收益。

---

## 二、Query Rewriting 实现

### 2.1 结合对话历史的指代消解

改写必须能看到对话历史，否则无法知道"那个东西"具体指什么：

```python
# retrieval/query_rewriter.py
REWRITE_PROMPT = """根据下面的对话历史，把用户的最后一句话改写成一个信息完整、
适合用于知识库检索的独立问题。要求：
1. 消除指代（"这个""那个""它"等要替换成具体名词）
2. 补全被省略的上下文信息
3. 如果原问题已经清晰完整，直接返回原问题，不要画蛇添足

对话历史：
{history}

用户最后一句话：{last_message}

改写后的独立问题："""

def rewrite_query(history: list[dict], last_message: str) -> str:
    history_text = "\n".join(f"{h['role']}: {h['content']}" for h in history)
    prompt = REWRITE_PROMPT.format(history=history_text, last_message=last_message)
    return call_llm(prompt, temperature=0)
```

### 2.2 Prompt 设计与代码实现

```python
history = [
    {"role": "user", "content": "我买的这款蓝牙耳机没声音了"},
    {"role": "assistant", "content": "请问是完全没声音，还是只有一边耳机没声音？"},
]
last_message = "那个东西怎么用"

rewritten = rewrite_query(history, last_message)
print(rewritten)
# 输出示例："蓝牙耳机没声音时应该如何排查和使用"
```

**关键设计**：Prompt 里明确要求"如果原问题已经清晰完整，直接返回原问题"——避免对本来就清楚的问题做不必要的改写，改写引入的风险是**可能引入语义偏移**，不清晰的问题才值得承担这个风险。

---

## 三、Multi-query Fusion 实现

### 3.1 生成多个查询变体的 Prompt 设计

```python
MULTI_QUERY_PROMPT = """请针对下面这个问题，生成 3 个不同角度的检索查询变体，
每个变体聚焦问题里的一个子话题或用不同措辞表达。
只输出 3 行查询，不要编号、不要解释。

问题：{question}
"""

def generate_query_variants(question: str, n: int = 3) -> list[str]:
    prompt = MULTI_QUERY_PROMPT.format(question=question)
    response = call_llm(prompt, temperature=0.5)   # 需要一定多样性，温度不能是0
    variants = [line.strip() for line in response.strip().split("\n") if line.strip()]
    return variants[:n]
```

```python
variants = generate_query_variants("退货流程和运费谁承担")
# ['退货申请流程是什么', '退货运费由谁承担', '退货政策中关于运费的规定']
```

### 3.2 分别检索 + RRF 融合

```python
# retrieval/multi_query_retriever.py
def multi_query_retrieve(question: str, hybrid_retriever, top_k: int = 5) -> list[dict]:
    variants = generate_query_variants(question, n=3)
    all_queries = [question] + variants   # 原始问题也保留一路，避免改写丢失原意

    result_lists = []
    for q in all_queries:
        vector_results = hybrid_retriever.vector_store.search(q, top_k=20)
        result_lists.append(vector_results)

    fused = reciprocal_rank_fusion(result_lists, k=60)   # 复用 Day 58 的 RRF
    return fused[:top_k]
```

**关键设计**：`all_queries` 里保留了原始问题这一路，不是完全用变体替代原始问题——变体是"补充覆盖角度"，不是"替代原始意图"，避免生成的变体偏离原始问题本身的核心意图。

---

## 四、完整实现：给模糊问题做改写 + 多查询扩展

```python
# main.py
def enhanced_retrieve(history: list[dict], last_message: str, hybrid_retriever, top_k: int = 5):
    # Step 1: 先做 Query Rewriting，消除指代和信息不全
    rewritten = rewrite_query(history, last_message)

    # Step 2: 对改写后的清晰问题做 Multi-query 扩展
    results = multi_query_retrieve(rewritten, hybrid_retriever, top_k=top_k)

    return {"original": last_message, "rewritten": rewritten, "results": results}
```

```python
history = [
    {"role": "user", "content": "我上周下单的订单一直没有物流更新"},
]
last_message = "那个还要多久，费用能退吗"

output = enhanced_retrieve(history, last_message, hybrid_retriever)
print(f"原始问题: {output['original']}")
print(f"改写后: {output['rewritten']}")
# 改写后示例："订单物流长时间无更新时的处理时效，以及是否可以申请退款"
```

两个技术串联使用：**先改写解决"这句话说的是什么"，再多查询解决"从哪些角度去检索这个已经说清楚的问题"**——顺序不能反过来，如果先做 Multi-query 再改写，生成的变体会基于模糊指代的原始问题，变体本身也是模糊的。

---

## 五、对比实验：改写前后的召回结果

```python
# experiments/rewrite_comparison.py
def compare_before_after(history, last_message, hybrid_retriever, top_k=5):
    direct_results = hybrid_retriever.vector_store.search(last_message, top_k=top_k)

    enhanced = enhanced_retrieve(history, last_message, hybrid_retriever, top_k=top_k)

    print(f"原始问题直接检索: {[r['text'][:30] for r in direct_results]}")
    print(f"改写+多查询后检索: {[r['text'][:30] for r in enhanced['results']]}")
```

**典型对比记录**：

| 场景 | 直接用原始问题检索 | 改写 + 多查询后检索 |
|-----|------------------|-------------------|
| "那个东西怎么用"（缺失产品上下文） | 检索到大量不相关的"使用说明"类文档（因为不知道具体是什么产品） | 改写后明确了"蓝牙耳机"，命中了正确的故障排查文档 |
| "那个还要多久，费用能退吗"（一句话两个隐含子问题） | 只能模糊命中"退款"或"物流"其中一类，另一半意图被忽略 | 多查询变体分别覆盖"物流时效"和"退款政策"，两类文档都被召回 |

**结论**：Query Rewriting 解决的是"检索系统根本不知道问题在问什么"（指代不明、信息缺失），Multi-query Fusion 解决的是"问题问得清楚，但一次检索覆盖不全所有隐含子意图"——两类问题的症状不同，对应的解法也不同，实际项目里通常需要根据具体的模糊类型选择用哪一种（或两者都用）。

---

## 六、Day 61 知识速查

### 两种技术对比

```
Query Rewriting：一对一改写，解决指代不明/信息不全，需要结合对话历史
Multi-query Fusion：一对多生成变体，解决单一查询覆盖角度有限，用 RRF 融合多路结果
```

### 和 HyDE 的分工

```
HyDE           → 改变检索锚点的文体（问题 → 假设答案）
Query Rewriting → 改变查询内容本身（模糊 → 清晰）
Multi-query    → 改变查询数量（一个 → 多个角度）
三者可以叠加，但每叠加一层多一次 LLM 调用，需要权衡延迟和收益
```

### 使用顺序原则

```
先改写（解决"这句话在问什么"）→ 再多查询（解决"从哪些角度检索这个清晰问题"）
顺序不能颠倒：先多查询会基于模糊指代生成同样模糊的变体
```

### Multi-query 融合实现要点

```python
all_queries = [original_question] + variants   # 保留原始问题这一路，避免偏离原意
result_lists = [search(q) for q in all_queries]
fused = reciprocal_rank_fusion(result_lists, k=60)   # 复用 RRF，不需要额外设计融合逻辑
```

---

## 七、实践任务

- [ ] 实现 `rewrite_query()`，构造一个带对话历史的模糊问题（如"那个东西怎么用"），验证改写后的问题补全了指代信息
- [ ] 实现 `generate_query_variants()`，对一个包含多个隐含子问题的查询（如"退货流程和运费谁承担"）生成 3 个变体
- [ ] 实现 `multi_query_retrieve()`，验证多路检索结果能通过 RRF 正确融合
- [ ] 跑 `compare_before_after()`，记录至少 2 个模糊问题在"直接检索"和"改写+多查询"下的召回结果差异
- [ ] 分析对比结果，写清楚每个 case 里改写具体解决了"指代不明""信息不全"还是"覆盖角度不够"中的哪一类问题

**产出标准**：改写前后召回结果的对比记录，明确说清楚改写解决了什么问题（指代消解 / 信息补全 / 多角度覆盖），而不只是"效果变好了"。

---

## 八、下一步预告

Day 62 是**第 10 周复盘**：回顾 Day 58–61 这四天引入的检索优化技术——混合检索、Reranker、HyDE、查询改写/多查询——梳理它们分别在检索流程的哪个环节起作用、彼此如何组合成一条完整的检索增强管道，以及在什么样的项目规模下这些优化手段才值得投入（呼应 Day 52 对工程化能力的同类判断逻辑）。
