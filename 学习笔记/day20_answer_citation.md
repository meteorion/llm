# Day 20：给回答加引用

> 学习目标：掌握 RAG 引用机制的核心技术——学会用结构化 JSON 输出让模型标注答案来源，实现引用溯源展示，检测"虚构引用"确保引用可信，完成一个带引用功能的完整 RAG 问答系统
>
> 📚 所属阶段：**第二阶段 · RAG 核心应用架构**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 20
>
> 🧭 导航：[← Day 19 · RAG 问答生成](day19_rag_generation.md) [→ Day 21 · 第 3 周复盘](day21_week3_review.md)

---

## 目录

- [一、引用机制的核心概念](#一引用机制的核心概念)
  - [1.1 为什么 RAG 需要引用](#11-为什么-rag-需要引用)
  - [1.2 引用的三个层次](#12-引用的三个层次)
  - [1.3 引用 vs 拒答：可解释性的两个侧面](#13-引用-vs-拒答可解释性的两个侧面)
- [二、结构化引用输出设计](#二结构化引用输出设计)
  - [2.1 从自然语言引用到结构化引用](#21-从自然语言引用到结构化引用)
  - [2.2 JSON Schema 设计：answer + sources](#22-json-schema-设计answer--sources)
  - [2.3 Prompt 设计：引导模型标注引用](#23-prompt-设计引导模型标注引用)
- [三、引用溯源展示](#三引用溯源展示)
  - [3.1 展示设计：回答 + 引用区块](#31-展示设计回答--引用区块)
  - [3.2 引用片段的截取与高亮](#32-引用片段的截取与高亮)
  - [3.3 多来源引用的排列策略](#33-多来源引用的排列策略)
- [四、引用准确性验证](#四引用准确性验证)
  - [4.1 虚构引用问题](#41-虚构引用问题)
  - [4.2 引用校验的三道防线](#42-引用校验的三道防线)
  - [4.3 引用覆盖率与忠实度](#43-引用覆盖率与忠实度)
- [五、完整实现：带引用的 RAG 问答系统](#五完整实现带引用的-rag-问答系统)
- [六、引用策略对比实验](#六引用策略对比实验)
  - [6.1 三版引用方案设计](#61-三版引用方案设计)
  - [6.2 引用质量对比](#62-引用质量对比)
- [七、Day 20 知识速查](#七day-20-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、引用机制的核心概念

### 1.1 为什么 RAG 需要引用

Day 19 完成了"检索 → 生成"的核心链路，但回答对用户来说是一个"黑箱"——用户无法判断模型说的内容是来自知识库，还是模型自己"脑补"的。

```
没有引用的 RAG 回答（Day 19 的 V2 Prompt 输出）：

  "购买后 30 天内可申请全额退款。三周（21天）在此范围内，
   所以您的商品可以申请退款。"

  用户的疑问：
  - 这 30 天的规定是从哪来的？
  - 是不是模型自己编的？
  - 如果我想核实，去哪里查？

有引用的 RAG 回答（Day 20 目标）：

  "购买后 30 天内可申请全额退款 [1]。三周（21天）在此范围内，
   所以您的商品可以申请退款 [1]。"

  引用来源：
  [1] 退款政策：购买后 30 天内可申请全额退款。超过 30 天不支持退款...

  用户的感受：
  - 答案有据可查
  - 可以点开引用核实
  - 对系统产生信任
```

引用的核心价值是**可解释性**（Explainability）——让用户能追溯答案的来源，而不是盲目信任模型。

### 1.2 引用的三个层次

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG 引用的三个层次                              │
├──────────────┬──────────────────────────────────────────────────┤
│  层次        │  说明                                             │
├──────────────┼──────────────────────────────────────────────────┤
│  L1 标记引用 │  在回答文本中标注来源编号                           │
│              │  "退款需 30 天内 [1]"                             │
│              │  → 最低成本，让用户知道"有出处"                      │
├──────────────┼──────────────────────────────────────────────────┤
│  L2 展示来源 │  回答后附上引用的原文片段                           │
│              │  [1] 退款政策：购买后 30 天内可申请全额退款...        │
│              │  → 用户可以直接核实，无需另外查找                    │
├──────────────┼──────────────────────────────────────────────────┤
│  L3 可验证   │  程序校验引用编号是否真实存在、内容是否匹配          │
│              │  sources=[1,3] → 检查 1 和 3 是否在检索结果中       │
│              │  → 防止模型"虚构引用"，保证引用可信                  │
└──────────────┴──────────────────────────────────────────────────┘

Day 20 的目标：实现 L1 + L2 + L3 的完整引用链路
```

### 1.3 引用 vs 拒答：可解释性的两个侧面

Day 19 学了拒答（"资料中没有"时说不知道），Day 20 学引用（"资料中有"时标注来源）。两者共同构成 RAG 的可解释性：

```
可解释性 = 知道边界 + 知道来源

  拒答（Day 19）          引用（Day 20）
  ─────────────          ─────────────
  "资料中没有" → 不说     "资料中有" → 标注来源
  防止幻觉               建立信任
  检索层 + 生成层        结构化输出 + 校验

  两者结合：用户知道系统"什么知道、什么不知道、知道的依据是什么"
```

| 维度 | 拒答（Day 19） | 引用（Day 20） |
|------|---------------|---------------|
| 触发条件 | 无相关资料 | 有相关资料 |
| 目标 | 防止幻觉 | 建立信任 |
| 实现层 | 检索层（min_score）+ 生成层（约束） | 结构化输出（JSON）+ 校验 |
| 用户体验 | "系统诚实地说了不知道" | "系统说了答案并给出依据" |

---

## 二、结构化引用输出设计

### 2.1 从自然语言引用到结构化引用

Day 19 的 V3 Prompt 已经让模型在自然语言中标注"根据[资料1]"，但这种"软引用"有三个问题：

```
自然语言引用（Day 19 V3）的问题：

  问题 1：格式不稳定
    模型可能写 "根据[资料1]"，也可能写 "根据资料1"，也可能写 "[1]"
    → 程序难以可靠地解析

  问题 2：无法程序化处理
    "根据[资料1]和[资料3]，退款时间为..."
    → 要从自然语言里提取 "1" 和 "3" 需要正则或再调一次模型

  问题 3：无法校验
    模型说 "根据[资料2]"，但实际资料 2 根本没有退款内容
    → 自然语言中混入的引用编号无法和资料做映射验证

结构化引用（Day 20）的解法：

  让模型输出 JSON：
  {
    "answer": "购买后 30 天内可申请全额退款，三周在此范围内可以退款。",
    "sources": [1]
  }

  → answer 字段：纯文本回答
  → sources 字段：引用的资料编号列表（整数数组）
  → 程序可以可靠解析、校验、展示
```

### 2.2 JSON Schema 设计：answer + sources

```python
from pydantic import BaseModel, Field

class RAGAnswer(BaseModel):
    """带引用的 RAG 回答结构"""
    answer: str = Field(
        description="基于参考资料生成的回答，不超过 300 字"
    )
    sources: list[int] = Field(
        description="引用的资料编号列表，编号对应参考资料中的序号（从 1 开始）"
    )
```

Schema 设计的三个考量：

```
┌─────────────────────────────────────────────────────────────────┐
│  字段设计决策                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. answer: str（纯文本，不含引用标记）                           │
│     为什么不放引用标记在 answer 里？                               │
│     → 让 answer 保持干净的文本，引用信息单独放 sources              │
│    → 展示时由程序决定怎么标注（[1] 还是上标¹ 还是超链接）            │
│                                                                  │
│  2. sources: list[int]（编号列表）                                │
│     为什么用整数列表而不是字符串？                                  │
│     → 整数可以和检索结果的索引直接做匹配                            │
│     → list 而非单个 int：一条回答可能引用多条资料                    │
│                                                                  │
│  3. 为什么不加 confidence 字段？                                   │
│     → 模型自评估的置信度不可靠（Day 10 已验证）                      │
│     → 置信度应该由检索分数 + 引用校验结果推导，而非模型自报           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Prompt 设计：引导模型标注引用

```python
CITATION_SYSTEM_PROMPT = """你是一个知识库问答助手，专门根据提供的参考资料回答问题。

行为规则：
1. 只根据"参考资料"中的内容回答，不引入外部知识
2. 在 sources 字段中标注你的答案引用了哪些资料（编号对应参考资料序号）
3. 如果参考资料与问题无关或信息不足，answer 设为"根据现有资料无法回答该问题"，sources 设为空列表
4. answer 字段只写纯文本回答，不要在文本中嵌入 [1] 等标记
5. sources 中只能出现参考资料中实际存在的编号"""


def build_citation_prompt(query: str, contexts: list[dict]) -> str:
    context_block = "\n\n".join(
        f"[资料{i+1}]（相关度 {r['score']:.2f}）\n{r['text']}"
        for i, r in enumerate(contexts)
    )
    return f"""参考资料：

{context_block}

---
用户问题：{query}

请根据以上参考资料回答问题，并标注引用来源。"""
```

调用方式（使用 `response_format` 强制 JSON 输出）：

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": CITATION_SYSTEM_PROMPT},
        {"role": "user", "content": build_citation_prompt(query, contexts)},
    ],
    temperature=0.1,
    max_tokens=800,
    response_format={"type": "json_object"},
)

result = json.loads(response.choices[0].message.content)
answer = RAGAnswer(**result)
```

Prompt 设计的关键决策：

| 决策 | 做法 | 原因 |
|------|------|------|
| 引用编号体系 | [资料1]、[资料2]... | 与检索结果索引一一对应，方便程序映射 |
| answer 不含标记 | 纯文本 | 程序化标注，避免格式混乱 |
| sources 只放整数 | list[int] | 可直接做索引匹配和校验 |
| 空引用处理 | sources=[] + answer="无法回答" | 统一的拒答信号 |
| JSON 模式 | response_format=json_object | 保证输出可解析，不依赖正则 |

---

## 三、引用溯源展示

### 3.1 展示设计：回答 + 引用区块

拿到模型的 `{"answer": "...", "sources": [1]}` 后，需要把引用的原文展示给用户：

```
┌─────────────────────────────────────────────────────────────────┐
│  带 citation 的 RAG 回答展示格式                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ 回答区 ─────────────────────────────────────────────────┐   │
│  │  购买后 30 天内可申请全额退款 [1]。三周（21天）在此范围     │   │
│  │  内，所以您的商品可以申请退款 [1]。                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ 引用来源 ───────────────────────────────────────────────┐   │
│  │  [1] 退款政策                                            │   │
│  │  来源：product_policy.txt (Chunk 3)                      │   │
│  │  相关度：0.87                                            │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ 退款政策：购买后 30 天内可申请全额退款。超过 30 天   │ │   │
│  │  │ 不支持退款，但可申请换货。退款申请通过后，款项将在    │ │   │
│  │  │ 3–5 个工作日内原路返回。                              │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

实现代码：

```python
def format_cited_answer(
    answer: str,
    sources: list[int],
    contexts: list[dict],
) -> str:
    """格式化带引用的回答"""
    lines = [answer, "", "─── 引用来源 ───"]

    for src_id in sorted(set(sources)):
        idx = src_id - 1  # 编号从 1 开始，索引从 0 开始
        if 0 <= idx < len(contexts):
            ctx = contexts[idx]
            meta = ctx.get("metadata", {})
            lines.append(f"\n[{src_id}] 相关度 {ctx['score']:.2f}")
            if "source" in meta:
                lines.append(f"    来源：{meta['source']}")
            lines.append(f"    {ctx['text']}")
        else:
            lines.append(f"\n[{src_id}] ⚠ 引用编号无效（不在参考资料范围内）")

    return "\n".join(lines)
```

### 3.2 引用片段的截取与高亮

当原文 Chunk 很长时，完整展示会占用大量屏幕空间。需要截取最相关的部分：

```
完整 Chunk（200 字）：
  退款政策：购买后 30 天内可申请全额退款。超过 30 天不支持退款，但可
  申请换货。退款申请通过后，款项将在 3–5 个工作日内原路返回。退款需
  提供订单号和购买凭证，通过官网或客服提交申请。

截取策略：
  方案 A：直接截取前 80 字 + "..."
  方案 B：根据问题关键词定位 + 前后各取 40 字（上下文窗口）
  方案 C：让模型额外输出一个 "cited_text" 字段，直接引用原文中的句子

推荐方案 B：关键词定位截取
```

```python
import re

def extract_relevant_snippet(
    text: str,
    query: str,
    window: int = 40,
    max_length: int = 120,
) -> str:
    """根据查询关键词从 Chunk 中截取最相关片段"""
    keywords = [w for w in re.split(r"[\s，。？]+", query) if len(w) >= 2]
    for kw in keywords:
        pos = text.find(kw)
        if pos >= 0:
            start = max(0, pos - window)
            end = min(len(text), pos + len(kw) + window)
            snippet = text[start:end]
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text) else ""
            if len(snippet) > max_length:
                snippet = snippet[:max_length]
            return f"{prefix}{snippet}{suffix}"
    return text[:max_length] + ("..." if len(text) > max_length else "")
```

### 3.3 多来源引用的排列策略

当一条回答引用了多条资料时（如 `sources=[1, 3]`），排列方式影响可读性：

| 策略 | 做法 | 适用场景 |
|------|------|---------|
| 编号升序 | [1] → [3] → [5] | 默认，逻辑清晰 |
| 相关度降序 | 最相关的排前面 | 用户只看第一条就能核实 |
| 原文顺序 | 按 chunk_idx 排列 | 引用跨多段，需连贯阅读 |

```python
def sort_sources(
    sources: list[int],
    contexts: list[dict],
    strategy: str = "ascending",
) -> list[int]:
    unique = sorted(set(sources))
    if strategy == "ascending":
        return unique
    elif strategy == "relevance":
        return sorted(unique, key=lambda s: -contexts[s-1]["score"])
    elif strategy == "original":
        return sorted(unique, key=lambda s: contexts[s-1]["metadata"].get("chunk_idx", 0))
    return unique
```

---

## 四、引用准确性验证

### 4.1 虚构引用问题

结构化输出虽然让引用变成了可解析的数字，但模型仍然可能"说谎"——声称引用了某条资料，但该资料中根本没有相关内容：

```
虚构引用的典型场景：

  参考资料：
  [1] 退款政策：购买后 30 天内可申请全额退款...
  [2] 配送说明：订单确认后 24 小时内发货...
  [3] 会员积分规则：每消费 1 元获得 1 积分...

  用户问题："积分能换什么礼品？"

  模型输出：
  {
    "answer": "积分可以兑换优惠券和实物礼品 [3]。",
    "sources": [3]
  }

  问题：资料 [3] 只说"1000 积分可抵扣 10 元"，根本没提"优惠券"和"实物礼品"
  → 模型把外部知识混入了回答，还用引用 [3] 来"背书"
  → 这比不引用更危险：用户以为有出处，实际是幻觉
```

虚构引用的三种类型：

```
┌─────────────────────────────────────────────────────────────────┐
│  虚构引用类型                                                     │
├──────────────────┬──────────────────────────────────────────────┤
│  类型 1：编号越界  │ sources=[5]，但只有 3 条资料                  │
│  检测：简单        │ → index out of range                         │
│  防御：容易        │                                              │
├──────────────────┼──────────────────────────────────────────────┤
│  类型 2：编号有效   │ sources=[3]，但 [3] 与问题无关                │
│  但内容不匹配      │ → 编号合法，但资料里没有 answer 中的内容        │
│  检测：困难        │ → 需要语义匹配校验                            │
│  防御：需额外校验  │                                              │
├──────────────────┼──────────────────────────────────────────────┤
│  类型 3：遗漏引用   │ 回答中有事实，但 sources 为空                  │
│  → 模型给出了     │ → 模型没意识到需要标注来源                      │
│  答案却不标来源    │                                              │
│  检测：中等        │ → 需要检查 answer 非空时 sources 是否也非空     │
└──────────────────┴──────────────────────────────────────────────┘
```

### 4.2 引用校验的三道防线

```python
def validate_citation(
    rag_answer: RAGAnswer,
    contexts: list[dict],
    query: str,
) -> dict:
    """校验引用准确性，返回校验结果"""
    issues = []

    # ── 防线 1：编号有效性（防止越界） ──
    valid_sources = []
    for src in rag_answer.sources:
        if 1 <= src <= len(contexts):
            valid_sources.append(src)
        else:
            issues.append(f"引用编号 {src} 越界（有效范围 1–{len(contexts)}）")

    # ── 防线 2：拒答一致性（answer 为"无法回答"时 sources 应为空） ──
    is_refusal = "无法回答" in rag_answer.answer
    if is_refusal and valid_sources:
        issues.append("回答为拒答但仍有引用来源，存在矛盾")
    if not is_refusal and not valid_sources and rag_answer.answer:
        issues.append("回答非空但未引用任何来源，可能遗漏引用")

    # ── 防线 3：内容匹配性（粗粒度关键词检查） ──
    answer_lower = rag_answer.answer.lower()
    for src in valid_sources:
        ctx_text = contexts[src - 1]["text"]
        shared_keywords = extract_shared_keywords(answer_lower, ctx_text)
        if not shared_keywords:
            issues.append(
                f"引用 [{src}] 与回答内容关键词不匹配，可能为虚构引用"
            )

    return {
        "is_valid": len(issues) == 0,
        "valid_sources": valid_sources,
        "issues": issues,
    }


def extract_shared_keywords(text_a: str, text_b: str, min_len: int = 3) -> list[str]:
    """提取两段文本共有的关键词（粗粒度语义匹配）"""
    words_a = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z]{3,}", text_a))
    words_b = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z]{3,}", text_b))
    return list(words_a & words_b)
```

三道防线的协同关系：

```
  模型输出 sources=[1, 5]
         ↓
  防线 1：编号有效性
  ├── [1] 有效 ✓
  └── [5] 越界 ✗ → 标记 issue，从 valid_sources 中剔除
         ↓
  防线 2：拒答一致性
  ├── answer 非"无法回答" 且 valid_sources=[1] 非空 → ✓ 通过
  └── 若 answer="无法回答" 但 sources=[1] → ✗ 标记矛盾
         ↓
  防线 3：内容匹配性
  ├── [1] 的原文与 answer 有共享关键词 → ✓ 通过
  └── [1] 的原文与 answer 无共享关键词 → ✗ 标记"可能虚构"
         ↓
  返回 {is_valid, valid_sources, issues}
```

### 4.3 引用覆盖率与忠实度

校验结果可以量化为两个指标：

```
引用覆盖率（Coverage）：
  = |valid_sources ∩ contexts| / |contexts|
  含义：检索到的资料中有多少被模型实际引用了
  高 → 模型充分利用了检索结果
  低 → 检索了但没用，可能检索质量差或模型忽视

忠实度（Faithfulness）：
  = 1 - |虚构引用数| / |total_sources|
  含义：引用中有多少是真实可信的
  高 → 引用可靠
  低 → 虚构引用多，系统不可信
```

```python
def compute_citation_metrics(
    validation_result: dict,
    contexts: list[dict],
    total_sources: int,
) -> dict:
    valid = validation_result["valid_sources"]
    cited_count = len(set(valid))
    retrieved_count = len(contexts)
    issue_count = len(validation_result["issues"])

    coverage = cited_count / retrieved_count if retrieved_count > 0 else 0
    faithfulness = 1 - (issue_count / total_sources) if total_sources > 0 else 1

    return {
        "coverage": round(coverage, 2),
        "faithfulness": round(faithfulness, 2),
        "cited_count": cited_count,
        "issue_count": issue_count,
    }
```

> 这两个指标对应 RAG 评估框架 RAGAS 中的 **Faithfulness**（忠实度）和 **Context Utilization**（上下文利用率），Day 15 的 `plan.md` 第二阶段提到了 RAGAS 评估体系，这里先实现一个简化版本。

---

## 五、完整实现：带引用的 RAG 问答系统

整合 Day 15（RAG 原理）、Day 16（文档加载）、Day 17（文本切分）、Day 18（向量检索）、Day 19（生成回答）和 Day 20（引用），完成一个完整的带引用功能的 RAG 问答系统：

```python
"""
rag_qa_with_citation.py — Day 20 完整实现
带引用溯源的 RAG 问答：加载 → 切分 → 向量化 → 检索 → 生成（带引用）→ 校验 → 展示
"""
from __future__ import annotations

import os
import re
import json
import numpy as np
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
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

    def search(self, q_vec, top_k=3, min_score=0.5):
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
# 引用结构定义（Day 20 核心新增）
# ──────────────────────────────────────────────

class RAGAnswer(BaseModel):
    answer: str = Field(description="基于参考资料生成的回答")
    sources: list[int] = Field(description="引用的资料编号列表")


# ──────────────────────────────────────────────
# Prompt 设计
# ──────────────────────────────────────────────

CITATION_SYSTEM = """你是一个知识库问答助手，专门根据提供的参考资料回答问题。

行为规则：
1. 只根据"参考资料"中的内容回答，不引入外部知识
2. 在 sources 字段中标注你的答案引用了哪些资料（编号对应参考资料序号）
3. 如果参考资料与问题无关或信息不足，answer 设为"根据现有资料无法回答该问题"，sources 设为空列表
4. answer 字段只写纯文本回答，不要在文本中嵌入 [1] 等标记
5. sources 中只能出现参考资料中实际存在的编号"""


def build_citation_prompt(query, contexts):
    ctx_block = "\n\n".join(
        f"[资料{i+1}]（相关度 {r['score']:.2f}）\n{r['text']}"
        for i, r in enumerate(contexts)
    )
    return f"""参考资料：

{ctx_block}

---
用户问题：{query}

请根据以上参考资料回答问题，并标注引用来源。"""


# ──────────────────────────────────────────────
# 引用校验
# ──────────────────────────────────────────────

def validate_citation(rag_answer, contexts):
    issues = []
    valid_sources = []

    for src in rag_answer.sources:
        if 1 <= src <= len(contexts):
            valid_sources.append(src)
        else:
            issues.append(f"引用编号 {src} 越界（有效范围 1-{len(contexts)}）")

    is_refusal = "无法回答" in rag_answer.answer
    if is_refusal and valid_sources:
        issues.append("回答为拒答但仍有引用来源，存在矛盾")
    if not is_refusal and not valid_sources and rag_answer.answer:
        issues.append("回答非空但未引用任何来源")

    answer_lower = rag_answer.answer.lower()
    for src in valid_sources:
        ctx_text = contexts[src - 1]["text"].lower()
        words_a = set(re.findall(r"[\u4e00-\u9fff]{2,}", answer_lower))
        words_b = set(re.findall(r"[\u4e00-\u9fff]{2,}", ctx_text))
        if not (words_a & words_b):
            issues.append(f"引用 [{src}] 与回答内容不匹配，可能为虚构引用")

    return {"is_valid": len(issues) == 0, "valid_sources": valid_sources, "issues": issues}


# ──────────────────────────────────────────────
# 引用展示
# ──────────────────────────────────────────────

def extract_snippet(text, query, window=40, max_length=120):
    keywords = [w for w in re.split(r"[\s，。？]+", query) if len(w) >= 2]
    for kw in keywords:
        pos = text.find(kw)
        if pos >= 0:
            start = max(0, pos - window)
            end = min(len(text), pos + len(kw) + window)
            snippet = text[start:end][:max_length]
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text) else ""
            return f"{prefix}{snippet}{suffix}"
    return text[:max_length] + ("..." if len(text) > max_length else "")


def format_cited_answer(rag_answer, contexts, validation):
    valid = sorted(set(validation["valid_sources"]))

    # 在回答文本中插入引用标记
    answer = rag_answer.answer
    for src in valid:
        answer += f" [{src}]"

    lines = [answer, "", "─── 引用来源 ───"]
    for src in valid:
        ctx = contexts[src - 1]
        meta = ctx.get("metadata", {})
        snippet = extract_snippet(ctx["text"], rag_answer.answer)
        lines.append(f"\n[{src}] 相关度 {ctx['score']:.2f}")
        if meta.get("source"):
            lines.append(f"    来源：{meta['source']}")
        lines.append(f"    {snippet}")

    if validation["issues"]:
        lines.append("\n⚠ 引用校验问题：")
        for issue in validation["issues"]:
            lines.append(f"  - {issue}")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 完整 Pipeline
# ──────────────────────────────────────────────

class CitedRAGPipeline:
    def __init__(self):
        self.store = VectorStore()
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )

    def build(self, documents, metadatas=None):
        print(f"构建索引：{len(documents)} 个文档片段...")
        vecs = embed(documents)
        self.store.add(documents, vecs, metadatas)
        print("索引就绪。")

    def ask(self, query, top_k=3, min_score=0.55, verbose=False):
        # 1. 检索
        q_vec = embed([query])[0]
        results = self.store.search(q_vec, top_k=top_k, min_score=min_score)

        if verbose:
            print(f"\n[检索结果] 找到 {len(results)} 条相关资料")
            for r in results:
                print(f"  score={r['score']:.3f} | {r['text'][:60]}...")

        # 2. 检索层拒答
        if not results:
            return "根据当前知识库，未找到与您问题相关的信息，无法回答。"

        # 3. 生成带引用的回答
        user_prompt = build_citation_prompt(query, results)
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": CITATION_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=800,
            response_format={"type": "json_object"},
        )

        raw = json.loads(response.choices[0].message.content)
        rag_answer = RAGAnswer(**raw)

        # 4. 引用校验
        validation = validate_citation(rag_answer, results)

        # 5. 格式化展示
        return format_cited_answer(rag_answer, results, validation)


# ──────────────────────────────────────────────
# 主程序演示
# ──────────────────────────────────────────────

if __name__ == "__main__":
    knowledge_base = [
        "退款政策：购买后 30 天内可申请全额退款。超过 30 天不支持退款，但可申请换货。退款申请通过后，款项将在 3-5 个工作日内原路返回。",
        "联系客服：工作日 9:00-18:00 可拨打客服热线 400-888-8888，或发送邮件至 support@example.com。节假日不受理电话，但邮件 48 小时内回复。",
        "商品质保：所有商品享有一年质保。质保期内非人为损坏可免费维修或换货。人为损坏、进水、改装不在质保范围内。",
        "配送说明：订单确认后 24 小时内发货（周末顺延至周一），预计 3-5 个工作日送达。偏远地区可能需要 7-10 个工作日。",
        "会员积分规则：每消费 1 元获得 1 积分，积分有效期为自获得之日起 2 年。1000 积分可抵扣 10 元，每笔订单最多使用 5000 积分。",
    ]

    metadatas = [
        {"source": "product_policy.txt", "chunk_idx": 0},
        {"source": "contact_info.txt", "chunk_idx": 0},
        {"source": "warranty.txt", "chunk_idx": 0},
        {"source": "shipping.txt", "chunk_idx": 0},
        {"source": "membership.txt", "chunk_idx": 0},
    ]

    pipeline = CitedRAGPipeline()
    pipeline.build(knowledge_base, metadatas)

    test_questions = [
        "我三周前买的东西可以退货吗？",
        "周末能打客服电话吗？",
        "手机进水了还能保修吗？",
        "积分可以换礼品吗？",
        "今天股市涨了吗？",
    ]

    print("\n" + "=" * 60)
    for question in test_questions:
        print(f"\n问：{question}")
        answer = pipeline.ask(question, verbose=True)
        print(f"\n答：\n{answer}")
        print("\n" + "-" * 50)
```

---

## 六、引用策略对比实验

### 6.1 三版引用方案设计

对比"自然语言引用"、"结构化引用无校验"、"结构化引用 + 校验"三种方案：

```python
# 方案 A：自然语言引用（Day 19 V3 的做法）
PROMPT_A = """请只根据参考资料回答问题。
在回答中标注你的答案来自哪条资料（如"根据[资料1]"）。
如果资料中没有明确答案，说明无法回答。"""

# 方案 B：结构化引用，无校验
PROMPT_B = CITATION_SYSTEM  # 同 Day 20 正文的设计
# → 输出 JSON {"answer": "...", "sources": [1]}
# → 不做 validate_citation 校验，直接展示

# 方案 C：结构化引用 + 校验（Day 20 完整方案）
PROMPT_C = CITATION_SYSTEM
# → 输出 JSON + validate_citation + format_cited_answer
# → 含编号校验、拒答一致性、内容匹配三道防线
```

### 6.2 引用质量对比

以"积分可以换礼品吗？"为例（知识库 [5] 只提"积分抵扣"，没提"换礼品"）：

```
方案 A 输出（自然语言引用）：
  "根据[资料5]，积分可以兑换优惠券和实物礼品。"
  → 引用了资料，但内容是幻觉（资料没提礼品）
  → 用户看到"根据[资料5]"会信以为真

方案 B 输出（结构化引用，无校验）：
  {
    "answer": "积分可以兑换优惠券和实物礼品。",
    "sources": [5]
  }
  → 展示时附上 [5] 的原文
  → 用户看原文发现"没提礼品"→ 可以自行判断
  → 但系统没有主动标注这个问题

方案 C 输出（结构化引用 + 校验）：
  {
    "answer": "积分可以兑换优惠券和实物礼品。",
    "sources": [5]
  }
  → validate_citation 检测到 [5] 与 answer 关键词不匹配
  → 展示时标注：⚠ 引用 [5] 与回答内容不匹配，可能为虚构引用
  → 用户看到警告，知道不能全信
```

| 维度 | 方案 A（自然语言） | 方案 B（结构化无校验） | 方案 C（结构化+校验） |
|------|-------------------|---------------------|---------------------|
| 引用可解析性 | 低（需正则/模型） | 高（JSON 直接取） | 高 |
| 虚构引用检测 | 无法检测 | 无法检测 | 可检测 |
| 引用展示 | 模型混入文本 | 程序化展示 | 程序化展示 + 警告 |
| 实现复杂度 | 低 | 中 | 高 |
| 可信度 | 低 | 中 | 高 |
| 推荐场景 | 原型测试 | 内部 Demo | 生产环境 |

**结论**：方案 C 是生产级 RAG 的推荐方案——结构化输出保证可解析，校验机制保证可信，两者缺一不可。

---

## 七、Day 20 知识速查

### 引用机制完整流程

```
用户问题
    ↓
检索（Day 18）→ list[dict]（text, score, metadata）
    ↓
min_score 过滤 → 空列表？→ 拒答（Day 19）
    ↓
build_citation_prompt(query, contexts)
    ↓
LLM 生成 JSON {"answer": str, "sources": list[int]}
    ↓
validate_citation（三道防线）
    ↓
format_cited_answer → 回答 + 引用区块 + 警告
    ↓
展示给用户
```

### 引用校验三道防线速查

| 防线 | 检查内容 | 检测的虚构类型 |
|------|---------|---------------|
| 1. 编号有效性 | sources 中的编号是否在 1–N 范围内 | 越界引用 |
| 2. 拒答一致性 | answer="无法回答" 时 sources 是否为空 | 逻辑矛盾 |
| 3. 内容匹配性 | 引用资料与 answer 是否有共享关键词 | 内容虚构 |

### JSON Schema 模板

```python
from pydantic import BaseModel, Field

class RAGAnswer(BaseModel):
    answer: str = Field(description="基于参考资料生成的回答")
    sources: list[int] = Field(description="引用的资料编号列表")
```

### 最小可运行模板

```python
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/v1")

SYSTEM = """你是文档问答助手。只根据参考资料回答。
在 sources 字段标注引用的资料编号（整数列表）。
资料不足时 answer 设为"无法回答"，sources 设为 []。"""

def cited_rag(query, chunks):
    ctx = "\n\n".join(f"[资料{i+1}] {c}" for i, c in enumerate(chunks))
    user = f"参考资料：\n{ctx}\n\n问题：{query}"
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.1, max_tokens=800,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)
```

### 关键参数速查

| 参数 | 推荐值 | 说明 |
|------|-------|------|
| `response_format` | `{"type": "json_object"}` | 强制 JSON 输出，保证可解析 |
| `temperature` | 0.1 | 与 Day 19 一致，低随机性 |
| `top_k` | 3 | 检索 3 个 Chunk |
| `min_score` | 0.55–0.65 | 检索层拒答阈值 |
| `max_tokens` | 800 | answer + sources 的 JSON 结构 |

---

## 八、实践任务

- [ ] 在 Day 19 的 RAG 系统基础上，改造 Prompt 让模型输出 `{"answer", "sources"}` 结构化 JSON
- [ ] 实现引用溯源展示：回答后附上引用的原文片段，包含相关度分数和来源文件名
- [ ] 实现引用校验三道防线：编号有效性 + 拒答一致性 + 内容匹配性
- [ ] 用 5 个测试问题运行系统：3 个知识库内问题 + 1 个边界问题（需要推理）+ 1 个完全无关的问题，记录每个问题的引用是否准确
- [ ] 对比方案 A（自然语言引用）和方案 C（结构化+校验），观察虚构引用的检测效果

**产出标准**：

- 一个带引用溯源的 RAG 问答脚本，回答后附引用来源，用户能看出答案来自哪段文档
- 引用校验能检测出越界编号和内容不匹配的虚构引用
- 对完全无关的问题返回拒答文案，且不附带任何引用

---

## 九、下一步预告

**Day 21：复盘第 3 周**

Day 15–20 完成了 RAG 的完整链路，Day 21 要做第 3 周复盘：

- **RAG 全链路回顾**：文档加载 → 切分 → Embedding → 检索 → 生成 → 引用，六个环节的串联逻辑
- **复盘三大问题**：
  - RAG 的准确率主要受哪些环节影响
  - Chunk 切分为什么会直接影响答案质量
  - 为什么引用来源对业务场景很重要
- **完整最小 RAG Demo**：Day 15 原理 → Day 16 加载 → Day 17 切分 → Day 18 检索 → Day 19 生成 → Day 20 引用，Day 21 整合成一个完整的可展示作品
- **RAG 优化方向预告**：多路召回、Reranker、HyDE、查询改写（第二阶段进阶内容）
