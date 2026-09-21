# Day 64：构建评估集与持续评估

> 学习目标：把 Day 63 的"跑一次 RAGAS"固化成可重复运行的评估资产；手写 20 条覆盖能回答/边界情况/超出资料范围三类的评估问题，构造"问题+标准答案+标准引用来源"三元组；写一个可重复运行的评估脚本，建立基准报表，让后续每次改动都能快速回归对比
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 64
>
> 🧭 导航：[← Day 63 · RAGAS 评估框架入门](day63_ragas_intro.md) → [Day 65 · PDF / 表格 / 扫描件解析进阶](day65_advanced_document_parsing.md)

---

## 目录

- [一、为什么要把评估集固化成资产](#一为什么要把评估集固化成资产)
  - [1.1 Day 63 的"跑一次"和今天的"持续评估"的区别](#11-day-63-的跑一次和今天的持续评估的区别)
  - [1.2 评估集的三个价值](#12-评估集的三个价值)
- [二、构造"问题 + 标准答案 + 标准引用来源"三元组](#二构造问题--标准答案--标准引用来源三元组)
  - [2.1 三元组结构设计](#21-三元组结构设计)
  - [2.2 覆盖三类 Case](#22-覆盖三类-case)
  - [2.3 优先把真实失败 Case 纳入评估集](#23-优先把真实失败-case-纳入评估集)
- [三、20 条评估问题设计示例](#三20-条评估问题设计示例)
- [四、离线评估流程化](#四离线评估流程化)
  - [4.1 评估脚本设计](#41-评估脚本设计)
  - [4.2 基准报表的保存与版本管理](#42-基准报表的保存与版本管理)
  - [4.3 拒答类 Case 的特殊评估方式](#43-拒答类-case-的特殊评估方式)
- [五、完整实现](#五完整实现)
- [六、Day 64 知识速查](#六day-64-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么要把评估集固化成资产

### 1.1 Day 63 的"跑一次"和今天的"持续评估"的区别

Day 63 演示的是"临时凑几条测试用例，跑一次 RAGAS 看当前分数"——这解决了"有没有量化指标"的问题，但还不是一个可长期使用的工程资产：

| 维度 | Day 63 的"跑一次" | Day 64 的"持续评估" |
|-----|------------------|---------------------|
| 测试用例 | 临时凑的几条 | 固定沉淀的 20 条，覆盖三类场景 |
| 运行方式 | 手动跑一次脚本看结果 | 可重复运行的脚本，每次改动后都能跑 |
| 结果记录 | 看完就丢，下次改动无从对比 | 有基准报表，每次运行都能和基准对比 |

### 1.2 评估集的三个价值

```
基准对比：有了固定的评估集和基准报表，才能说清楚"这次改动让 Context Recall 从 0.65 提升到 0.78"
          而不是"感觉好像好一点"

回归检测：改了 Chunk 切分参数或 Prompt 后，重跑评估集，
          如果发现某类 case 的分数突然下降，能第一时间发现"这次改动引入了新问题"

持续追踪：随着 Day 55 反馈追踪采集到新的低分 case，评估集本身也会持续扩充，
          让评估集越来越贴近真实使用中暴露出的问题，而不是停留在开发者主观设想的测试场景
```

---

## 二、构造"问题 + 标准答案 + 标准引用来源"三元组

### 2.1 三元组结构设计

```python
from dataclasses import dataclass

@dataclass
class EvalCase:
    case_id: str
    question: str
    ground_truth_answer: str        # 标准答案，供 Context Recall / 人工核对使用
    ground_truth_sources: list[str] # 标准答案应该来自哪些文档片段（用于校验检索是否命中正确来源）
    category: str                   # answerable / boundary / out_of_scope
```

`ground_truth_sources` 是这个三元组比 Day 63 单纯的"问题+标准答案"多出的一环——它不仅告诉系统"应该答成什么样"，还告诉系统"应该基于哪些文档回答"，这样即使系统给出的答案表述不同但内容正确，也能通过检查"是否命中了正确的来源文档"来验证检索环节的准确性，而不只是靠生成答案的语义相似度判断。

### 2.2 覆盖三类 Case

| 类别 | 含义 | 评估目的 |
|-----|------|---------|
| **answerable（能回答）** | 知识库里有明确答案，系统应该准确回答 | 验证正常场景下的检索和生成质量 |
| **boundary（边界情况）** | 问题部分模糊、信息不全、或答案分散在多篇文档里 | 验证系统在信息不完整时的稳健性（不臆造、不遗漏） |
| **out_of_scope（超出资料范围）** | 知识库里根本没有相关信息 | 验证 Day 19 的"无资料拒答"机制是否生效，系统不应该编造答案 |

**三类缺一不可**：只测 answerable 类会让评估集看起来分数很高但掩盖了系统在边界和拒答场景下的真实短板——这正是"只跑几个顺利 case 就以为系统很好"的常见误区。

### 2.3 优先把真实失败 Case 纳入评估集

```python
# 结合 Day 55 的低分回答清单，把真实失败过的 case 转化成评估用例
def build_eval_case_from_feedback(low_score_record: dict) -> EvalCase:
    return EvalCase(
        case_id=f"regression_{low_score_record['trace_id']}",
        question=low_score_record["user_input"],
        ground_truth_answer="",   # 需要人工补充标注正确答案
        ground_truth_sources=[],  # 需要人工补充标注正确来源
        category="answerable",    # 按实际情况分类
    )
```

**这是评估集持续演进的关键机制**：不是一次性写完 20 条就结束，而是把 Day 55 反馈追踪发现的真实失败 case 持续转化成评估用例——这样评估集会越来越贴近生产环境真实暴露出的问题模式，而不是永远停留在开发者最初设想的几种场景。

---

## 三、20 条评估问题设计示例

```python
EVAL_SET = [
    # ── answerable（10 条，覆盖核心业务场景）──
    EvalCase("a01", "退货运费谁承担？", "质量问题退货运费由卖家承担，非质量问题由买家承担",
              ["退货政策-运费条款"], "answerable"),
    EvalCase("a02", "会员积分怎么兑换？", "积分满1000可在积分商城兑换商品或抵扣现金",
              ["会员积分规则"], "answerable"),
    EvalCase("a03", "产品保修期是多久？", "保修期为购买之日起12个月",
              ["产品保修条款"], "answerable"),
    # ...（共10条，覆盖不同业务模块）

    # ── boundary（6 条，边界情况）──
    EvalCase("b01", "退货流程和运费谁承担", "退货流程分四步：申请→审核→寄回→到账；运费规则见上",
              ["退货流程说明", "退货政策-运费条款"], "boundary"),   # 答案分散在两篇文档
    EvalCase("b02", "那个多久能到账", "（缺少上下文，应结合对话历史判断具体指什么）",
              [], "boundary"),   # 依赖对话历史的模糊问题
    # ...（共6条，覆盖信息分散/指代不明/部分信息缺失）

    # ── out_of_scope（4 条，超出资料范围）──
    EvalCase("o01", "你们支持火星发货吗？", "（应礼貌拒答，说明不支持或无相关信息）",
              [], "out_of_scope"),
    EvalCase("o02", "公司今年营收多少？", "（应礼貌拒答，知识库不包含财务信息）",
              [], "out_of_scope"),
    # ...（共4条，覆盖知识库完全没有覆盖的话题）
]
```

**比例设计参考**：10 条 answerable（覆盖核心业务场景，保证基本盘）+ 6 条 boundary（暴露系统在模糊/分散信息场景下的短板）+ 4 条 out_of_scope（验证拒答机制），总数 20 条，覆盖了 Day 62 复盘时提到的"召回不到""排序不准"以及生成环节"是否老实拒答"的多个维度。

---

## 四、离线评估流程化

### 4.1 评估脚本设计

```python
# evaluation/regression_eval.py
import json
from datetime import datetime

def run_full_evaluation(rag_system, eval_set: list[EvalCase]) -> dict:
    answerable_cases = [c for c in eval_set if c.category == "answerable"]
    boundary_cases = [c for c in eval_set if c.category == "boundary"]
    out_of_scope_cases = [c for c in eval_set if c.category == "out_of_scope"]

    # answerable / boundary 用 RAGAS 四指标评估
    ragas_dataset = build_eval_dataset(rag_system, answerable_cases + boundary_cases)
    ragas_scores = evaluate(ragas_dataset, metrics=[faithfulness, answer_relevancy,
                                                      context_precision, context_recall])

    # out_of_scope 用专门的"是否正确拒答"规则评估（不适用 RAGAS 四指标）
    refusal_accuracy = evaluate_refusal(rag_system, out_of_scope_cases)

    return {
        "timestamp": None,   # 运行时由调用方传入实际时间戳，脚本本身不生成时间
        "ragas_scores": ragas_scores.to_pandas().mean().to_dict(),
        "refusal_accuracy": refusal_accuracy,
        "total_cases": len(eval_set),
    }

def evaluate_refusal(rag_system, cases: list[EvalCase]) -> float:
    """超出资料范围的问题，检查系统是否老实拒答而非编造"""
    correct = 0
    for case in cases:
        result = rag_system.query(case.question)
        if is_refusal_response(result["answer"]):   # 检查回答里是否包含拒答特征（复用 Day 19 的拒答判断逻辑）
            correct += 1
    return correct / len(cases)
```

### 4.2 基准报表的保存与版本管理

```python
def save_baseline(report: dict, version_tag: str, baseline_dir: str = "eval_baselines"):
    filepath = f"{baseline_dir}/baseline_{version_tag}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

def compare_with_baseline(current: dict, baseline_path: str) -> dict:
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    diffs = {}
    for metric, value in current["ragas_scores"].items():
        baseline_value = baseline["ragas_scores"].get(metric, 0)
        diffs[metric] = round(value - baseline_value, 4)
    diffs["refusal_accuracy"] = round(current["refusal_accuracy"] - baseline["refusal_accuracy"], 4)
    return diffs
```

**版本管理原则**：每次做了一轮明确的优化（比如接入了 Day 58 的混合检索），跑完评估后把这次的报表存成一个新的基准文件（用版本标签命名，如 `baseline_v2_hybrid_retrieval.json`），下次改动后和最近的基准对比——这样能清楚追溯"哪次改动带来了哪些指标的变化"。

### 4.3 拒答类 Case 的特殊评估方式

`out_of_scope` 类 case 不适合用标准的 RAGAS 四指标评估——因为这类问题本身就没有"标准答案"和"标准来源"，评估的核心是"系统有没有老实说不知道"，而不是"答案内容准不准确"：

```python
REFUSAL_KEYWORDS = ["不支持", "没有相关信息", "无法回答", "超出", "暂不清楚"]

def is_refusal_response(answer: str) -> bool:
    return any(kw in answer for kw in REFUSAL_KEYWORDS)
```

这是一个独立于 RAGAS 的补充指标——**拒答准确率（Refusal Accuracy）**，反映的是 Day 19 的"无资料拒答"机制在真实评估集上的表现，和 RAGAS 四指标一起构成完整的评估报表。

---

## 五、完整实现

```python
# main.py
import json

def run_and_report(rag_system, eval_set: list[EvalCase], version_tag: str):
    report = run_full_evaluation(rag_system, eval_set)

    print(f"=== 评估报表（{version_tag}）===")
    for metric, score in report["ragas_scores"].items():
        print(f"  {metric}: {score:.3f}")
    print(f"  refusal_accuracy: {report['refusal_accuracy']:.3f}")

    save_baseline(report, version_tag)

    # 如果存在上一个版本的基准，自动对比
    import os
    prev_baselines = sorted(os.listdir("eval_baselines"))
    if len(prev_baselines) >= 2:
        diffs = compare_with_baseline(report, f"eval_baselines/{prev_baselines[-2]}")
        print("\n=== 与上一版本对比 ===")
        for metric, diff in diffs.items():
            arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
            print(f"  {metric}: {arrow} {diff:+.4f}")

    return report
```

预期输出：

```
=== 评估报表（v2_hybrid_retrieval）===
  faithfulness: 0.910
  answer_relevancy: 0.882
  context_precision: 0.780
  context_recall: 0.810
  refusal_accuracy: 0.900

=== 与上一版本对比 ===
  faithfulness: → +0.0020
  answer_relevancy: → -0.0050
  context_precision: ↑ +0.0600
  context_recall: ↑ +0.1600
  refusal_accuracy: → +0.0000
```

这份对比清楚地说明了"接入混合检索这次改动，主要提升了 Context Precision 和 Context Recall（检索环节指标大幅提升），生成环节指标基本没变（符合预期，因为这次改动没有涉及生成部分）"——这正是持续评估要达成的效果：**每次改动都能精确说明它改进了什么、有没有带来副作用**。

---

## 六、Day 64 知识速查

### 评估集三元组结构

```python
EvalCase(case_id, question, ground_truth_answer, ground_truth_sources, category)
category ∈ {answerable, boundary, out_of_scope}
```

### 20 条评估问题的比例参考

```
10 条 answerable（核心业务场景）
6 条 boundary（信息分散/指代不明/部分缺失）
4 条 out_of_scope（知识库完全没覆盖的话题）
```

### 评估流程分工

```
answerable + boundary → RAGAS 四指标（faithfulness / answer_relevancy / context_precision / context_recall）
out_of_scope          → 独立的 Refusal Accuracy（拒答准确率），不适用 RAGAS 四指标
```

### 持续评估的核心机制

```
基准报表版本化保存（baseline_v1.json / baseline_v2.json ...）
每次改动后重跑评估集，和上一版本自动对比差异
Day 55 反馈追踪发现的真实失败 case 持续转化为新的评估用例，让评估集越来越贴近生产真实问题
```

---

## 七、实践任务

- [ ] 手写 20 条评估问题，按 10/6/4 的比例覆盖 answerable/boundary/out_of_scope 三类，为每条标注 `ground_truth_answer` 和 `ground_truth_sources`
- [ ] 实现 `run_full_evaluation()`，验证能对 answerable/boundary 跑 RAGAS 四指标、对 out_of_scope 跑独立的拒答准确率
- [ ] 跑一次评估，把结果保存成第一版基准报表 `baseline_v1.json`
- [ ] 对项目做一次实际改动（如接入 Day 58 的混合检索），重跑评估集，和 `baseline_v1.json` 对比，记录哪些指标提升、哪些没变化
- [ ] 从 Day 55 的低分回答清单里挑 2-3 条真实失败 case，人工标注标准答案和来源后加入评估集，验证评估集能持续扩充

**产出标准**：一个可重复运行的评估脚本 + 一份基准报表，后续每次优化都能基于这份基准对比出具体的指标变化，而不是重新凭感觉判断"是不是变好了"。

---

## 八、下一步预告

Day 65 进入**PDF / 表格 / 扫描件解析进阶**：今天建立的评估集能告诉我们系统在"文本已经切分好、检索已经跑通"的前提下表现如何，但如果知识库里的原始文档本身就没被正确解析（PDF 里的表格被解析成乱码、扫描件没有文本层），那么再精细的检索和评估都是建立在错误数据之上的。Day 65 要往前一步，解决 RAG 流程最上游的"数据质量"问题。
