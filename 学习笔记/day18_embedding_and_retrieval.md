# Day 18：Embedding 与向量检索

> 学习目标：掌握文本向量化的原理与实现——理解为什么语义相近的文本向量距离更近，学会调用 Embedding API 和本地模型，实现余弦相似度检索，并将向量索引升级到 FAISS / Chroma，完成 RAG 流程中的核心检索组件
>
> 📚 所属阶段：**第二阶段 · RAG 核心应用架构**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 18
>
> 🧭 导航：[← Day 17 · 文本切分](day17_text_chunking.md) → Day 19 · 把检索结果喂给模型（待更新）

---

## 目录

- [一、Embedding 的本质](#一embedding-的本质)
  - [1.1 从词向量到句向量的演进](#11-从词向量到句向量的演进)
  - [1.2 为什么语义相近的文本向量距离更近](#12-为什么语义相近的文本向量向量距离更近)
  - [1.3 Embedding 模型的选择原则](#13-embedding-模型的选择原则)
- [二、Embedding API 调用与批量优化](#二embedding-api-调用与批量优化)
  - [2.1 OpenAI 兼容接口调用 Embedding](#21-openai-兼容接口调用-embedding)
  - [2.2 本地模型：sentence-transformers](#22-本地模型sentence-transformers)
  - [2.3 批量向量化：降低 API 调用次数](#23-批量向量化降低-api-调用次数)
- [三、相似度计算与纯 numpy 检索](#三相似度计算与纯-numpy-检索)
  - [3.1 三种距离度量对比](#31-三种距离度量对比)
  - [3.2 纯 numpy 实现向量检索](#32-纯-numpy-实现向量检索)
  - [3.3 检索参数的影响：Top-K 与相似度阈值](#33-检索参数的影响top-k-与相似度阈值)
- [四、向量数据库：从 numpy 升级到 FAISS 和 Chroma](#四向量数据库从-numpy-升级到-faiss-和-chroma)
  - [4.1 为什么需要向量数据库](#41-为什么需要向量数据库)
  - [4.2 FAISS：高性能向量检索库](#42-faiss高性能向量检索库)
  - [4.3 Chroma：带元数据的向量数据库](#43-chroma带元数据的向量数据库)
- [五、完整实现：RAG 检索组件](#五完整实现rag-检索组件)
- [六、Day 18 知识速查](#六day-18-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、Embedding 的本质

### 1.1 从词向量到句向量的演进

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Embedding 技术演进路线                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Word2Vec（2013）                                                    │
│  "猫" → [0.2, -0.5, 0.8, ...]  （300 维）                           │
│  "狗" → [0.3, -0.4, 0.7, ...]                                       │
│  问题：同一个词只有一个向量，"苹果（水果）"和"苹果（公司）"无法区分          │
│                                                                      │
│  BERT（2018）                                                        │
│  "我买了苹果" → ["苹果"上下文向量 = 水果含义]                           │
│  "苹果发布了新款" → ["苹果"上下文向量 = 公司含义]                       │
│  解决了多义词问题，但没有针对"语义相似度"优化                             │
│                                                                      │
│  Sentence-BERT / text-embedding-ada（2019–2022）                    │
│  整句 → 一个固定长度的向量（如 1536 维）                                │
│  专门针对"句子相似度"任务训练，余弦相似度直接反映语义接近程度                │
│  这就是 RAG 中实际使用的 Embedding 模型                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Embedding 的核心作用**：将文本映射到向量空间，使得语义相近的文本在空间中靠近，语义不同的文本距离远。RAG 的"检索"步骤完全依赖这个性质。

### 1.2 为什么语义相近的文本向量距离更近

Embedding 模型的训练目标是：对于语义相近的句子对（正样本），缩小它们的向量距离；对于语义不同的句子对（负样本），拉大距离。

```
向量空间示意（降维到 2D 理解）：

                退款政策●    ●如何申请退款
                              ↑ 余弦相似度 ≈ 0.92（相近）
  ●如何开发功能
              ↖                       ↗
    ●深度学习      ...           ...   ●怎么退货

   ●苹果口味怎么样

（"退款政策"和"如何申请退款"距离近；与"深度学习"距离很远）
```

**余弦相似度**：衡量两个向量的夹角余弦值，与向量长度无关，只看方向：

```
cos(A, B) = (A · B) / (||A|| × ||B||)

结果范围：[-1, 1]
  1.0 → 方向完全相同（语义相同）
  0.0 → 方向垂直（语义无关）
 -1.0 → 方向相反（语义相反，较少见）

实践中：
  ≥ 0.85 → 语义非常相近
  0.7–0.85 → 相关
  < 0.7 → 关系不大
```

### 1.3 Embedding 模型的选择原则

| 方案 | 代表模型 | 向量维度 | 优点 | 缺点 | 适用场景 |
|------|---------|---------|------|------|---------|
| API-based（闭源） | `text-embedding-ada-002`、DeepSeek Embedding | 1536、1024 | 效果好、零运维 | 按 Token 计费、数据出境 | 快速开发、云端应用 |
| API-based（国产） | 阿里 `text-embedding-v3`、智谱 `embedding-2` | 1024 | 中文效果好、低延迟 | 按量付费 | 国内中文场景 |
| 本地（轻量） | `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 免费、低延迟、支持中英文 | 效果略低于大模型 | 学习/原型/离线场景 |
| 本地（高质量） | `bge-large-zh-v1.5`（BAAI） | 1024 | 中文效果最强 | 需 GPU 或较多内存 | 生产中文知识库 |

**一致性约束**（RAG 中最关键的约束）：
```
离线构建时用哪个 Embedding 模型，在线问答时必须用同一个模型。
原因：不同模型的向量空间不同，混用等于比较"苹果和橙子的距离"。
```

---

## 二、Embedding API 调用与批量优化

### 2.1 OpenAI 兼容接口调用 Embedding

DeepSeek 的 Embedding API 与 OpenAI SDK 完全兼容：

```bash
pip install openai python-dotenv
```

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)


def get_embedding(text: str, model: str = "deepseek-embedding") -> list[float]:
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


# 测试
vec = get_embedding("退款政策是什么")
print(f"向量维度：{len(vec)}")   # 1024
print(f"前 5 个值：{vec[:5]}")
```

**响应结构解析**：

```python
# API 响应示例
{
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "index": 0,
            "embedding": [0.0023, -0.0091, ...]   # 1024 维浮点数
        }
    ],
    "model": "deepseek-embedding",
    "usage": {
        "prompt_tokens": 6,
        "total_tokens": 6
    }
}
```

### 2.2 本地模型：sentence-transformers

不消耗 API 额度，适合学习和原型阶段：

```bash
pip install sentence-transformers
```

```python
from sentence_transformers import SentenceTransformer

# 下载约 120MB，支持中英文双语
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def get_embedding_local(text: str) -> list[float]:
    vec = model.encode([text])[0]
    return vec.tolist()


def get_embeddings_local(texts: list[str]) -> list[list[float]]:
    vecs = model.encode(texts)           # 一次批量处理所有文本
    return [v.tolist() for v in vecs]
```

**API vs 本地的实际对比**：

```
API（DeepSeek Embedding）：
  延迟：100–300ms（网络 I/O 为主）
  成本：约 0.0007 元 / 1000 Token
  效果：商用级，中文优化好

本地（MiniLM-L12-v2，CPU）：
  延迟：单句 5–20ms，批量 50–100ms/100句
  成本：零
  效果：略低，但 RAG 场景通常够用
  内存：~120MB 模型权重
```

### 2.3 批量向量化：降低 API 调用次数

知识库构建时通常有数百甚至上千个 Chunk，逐一调用 API 既慢又贵：

```python
import time
from typing import Generator


def batch_embed(
    texts: list[str],
    batch_size: int = 50,
    sleep_between: float = 0.1,
) -> list[list[float]]:
    """
    分批调用 Embedding API，避免单次请求过大（API 通常限制 batch ≤ 100）
    """
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        # 清洗文本（去换行，避免 API 报错）
        batch = [t.replace("\n", " ") for t in batch]

        response = client.embeddings.create(input=batch, model="deepseek-embedding")
        batch_vecs = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        all_embeddings.extend(batch_vecs)

        if i + batch_size < len(texts):
            time.sleep(sleep_between)   # 避免触发限速

    return all_embeddings
```

**批量 vs 逐一对比**：

```
100 个 Chunk 向量化：

逐一调用：
  API 请求次数 = 100
  总耗时 ≈ 100 × 200ms = 20 秒
  风险：某次失败需要从头重来

批量调用（batch_size=50）：
  API 请求次数 = 2
  总耗时 ≈ 2 × 300ms = 0.6 秒
  可以对每批单独重试，失败影响范围小
```

---

## 三、相似度计算与纯 numpy 检索

### 3.1 三种距离度量对比

| 度量方式 | 公式 | 范围 | 特点 | 适用场景 |
|---------|------|------|------|---------|
| 余弦相似度 | `(A·B)/(||A||·||B||)` | [-1, 1] | 忽略向量长度，只看方向 | 语义相似度（**最常用**） |
| 内积（点积） | `A·B` | 无限制 | 同时考虑方向和长度 | 向量已归一化时等价于余弦；某些 Embedding 模型推荐 |
| L2 距离（欧氏距离） | `√Σ(aᵢ-bᵢ)²` | [0, ∞) | 绝对距离，长度影响结果 | 图像/数值特征，文本 Embedding 较少用 |

**为什么 RAG 通常用余弦相似度**：

```
同一个问题的短写法和长写法：
  "退款" → 短向量，||v|| 较小
  "请问我购买的商品能退款吗，具体怎么操作" → 长向量，||v|| 较大

内积：短问题的相似度会被长问题"压制"（因为长文本向量模更大）
余弦：只看方向，两者相似度接近（都是在问退款）
```

### 3.2 纯 numpy 实现向量检索

不依赖任何向量数据库，用 numpy 矩阵运算实现高效批量检索：

```python
import numpy as np
from dataclasses import dataclass, field


@dataclass
class VectorIndex:
    """基于 numpy 的内存向量索引"""

    texts: list[str] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)
    metadatas: list[dict] = field(default_factory=list)

    def add(self, texts: list[str], embeddings: list[list[float]], metadatas: list[dict] | None = None) -> None:
        self.texts.extend(texts)
        self.embeddings.extend(embeddings)
        if metadatas:
            self.metadatas.extend(metadatas)
        else:
            self.metadatas.extend([{}] * len(texts))

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        if not self.embeddings:
            return []

        q = np.array(query_embedding)
        q_norm = q / (np.linalg.norm(q) + 1e-10)

        # 矩阵运算：一次计算所有 Chunk 的余弦相似度
        matrix = np.array(self.embeddings)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
        matrix_normed = matrix / norms
        scores = matrix_normed @ q_norm   # 矩阵乘法，shape: (N,)

        # 取 Top-K
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            {
                "text": self.texts[i],
                "score": float(scores[i]),
                "metadata": self.metadatas[i],
                "index": int(i),
            }
            for i in top_indices
        ]

    def __len__(self) -> int:
        return len(self.texts)
```

使用示例：

```python
# 构建索引
index = VectorIndex()
chunks = ["退款政策：30 天内可申请", "如何联系客服", "商品质保期为一年"]
chunk_vecs = get_embeddings_local(chunks)
index.add(chunks, chunk_vecs)

# 检索
query = "退货申请怎么办理"
query_vec = get_embedding_local(query)
results = index.search(query_vec, top_k=2)

for r in results:
    print(f"Score: {r['score']:.4f} | {r['text']}")
# Score: 0.8712 | 退款政策：30 天内可申请
# Score: 0.6341 | 如何联系客服
```

### 3.3 检索参数的影响：Top-K 与相似度阈值

```
Top-K 的选取影响：

K=1：只取最相关的一段，上下文信息量少，但噪音也少
K=3：通常的默认值，在信息量和噪音之间取得平衡
K=5：上下文丰富，但更多无关内容可能干扰模型回答
K=10+：适合"广泛查找"场景（如多跳问答），需要更大的 Context 窗口


相似度阈值（score threshold）的作用：

查询："太阳系有几颗行星"
知识库内容：全部是关于产品退款的文档

Top-1 结果 score = 0.43（根本不相关，但是最"相关"的一篇）
→ 如果不设阈值，模型会强行用这段文档"回答"天文问题

设置 threshold = 0.7：过滤掉 score < 0.7 的结果
→ 没有满足阈值的结果 → 返回"无相关文档" → 模型可以诚实地说不知道
```

**兜底策略**：

```python
def search_with_threshold(
    index: VectorIndex,
    query_embedding: list[float],
    top_k: int = 3,
    min_score: float = 0.6,
) -> list[dict]:
    results = index.search(query_embedding, top_k=top_k)
    filtered = [r for r in results if r["score"] >= min_score]
    return filtered   # 可能为空列表，调用方需要处理
```

---

## 四、向量数据库：从 numpy 升级到 FAISS 和 Chroma

### 4.1 为什么需要向量数据库

| 对比维度 | numpy 数组 | FAISS | Chroma |
|---------|-----------|-------|--------|
| 最大向量数 | ~10 万（受内存限制） | 亿级 | 百万级 |
| 检索速度 | O(N) 线性扫描 | ANN（近似最近邻），亚线性 | 中等 |
| 持久化 | 需手动 `np.save` | 支持索引序列化 | 自动持久化到磁盘 |
| 元数据过滤 | 需手动实现 | 不支持 | 原生支持 |
| 上手难度 | 极简 | 中等 | 简单 |
| 适用规模 | Demo / 小文档 | 大规模生产 | 中小型 RAG 项目 |

**结论**：学习阶段用 numpy，项目阶段用 Chroma（简单好上手），大规模生产考虑 FAISS 或 Milvus。

### 4.2 FAISS：高性能向量检索库

```bash
pip install faiss-cpu   # CPU 版本，够用
# pip install faiss-gpu  # 需要 CUDA
```

```python
import faiss
import numpy as np
import pickle


class FAISSIndex:
    def __init__(self, dim: int):
        # IndexFlatIP：内积（Inner Product）索引，向量归一化后等价于余弦相似度
        self.index = faiss.IndexFlatIP(dim)
        self.texts: list[str] = []
        self.metadatas: list[dict] = []
        self.dim = dim

    def add(self, texts: list[str], embeddings: list[list[float]], metadatas: list[dict] | None = None) -> None:
        vecs = np.array(embeddings, dtype=np.float32)
        # 归一化：使内积等价于余弦相似度
        faiss.normalize_L2(vecs)
        self.index.add(vecs)
        self.texts.extend(texts)
        self.metadatas.extend(metadatas or [{}] * len(texts))

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        q = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(q)
        scores, indices = self.index.search(q, top_k)
        return [
            {
                "text": self.texts[idx],
                "score": float(scores[0][rank]),
                "metadata": self.metadatas[idx],
            }
            for rank, idx in enumerate(indices[0])
            if idx != -1   # FAISS 用 -1 表示无效结果
        ]

    def save(self, path: str) -> None:
        faiss.write_index(self.index, path + ".faiss")
        with open(path + ".meta", "wb") as f:
            pickle.dump({"texts": self.texts, "metadatas": self.metadatas}, f)

    @classmethod
    def load(cls, path: str, dim: int) -> "FAISSIndex":
        obj = cls(dim)
        obj.index = faiss.read_index(path + ".faiss")
        with open(path + ".meta", "rb") as f:
            meta = pickle.load(f)
        obj.texts = meta["texts"]
        obj.metadatas = meta["metadatas"]
        return obj
```

### 4.3 Chroma：带元数据的向量数据库

Chroma 是当前 RAG 项目中最流行的轻量向量数据库，支持元数据过滤、持久化和内置 Embedding 函数：

```bash
pip install chromadb
```

```python
import chromadb
from chromadb.config import Settings


def build_chroma_index(
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict] | None = None,
    persist_dir: str = "./chroma_db",
    collection_name: str = "knowledge_base",
) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=persist_dir)

    # 删除旧集合（重建索引时用）
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},   # 使用余弦相似度
    )

    collection.add(
        ids=[f"chunk_{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas or [{}] * len(chunks),
    )

    print(f"Chroma 索引构建完成，共 {collection.count()} 个 Chunk")
    return collection


def search_chroma(
    collection: chromadb.Collection,
    query_embedding: list[float],
    top_k: int = 3,
    where: dict | None = None,   # 元数据过滤，如 {"source": "合同.pdf"}
) -> list[dict]:
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "distances", "metadatas"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    for doc, dist, meta in zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0],
    ):
        # Chroma cosine 返回的是距离（越小越相近），转换为相似度
        score = 1.0 - dist
        output.append({"text": doc, "score": score, "metadata": meta})
    return output
```

**Chroma 的元数据过滤**（在大型知识库中非常有用）：

```python
# 构建时带上来源信息
metadatas = [{"source": "产品手册.pdf", "page": 3}, ...]

# 检索时只搜索特定来源
results = search_chroma(
    collection, query_vec, top_k=3,
    where={"source": "产品手册.pdf"}
)
```

---

## 五、完整实现：RAG 检索组件

将 Day 16（文档加载）、Day 17（文本切分）和本天的向量检索整合为一个可复用的 RAG 检索组件：

```python
"""
rag_retriever.py — Day 18 完整实现
整合文档加载 + 文本切分 + Embedding + 向量检索
"""
from __future__ import annotations

import os
import json
import time
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()


# ──────────────────────────────────────────────
# Embedding 封装（支持 API 和本地两种模式）
# ──────────────────────────────────────────────

class EmbeddingModel:
    def __init__(self, mode: str = "local"):
        self.mode = mode
        if mode == "api":
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/v1",
            )
            self.api_model = "deepseek-embedding"
        else:
            self._local_model = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2"
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.mode == "api":
            return self._embed_api(texts)
        return self._embed_local(texts)

    def _embed_api(self, texts: list[str], batch_size: int = 50) -> list[list[float]]:
        all_vecs: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t.replace("\n", " ") for t in texts[i : i + batch_size]]
            resp = self.client.embeddings.create(input=batch, model=self.api_model)
            batch_vecs = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
            all_vecs.extend(batch_vecs)
            if i + batch_size < len(texts):
                time.sleep(0.1)
        return all_vecs

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        vecs = self._local_model.encode(texts, show_progress_bar=len(texts) > 50)
        return [v.tolist() for v in vecs]


# ──────────────────────────────────────────────
# 向量索引（numpy 实现，支持持久化）
# ──────────────────────────────────────────────

@dataclass
class VectorStore:
    texts: list[str] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)
    metadatas: list[dict] = field(default_factory=list)

    def add(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        self.texts.extend(texts)
        self.embeddings.extend(embeddings)
        self.metadatas.extend(metadatas or [{}] * len(texts))

    def search(
        self,
        query_vec: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict]:
        if not self.embeddings:
            return []
        q = np.array(query_vec)
        q_norm = q / (np.linalg.norm(q) + 1e-10)
        matrix = np.array(self.embeddings)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
        scores = (matrix / norms) @ q_norm
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [
            {"text": self.texts[i], "score": float(scores[i]), "metadata": self.metadatas[i]}
            for i in top_idx
            if float(scores[i]) >= min_score
        ]

    def save(self, path: str) -> None:
        data = {
            "texts": self.texts,
            "embeddings": self.embeddings,
            "metadatas": self.metadatas,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "VectorStore":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        store = cls()
        store.texts = data["texts"]
        store.embeddings = data["embeddings"]
        store.metadatas = data["metadatas"]
        return store

    def __len__(self) -> int:
        return len(self.texts)


# ──────────────────────────────────────────────
# RAG 检索器（整合文档加载 + 切分 + 向量化 + 检索）
# ──────────────────────────────────────────────

class RAGRetriever:
    def __init__(self, embedding_mode: str = "local"):
        self.embedder = EmbeddingModel(mode=embedding_mode)
        self.store = VectorStore()

    def build_from_texts(
        self,
        chunks: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        print(f"正在向量化 {len(chunks)} 个 Chunk...")
        vecs = self.embedder.embed(chunks)
        self.store.add(chunks, vecs, metadatas)
        print(f"索引构建完成，共 {len(self.store)} 个 Chunk")

    def build_from_directory(self, directory: str, chunk_size: int = 400) -> None:
        """读取目录下所有 txt/md 文件，切分后构建索引"""
        chunks, metadatas = [], []
        for file_path in Path(directory).rglob("*"):
            if file_path.suffix not in {".txt", ".md"}:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
            file_chunks = _simple_chunk(text, chunk_size)
            for i, chunk in enumerate(file_chunks):
                chunks.append(chunk)
                metadatas.append({"source": file_path.name, "chunk_idx": i})
        self.build_from_texts(chunks, metadatas)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.5,
    ) -> list[dict]:
        q_vec = self.embedder.embed([query])[0]
        return self.store.search(q_vec, top_k=top_k, min_score=min_score)

    def save(self, path: str) -> None:
        self.store.save(path)
        print(f"索引已保存到 {path}")

    def load(self, path: str) -> None:
        self.store = VectorStore.load(path)
        print(f"索引已加载，共 {len(self.store)} 个 Chunk")


def _simple_chunk(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) <= chunk_size:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if len(current) >= 50:
                chunks.append(current)
            current = para
    if len(current) >= 50:
        chunks.append(current)
    return chunks


# ──────────────────────────────────────────────
# 主程序：演示端到端检索
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # 准备示例文档
    documents = [
        "退款政策：购买后 30 天内可申请全额退款。超过 30 天不支持退款，但可申请换货。",
        "联系客服：工作日 9:00–18:00，电话 400-888-8888，或发送邮件至 support@example.com。",
        "质保期：所有商品享有一年质保，人为损坏不在质保范围内。",
        "配送说明：订单 24 小时内发货，预计 3–5 个工作日送达。偏远地区可能延迟。",
        "会员积分：每消费 1 元获得 1 积分，1000 积分可抵扣 10 元。",
    ]

    retriever = RAGRetriever(embedding_mode="local")
    retriever.build_from_texts(documents)

    test_queries = [
        "我能退货吗？",
        "怎么联系你们？",
        "商品保修多久？",
        "太阳系有几颗行星？",   # 无关问题，测试阈值
    ]

    for query in test_queries:
        print(f"\n问题：{query}")
        results = retriever.retrieve(query, top_k=2, min_score=0.5)
        if not results:
            print("  → 未找到相关文档（低于相似度阈值）")
        else:
            for r in results:
                print(f"  Score={r['score']:.4f} | {r['text'][:60]}...")
```

运行示例输出：

```
正在向量化 5 个 Chunk...
索引构建完成，共 5 个 Chunk

问题：我能退货吗？
  Score=0.8234 | 退款政策：购买后 30 天内可申请全额退款。超过 30 天不支持退...
  Score=0.6512 | 质保期：所有商品享有一年质保，人为损坏不在质保范围内。...

问题：怎么联系你们？
  Score=0.8941 | 联系客服：工作日 9:00–18:00，电话 400-888-8888...

问题：商品保修多久？
  Score=0.8102 | 质保期：所有商品享有一年质保，人为损坏不在质保范围内。...

问题：太阳系有几颗行星？
  → 未找到相关文档（低于相似度阈值）
```

---

## 六、Day 18 知识速查

### Embedding 方案选择速查

```
需求 → 推荐方案：

  学习 / 原型（免费）           → sentence-transformers（MiniLM-L12-v2）
  
  生产 / 中文效果要求高          → API（DeepSeek Embedding 或阿里 text-embedding-v3）
  
  大规模知识库（> 10 万 Chunk）  → FAISS + 批量 API Embedding
  
  中小型项目，需要持久化和过滤    → Chroma + 本地/API Embedding
```

### 关键参数速查

| 参数 | 推荐值 | 说明 |
|------|-------|------|
| `top_k` | 3–5 | 检索返回的 Chunk 数，后续全部送给模型 |
| `min_score` | 0.5–0.7 | 过滤无关结果；高精度场景可调高到 0.75 |
| `batch_size`（API） | 50 | 每次请求的 Chunk 数，过大可能触发限速 |
| Embedding 维度 | 384–1536 | 维度越高效果越好，存储和计算成本也越高 |

### 最小代码模板

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# 离线构建
chunks = ["文档片段1", "文档片段2", ...]
chunk_vecs = model.encode(chunks)   # shape: (N, 384)

# 在线检索
query_vec = model.encode(["用户问题"])[0]
scores = chunk_vecs @ query_vec / (
    np.linalg.norm(chunk_vecs, axis=1) * np.linalg.norm(query_vec)
)
top_k_idx = np.argsort(scores)[::-1][:3]
top_chunks = [chunks[i] for i in top_k_idx]
```

---

## 七、实践任务

- [ ] 安装 `sentence-transformers`，调用 `MiniLM-L12-v2` 对 5 段不同文本向量化，打印向量维度
- [ ] 计算 3 个句子对的余弦相似度：两个语义相近的句子 + 一个无关句子，观察分数差距
- [ ] 实现 `VectorStore` 类（或直接用本文代码），构建 5–10 个 Chunk 的索引，测试检索结果是否符合预期
- [ ] 设置 `min_score=0.6`，用一个与知识库完全无关的问题测试"拒绝回答"逻辑是否生效
- [ ] 将 Day 16 加载的文档 + Day 17 的切分器 + 本天的检索组件串联，实现端到端的"加载→切分→向量化→检索"流程

**产出标准**：

- 一个可以接受问题、返回 Top-3 相关 Chunk（含相似度分数）的检索脚本
- 对无关问题返回空列表，而不是强行返回结果

---

## 八、下一步预告

**Day 19：把检索结果喂给模型回答**

Day 18 解决了"怎么找"的问题，Day 19 要完成 RAG 的最后一步——把检索到的 Chunk 拼入 Prompt，让模型基于上下文生成答案：

- 上下文拼接策略：如何将多个 Chunk 组织成 Prompt 中的"资料"部分
- "只根据资料回答"约束：防止模型忽视检索结果、自己"发挥"
- 无相关文档时的拒答逻辑：RAG 系统的诚实性设计
- 完整 RAG 问答脚本：Day 15 原型 → Day 16 加载 → Day 17 切分 → Day 18 检索 → Day 19 生成
