# Day 17：文本切分

> 学习目标：掌握文本切分（Chunking）的多种策略及其适用场景——理解固定大小切分的局限，学会按段落/句子边界切分，实现递归切分器，并通过对比实验找到不同文档类型的最优参数
>
> 📚 所属阶段：**第二阶段 · RAG 核心应用架构**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 17
>
> 🧭 导航：[← Day 16 · 读取本地文档](day16_document_loader.md) [→ Day 18 · Embedding 与向量检索](day18_embedding_and_retrieval.md)

---

## 目录

- [一、为什么切分策略很重要](#一为什么切分策略很重要)
  - [1.1 切分质量对 RAG 效果的影响链](#11-切分质量对-rag-效果的影响链)
  - [1.2 四种切分策略总览](#12-四种切分策略总览)
- [二、固定大小切分](#二固定大小切分)
  - [2.1 按字符数切分](#21-按字符数切分)
  - [2.2 按 Token 数切分](#22-按-token-数切分)
  - [2.3 固定大小切分的局限](#23-固定大小切分的局限)
- [三、按语义边界切分](#三按语义边界切分)
  - [3.1 按段落切分](#31-按段落切分)
  - [3.2 按句子切分](#32-按句子切分)
  - [3.3 段落 + 大小限制的结合策略](#33-段落--大小限制的结合策略)
- [四、递归字符切分](#四递归字符切分)
  - [4.1 递归切分的思路](#41-递归切分的思路)
  - [4.2 完整实现](#42-完整实现)
- [五、切分策略对比实验](#五切分策略对比实验)
  - [5.1 实验框架](#51-实验框架)
  - [5.2 不同策略的 Chunk 分布对比](#52-不同策略的-chunk-分布对比)
  - [5.3 对 RAG 检索质量的影响](#53-对-rag-检索质量的影响)
- [六、Day 17 知识速查](#六day-17-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么切分策略很重要

### 1.1 切分质量对 RAG 效果的影响链

```
┌─────────────────────────────────────────────────────────────────────┐
│                 切分策略如何影响最终回答质量                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  切分过细（每块太小）：                                                │
│  "退款" → 向量化 → 检索到"30 天" 这个碎片                             │
│  → 模型只看到一个词，没有上下文 → "30 天什么？不知道"                  │
│                                                                      │
│  切分过粗（每块太大）：                                                │
│  整章 2000 字 → 一个向量 → 向量是"混合语义"                            │
│  → 检索"退款"时，召回这个 2000 字块                                    │
│  → 模型看到大量无关内容 → 被带偏，回答质量下降                          │
│                                                                      │
│  在语义边界切断：                                                      │
│  "退款需要 30 天内   |   提交申请并通过审核"                            │
│                     ↑ 错误切断点                                      │
│  → Chunk 1 只有"30 天内"，Chunk 2 只有"提交申请"                       │
│  → 检索"退款条件"时，两块都只包含一半信息                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**切分的核心矛盾**：

```
检索精度 ────────────────────────────── 上下文完整性
   ↑                                          ↑
Chunk 越小，检索越精准             Chunk 越大，上下文越完整
（但语义可能不完整）               （但检索时会带入大量无关内容）

最优切分：在"语义完整的自然边界"处切割，而不是按固定字符数机械切割
```

### 1.2 四种切分策略总览

| 策略 | 切分依据 | 优点 | 缺点 | 适用场景 |
|------|---------|------|------|---------|
| 固定字符数 | 每 N 个字符切一刀 | 实现简单，Chunk 大小均匀 | 可能在句子中间切断 | 快速原型，内容均匀的文档 |
| 固定 Token 数 | 每 N 个 Token 切一刀 | 与模型输入单位一致 | 实现稍复杂，需要 tokenizer | 精确控制模型输入成本 |
| 按段落/句子边界 | 双换行或句号等 | 保留语义完整性 | Chunk 大小不均匀 | 有清晰段落结构的文档 |
| 递归字符切分 | 先用大分隔符，再用小分隔符 | 兼顾语义边界和大小控制 | **推荐默认策略** | 通用文档 |

---

## 二、固定大小切分

### 2.1 按字符数切分

Day 15 已经实现了最简版的按词数切分，这里改为更精确的按字符数切分：

```python
def chunk_by_chars(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]
```

**字符数 vs 词数切分的差异**：

```
中文句子："退款政策规定：购买后 30 天内可申请退款。"
  按词数（每词≈1字）：每 300 词 ≈ 300 字
  按字符数：每 500 字符 ≈ 500 字（中英混合时字符数更准确）

英文句子："Refund policy: within 30 days of purchase."
  按词数：每 300 词 ≈ 平均英文单词长度约 5 字符，300 词 ≈ 1500 字符
  按字符数：更准确反映文本实际长度
```

**字符数切分的主要问题**：可能在汉字中间或英文单词中间切断（虽然可以找到最近的空格，但中文没有空格）。对于中英文混合文档，按字符数是可接受的简单策略，但有更好的替代方案。

### 2.2 按 Token 数切分

Token 是模型的实际计费和处理单位，按 Token 切分最准确地控制每块的模型处理成本：

```bash
pip install tiktoken
```

```python
import tiktoken

def chunk_by_tokens(
    text: str,
    chunk_size: int = 300,
    overlap: int = 50,
    model: str = "gpt-3.5-turbo",  # tiktoken 用模型名确定 tokenizer
) -> list[str]:
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]
```

**何时选按 Token 数切分**：
- 需要精确控制每个 Chunk 的模型处理成本（结合 Day 12 的成本意识）
- 知识库非常大，每块的 Token 数直接影响检索后喂给模型的成本
- 接入的 Embedding API 按 Token 计费时

**注意**：DeepSeek 的 tokenizer 和 GPT 系列有差异，如果没有 DeepSeek 专用的 tokenizer，用 `cl100k_base` 做粗估即可：

```python
enc = tiktoken.get_encoding("cl100k_base")  # 通用，不绑定特定模型
```

### 2.3 固定大小切分的局限

```
┌─────────────────────────────────────────────────────────────────────┐
│  固定大小切分的问题（以字符数为例，chunk_size=50）                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  原始文本：                                                           │
│  "退款政策规定：购买后 30 天内可申请退款。退款需通过官网客服提交。"          │
│                                                                      │
│  chunk_size=30, overlap=0 的结果：                                   │
│  Chunk 1: "退款政策规定：购买后 30 天内可申请退"                        │
│                                                 ↑ 从"退"字处截断      │
│  Chunk 2: "款。退款需通过官网客服提交。"                               │
│           ↑ "款"是上一句的结尾，被带进了下一块                          │
│                                                                      │
│  这种切断不影响人类阅读（能拼起来），但向量化后，                          │
│  Chunk 1 的语义被"截断的退字"污染了                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

固定大小切分是最简单的入门策略，但在文档质量要求较高的场景下，需要更智能的语义边界切分。

---

## 三、按语义边界切分

### 3.1 按段落切分

段落（双换行分隔）是文档中最自然的语义单元，每个段落通常表达一个完整的思想：

```python
def chunk_by_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n")]
    return [p for p in paragraphs if len(p) > 20]  # 过滤掉太短的段落（可能是噪音）
```

**段落切分的问题**：段落大小差异极大——有的段落只有一行（几十字），有的段落长达几千字。直接按段落切分会导致 Chunk 大小非常不均匀，影响检索的稳定性（太短的块语义不完整，太长的块精度低）。

**处理方案**：段落切分后，对太长的段落再做二次切分，对太短的段落进行合并：

```python
def chunk_by_paragraphs_bounded(
    text: str,
    min_size: int = 100,
    max_size: int = 800,
) -> list[str]:
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for para in raw_paragraphs:
        if len(current) + len(para) <= max_size:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current and len(current) >= min_size:
                chunks.append(current)
            current = para

        # 如果单个段落已经超过 max_size，强制切分
        while len(current) > max_size:
            chunks.append(current[:max_size])
            current = current[max_size:]

    if current and len(current) >= min_size:
        chunks.append(current)

    return chunks
```

### 3.2 按句子切分

比段落更细粒度的语义单元是句子。按句子切分能保证每块都是完整的表述，适合回答精度要求高的场景：

```python
import re

def split_sentences(text: str) -> list[str]:
    # 中英文句子分隔符：。！？.!? 后面跟空格或换行
    pattern = r'(?<=[。！？.!?])\s*'
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_by_sentences(
    text: str,
    chunk_size: int = 300,
    overlap_sentences: int = 1,
) -> list[str]:
    sentences = split_sentences(text)
    chunks = []
    current_sentences = []
    current_len = 0

    for sent in sentences:
        if current_len + len(sent) > chunk_size and current_sentences:
            chunks.append(" ".join(current_sentences))
            # overlap：保留最后 N 句作为下一块的开头
            current_sentences = current_sentences[-overlap_sentences:]
            current_len = sum(len(s) for s in current_sentences)

        current_sentences.append(sent)
        current_len += len(sent)

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks
```

**句子切分 vs 字符数切分的对比**：

```
原文："退款政策规定：购买后 30 天内可申请退款。退款需通过官网客服提交。审核通过后 3-5 个工作日退回。"

字符数切分（chunk_size=30）：
  "退款政策规定：购买后 30 天内可申请" / "退款。退款需通过官网客服提交。" / ...
  → 切断了"申请退款"

句子切分：
  "退款政策规定：购买后 30 天内可申请退款。" / "退款需通过官网客服提交。" / "审核通过后 3-5 个工作日退回。"
  → 每句话是完整的语义单元
```

### 3.3 段落 + 大小限制的结合策略

实践中最常用的策略是"先找语义边界，再做大小兜底"：

```
步骤：
  1. 按段落切分（双换行）
  2. 相邻的短段落合并（直到接近 max_size）
  3. 超长段落继续按句子切分
  4. 最终保证每块在 [min_size, max_size] 范围内
```

这个策略在下一节的递归切分器里会以更优雅的方式实现。

---

## 四、递归字符切分

### 4.1 递归切分的思路

递归字符切分（Recursive Character Text Splitter）是 LangChain 中最受欢迎的切分器，思路如下：

```
给定一组按优先级排列的分隔符：["\n\n", "\n", "。", ".", " ", ""]

尝试用最高优先级的分隔符（"\n\n"，即段落）切分：
  ✓ 如果切分后每块 ≤ chunk_size → 完成
  ✗ 如果某块仍然 > chunk_size → 用下一个分隔符（"\n"，即行）继续切这块
  ✗ 如果仍然 > chunk_size → 用句子分隔符继续
  ✗ 如果仍然 > chunk_size → 用空格（英文词）继续
  ✗ 如果仍然 > chunk_size → 按字符强制切分（最后的兜底）

结果：尽可能在语义边界处切，只有在找不到合适边界时才强制截断
```

### 4.2 完整实现

```python
from __future__ import annotations


class RecursiveCharacterSplitter:
    """
    递归字符切分器：优先在语义边界处切，大小超限时递归用更细粒度的分隔符
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", "。", ".", "！", "!", "？", "?", "；", ";", " ", ""]

    def __init__(
        self,
        chunk_size: int = 400,
        chunk_overlap: int = 80,
        separators: list[str] | None = None,
        min_chunk_size: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS
        self.min_chunk_size = min_chunk_size

    def split(self, text: str) -> list[str]:
        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        if not separators:
            # 所有分隔符都试过了，强制按字符切
            return self._split_by_size(text)

        sep = separators[0]
        remaining = separators[1:]

        if sep == "":
            return self._split_by_size(text)

        parts = text.split(sep)

        chunks: list[str] = []
        current = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            candidate = (current + sep + part).strip() if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                    # Overlap：把 current 的最后一部分带入下一块
                    overlap_text = current[-self.chunk_overlap:] if len(current) > self.chunk_overlap else current
                    current = (overlap_text + sep + part).strip() if overlap_text else part
                else:
                    # 单个 part 就已经超过 chunk_size，递归处理
                    sub_chunks = self._split_recursive(part, remaining)
                    if sub_chunks:
                        chunks.extend(sub_chunks[:-1])
                        current = sub_chunks[-1]

        if current and len(current) >= self.min_chunk_size:
            chunks.append(current)

        return [c for c in chunks if len(c) >= self.min_chunk_size]

    def _split_by_size(self, text: str) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk = text[start:end].strip()
            if len(chunk) >= self.min_chunk_size:
                chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        return chunks
```

---

## 五、切分策略对比实验

### 5.1 实验框架

用同一份文档测试不同策略，记录 Chunk 数量、大小分布和对 RAG 检索的影响：

```python
from statistics import mean, stdev


def analyze_chunks(chunks: list[str], strategy_name: str) -> dict:
    sizes = [len(c) for c in chunks]
    return {
        "strategy": strategy_name,
        "count": len(chunks),
        "mean_size": round(mean(sizes), 1) if sizes else 0,
        "std_size": round(stdev(sizes), 1) if len(sizes) > 1 else 0,
        "min_size": min(sizes) if sizes else 0,
        "max_size": max(sizes) if sizes else 0,
    }


def compare_strategies(text: str) -> None:
    splitter = RecursiveCharacterSplitter(chunk_size=400, chunk_overlap=80)

    strategies = {
        "固定字符(400/80)": chunk_by_chars(text, 400, 80),
        "按段落限大小(100-800)": chunk_by_paragraphs_bounded(text, 100, 800),
        "按句子(300字/1句重叠)": chunk_by_sentences(text, 300, 1),
        "递归切分(400/80)": splitter.split(text),
    }

    print(f"{'策略':<20}{'块数':>6}{'均值':>8}{'标准差':>8}{'最小':>8}{'最大':>8}")
    print("-" * 60)
    for name, chunks in strategies.items():
        r = analyze_chunks(chunks, name)
        print(f"{r['strategy']:<20}{r['count']:>6}{r['mean_size']:>8}{r['std_size']:>8}"
              f"{r['min_size']:>8}{r['max_size']:>8}")
```

### 5.2 不同策略的 Chunk 分布对比

以一份 3000 字的产品文档为例，典型对比结果：

```
策略                块数    均值     标准差    最小    最大
------------------------------------------------------------
固定字符(400/80)      9     388      45       320     400   ← 大小最均匀，但可能截断句子
按段落限大小(100-800) 6     520     180       120     780   ← 大小差异大，但保留了段落结构
按句子(300字/1句重叠) 12    255      95        45     310   ← 大小适中，每块都是完整句子
递归切分(400/80)      8     375      85       100     400   ← 最均匀且最少在句子中截断
```

**结论**：递归切分在"大小均匀"和"语义完整"之间取得了最好的平衡——这正是它成为 LangChain 默认切分器的原因。

### 5.3 对 RAG 检索质量的影响

用一组测试问题，分别用不同策略构建索引后检索，对比最相关 Chunk 的相似度分数：

```python
from sentence_transformers import SentenceTransformer
import numpy as np


def evaluate_retrieval(
    query: str,
    text: str,
    strategies: dict[str, list[str]],
    top_k: int = 1,
) -> None:
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    q_vec = model.encode([query])[0]

    print(f"\n问题：{query}")
    print(f"{'策略':<22}{'最高相似度':>12}{'最相关片段（前40字）'}")
    print("-" * 80)

    for name, chunks in strategies.items():
        if not chunks:
            continue
        vecs = model.encode(chunks)
        scores = [
            float(np.dot(q_vec, v) / (np.linalg.norm(q_vec) * np.linalg.norm(v)))
            for v in vecs
        ]
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        best_score = scores[best_idx]
        best_chunk = chunks[best_idx][:40].replace("\n", " ")
        print(f"{name:<22}{best_score:>12.4f}  {best_chunk}...")
```

典型结果：**递归切分和句子切分通常检索相似度最高**（因为 Chunk 内部语义更纯粹），固定字符切分次之，过粗的段落切分最差（因为一块里混了太多话题，向量是平均语义）。

---

## 六、Day 17 知识速查

### 切分策略选择指南

```
文档类型 / 需求 → 推荐策略：

  快速原型或文档结构不明确    → 固定字符数（chunk_size=300, overlap=50）
  
  有清晰段落结构（报告/手册）  → 段落切分 + 大小边界（min=100, max=800）
  
  高精度回答（法律/合同/FAQ）  → 句子切分（chunk_size=200, overlap_sentences=1）
  
  通用文档（首选）            → 递归字符切分（chunk_size=400, overlap=80）
```

### 参数选取经验

| 参数 | 默认推荐值 | 何时调大 | 何时调小 |
|------|-----------|---------|---------|
| `chunk_size` | 400 字符 | 问答需要更多上下文；文档句子很长 | 检索精度要求高；输入成本敏感 |
| `chunk_overlap` | 80 字符（20%） | 边界处经常遗漏关键信息 | 索引大小敏感；文档结构清晰 |
| `min_chunk_size` | 50 字符 | 文档有大量短小标题 | 无需调整 |

### 最小代码模板

```python
splitter = RecursiveCharacterSplitter(chunk_size=400, chunk_overlap=80)
chunks = splitter.split(document_text)

# 接入 Day 15/16 的 RAG 流程
from day16_document_loader import load_directory
docs = load_directory("./知识库/")
all_chunks = [c for doc in docs for c in splitter.split(doc.text)]
```

---

## 七、实践任务

- [ ] 准备一份 500 字以上的中文文本（可以是任意文章或前几天的笔记内容）
- [ ] 分别用四种策略（固定字符/段落/句子/递归）对这份文本切分，打印每种策略的 Chunk 数量和大小统计
- [ ] 用 `compare_strategies()` 函数对比结果，观察哪些位置被固定字符切分但在递归切分中得到了保留
- [ ] 实现 `RecursiveCharacterSplitter`，集成进 Day 16 的 `DocumentLoader`，替换掉 Day 15 的简单 `chunk_text()`
- [ ] 选一个测试问题，用不同策略构建 RAG 索引后检索，对比最高相似度分数

**产出标准**：

- 一个切分脚本，支持四种策略，能打印每种策略的 Chunk 数量和大小分布
- `RecursiveCharacterSplitter` 成功集成到 RAG 流程，问答链路可以端到端运行

---

## 八、下一步预告

**Day 18：接入 Embedding 和向量检索**

Day 17 解决了"怎么切"的问题，Day 18 要深入"怎么向量化"：

- Day 15 用的是本地 `sentence-transformers`，Day 18 会引入 API-based Embedding（OpenAI / DeepSeek）
- 向量数据库：从 Day 15 的纯 numpy 数组升级到真正的向量数据库（Chroma / FAISS）
- 相似度检索的几种变体：余弦相似度 vs 内积 vs L2 距离，适用场景各不同
- 批量向量化优化：一次请求向量化多个 Chunk，降低 API 调用次数和成本
