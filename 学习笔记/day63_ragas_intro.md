# Day 63：RAGAS 评估框架入门

> 学习目标：理解为什么"感觉答得不错"这种主观判断必须被量化指标替代；掌握 RAGAS 四个核心指标——忠实度（Faithfulness）、答案相关性（Answer Relevancy）、上下文精度（Context Precision）、上下文召回率（Context Recall）分别评估的是检索还是生成环节；给已有 RAG 系统跑一次 RAGAS 评估，产出一份能指出最弱环节的指标报表
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 63
>
> 🧭 导航：[← Day 62 · 第 10 周复盘](day62_week10_rag_optimization_review.md) → [Day 64 · 构建评估集与持续评估](day64_eval_set_and_continuous_evaluation.md)

---

## 目录

- [一、为什么"感觉答得不错"不够用](#一为什么感觉答得不错不够用)
  - [1.1 主观评估的三个问题](#11-主观评估的三个问题)
  - [1.2 RAGAS 是什么](#12-ragas-是什么)
- [二、四个核心指标详解](#二四个核心指标详解)
  - [2.1 忠实度（Faithfulness）](#21-忠实度faithfulness)
  - [2.2 答案相关性（Answer Relevancy）](#22-答案相关性answer-relevancy)
  - [2.3 上下文精度（Context Precision）](#23-上下文精度context-precision)
  - [2.4 上下文召回率（Context Recall）](#24-上下文召回率context-recall)
- [三、四指标对应 RAG 链路的哪个环节](#三四指标对应-rag-链路的哪个环节)
- [四、给已有 RAG 系统跑一次 RAGAS 评估](#四给已有-rag-系统跑一次-ragas-评估)
  - [4.1 安装与评估数据集格式](#41-安装与评估数据集格式)
  - [4.2 完整代码实现](#42-完整代码实现)
- [五、记录指标报表，定位最弱环节](#五记录指标报表定位最弱环节)
- [六、Day 63 知识速查](#六day-63-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么"感觉答得不错"不够用

### 1.1 主观评估的三个问题

Day 1–62 里评估 RAG 效果的方式基本都是"跑几个 case 看看回答像不像样"，这在早期验证阶段够用，但作为长期质量保障手段有三个根本问题：

| 问题 | 具体表现 |
|-----|---------|
| **不可复现** | "感觉答得不错"因人而异、因心情而异，两个人（甚至同一个人不同时间）对同一个回答的判断可能不一致 |
| **无法量化对比** | 改了一版 Prompt 或调整了 Chunk 切分参数，"感觉好像变好了"无法说清楚具体好了多少、是否在某些方面反而变差了 |
| **无法追踪回归** | 没有历史指标基线，无法在每次改动后自动判断"这次改动是不是引入了新的问题" |

### 1.2 RAGAS 是什么

RAGAS（Retrieval Augmented Generation Assessment）是专门为 RAG 系统设计的评估框架，核心思路是**用另一个 LLM 作为"评判者"（LLM-as-judge），针对问题、答案、检索到的上下文之间的关系，自动计算出可量化的分数**，替代人工主观判断：

```
传统评估：人工看几个 case，凭感觉判断"答得好不好"
RAGAS 评估：LLM 作为裁判，针对 (问题, 答案, 检索上下文) 三元组，
           从四个维度分别打分，输出 0-1 之间的量化指标
```

---

## 二、四个核心指标详解

### 2.1 忠实度（Faithfulness）

**衡量什么**：答案里的每一个论断，是否都能在检索到的上下文里找到依据，而不是模型凭空编造（幻觉）。

```
问题："退货运费谁承担？"
检索上下文："因产品质量问题退货的，运费由卖家承担；非质量问题退货，运费由买家承担。"
模型答案："因质量问题退货运费由卖家承担，退货有效期为 30 天。"
                                                ↑
                                    "30 天"这个信息在上下文里完全没有出现——这是幻觉

Faithfulness 会因为这句编造内容而被扣分
```

**计算思路**：把答案拆解成多个独立的论断（claim），逐一检查每个论断能否被上下文支撑，最终分数是"能被支撑的论断数 / 总论断数"。

### 2.2 答案相关性（Answer Relevancy）

**衡量什么**：答案是否切题地回应了用户的问题——即使答案完全忠实于上下文（没有幻觉），也可能跑题、啰嗦、没有真正回答问题本身。

```
问题："退货运费谁承担？"
答案："我们公司非常重视用户体验，退货政策的设计参考了行业标准……"（绕了一大圈没有直接回答）

Answer Relevancy 会因为答案没有切中问题核心而被扣分，
即使这段话里的每一句都是真实的（Faithfulness 可能很高）
```

**计算思路**：反向操作——让 LLM 根据答案反推出"这个答案可能在回答什么问题"，再和原始问题计算语义相似度，相似度越高说明答案越切题。

### 2.3 上下文精度（Context Precision）

**衡量什么**：检索到的上下文里，排在前面的内容是否都是真正有用的——这是一个**检索排序质量**的指标，不看生成结果。

```
检索到的 Top-3 上下文：
  ① "退货运费由谁承担的规定……"（相关）
  ② "公司成立于2010年……"（不相关，混进来的噪音）
  ③ "质量问题退货流程说明……"（相关）

Context Precision 会因为第②条不相关内容排在了相关内容之间而被扣分
```

**计算思路**：类似 Reranker 评估里的思路——检查每个检索位置上的内容是否相关，越靠前的位置命中相关内容，分数越高（体现了"位置越靠前权重越大"的排序质量要求）。

### 2.4 上下文召回率（Context Recall）

**衡量什么**：检索到的上下文，是否覆盖了**回答这个问题所需要的全部信息**——这是纯粹的**检索覆盖率**指标，需要依赖标注好的 `ground_truth`（标准答案）。

```
标准答案："质量问题退货运费由卖家承担，非质量问题由买家承担，退货时限为7天。"
检索到的上下文：只包含"运费承担规则"，完全没有提到"退货时限为7天"这条信息

Context Recall 会因为遗漏了标准答案里的部分信息而被扣分
——即使检索到的内容本身是准确的，只是不完整
```

**计算思路**：把标准答案拆解成多个信息点，检查每个信息点是否能在检索到的上下文里找到对应内容，分数是"能找到对应内容的信息点数 / 标准答案总信息点数"。

---

## 三、四指标对应 RAG 链路的哪个环节

| 指标 | 评估对象 | 对应环节 |
|-----|---------|---------|
| Faithfulness（忠实度） | 答案是否基于上下文，无编造 | **生成环节** |
| Answer Relevancy（答案相关性） | 答案是否切题回应了问题 | **生成环节** |
| Context Precision（上下文精度） | 检索到的上下文排序是否合理，无噪音靠前 | **检索环节** |
| Context Recall（上下文召回率） | 检索到的上下文是否覆盖了所需的全部信息 | **检索环节** |

```
生成环节两指标（Faithfulness / Answer Relevancy）
  → 对应 Day 19 的"只根据资料回答"约束、Day 11 的 Prompt 优化方法论

检索环节两指标（Context Precision / Context Recall）
  → 对应 Day 58–61 的混合检索/Reranker/HyDE/查询改写这一整周的优化手段
```

**这个分工的核心价值**：跑完一次 RAGAS 评估后，能立即知道"如果分数低的是检索环节两个指标，问题出在 Day 58–61 那一层；如果分数低的是生成环节两个指标，问题出在 Prompt 设计或生成约束"——不用凭感觉猜是哪个环节的问题，直接看是哪个指标低。

---

## 四、给已有 RAG 系统跑一次 RAGAS 评估

### 4.1 安装与评估数据集格式

```bash
pip install ragas datasets
```

RAGAS 需要的评估数据集是一个包含以下字段的结构：

```python
{
    "question": "退货运费谁承担？",
    "answer": "因质量问题退货运费由卖家承担",             # 系统生成的答案
    "contexts": ["因产品质量问题退货的，运费由卖家承担……"],  # 检索到的上下文列表
    "ground_truth": "质量问题退货运费由卖家承担，非质量问题由买家承担，退货时限为7天",  # 标注的标准答案
}
```

**注意**：`ground_truth` 只有 `context_recall` 指标需要，`faithfulness`/`answer_relevancy`/`context_precision` 不依赖标注，可以先跑这三项，标注工作量不足时先看这三个指标。

### 4.2 完整代码实现

```python
# evaluation/ragas_eval.py
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

def build_eval_dataset(rag_system, test_cases: list[dict]) -> Dataset:
    """test_cases: [{"question": ..., "ground_truth": ...}, ...]"""
    records = []
    for case in test_cases:
        result = rag_system.query(case["question"])   # 复用 Day 19 的 RAG 问答生成器
        records.append({
            "question": case["question"],
            "answer": result["answer"],
            "contexts": result["retrieved_contexts"],   # 本次检索到的原文列表
            "ground_truth": case["ground_truth"],
        })
    return Dataset.from_list(records)

def run_ragas_evaluation(rag_system, test_cases: list[dict]) -> dict:
    dataset = build_eval_dataset(rag_system, test_cases)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    return result.to_pandas()
```

```python
TEST_CASES = [
    {"question": "退货运费谁承担？", "ground_truth": "质量问题退货运费由卖家承担，非质量问题由买家承担，退货时限为7天"},
    {"question": "会员积分怎么兑换？", "ground_truth": "积分满1000可在积分商城兑换商品或抵扣现金，1积分=0.1元"},
    # ... 更多标注好的测试用例
]

report_df = run_ragas_evaluation(rag_system, TEST_CASES)
print(report_df[["faithfulness", "answer_relevancy", "context_precision", "context_recall"]].mean())
```

---

## 五、记录指标报表，定位最弱环节

**示例指标报表**：

| 指标 | 平均分 | 环节 |
|-----|-------|------|
| Faithfulness | 0.91 | 生成 |
| Answer Relevancy | 0.88 | 生成 |
| Context Precision | 0.72 | 检索 |
| Context Recall | 0.65 | 检索 |

**结果解读**：

```
生成环节两项指标（0.91 / 0.88）都不错，说明模型基本能忠实于上下文回答、且回答切题
检索环节两项指标明显更低（0.72 / 0.65），尤其 Context Recall 只有 0.65

结论：这个系统当前最弱的环节是检索——具体是"检索到的信息不够全"（Context Recall 低），
     而不是生成阶段的问题；下一步应该回到 Day 58–61 的检索优化手段
     （混合检索/Reranker/HyDE/查询改写）里针对性排查，而不是继续调 Prompt
```

**报表的价值**：如果没有这份量化报表，仅凭"感觉答得还行"，很容易把改进精力错误地投入到生成 Prompt 调优上（因为生成阶段的问题更直观、更容易被人工发现），而真正的短板（检索覆盖不全）反而被忽视——量化指标把"哪里最弱"这件事变得可验证。

---

## 六、Day 63 知识速查

### 四个核心指标速查

```
Faithfulness（忠实度）      → 生成 → 答案有没有编造上下文之外的内容
Answer Relevancy（答案相关性）→ 生成 → 答案有没有切题回答问题
Context Precision（上下文精度）→ 检索 → 检索结果排序里靠前的是否都相关
Context Recall（上下文召回率）→ 检索 → 检索结果是否覆盖了回答所需的全部信息
```

### 指标依赖关系

```
不需要 ground_truth：Faithfulness / Answer Relevancy / Context Precision
需要 ground_truth（标注标准答案）：Context Recall
标注资源有限时，可以先跑不需要标注的三项
```

### 定位问题环节的判断逻辑

```
生成两指标低 → 回到 Prompt 设计（Day 11/19）排查"只根据资料回答"约束是否到位
检索两指标低 → 回到 Day 58-61 的检索优化手段排查（混合检索/Reranker/HyDE/查询改写）
```

---

## 七、实践任务

- [ ] 安装 `ragas` 库，标注至少 5-10 条测试用例（问题 + 标准答案）
- [ ] 实现 `build_eval_dataset()`，让已有的 RAG 系统对这批测试用例分别生成答案和检索上下文
- [ ] 跑 `run_ragas_evaluation()`，记录四个指标的当前分数
- [ ] 对照 5.1 节的解读方法，判断当前系统最弱的环节是检索还是生成
- [ ] 针对识别出的最弱环节，写一段简短分析，说明接下来应该优先排查哪个具体手段（如"Context Recall 低 → 检查是否需要引入 Day 61 的多查询检索来扩大覆盖面"）

**产出标准**：一份包含四个指标当前值的报表，并能明确指出当前系统最弱的那个环节（检索还是生成，以及具体是哪个指标）。

---

## 八、下一步预告

Day 64 进入**构建评估集与持续评估**：今天只是"跑了一次"RAGAS 评估，得到一份静态的当前状态快照；Day 64 要把评估集正式沉淀下来（结合 Day 55 反馈追踪采集的低分回答清单扩充测试用例），并建立"每次改动后自动重新跑一遍评估"的流程，让 RAGAS 从"一次性体检"变成"持续追踪质量变化"的常规机制。
