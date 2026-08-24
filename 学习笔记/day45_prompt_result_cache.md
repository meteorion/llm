# Day 45：Prompt / 结果缓存

> 学习目标：理解精确匹配缓存与语义缓存的区别及各自适用场景；掌握缓存失效策略的设计思路；给高频重复查询加一层缓存层，量化缓存命中率和响应时间 / 成本的改善幅度
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 45
>
> 🧭 导航：[← Day 44 · 结构化日志与成本监控面板](day44_structured_logging_cost_dashboard.md) → Day 46 · 批处理（Batching）（待更新）

---

## 目录

- [一、为什么需要缓存](#一为什么需要缓存)
  - [1.1 LLM 调用的双重代价](#11-llm-调用的双重代价)
  - [1.2 哪类请求适合缓存](#12-哪类请求适合缓存)
- [二、精确匹配缓存](#二精确匹配缓存)
  - [2.1 原理与适用场景](#21-原理与适用场景)
  - [2.2 缓存键的设计](#22-缓存键的设计)
  - [2.3 实现：内存 + 磁盘两级缓存](#23-实现内存--磁盘两级缓存)
- [三、语义缓存](#三语义缓存)
  - [3.1 为什么精确匹配不够](#31-为什么精确匹配不够)
  - [3.2 语义缓存的工作原理](#32-语义缓存的工作原理)
  - [3.3 实现：embedding + 相似度阈值](#33-实现embedding--相似度阈值)
- [四、缓存失效策略](#四缓存失效策略)
  - [4.1 TTL（基于时间过期）](#41-ttl基于时间过期)
  - [4.2 基于内容特征的失效](#42-基于内容特征的失效)
  - [4.3 主动失效 vs 被动过期](#43-主动失效-vs-被动过期)
- [五、缓存效果量化](#五缓存效果量化)
  - [5.1 命中率统计](#51-命中率统计)
  - [5.2 响应时间对比](#52-响应时间对比)
  - [5.3 成本节省估算](#53-成本节省估算)
- [六、精确匹配 vs 语义缓存选型指南](#六精确匹配-vs-语义缓存选型指南)
- [七、Day 45 知识速查](#七day-45-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、为什么需要缓存

### 1.1 LLM 调用的双重代价

每次调用 LLM API 都有两项开销：

| 代价 | 典型数值 | 影响 |
|-----|---------|------|
| **时间代价** | 2–8 秒（首 Token 延迟 + 生成时间） | 用户体验差，尤其是重复同样的问题时 |
| **Token 成本** | $0.0001–$0.01 / 次（视模型和 Prompt 长度） | 高频重复请求叠加后成本可观 |

Day 44 的成本报表告诉你"哪里贵"，缓存解决"让常见请求不再重复花钱"——对于重复率高的请求，缓存可以把延迟从秒级降到毫秒级，成本降到零。

### 1.2 哪类请求适合缓存

| 特征 | 适合缓存 | 不适合缓存 |
|-----|---------|----------|
| **时效性** | 答案长期稳定（城市介绍、知识类 QA、固定话术） | 答案随时间变化（今天天气、实时汇率） |
| **重复率** | 大量用户问同类问题 | 每个用户的问题都高度个性化 |
| **个性化程度** | 答案与用户无关（通用知识） | 答案依赖用户上下文（个人偏好、账户信息） |
| **容错性** | 允许返回几分钟前的答案 | 必须实时（金融交易类） |

---

## 二、精确匹配缓存

### 2.1 原理与适用场景

精确匹配缓存：**缓存键 = 请求内容的哈希值**。只有完全相同的请求才能命中缓存。

```
用户输入 "北京有哪些著名景点？" 
  → MD5/SHA256 → "a3f2..."
  → 查缓存: hit → 直接返回缓存结果（< 1ms）
  → 查缓存: miss → 调用 LLM → 存入缓存 → 返回

用户输入 "北京有哪些著名的景点？"（多了"的"字）
  → 不同哈希 → 缓存 miss → 重新调用 LLM
```

**适合场景**：
- 固定话术（FAQ、产品介绍）
- 内部工具的批量处理（每次跑同一批数据）
- SDK / 文档的代码生成（相同签名生成相同代码）

### 2.2 缓存键的设计

缓存键必须包含会影响输出的所有因素，少一个都会导致缓存污染（返回错误结果）：

```python
import hashlib
import json

def make_cache_key(
    messages: list[dict],
    model: str,
    temperature: float,
    system_prompt: str = "",
) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "system_prompt": system_prompt,
        "messages": messages,
    }
    # 用 sort_keys 保证相同内容不同键顺序也能命中
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

**常见缓存键错误**：
- 只用用户消息内容，忽略 System Prompt → 换 System Prompt 后仍命中旧缓存
- 忽略 `temperature` → `temperature=0` 和 `temperature=0.7` 返回相同缓存（结果性质不同）
- 忽略 `model` → 换模型后仍返回旧模型的缓存

### 2.3 实现：内存 + 磁盘两级缓存

```python
import json
import time
from pathlib import Path
from functools import lru_cache

CACHE_DIR = Path("cache/exact")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 内存缓存（进程重启后失效，但访问最快）
_mem_cache: dict[str, tuple[str, float]] = {}   # key → (result, expires_at)


def cache_get(key: str) -> str | None:
    # 1. 先查内存
    if key in _mem_cache:
        result, expires_at = _mem_cache[key]
        if expires_at > time.monotonic():
            return result
        del _mem_cache[key]

    # 2. 再查磁盘
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if data["expires_at"] > time.time():
            # 回填内存缓存
            _mem_cache[key] = (data["result"], data["expires_at"] - time.time() + time.monotonic())
            return data["result"]
        cache_file.unlink()   # 过期文件删除

    return None


def cache_set(key: str, result: str, ttl_seconds: int = 3600) -> None:
    expires_at = time.time() + ttl_seconds
    # 写内存
    _mem_cache[key] = (result, time.monotonic() + ttl_seconds)
    # 写磁盘
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(
        json.dumps({"result": result, "expires_at": expires_at}, ensure_ascii=False),
        encoding="utf-8",
    )


def cached_llm_call(
    client,
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0,
    system_prompt: str = "",
    ttl: int = 3600,
) -> tuple[str, bool]:
    """返回 (结果, 是否命中缓存)"""
    key = make_cache_key(messages, model, temperature, system_prompt)
    cached = cache_get(key)
    if cached is not None:
        return cached, True

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "system", "content": system_prompt}, *messages] if system_prompt else messages,
    )
    result = response.choices[0].message.content
    cache_set(key, result, ttl_seconds=ttl)
    return result, False
```

---

## 三、语义缓存

### 3.1 为什么精确匹配不够

同一个问题有无数种说法，精确匹配都算 miss：

```
"北京有哪些著名景点？"         → 缓存 miss（第一次）
"北京有什么出名的旅游景点？"   → 缓存 miss（语义相同，但字符串不同）
"帮我推荐几个北京的景点"       → 缓存 miss（语义相同，表达更口语）
"去北京旅游，有哪些必去的地方" → 缓存 miss（语义相同，加了旅游场景）
```

四个问题都调用了 LLM，但答案几乎一样——语义缓存把"语义相似的问题"视为同一个缓存条目。

### 3.2 语义缓存的工作原理

```
写入缓存时：
  问题 → Embedding 模型 → 向量 → 存入向量数据库（附带原始答案）

查询缓存时：
  新问题 → Embedding 模型 → 查询向量
  → 在向量数据库中找最近邻
  → 相似度 > 阈值（如 0.92）→ 命中，返回最近邻的答案
  → 相似度 ≤ 阈值 → miss，调用 LLM，新向量写入数据库
```

关键参数：**相似度阈值**（cosine similarity）
- 阈值过高（0.99）→ 命中率低，接近精确匹配
- 阈值过低（0.80）→ 误命中（语义不同但向量相近的问题返回错误答案）
- 推荐起点：**0.90–0.95**，根据业务容忍度调整

### 3.3 实现：embedding + 相似度阈值

```python
import numpy as np
import json
from pathlib import Path

# 简化实现：用文件存储向量库（生产环境用 Chroma / FAISS / Qdrant）
SEMANTIC_CACHE_FILE = Path("cache/semantic_cache.json")

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def get_embedding(client, text: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",   # 或使用 DeepSeek 兼容的 embedding 接口
        input=text,
    )
    return response.data[0].embedding


def semantic_cache_get(
    client,
    query: str,
    threshold: float = 0.92,
) -> str | None:
    if not SEMANTIC_CACHE_FILE.exists():
        return None

    entries = json.loads(SEMANTIC_CACHE_FILE.read_text(encoding="utf-8"))
    if not entries:
        return None

    query_vec = get_embedding(client, query)
    best_score, best_answer = 0.0, None

    for entry in entries:
        score = cosine_similarity(query_vec, entry["embedding"])
        if score > best_score:
            best_score, best_answer = score, entry["answer"]

    if best_score >= threshold:
        return best_answer
    return None


def semantic_cache_set(client, query: str, answer: str) -> None:
    entries = []
    if SEMANTIC_CACHE_FILE.exists():
        entries = json.loads(SEMANTIC_CACHE_FILE.read_text(encoding="utf-8"))

    embedding = get_embedding(client, query)
    entries.append({"query": query, "embedding": embedding, "answer": answer})
    SEMANTIC_CACHE_FILE.write_text(
        json.dumps(entries, ensure_ascii=False),
        encoding="utf-8",
    )
```

**注意**：语义缓存本身也要调用 embedding API（有一定成本），只有当 LLM 调用成本 >> embedding 成本时才值得。embedding 的成本通常比 LLM 低 10-100 倍。

---

## 四、缓存失效策略

### 4.1 TTL（基于时间过期）

最简单、最常用的失效策略：给每条缓存设置一个存活时间（Time To Live）：

| 内容类型 | 推荐 TTL |
|---------|---------|
| 实时数据（天气、汇率） | 不缓存，或 5–15 分钟 |
| 频繁更新的内容（新闻摘要） | 1–6 小时 |
| 相对稳定的知识（城市介绍） | 24 小时–7 天 |
| 几乎不变的内容（历史事件） | 30 天 + |

### 4.2 基于内容特征的失效

某些内容特征天然指示"不该缓存"：

```python
NO_CACHE_KEYWORDS = ["现在", "今天", "最新", "实时", "当前", "刚刚"]

def should_skip_cache(user_input: str) -> bool:
    return any(kw in user_input for kw in NO_CACHE_KEYWORDS)
```

对于天气查询：即使用户问"北京天气怎么样"——这个查询可以缓存 15 分钟；但"北京今天天气"包含时效性词语，缓存时间应更短或直接跳过。

### 4.3 主动失效 vs 被动过期

| 方式 | 机制 | 适用场景 |
|-----|------|---------|
| **被动过期（TTL）** | 读取时检查时间，过期则作废 | 大多数场景，实现简单 |
| **主动失效** | 数据源更新时主动删除对应缓存 | 有明确更新事件（如产品信息更新后清空该产品的所有缓存） |

主动失效需要在数据更新逻辑里调用 `cache_delete(key)`，耦合较强，只在 TTL 不够精确时使用。

---

## 五、缓存效果量化

### 5.1 命中率统计

```python
from dataclasses import dataclass, field

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def report(self) -> str:
        total = self.hits + self.misses
        return (
            f"总请求: {total} | 命中: {self.hits} | 未命中: {self.misses} "
            f"| 命中率: {self.hit_rate:.1%}"
        )

stats = CacheStats()

# 调用时统计
result, hit = cached_llm_call(client, messages, ...)
if hit:
    stats.hits += 1
else:
    stats.misses += 1
```

### 5.2 响应时间对比

```python
import time

times_hit = []
times_miss = []

t0 = time.monotonic()
result, hit = cached_llm_call(client, messages, ...)
elapsed = (time.monotonic() - t0) * 1000

if hit:
    times_hit.append(elapsed)
else:
    times_miss.append(elapsed)

# 汇总
if times_hit and times_miss:
    print(f"缓存命中均耗时: {sum(times_hit)/len(times_hit):.1f}ms")
    print(f"缓存未命中均耗时: {sum(times_miss)/len(times_miss):.1f}ms")
    print(f"加速比: {sum(times_miss)/len(times_miss) / (sum(times_hit)/len(times_hit)):.0f}x")
```

典型输出：

```
总请求: 100 | 命中: 67 | 未命中: 33 | 命中率: 67.0%
缓存命中均耗时:   0.8ms
缓存未命中均耗时: 3412.0ms
加速比: 4265x

成本节省：67 次命中 × $0.00015/次 = $0.010 节省
```

### 5.3 成本节省估算

```python
def estimate_savings(stats: CacheStats, avg_cost_per_call: float) -> float:
    """估算因缓存节省的总成本（命中次数 × 单次调用成本）"""
    return stats.hits * avg_cost_per_call
```

---

## 六、精确匹配 vs 语义缓存选型指南

| 维度 | 精确匹配缓存 | 语义缓存 |
|-----|-----------|---------|
| **实现复杂度** | 低（哈希 + KV 存储） | 高（需要 Embedding API + 向量库） |
| **额外成本** | 无 | Embedding API 调用费用 |
| **命中率** | 低（只有完全相同才命中） | 高（语义相似都能命中） |
| **误命中风险** | 无 | 有（阈值设置不当时返回错误答案） |
| **适用内容** | 完全固定的查询（批处理、FAQ 精确匹配） | 语义相似的自然语言查询 |
| **适用阶段** | 先上精确匹配，效果立竿见影 | 命中率不达预期时升级 |

**推荐路径**：先上精确匹配缓存（实现简单、无误命中风险），跑 7 天后如果命中率 < 30%，再考虑升级语义缓存。

---

## 七、Day 45 知识速查

### 两种缓存核心对比

```
精确匹配缓存：
  键 = hash(model + temperature + system_prompt + messages)
  完全相同才命中，无误命中，命中率低

语义缓存：
  键 = embedding(query) 的最近邻
  相似度 > 阈值才命中，可能误命中，命中率高
  额外成本 = embedding API 调用
```

### 缓存键必须包含的字段

```
✅ model（不同模型输出不同）
✅ temperature（影响随机性）
✅ system_prompt（影响输出风格和约束）
✅ messages（用户输入内容）
❌ timestamp（每次不同，导致永远 miss）
❌ trace_id（每次不同）
```

### 失效策略速查

```
时效性内容    → TTL（分钟到小时级）
稳定知识      → TTL（天到周级）
含"今天/实时" → 跳过缓存或超短 TTL
数据源更新    → 主动失效（调用 cache_delete）
```

---

## 八、实践任务

- [ ] 实现 `cached_llm_call()` 函数，加内存 + 磁盘两级精确匹配缓存；向同一个问题发 3 次请求，验证第 2/3 次命中缓存且耗时 < 5ms
- [ ] 实现 `CacheStats` 命中率统计；向缓存发 20 次请求（其中 10 条重复、10 条新问题），打印命中率报告
- [ ] 测量缓存命中 vs 未命中的响应时间，记录加速比（预期 > 1000x）
- [ ] 给天气查询加上 `should_skip_cache()` 检测：含"今天"/"实时"的请求绕过缓存，其他天气问题缓存 15 分钟；验证两类请求行为不同
- [ ] （进阶）实现语义缓存原型：用同一个问题的 3 种不同表述测试，验证相似度 > 0.92 时都能命中同一条缓存

**产出标准**：命中率统计报告（含总请求数、命中数、命中率）+ 响应时间对比（命中 vs 未命中的均值）。

---

## 九、下一步预告

Day 46 进入**批处理（Batching）**：缓存解决"重复请求不花钱"，批处理解决"大批量请求怎么快又省"。当需要批量处理 100 条商品描述时，逐条串行调用需要等 100 × 单次延迟；批处理用 `asyncio` 并发 + Semaphore 限速，在 API 限流范围内最大化吞吐量，把总耗时压缩到接近单次调用的水平——以及学习部分厂商的专用 Batch API，了解"异步提交换取 50% 价格折扣"的适用场景。
