# Day 10：做一个文本分类器

> 学习目标：理解分类任务和抽取/摘要任务在 Prompt 设计上的本质差异，掌握用 `enum` 把标签集合锁死在固定类别里的方法，实现一个可重复运行的用户反馈分类器，并建立对"分类结果是否可信"的验证意识——模型给出的标签本身可能不可靠，需要用多次采样、小样本人工核对等手段做置信度评估
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 10
>
> 🧭 导航：[← Day 9 · 输出校验与异常处理](day09_error_handling.md) → [Day 11 · 练 Prompt 优化](day11_prompt_optimization.md)

---

## 目录

- [一、分类任务的核心概念](#一分类任务的核心概念)
  - [1.1 分类 vs 抽取 vs 摘要的本质区别](#11-分类-vs-抽取-vs-摘要的本质区别)
  - [1.2 分类任务的输入输出形态](#12-分类任务的输入输出形态)
  - [1.3 标签集合的设计原则](#13-标签集合的设计原则)
- [二、标签集合约束的实现](#二标签集合约束的实现)
  - [2.1 用 enum 锁定标签范围](#21-用-enum-锁定标签范围)
  - [2.2 单标签 vs 多标签分类](#22-单标签-vs-多标签分类)
  - [2.3 "无法归类"的兜底标签设计](#23-无法归类的兜底标签设计)
- [三、文本分类器实现](#三文本分类器实现)
  - [3.1 基础版单标签分类器](#31-基础版单标签分类器)
  - [3.2 Pydantic + enum 集成的强类型分类器](#32-pydantic--enum-集成的强类型分类器)
  - [3.3 批量分类与结果统计](#33-批量分类与结果统计)
- [四、分类结果的置信度与验证](#四分类结果的置信度与验证)
  - [4.1 为什么"模型给的标签"不完全可信](#41-为什么模型给的标签不完全可信)
  - [4.2 用多次采样估计置信度（Self-Consistency）](#42-用多次采样估计置信度self-consistency)
  - [4.3 用小样本人工标注评估准确率](#43-用小样本人工标注评估准确率)
- [五、对比实验：Prompt 设计对分类准确率的影响](#五对比实验prompt-设计对分类准确率的影响)
- [六、Day 10 知识速查](#六day-10-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、分类任务的核心概念

### 1.1 分类 vs 抽取 vs 摘要的本质区别

Day 5（摘要）、Day 6/8/9（抽取）、Day 10（分类）是三种完全不同的输出形态，很多人容易把"输出 JSON"简单等同于"结构化任务都差不多"，但三者对模型的要求截然不同：

```
┌────────────────────────────────────────────────────────────────────────┐
│                  摘要 / 抽取 / 分类 的核心差异                             │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  摘要：输入文本 → 输出一段新文本（自由生成，允许改写）                       │
│  "这篇文章讲了...\n核心观点是..."                                          │
│                                                                          │
│  抽取：输入文本 → 输出文本中已有的若干字段（复制，不允许推断/改写）           │
│  {"name": "张伟", "phone": "13800001111"}                                │
│                                                                          │
│  分类：输入文本 → 从一个"预先定义好的、有限的"标签集合中选一个（或几个）      │
│  {"category": "投诉"}   ← 答案只能是 {咨询, 投诉, 建议, 故障} 之一          │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

分类任务的特殊性在于：**答案空间是有限且预先确定的**。这意味着分类比抽取更"死板"——不存在"字段找不到就填 null"这种灵活兜底，模型必须在给定选项里选一个，选错了就是错了，没有"部分正确"。

| 对比维度 | 摘要 | 抽取 | 分类 |
|---------|------|------|------|
| 答案空间 | 无限（自然语言） | 半开放（原文中的值） | **有限且预定义** |
| 输出自由度 | 高（允许改写） | 中（不能改写，但值来自原文） | 低（只能是标签集合中的值） |
| 评估方式 | 主观评分（覆盖度/忠实度） | 字段级别对错 | **准确率、混淆矩阵**（客观可量化） |
| 典型 temperature | 0.1–0.3 | 0.0 | 0.0（分类几乎不需要随机性） |

### 1.2 分类任务的输入输出形态

```
用户反馈原文：
"我上个月买的耳机用了一周就没电了，客服还一直不回消息，太差劲了"
         │
         ▼
     分类器（LLM）
         │
         ▼
{"category": "投诉"}
```

分类任务的 Prompt 结构通常比抽取更简单——不需要描述"字段"，而是描述"标签集合"和"每个标签的定义"：

```
你是一个客服工单分类助手。请把以下用户反馈分类为以下四类之一：
- 咨询：用户询问产品信息、使用方法，没有表达不满
- 投诉：用户对产品/服务表达不满，或描述了负面体验
- 建议：用户主动提出改进意见，语气中性或正面
- 故障：用户报告产品无法正常使用的技术问题

只输出 JSON：{"category": "<四个类别之一>"}

用户反馈：{text}
```

### 1.3 标签集合的设计原则

```
┌──────────────────────────────────────────────────────────────────┐
│                     好的标签集合应满足                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ① 互斥（Mutually Exclusive）                                       │
│     每条数据理想情况下只应该明确属于一个类别，类别定义之间不应重叠       │
│     反例："投诉" 和 "故障" 定义模糊时，报修类投诉两个类别都沾边          │
│                                                                    │
│  ② 完备（Collectively Exhaustive）                                  │
│     标签集合要能覆盖绝大多数真实数据，否则模型会被迫"矬子里拔将军"        │
│     兜底：预留一个"其他"类别，而不是让模型在不合适的类别里硬选           │
│                                                                    │
│  ③ 定义清晰、模型能理解                                              │
│     每个标签配一句话定义 + 最好各配 1-2 个示例，而不是只给一个词         │
│     反例：只写"故障"两个字，模型不知道"退货算不算故障"                  │
│                                                                    │
│  ④ 数量适中（通常 3-15 类）                                          │
│     类别太多时，模型在长列表中选择的准确率会明显下降                    │
│     类别太多可以考虑先做"大类"分类，再对某个大类做"细分类"（两级分类）    │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、标签集合约束的实现

### 2.1 用 enum 锁定标签范围

Day 8 提到过 `enum` 约束，当时是信息抽取里的一个"加分项"；在分类任务里，`enum` 是**核心机制**，因为分类任务的本质就是"从枚举值里选一个"：

```python
from pydantic import BaseModel
from enum import Enum

class FeedbackCategory(str, Enum):
    CONSULT = "咨询"
    COMPLAINT = "投诉"
    SUGGESTION = "建议"
    FAULT = "故障"

class ClassificationResult(BaseModel):
    category: FeedbackCategory
```

用 Python 原生 `Enum`（而不是普通字符串 + `Field(pattern=...)`）的好处：Pydantic 会自动校验模型输出是否落在枚举值范围内，值不在集合里直接抛 `ValidationError`，不需要手写 `if category not in [...]` 这种校验逻辑。

```python
schema = ClassificationResult.model_json_schema()
print(json.dumps(schema, ensure_ascii=False))
# {"$defs": {"FeedbackCategory": {"enum": ["咨询", "投诉", "建议", "故障"], "title": "FeedbackCategory", "type": "string"}}, ...}
```

`model_json_schema()` 自动把 `Enum` 转换成 JSON Schema 的 `enum` 约束，可以直接拼进 Prompt，Schema 定义和校验逻辑共用同一份代码，不会出现"文档里写了 5 个类别，代码里只校验了 4 个"这种不一致。

### 2.2 单标签 vs 多标签分类

有些场景下一条数据可能同时属于多个类别（比如一条反馈"既有故障描述又表达了不满"），这时候需要区分是**单标签**还是**多标签**分类：

```python
# 单标签：一条数据只能属于一个类别
class SingleLabelResult(BaseModel):
    category: FeedbackCategory


# 多标签：一条数据可以同时属于多个类别
class MultiLabelResult(BaseModel):
    categories: list[FeedbackCategory]
```

```
┌───────────────────────────────────────────────────────────────┐
│               单标签 vs 多标签 Prompt 措辞差异                     │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  单标签："请选择最符合的一个类别"                                   │
│  {"category": "投诉"}                                           │
│                                                                 │
│  多标签："请选择所有符合的类别（可以是多个）"                         │
│  {"categories": ["投诉", "故障"]}                                 │
│                                                                 │
│  易错点：Prompt 里如果没写清楚"只能选一个"还是"可以选多个"，           │
│  模型的行为会不稳定——有时候输出单个字符串，有时候输出列表              │
│                                                                 │
└───────────────────────────────────────────────────────────────┘
```

单标签任务用普通 `enum` 字段即可；多标签任务用 `list[枚举类型]`，两者的 Prompt 措辞和下游消费逻辑都不同，**设计前必须先确认业务到底是哪一种**。

### 2.3 "无法归类"的兜底标签设计

真实数据里总有一些文本模糊不清或压根不属于预定义的任何类别，如果标签集合里没有兜底选项，模型会被迫"矬子里拔将军"，硬选一个不太合适的标签，污染统计结果：

```python
class FeedbackCategory(str, Enum):
    CONSULT = "咨询"
    COMPLAINT = "投诉"
    SUGGESTION = "建议"
    FAULT = "故障"
    OTHER = "其他"   # 兜底类别，容纳无法明确归类的数据
```

Prompt 中要明确说明"其他"的使用条件，避免模型偷懒把所有拿不准的都扔进"其他"：

```
- 其他：内容与产品/服务无关，或信息不足以判断类别时才使用，不要滥用此类别
```

---

## 三、文本分类器实现

### 3.1 基础版单标签分类器

```python
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

CATEGORIES = ["咨询", "投诉", "建议", "故障", "其他"]

CATEGORY_DEFINITIONS = {
    "咨询": "用户询问产品信息、使用方法，没有表达不满",
    "投诉": "用户对产品/服务表达不满，或描述了负面体验",
    "建议": "用户主动提出改进意见，语气中性或正面",
    "故障": "用户报告产品无法正常使用的技术问题",
    "其他": "内容与产品/服务无关，或信息不足以判断类别时才使用",
}


def build_classify_prompt(text: str) -> str:
    definitions = "\n".join(f"- {k}：{v}" for k, v in CATEGORY_DEFINITIONS.items())
    return (
        f"你是一个客服工单分类助手。请把以下用户反馈分类为以下类别之一：\n{definitions}\n\n"
        f"只输出 JSON：{{\"category\": \"<类别>\"}}，category 必须是上述类别之一，不要输出其他内容。\n\n"
        f"用户反馈：{text}"
    )


def classify(text: str) -> str:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": build_classify_prompt(text)}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    category = data.get("category", "其他")
    return category if category in CATEGORIES else "其他"


if __name__ == "__main__":
    feedbacks = [
        "我上个月买的耳机用了一周就没电了，客服还一直不回消息，太差劲了",
        "请问这款耳机支持双设备连接吗？",
        "希望下一代产品能加个降噪开关的物理按键",
        "耳机突然连不上蓝牙了，重启也没用",
    ]
    for fb in feedbacks:
        print(f"[{classify(fb)}] {fb}")
```

```
运行输出：
[投诉] 我上个月买的耳机用了一周就没电了，客服还一直不回消息，太差劲了
[咨询] 请问这款耳机支持双设备连接吗？
[建议] 希望下一代产品能加个降噪开关的物理按键
[故障] 耳机突然连不上蓝牙了，重启也没用
```

注意 `category if category in CATEGORIES else "其他"` 这一行——即使 Prompt 里明确约束了类别集合，模型仍有极小概率输出集合之外的值（比如"退货"），代码层必须做二次兜底，而不是假设 Prompt 约束 100% 生效。

### 3.2 Pydantic + enum 集成的强类型分类器

把 3.1 的字符串校验升级为 Day 8/9 学到的 Pydantic 强类型校验，配合 Day 9 的重试机制：

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ValidationError


class FeedbackCategory(str, Enum):
    CONSULT = "咨询"
    COMPLAINT = "投诉"
    SUGGESTION = "建议"
    FAULT = "故障"
    OTHER = "其他"


class ClassificationResult(BaseModel):
    category: FeedbackCategory


def classify_structured(text: str, max_retries: int = 2) -> ClassificationResult:
    prompt = build_classify_prompt(text)
    last_error = None

    for attempt in range(max_retries):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
            return ClassificationResult(**data)   # enum 校验：值不在集合内直接 ValidationError
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            continue

    # 重试耗尽仍失败，兜底归为"其他"，而不是让程序崩溃
    return ClassificationResult(category=FeedbackCategory.OTHER)
```

相比 3.1 手写 `if category in CATEGORIES`，用 `Enum` 类型的好处是**类型系统本身就是校验规则**——`ClassificationResult(category="退货")` 会直接抛 `ValidationError`，不需要额外写归一化逻辑，IDE 也能对 `category` 字段做自动补全和类型检查。

### 3.3 批量分类与结果统计

```python
from collections import Counter


def batch_classify(texts: list[str]) -> dict:
    results = [classify_structured(t) for t in texts]
    counter = Counter(r.category.value for r in results)
    return {
        "results": list(zip(texts, results)),
        "distribution": dict(counter),
    }


if __name__ == "__main__":
    feedbacks = [
        "我上个月买的耳机用了一周就没电了，客服还一直不回消息，太差劲了",
        "请问这款耳机支持双设备连接吗？",
        "希望下一代产品能加个降噪开关的物理按键",
        "耳机突然连不上蓝牙了，重启也没用",
        "今天天气不错",   # 与产品无关，测试"其他"兜底
    ]
    report = batch_classify(feedbacks)
    print("类别分布：", report["distribution"])
    # 类别分布：{'投诉': 1, '咨询': 1, '建议': 1, '故障': 1, '其他': 1}
```

批量分类后统计**类别分布**是分类任务特有的、抽取任务没有的产出——它能直接回答业务问题（"这批反馈里投诉占比多少"），这也是分类任务区别于抽取任务的价值所在。

---

## 四、分类结果的置信度与验证

### 4.1 为什么"模型给的标签"不完全可信

分类任务最大的陷阱是：**模型永远会给出一个看起来"言之凿凿"的标签，即使这条数据本身很模糊**。和传统机器学习分类器不同，直接调用 Chat API 拿到的是一个确定的字符串，而不是一组带概率的候选（虽然底层 API 通常提供 `logprobs` 参数可以拿到 Token 级别概率，但工程上很少直接用它做"标签置信度"）：

```
┌───────────────────────────────────────────────────────────────────┐
│              为什么不能盲目相信模型给的单次分类结果                     │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  传统分类器：predict_proba() 能告诉你                                │
│  投诉: 0.55, 故障: 0.40, 其他: 0.05  ← 天然带置信度                   │
│                                                                     │
│  LLM 单次调用：只返回                                                │
│  {"category": "投诉"}  ← 看起来 100% 确定，实际上模糊数据也会给出       │
│                        确定的答案，看不出模型内部其实"很纠结"           │
│                                                                     │
│  风险：把模糊数据的单次分类结果当成绝对正确，会让统计报表里混入           │
│  一批"模型也不确定，但被迫选了一个"的错误分类                          │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

### 4.2 用多次采样估计置信度（Self-Consistency）

对于容易模糊的场景，可以用**同一条数据多次调用（提高 temperature 引入随机性），看结果是否一致**来间接估计置信度，这个思路叫 Self-Consistency：

```python
def classify_with_confidence(text: str, n_samples: int = 5) -> dict:
    """多次采样同一条数据，用结果的一致程度近似置信度"""
    votes = []
    for _ in range(n_samples):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": build_classify_prompt(text)}],
            temperature=0.7,   # 采样阶段需要一定随机性，否则每次结果都一样，失去统计意义
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        votes.append(data.get("category", "其他"))

    counter = Counter(votes)
    top_category, top_count = counter.most_common(1)[0]
    confidence = top_count / n_samples

    return {
        "category": top_category,
        "confidence": confidence,       # 5 次里有几次投给了最终类别
        "vote_distribution": dict(counter),
    }
```

```
示例：
"这个东西感觉一般般，也不算坏也没什么亮点"（模糊反馈）
→ 5 次采样：["其他", "建议", "其他", "咨询", "其他"]
→ {"category": "其他", "confidence": 0.6, "vote_distribution": {"其他": 3, "建议": 1, "咨询": 1}}

"耳机用一周就坏了，客服态度还很差"（清晰反馈）
→ 5 次采样：["投诉", "投诉", "投诉", "投诉", "投诉"]
→ {"category": "投诉", "confidence": 1.0, "vote_distribution": {"投诉": 5}}
```

`confidence` 低的记录（比如 < 0.6）适合标记为"待人工复核"（复用 Day 9 学到的三态思路），而不是直接采信。这个方法的代价是**调用次数和成本乘以 n_samples**，通常只对少量关键数据或抽样质检使用，不建议对全量数据都跑 5 次。

### 4.3 用小样本人工标注评估准确率

Self-Consistency 只能衡量"模型自己纠不纠结"，无法衡量"模型是不是真的分对了"——这需要一批**人工标注的真实标签**做基准：

```python
def evaluate_accuracy(texts: list[str], ground_truth: list[str]) -> dict:
    predictions = [classify(t) for t in texts]
    correct = sum(p == g for p, g in zip(predictions, ground_truth))
    accuracy = correct / len(texts)

    confusion = Counter(zip(ground_truth, predictions))   # (真实类别, 预测类别) 计数
    return {"accuracy": accuracy, "confusion": dict(confusion)}


if __name__ == "__main__":
    texts = ["耳机坏了", "怎么配对蓝牙", "希望加个按键", "态度太差了"]
    ground_truth = ["故障", "咨询", "建议", "投诉"]   # 人工标注的真实标签

    result = evaluate_accuracy(texts, ground_truth)
    print(f"准确率：{result['accuracy']:.0%}")
    print(f"混淆情况：{result['confusion']}")
```

**实用做法**：从真实数据里随机抽 30–50 条，人工标注真实类别，跑一遍分类器算准确率；如果发现某两个类别之间混淆率特别高（比如"投诉"总被分成"故障"），说明这两个类别的**定义描述不够清晰**，需要回到 Prompt 里把类别定义写得更具体、再各补 1-2 个示例。

---

## 五、对比实验：Prompt 设计对分类准确率的影响

用同一批测试数据，对比三种不同详细程度的 Prompt，观察准确率差异：

```python
PROMPT_VERSIONS = {
    "V1_极简": lambda text: f"把以下反馈分类为：咨询/投诉/建议/故障/其他。只输出 JSON：{{\"category\": \"...\"}}\n\n{text}",

    "V2_带定义": lambda text: build_classify_prompt(text),   # 3.1 中带类别定义的版本

    "V3_带定义和示例": lambda text: (
        build_classify_prompt(text).replace(
            "只输出 JSON",
            "参考示例：\n"
            "反馈：\"用了两天就黑屏了\" → 故障\n"
            "反馈：\"能不能出个粉色款\" → 建议\n\n"
            "只输出 JSON"
        )
    ),
}


def compare_prompt_versions(texts: list[str], ground_truth: list[str]):
    for name, prompt_fn in PROMPT_VERSIONS.items():
        correct = 0
        for text, truth in zip(texts, ground_truth):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt_fn(text)}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            predicted = json.loads(response.choices[0].message.content).get("category")
            correct += (predicted == truth)
        print(f"{name}：准确率 {correct}/{len(texts)}")
```

```
典型实验结论（10 条测试数据）：
V1_极简       ：准确率 6/10   ← 无定义时，模型对"咨询 vs 建议"边界案例判断不稳定
V2_带定义     ：准确率 8/10   ← 补充类别定义后，边界案例明显改善
V3_带定义和示例：准确率 9/10   ← few-shot 示例进一步锚定了模糊案例的判断标准
```

**结论**：分类任务的准确率高度依赖类别定义是否清晰。类别名本身（如"投诉"）对人类来说含义明确，但对模型来说只是一个字符串标签，**必须靠一句话定义 + 边界案例示例，才能让模型的判断标准和人工标注标准对齐**。

---

## 六、Day 10 知识速查

### 三种任务类型对比

| 维度 | 摘要 | 抽取 | 分类 |
|------|------|------|------|
| 答案空间 | 无限 | 半开放 | 有限且预定义 |
| 核心约束手段 | 长度/格式描述 | JSON Schema + Pydantic | `enum` |
| 评估方式 | 主观评分 | 字段级别对错 | 准确率、混淆矩阵 |

### 标签集合设计四原则

```
互斥（不重叠）+ 完备（覆盖全面，留"其他"兜底）
+ 定义清晰（一句话定义 + 示例）+ 数量适中（3-15 类）
```

### 置信度评估速查

| 方法 | 做法 | 衡量什么 | 成本 |
|------|------|---------|------|
| Self-Consistency | 同一数据多次采样（temperature > 0），看结果一致率 | 模型自己纠不纠结 | n_samples 倍调用成本 |
| 人工标注评估 | 小样本人工标真实标签，算准确率/混淆矩阵 | 模型是否真的分对了 | 人工标注成本 |

### 最小模板

```python
class Category(str, Enum):
    A = "..."; B = "..."; OTHER = "其他"

class Result(BaseModel):
    category: Category

def classify(text):
    prompt = f"分类为：{[c.value for c in Category]}\n定义：...\n只输出 JSON\n\n{text}"
    raw = call_llm(prompt, temperature=0.0, response_format=json_object)
    return Result(**json.loads(raw))   # Enum 自动校验取值范围
```

---

## 七、实践任务

- [ ] 定义一组至少 4 个类别的标签集合（含"其他"兜底类别），每个类别配一句话定义
- [ ] 用 `Enum` + Pydantic 实现一个强类型分类器，验证模型输出集合外的值时能被 `ValidationError` 拦截
- [ ] 用至少 10 条真实/构造的反馈文本跑通批量分类，统计类别分布
- [ ] 人工标注这 10 条数据的真实类别，计算分类器的准确率，找出混淆最多的两个类别
- [ ] 针对混淆率最高的类别对，补充更清晰的定义或示例，重新测试，验证准确率是否提升

**产出标准**：

- 一个可重复运行的文本分类脚本，输入一批文本，输出每条的分类结果和整体类别分布
- 一份包含准确率和混淆情况的评估记录

---

## 八、下一步预告

**Day 11：练 Prompt 优化**

Day 10 已经在分类场景里验证了"类别定义 + 示例"对准确率的影响，Day 11 会把 Prompt 优化系统化：

- 角色设定、目标声明、Few-shot 示例、输出限制这四类优化手段分别解决什么问题
- 如何针对同一个任务写出 3 个版本的 Prompt，并设计一套可复现的对比方法
- 稳定性和准确率之间如何权衡——更"聪明"的 Prompt 是否一定更稳定

核心问题：当一个 Prompt 在测试集上表现不错，如何判断这是"真的优化了"还是"恰好蒙对了这几条测试数据"。
