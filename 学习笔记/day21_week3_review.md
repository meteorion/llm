# Day 21：第 3 周复盘

> 学习目标：系统梳理 Day 15–20 的 RAG 完整闭环，深度回答三个复盘问题（RAG 准确率的影响链、Chunk 切分对质量的传导路径、引用来源的业务必要性），整理出一个可运行的完整最小 RAG Demo
>
> 📚 所属阶段：**第二阶段 · RAG 核心应用架构**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 21
>
> 🧭 导航：[← Day 20 · 给回答加引用](day20_answer_citation.md) [→ Day 22 · 理解 Tool Calling](day22_tool_calling_basics.md)

---

## 目录

- [一、第 3 周全景回顾](#一第-3-周全景回顾)
  - [1.1 Day 15–20 知识地图](#11-day-1520-知识地图)
  - [1.2 本周六个主题的逻辑链](#12-本周六个主题的逻辑链)
- [二、深度复盘三大问题](#二深度复盘三大问题)
  - [2.1 RAG 准确率主要受哪些环节影响](#21-rag-准确率主要受哪些环节影响)
  - [2.2 Chunk 切分为什么会直接影响答案质量](#22-chunk-切分为什么会直接影响答案质量)
  - [2.3 为什么引用来源对业务场景很重要](#23-为什么引用来源对业务场景很重要)
- [三、完整最小 RAG Demo](#三完整最小-rag-demo)
- [四、第 3 周完整工程骨架](#四第-3-周完整工程骨架)
- [五、Day 21 知识速查](#五day-21-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、第 3 周全景回顾

### 1.1 Day 15–20 知识地图

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       第 3 周知识地图（Day 15–20）                           │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Day 15 · RAG 基本原理                                                     │
│  ────────────────────────────────────────────────────────────────         │
│  知识局限三大问题（截止/私有/幻觉）→ 离线构建+在线问答两阶段→ 纯Python最小RAG   │
│                           │                                                │
│                           ↓                                                │
│  Day 16 · 读取本地文档                                                     │
│  ────────────────────────────────────────────────────────────────         │
│  TXT/MD/PDF 三格式读取 → 编码自动检测（chardet）→ 文本清洗 → 统一Document    │
│                           │                                                │
│                           ↓                                                │
│  Day 17 · 文本切分                                                         │
│  ────────────────────────────────────────────────────────────────         │
│  固定字符/Token → 段落/句子边界 → RecursiveCharacterSplitter → 策略对比实验  │
│                           │                                                │
│                           ↓                                                │
│  Day 18 · Embedding 与向量检索                                             │
│  ────────────────────────────────────────────────────────────────         │
│  句向量原理 → API/本地 Embedding → 余弦相似度 → FAISS/Chroma 向量库          │
│                           │                                                │
│                           ↓                                                │
│  Day 19 · RAG 问答生成                                                     │
│  ────────────────────────────────────────────────────────────────         │
│  上下文拼接策略 → "只根据资料回答"约束 → 双层拒答逻辑 → 端到端问答生成器       │
│                           │                                                │
│                           ↓                                                │
│  Day 20 · 给回答加引用                                                     │
│  ────────────────────────────────────────────────────────────────         │
│  结构化 JSON 引用 → 三道校验防线（格式/逻辑/语义）→ 引用溯源展示               │
│                                                                            │
└───────────────────────────────────────────────────────────────────────────┘
```

### 1.2 本周六个主题的逻辑链

第 3 周的六个主题是同一条数据流的六个环节——**把"私有文档"转化为"可信回答"**。每一步的质量直接决定最终效果：

```
原始文档（PDF/TXT/MD）
    ↓
Day 16 · 读取与清洗：噪音决定后续所有环节的信噪比
    ↓
Day 17 · 文本切分：Chunk 质量决定检索颗粒度和语义完整性
    ↓
Day 18 · Embedding 与向量检索：相似度计算决定"找到什么"
    ↓
Day 19 · 上下文增强与生成：拼接策略 + 约束 Prompt 决定"说什么"
    ↓
Day 20 · 引用溯源：校验机制决定"是否可信"
    ↓
可解释的 RAG 问答系统（Day 21 整合）
```

这条链路**每一步都是瓶颈**：再好的 LLM 也救不了"读入了满是噪音的文档"；再精准的 Prompt 也救不了"把关键句子切断到不同 Chunk 里"。**RAG 的质量上限由最弱的环节决定**，不是由最强的环节决定。

---

## 二、深度复盘三大问题

### 2.1 RAG 准确率主要受哪些环节影响

"准确率"在 RAG 场景下有两层含义：
- **检索准确率**：提问后能否找到包含答案的 Chunk
- **生成准确率**：找到了正确 Chunk 后，最终回答是否忠实地提取了答案

这两层是串联的——检索准确率是上界，生成准确率不可能超过它。

```
RAG 准确率影响链（由上游到下游）：

  ┌─────────────────────────────────────────────────────────────────┐
  │ 环节 1：文档读取质量                                              │
  │   噪音过多 → Chunk 向量被噪音"稀释" → 与问题相似度虚假降低         │
  │   典型表现：正确答案在文档里，但没被召回（召回率低）               │
  │   修复：文本清洗（去页眉页脚、压缩空行）+ 编码正确处理              │
  ├─────────────────────────────────────────────────────────────────┤
  │ 环节 2：切分策略                                                  │
  │   切断语义边界 → 单个 Chunk 语义不完整 → 向量表示不准确            │
  │   典型表现：模型说"资料不足"，实际上答案就在相邻两个 Chunk 的边界   │
  │   修复：RecursiveCharacterSplitter + 合理 Overlap（~15%）        │
  ├─────────────────────────────────────────────────────────────────┤
  │ 环节 3：Embedding 模型选择                                        │
  │   中英文混用的文档用纯英文模型 → 中文语义失真                      │
  │   典型表现："产品 A 的退款政策"检索不到关于"A 商品"的相关段落       │
  │   修复：使用多语言或专门中文 Embedding 模型                        │
  ├─────────────────────────────────────────────────────────────────┤
  │ 环节 4：Top-K 和相似度阈值                                        │
  │   Top-K 过小 → 答案在第 4 条但只取 Top-3 → 漏召回                │
  │   阈值过高 → 本来相关的 Chunk 被过滤 → 误拒答                     │
  │   典型表现：问模型"有没有相关信息"，模型说"没有"，但文档里有         │
  │   修复：先调 Top-K（5–10），再用阈值过滤（0.5–0.65）              │
  ├─────────────────────────────────────────────────────────────────┤
  │ 环节 5：Prompt 约束强度                                           │
  │   约束太弱 → 模型混入训练知识回答，看起来准确但来源不可追溯         │
  │   约束太强 → 资料稍有瑕疵就拒答，用户体验差                        │
  │   典型表现：禁用搜索引擎后还能回答"GPT-4 是 2023 年发布的"         │
  │   修复：System Prompt 明确"未在参考资料中的内容必须说无法回答"      │
  └─────────────────────────────────────────────────────────────────┘
```

**诊断优先级**：遇到 RAG 答案不准时，先检查检索结果（打印 Top-K 的 Chunk 内容），再检查文档读取（打印原始文本），最后才调整 Prompt。

```python
def debug_rag(query: str, store, embed_fn):
    q_vec = embed_fn([query])[0]
    results = store.search(q_vec, top_k=5, min_score=0.0)  # 阈值设 0 看全部结果
    print(f"=== 检索结果 (Top-5) ===")
    for i, r in enumerate(results):
        print(f"[{i+1}] score={r['score']:.3f} | {r['text'][:100]}...")
    # 如果答案在这里 → 问题在生成层（Prompt/约束）
    # 如果答案不在这里 → 问题在检索层（切分/Embedding/阈值）
```

### 2.2 Chunk 切分为什么会直接影响答案质量

Chunk 切分的影响是**系统性的**，不是局部的——一个错误的切分决策会在后续所有环节中被放大，最终导致看起来"模型问题"实则是"数据处理问题"。

**影响路径一：切断语义 → 向量表示失真**

```
原始文档：
  "退款申请需在购买后 30 天内提交。提交后 3-5 个工作日退回原支付方式。"

切分后（在"提交"后切断）：
  Chunk A：退款申请需在购买后 30 天内提交。
  Chunk B：提交后 3-5 个工作日退回原支付方式。

问题："退款需要多长时间处理？"

Chunk A 向量：包含"退款/30天/提交"→ 与"多长时间"相关度较高
Chunk B 向量：包含"提交/工作日/退回"→ 与"多长时间"相关度较高
但 Chunk A 不包含"处理时间"，Chunk B 不包含完整语境
→ 检索到了但给出了不完整的答案
```

**影响路径二：Chunk 过小 → 检索噪音多**

```
Chunk Size = 50 Token（过小）：
  Chunk 1: "关于退款政策"
  Chunk 2: "申请需在 30 天内"
  Chunk 3: "提交至客服邮箱"
  Chunk 4: "我们将在"
  Chunk 5: "3-5 个工作日内处理"

问题："退款如何申请？"
→ Top-3 结果可能包含 Chunk 1、2、4——拼在一起语义跳跃
→ 模型看到 "...申请需在 30 天内...我们将在..." 的拼接，理解困难
```

**影响路径三：Chunk 过大 → 检索精度下降**

```
Chunk Size = 2000 Token（过大）：
  单个 Chunk 包含：退款政策 + 发货政策 + 会员权益 + 投诉流程

问题："退款需要多久？"
→ Chunk 向量是整段内容的"平均"，被非退款内容稀释
→ 相似度得分低于只谈退款的小 Chunk，可能排名靠后
→ 同时喂给模型 2000 Token 的混杂内容，干扰生成质量
```

**切分参数的实用选择指南**：

| 文档类型 | Chunk Size | Overlap | 切分策略 |
|---------|-----------|---------|---------|
| FAQ 问答对 | 100–200 Token | 20 Token | 按条目（每问一 Chunk） |
| 通用文档（说明书、手册） | 300 Token | 50 Token（默认） | RecursiveCharacterSplitter |
| 法律/合同（长句、严格逻辑） | 500 Token | 100 Token | 段落边界优先 |
| 技术文档（代码+说明） | 400 Token | 60 Token | 按函数/类边界 |

### 2.3 为什么引用来源对业务场景很重要

这道题的答案超越了技术层面，涉及**系统信任度**的本质——在业务场景中，"答案是否正确"和"答案是否可信"是两个不同的问题，引用机制解决的是后者。

```
两类 RAG 错误的不同破坏力：

  类型 A：模型给出了错误答案（无引用）
    用户："退款需要多久？"
    系统："3 个工作日"（实际是 5 个）
    影响：用户等了 3 天没到账，打电话投诉 → 1 个用户的体验问题
  
  类型 B：模型给出了错误答案（无引用）+ 用户相信了它
    系统（同样的答案）："3 个工作日"（实际是 5 个）
    影响：用户告诉 10 个朋友"他们家退款只需 3 天"
          → 10 个朋友都产生错误预期 → 10 个投诉 → 信誉损失
  
  类型 C：模型给出了错误答案（有引用）
    系统："3 个工作日 [1]"，[1] 实际写的是"5 个工作日"
    影响：用户点击查看 [1]，发现原文是 5 天 → 发现了系统的错误
          → 用户对系统保持合理质疑，不会传播错误信息
          → 企业有机会修复知识库，而不是等到投诉积累
```

**引用的核心价值——让用户保持合理质疑**：

```
  没有引用：用户必须选择"信"或"不信"
             → 习惯信任 → 偶发错误被放大
             → 习惯不信 → 系统失去使用价值
  
  有引用：用户可以"带着问题信"
           → 重要决策时验证来源 → 建立有边界的信任
           → 轻微问题时直接接受 → 降低使用成本
```

**三类业务场景引用必要性对比**：

| 业务场景 | 引用必要性 | 原因 |
|---------|----------|------|
| 企业知识库客服 | 极高 | 错误信息可能导致法律纠纷（如退款政策、合同条款） |
| 医疗/法律咨询 | 极高 | 错误信息有安全风险，用户需要原始来源做决策 |
| 内部工作助手 | 高 | 员工需要引用政策文件向上级说明依据 |
| 个人知识库问答 | 中 | 用户了解自己的知识库边界，但仍需定位原文 |
| 纯娱乐聊天机器人 | 低 | 没有需要追溯的权威来源 |

---

## 三、完整最小 RAG Demo

把 Day 15–20 的所有组件整合成一个完整的、带引用的 RAG 系统。这是第 3 周的核心产出。

```python
"""
week3_rag_demo.py — 完整最小 RAG Demo（带引用与校验）
整合：文档加载（Day 16）/ 文本切分（Day 17）/ Embedding+检索（Day 18）
     / 问答生成（Day 19）/ 引用溯源（Day 20）
"""

import os
import json
import re
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── 文档结构（Day 16）─────────────────────────────────────────────────────

@dataclass
class Document:
    text: str
    source: str
    metadata: dict = field(default_factory=dict)


# ─── 文档加载（Day 16）─────────────────────────────────────────────────────

def load_txt(path: str) -> Document:
    for enc in ["utf-8", "utf-8-sig", "gbk", "gb2312"]:
        try:
            text = Path(path).read_text(encoding=enc)
            return Document(text=_clean(text), source=path)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(f"无法读取 {path}")


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ─── 文本切分（Day 17）─────────────────────────────────────────────────────

class RecursiveCharacterSplitter:
    def __init__(self, size: int = 300, overlap: int = 50):
        self.size = size
        self.overlap = overlap
        self._seps = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]

    def split(self, text: str) -> list[str]:
        return self._split_text(text, self._seps)

    def _split_text(self, text: str, seps: list[str]) -> list[str]:
        sep = ""
        rest_seps = []
        for s in seps:
            if s == "" or s in text:
                sep = s
                rest_seps = seps[seps.index(s) + 1:]
                break
        parts = text.split(sep) if sep else [text]
        chunks, current = [], ""
        for part in parts:
            candidate = (current + sep + part).strip() if current else part.strip()
            if len(candidate) <= self.size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > self.size and rest_seps:
                    chunks.extend(self._split_text(part, rest_seps))
                    current = ""
                else:
                    current = part
        if current:
            chunks.append(current)
        # 加 Overlap
        result = []
        for i, chunk in enumerate(chunks):
            if i > 0 and self.overlap > 0:
                prev = chunks[i - 1]
                overlap_text = prev[-self.overlap:] if len(prev) > self.overlap else prev
                chunk = overlap_text + chunk
            result.append(chunk)
        return [c for c in result if len(c.strip()) > 20]


# ─── Embedding（Day 18）────────────────────────────────────────────────────
# 与 Day 18 保持一致：默认使用本地 sentence-transformers，避免与 DeepSeek
# Embedding 端点的模型名称混淆（text-embedding-3-small 是 OpenAI 专有名称）。

class EmbeddingModel:
    def __init__(self, mode: str = "local"):
        self.mode = mode
        if mode == "api":
            self._client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/v1",
            )
            self._api_model = "deepseek-embedding"
        else:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2"
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.mode == "api":
            resp = self._client.embeddings.create(input=texts, model=self._api_model)
            return [item.embedding for item in resp.data]
        vecs = self._local_model.encode(texts, show_progress_bar=False)
        return vecs.tolist()


# ─── 向量库（Day 18）───────────────────────────────────────────────────────

class VectorStore:
    def __init__(self):
        self._texts: list[str] = []
        self._vecs: list[list[float]] = []
        self._sources: list[str] = []

    def add(self, texts: list[str], vecs: list[list[float]], sources: list[str]):
        self._texts.extend(texts)
        self._vecs.extend(vecs)
        self._sources.extend(sources)

    def search(self, q_vec: list[float], top_k: int = 3, min_score: float = 0.55) -> list[dict]:
        if not self._vecs:
            return []
        q = np.array(q_vec)
        scores = []
        for v in self._vecs:
            arr = np.array(v)
            cos = float(np.dot(q, arr) / (np.linalg.norm(q) * np.linalg.norm(arr) + 1e-8))
            scores.append(cos)
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            {"text": self._texts[i], "score": scores[i], "source": self._sources[i]}
            for i in top_idx if scores[i] >= min_score
        ]


# ─── 引用回答结构（Day 20）─────────────────────────────────────────────────

@dataclass
class RAGAnswer:
    answer: str
    sources: list[int]


# ─── 引用校验（Day 20）────────────────────────────────────────────────────

def validate_citation(rag_answer: RAGAnswer, contexts: list[dict]) -> dict:
    issues = []
    valid_sources = []
    for src in rag_answer.sources:
        if 1 <= src <= len(contexts):
            valid_sources.append(src)
        else:
            issues.append(f"引用编号 {src} 越界（共 {len(contexts)} 条资料）")
    is_refusal = any(kw in rag_answer.answer for kw in ["无法回答", "不在参考资料", "未找到"])
    if is_refusal and valid_sources:
        issues.append("回答为拒答但 sources 非空，存在逻辑矛盾")
    for src in valid_sources:
        ctx_text = contexts[src - 1]["text"]
        answer_words = set(rag_answer.answer.replace(" ", ""))
        ctx_words = set(ctx_text.replace(" ", ""))
        shared = len(answer_words & ctx_words)
        if shared < 3:
            issues.append(f"引用 [{src}] 与回答内容关键词重合度低，可能为虚构引用")
    return {"is_valid": len(issues) == 0, "valid_sources": valid_sources, "issues": issues}


# ─── 完整 RAG Pipeline（Day 15–20 整合）────────────────────────────────────

class RAGPipeline:
    def __init__(self):
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )
        self.llm = client
        self.embedder = EmbeddingModel(mode="local")  # 与 Day 18 一致，默认用本地模型
        self.splitter = RecursiveCharacterSplitter(size=300, overlap=50)
        self.store = VectorStore()

    def build(self, docs: list[Document]) -> None:
        all_chunks, all_sources = [], []
        for doc in docs:
            chunks = self.splitter.split(doc.text)
            all_chunks.extend(chunks)
            all_sources.extend([doc.source] * len(chunks))
        vecs = self.embedder.embed(all_chunks)
        self.store.add(all_chunks, vecs, all_sources)
        print(f"索引构建完成：{len(all_chunks)} 个 Chunk")

    def ask(self, query: str) -> str:
        q_vec = self.embedder.embed([query])[0]
        results = self.store.search(q_vec, top_k=3, min_score=0.55)

        if not results:
            return "根据当前知识库，未找到与您问题相关的信息。"

        context_parts = []
        for i, r in enumerate(results):
            context_parts.append(f"[资料 {i+1}]（来源：{r['source']}）\n{r['text']}")
        context = "\n\n---\n\n".join(context_parts)

        messages = [
            {
                "role": "system",
                "content": (
                    "你是文档问答助手，严格根据参考资料回答问题。"
                    "回答时必须引用资料编号，格式为 [编号]。"
                    "输出 JSON，格式：{\"answer\": \"回答文本（含[编号]标注）\", \"sources\": [编号列表]}。"
                    "参考资料中没有的内容请明确说无法回答，sources 填空列表。"
                    "只输出 JSON，不输出任何其他内容。"
                ),
            },
            {
                "role": "user",
                "content": f"参考资料：\n\n{context}\n\n问题：{query}",
            },
        ]

        resp = self.llm.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        rag_answer = RAGAnswer(answer=data.get("answer", ""), sources=data.get("sources", []))

        validation = validate_citation(rag_answer, results)

        return _format_answer(rag_answer, results, validation)


def _format_answer(rag_answer: RAGAnswer, results: list[dict], validation: dict) -> str:
    lines = [rag_answer.answer, ""]
    if validation["valid_sources"]:
        lines.append("📎 引用来源：")
        for src in validation["valid_sources"]:
            ctx = results[src - 1]
            snippet = ctx["text"][:80] + ("…" if len(ctx["text"]) > 80 else "")
            lines.append(f"  [{src}] {ctx['source']}")
            lines.append(f"      "{snippet}"")
    if validation["issues"]:
        lines.append("")
        for issue in validation["issues"]:
            lines.append(f"⚠ {issue}")
    return "\n".join(lines)


# ─── 运行示例 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 创建示例文档
    sample_text = """
退款政策

退款申请需在购买后 30 天内提交。超过 30 天将不予受理。

退款申请提交后，我们将在 3-5 个工作日内退回原支付方式。
节假日可能延长至 7 个工作日。

以下情况不支持退款：
- 数字内容（如电子书、软件激活码）已激活
- 定制商品已生产
- 食品类商品已拆封

如需申请退款，请联系客服邮箱：support@example.com
    """.strip()

    pipeline = RAGPipeline()
    pipeline.build([Document(text=sample_text, source="退款政策.txt")])

    questions = [
        "退款需要多久处理？",
        "超过 30 天还能退款吗？",
        "数字内容可以退款吗？",
        "如何联系客服？",
        "商品保修政策是什么？",  # 知识库中没有，期望拒答
    ]

    for q in questions:
        print(f"\n{'='*60}")
        print(f"问题：{q}")
        print("-" * 40)
        print(pipeline.ask(q))
```

---

## 四、第 3 周完整工程骨架

第 3 周各 Day 的核心组件与接口速查：

```
week3_rag/
├── document_loader.py     # Day 16：Document dataclass + load_txt/load_md/load_pdf
├── text_splitter.py       # Day 17：RecursiveCharacterSplitter + split_by_paragraph
├── embedding.py           # Day 18：EmbeddingModel（API/本地）+ 批量向量化
├── vector_store.py        # Day 18：VectorStore（numpy/FAISS/Chroma）+ 持久化
├── rag_generator.py       # Day 19：build_prompt + 约束生成 + 双层拒答
├── citation.py            # Day 20：RAGAnswer + validate_citation + format_answer
└── rag_pipeline.py        # Day 21：RAGPipeline（组合以上所有模块）
```

各模块接口契约：

| 模块 | 输入 | 输出 | 关键依赖 |
|------|------|------|---------|
| `document_loader` | 文件路径 | `Document(text, source)` | chardet、pdfplumber |
| `text_splitter` | `str` | `list[str]`（Chunks） | 无 |
| `embedding` | `list[str]` | `list[list[float]]` | OpenAI/sentence-transformers |
| `vector_store` | Chunks + 向量 | 检索结果 `list[dict]` | numpy/faiss/chromadb |
| `rag_generator` | query + contexts | `str`（回答 JSON） | OpenAI |
| `citation` | `RAGAnswer` + contexts | 校验结果 + 格式化展示 | 无 |

---

## 五、Day 21 知识速查

### 第 3 周六个主题一览

| Day | 主题 | 核心产出 | 关键工具/概念 |
|-----|------|---------|-------------|
| 15 | RAG 基本原理 | 离线+在线两阶段 + 最小实现 | 向量检索 + 增强 Prompt |
| 16 | 读取本地文档 | 多格式统一加载器 | chardet, pdfplumber, Document |
| 17 | 文本切分 | RecursiveCharacterSplitter | Chunk Size / Overlap 参数 |
| 18 | Embedding 与检索 | 向量索引 + 相似度检索 | sentence-transformers / FAISS |
| 19 | RAG 问答生成 | 双层拒答 + 约束 Prompt | 三明治排列 / Lost in Middle |
| 20 | 引用与可解释性 | 结构化引用 + 三道校验 | RAGAnswer / validate_citation |

### RAG 问题诊断速查

```
回答错误 or 模型说"没有相关信息"但文档里有？

  Step 1：打印 Top-K 检索结果
    ├── 结果里有正确 Chunk → 问题在生成层（Prompt/约束过强）
    └── 结果里没有正确 Chunk → 问题在检索层
         ├── 降低 min_score 阈值，再搜一次
         │    ├── 找到了 → 阈值过高，适当降低
         │    └── 还是没有 → 问题在切分/Embedding
         └── 检查原始文档
              ├── 文档里有 → 切分把答案切断了（调整 Chunk 策略）
              └── 文档里没有 → 知识库缺乏该内容（补充文档）
```

### 关键参数经验值

```python
# 切分（Day 17）
CHUNK_SIZE = 300       # Token，通用场景默认值
CHUNK_OVERLAP = 50     # ~15%，防止边界截断

# 检索（Day 18）
TOP_K = 3              # 平衡召回率和上下文长度
MIN_SCORE = 0.55       # 余弦相似度阈值，过低引入噪音

# 生成（Day 19）
TEMPERATURE = 0.1      # RAG 场景低温度，增强忠实性

# 引用校验（Day 20）
MIN_SHARED_KEYWORDS = 3  # 引用匹配的最小关键词重合数
```

---

## 六、实践任务

- [ ] 回答三道复盘题：① RAG 准确率受哪些环节影响；② 切分策略如何影响答案质量；③ 为什么引用来源对业务重要
- [ ] 整合 Day 16–20 的代码，跑通 `week3_rag_demo.py`，输出：索引构建成功 + 5 个问题的带引用回答
- [ ] 对其中一个答案验证引用：点开 [1] 看原文，确认模型给的答案确实来自该片段
- [ ] 测试边界情况：问一个知识库中没有答案的问题，确认系统返回拒答（不是编造答案）
- [ ] 故意把 `min_score` 调高到 0.9，观察哪些问题变成了拒答，理解阈值的影响
- [ ] 检查整个 RAG Demo：确认 `.env` 未提交，确认日志记录了索引构建和问答的 Token 消耗

**产出标准**：

- 一个完整运行的 `week3_rag_demo.py`，能对本地文档回答 5 个问题，输出带编号引用
- 对 2.1 的诊断优先级有直观感受：能说出"先查检索结果，再查文档，最后调 Prompt"的原因

---

## 七、下一步预告

**Day 22：理解 Tool Calling**

第 3 周把 RAG 做扎实，Day 22 起进入**第三阶段：Tool Calling / Agent**。两个阶段能力互补：

- **RAG 解决"知识问题"**：让模型知道私有文档里的内容
- **Tool Calling 解决"执行问题"**：让模型能调用外部服务做实际操作（查天气、查数据库、发邮件）

第 3 周积累的工程能力在 Tool Calling 开发中同样用得上：
- **结构化输出（Day 8/9）**：工具的参数定义和返回值都需要 JSON Schema 约束
- **日志和配置（Day 13）**：工具调用链的每一步都需要记录，方便排查"模型调了哪个工具、传了什么参数"
- **引用溯源思想（Day 20）**：Agent 的"思考-行动"过程也需要可解释性，让用户看到每步操作的依据

Day 22 的核心任务：用自己的话解释"回答问题"和"调用工具做事"的本质区别。
