# Day 46：批处理（Batching）

> 学习目标：理解批处理适合哪类场景、与缓存和路由的区别；用 Python `asyncio` 并发 + `Semaphore` 限速实现批处理，把逐条串行调用改造成并发批处理；量化批处理相比逐条调用节省的时间和成本
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 46
>
> 🧭 导航：[← Day 45 · Prompt / 结果缓存](day45_prompt_result_cache.md) → [Day 47 · 模型分级路由](day47_model_routing.md)

---

## 目录

- [一、批处理解决什么问题](#一批处理解决什么问题)
  - [1.1 串行调用的代价](#11-串行调用的代价)
  - [1.2 批处理 vs 缓存 vs 路由：三者的区别](#12-批处理-vs-缓存-vs-路由三者的区别)
  - [1.3 哪类任务适合批处理](#13-哪类任务适合批处理)
- [二、实现方式 A：asyncio 并发 + Semaphore 限速](#二实现方式-a-asyncio-并发--semaphore-限速)
  - [2.1 为什么用 asyncio 而不是多线程](#21-为什么用-asyncio-而不是多线程)
  - [2.2 asyncio.Semaphore：不让并发压垮 API 限速](#22-asynciosemaphore不让并发压垮-api-限速)
  - [2.3 完整实现：100 条商品描述批量打标签](#23-完整实现100-条商品描述批量打标签)
  - [2.4 错误处理与重试](#24-错误处理与重试)
- [三、实现方式 B：Batch API（异步提交）](#三实现方式-b-batch-api异步提交)
  - [3.1 Batch API 的原理与取舍](#31-batch-api-的原理与取舍)
  - [3.2 OpenAI / Anthropic Batch API 接入思路](#32-openai--anthropic-batch-api-接入思路)
  - [3.3 两种方式对比](#33-两种方式对比)
- [四、性能对比量化](#四性能对比量化)
  - [4.1 对比方法](#41-对比方法)
  - [4.2 典型对比数据](#42-典型对比数据)
  - [4.3 吞吐量 vs 延迟的权衡](#43-吞吐量-vs-延迟的权衡)
- [五、Day 46 知识速查](#五day-46-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、批处理解决什么问题

### 1.1 串行调用的代价

假设需要给 100 条商品描述打情感标签（正面 / 中性 / 负面），每次调用 LLM 耗时约 2 秒：

```
串行调用：100 次 × 2s = 200 秒（约 3.3 分钟）
```

200 秒的等待在任何生产环境都不可接受。问题不在于单次调用慢——LLM 的单次延迟已经很难压缩——而在于串行把等待叠加了 100 次。

串行调用的固定开销：

| 开销项 | 描述 |
|-------|------|
| **连接建立** | 每次 HTTP 请求需要 TCP 握手（如果不复用连接） |
| **排队等待** | 第 N 条必须等第 N-1 条完成才能开始 |
| **Prompt 前缀重复处理** | 100 次请求的 System Prompt 完全相同，但服务端每次都要处理（部分 Batch API 会做前缀缓存优化） |

### 1.2 批处理 vs 缓存 vs 路由：三者的区别

这三种优化手段经常被混淆，实际上各自针对不同类型的浪费：

| 优化手段 | 省的是什么 | 适用场景 |
|---------|----------|---------|
| **缓存**（Day 45） | 重复请求的 Token 成本：相同/相似请求复用历史结果 | 高重复率的查询（FAQ、固定话术） |
| **批处理**（今天） | 串行等待的时间：N 个独立请求并发而非排队执行 | 大批量、彼此独立、非实时的任务 |
| **路由**（Day 47） | 用错模型的成本：简单任务不应该用贵模型 | 请求复杂度差异大的混合场景 |

三者可以叠加使用：先路由（选对模型档位），再查缓存（避免重复调用），最后批处理（并发执行剩余请求）。

### 1.3 哪类任务适合批处理

| 特征 | 适合 | 不适合 |
|-----|------|-------|
| **实时性要求** | 可以容忍分钟级等待（离线处理） | 需要秒级响应（对话类） |
| **任务依赖关系** | 各条任务彼此独立 | 任务 B 依赖任务 A 的结果 |
| **数量规模** | 几十条到数万条 | 单条请求 |
| **典型场景** | 批量打标签、批量摘要、批量翻译、批量向量化 | 实时对话、需要流式输出的场景 |

---

## 二、实现方式 A：asyncio 并发 + Semaphore 限速

### 2.1 为什么用 asyncio 而不是多线程

LLM API 调用是 I/O 密集型操作（大部分时间在等待网络响应）。Python 的 GIL 不影响 I/O 等待，但多线程有线程创建和切换的开销。`asyncio` 的协程在单线程内切换，没有线程开销，且 `httpx` / `aiohttp` 都原生支持异步：

```python
# 同步版本（OpenAI SDK 默认）
response = client.chat.completions.create(...)

# 异步版本（AsyncOpenAI）
response = await async_client.chat.completions.create(...)
```

### 2.2 asyncio.Semaphore：不让并发压垮 API 限速

直接把 100 个请求全部并发发出会触发 API 限速（Rate Limit），导致大量 429 错误。`Semaphore` 像令牌桶——同时持有令牌的协程数不超过设定值：

```python
import asyncio

# 最多同时 10 个并发请求（根据 API 限速额度调整）
sem = asyncio.Semaphore(10)

async def call_with_limit(item):
    async with sem:   # 等待令牌，自动释放
        return await process_item(item)
```

**并发数怎么设定**：
- 查 API 文档的 RPM（Requests Per Minute）限制
- 粗略公式：`max_concurrency = RPM / 60 × 平均单次耗时(s)`
- 例：RPM=60，平均耗时 2s → `max_concurrency = 60/60 × 2 = 2`（保守值）
- 实践上从 5-10 开始，监控 429 错误率，逐步调高

### 2.3 完整实现：100 条商品描述批量打标签

```python
import asyncio
import time
from openai import AsyncOpenAI

async_client = AsyncOpenAI(
    api_key="your_api_key",
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = """你是一个商品情感分析助手。
对给定的商品描述，只输出一个标签：正面、中性、负面。
不要输出其他任何内容。"""

MAX_CONCURRENCY = 10   # 根据 API 限速调整
sem = asyncio.Semaphore(MAX_CONCURRENCY)


async def label_one(item_id: int, description: str) -> dict:
    """给单条商品描述打标签，带重试"""
    async with sem:
        for attempt in range(3):
            try:
                response = await async_client.chat.completions.create(
                    model="deepseek-chat",
                    temperature=0,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": description},
                    ],
                )
                label = response.choices[0].message.content.strip()
                return {
                    "id": item_id,
                    "description": description[:30] + "...",
                    "label": label,
                    "tokens": response.usage.total_tokens,
                    "status": "ok",
                }
            except Exception as e:
                if attempt == 2:
                    return {"id": item_id, "label": "ERROR", "error": str(e), "status": "error"}
                await asyncio.sleep(2 ** attempt)   # 指数退避


async def batch_label(descriptions: list[str]) -> list[dict]:
    """并发打标签，保留原始顺序"""
    tasks = [label_one(i, desc) for i, desc in enumerate(descriptions)]
    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda r: r["id"])   # 保持顺序


def run_batch(descriptions: list[str]) -> tuple[list[dict], float]:
    t0 = time.monotonic()
    results = asyncio.run(batch_label(descriptions))
    elapsed = time.monotonic() - t0
    return results, elapsed
```

### 2.4 错误处理与重试

批处理中任意一条失败不应阻断其他条目。上面实现的两个关键点：

1. **`asyncio.gather(*tasks)` 不会因单个任务失败而全部取消**（默认 `return_exceptions=False`，但我们在 `label_one` 内部捕获了异常，不会抛出）
2. **指数退避**：遇到限速或临时错误，等待 1s / 2s / 4s 再重试，避免重试风暴

对于失败条目，记录 `status="error"` 后继续处理其他条目，最后汇总失败列表，按需人工处理或单独重跑。

---

## 三、实现方式 B：Batch API（异步提交）

### 3.1 Batch API 的原理与取舍

部分厂商（OpenAI、Anthropic）提供专用 Batch API：

```
普通 API：提交 → 立即等待 → 返回结果（秒级）
Batch API：提交整批任务 → 服务端排队处理 → 轮询/回调获取结果（几分钟到 24 小时）
```

**Batch API 的收益**：
- 通常有 **50% 价格折扣**（厂商用空闲算力处理，成本更低）
- 吞吐量上限更高（不受实时 RPM 限制）

**Batch API 的代价**：
- 延迟不可控（可能几分钟，也可能 24 小时）
- 需要轮询或 Webhook 接收结果，复杂度更高
- 不适合任何有时效要求的任务

### 3.2 OpenAI / Anthropic Batch API 接入思路

```python
# OpenAI Batch API 流程（伪代码，以实际 SDK 版本为准）
import json

# 1. 构造 JSONL 格式的批量请求文件
requests = []
for i, desc in enumerate(descriptions):
    requests.append({
        "custom_id": f"item-{i}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": desc},
            ],
            "temperature": 0,
        },
    })

# 写成 JSONL 文件
with open("batch_input.jsonl", "w") as f:
    for req in requests:
        f.write(json.dumps(req) + "\n")

# 2. 上传文件
batch_file = client.files.create(file=open("batch_input.jsonl", "rb"), purpose="batch")

# 3. 创建 batch 任务
batch = client.batches.create(
    input_file_id=batch_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
)

# 4. 轮询状态（实际应用用定时任务或 Webhook）
import time
while batch.status not in ("completed", "failed", "cancelled"):
    time.sleep(60)
    batch = client.batches.retrieve(batch.id)

# 5. 获取结果
if batch.status == "completed":
    result_file = client.files.content(batch.output_file_id)
    results = [json.loads(line) for line in result_file.text.splitlines()]
```

**DeepSeek 目前没有专用 Batch API**——对本路线的项目，使用实现方式 A（asyncio 并发）即可。

### 3.3 两种方式对比

| 维度 | 方式 A：asyncio 并发 | 方式 B：Batch API |
|-----|-------------------|----------------|
| **延迟** | 秒到分钟级（并发数控制） | 分钟到小时级（不可控） |
| **成本** | 正常定价 | 通常 50% 折扣 |
| **实现复杂度** | 低（几十行代码） | 高（需要文件上传、轮询、结果下载） |
| **Provider 支持** | 所有支持 OpenAI SDK 的 Provider | 仅部分厂商（OpenAI、Anthropic） |
| **适合场景** | 需要分钟内完成的批量任务 | 可以等待数小时、追求最低成本 |

---

## 四、性能对比量化

### 4.1 对比方法

```python
import time

# 串行版本（基准）
def serial_label(descriptions: list[str]) -> tuple[list[dict], float]:
    t0 = time.monotonic()
    results = []
    for i, desc in enumerate(descriptions):
        response = client.chat.completions.create(
            model="deepseek-chat",
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": desc},
            ],
        )
        results.append({
            "id": i,
            "label": response.choices[0].message.content.strip(),
            "tokens": response.usage.total_tokens,
        })
    return results, time.monotonic() - t0


# 对比实验（建议用 20 条数据，避免等太久）
N = 20
sample = descriptions[:N]

print("=== 串行调用 ===")
_, serial_time = serial_label(sample)
print(f"总耗时: {serial_time:.1f}s，平均单条: {serial_time/N:.2f}s")

print("\n=== 批处理（asyncio 并发，MAX_CONCURRENCY=10）===")
_, batch_time = run_batch(sample)
print(f"总耗时: {batch_time:.1f}s，平均单条: {batch_time/N:.2f}s")

print(f"\n加速比: {serial_time/batch_time:.1f}x")
print(f"预计 100 条串行: {serial_time/N*100:.0f}s，批处理: {batch_time/N*100:.0f}s")
```

### 4.2 典型对比数据

以 20 条商品描述、单条平均耗时 2s、`MAX_CONCURRENCY=10` 为例：

| 指标 | 串行调用 | 批处理（并发 10） | 改善幅度 |
|-----|---------|---------------|---------|
| **总耗时（20 条）** | ~40s | ~4–6s | **7–10x 加速** |
| **平均单条耗时** | 2.0s | 0.2–0.3s | — |
| **Token 成本** | 相同 | 相同 | 0%（成本不变） |
| **API 错误率** | 低 | 略高（需重试） | Semaphore 控制后可接受 |

**重要结论**：批处理压缩的是**等待时间**（并发执行），而非 Token 成本——100 条请求的 Token 总量不变，变的是总耗时从串行叠加变成约等于单条耗时 × ceil(100 / MAX_CONCURRENCY)。

### 4.3 吞吐量 vs 延迟的权衡

`MAX_CONCURRENCY` 是批处理的关键调参：

```
吞吐量 ↑ = MAX_CONCURRENCY ↑
延迟风险 ↑ = MAX_CONCURRENCY ↑（更易触发 Rate Limit → 429 → 重试 → 总时间反而变长）
```

调参策略：
1. 从 `MAX_CONCURRENCY = 5` 开始
2. 监控日志中的 429 错误次数
3. 若 429 < 5%，逐步提高到 10、20
4. 若 429 > 10%，降低并发数

---

## 五、Day 46 知识速查

### 三种优化手段的分工

```
缓存（Day 45）   → 省 Token 成本（重复请求不重复花钱）
批处理（今天）   → 省时间（N 个独立任务并发执行）
路由（Day 47）   → 省模型成本（简单任务用便宜模型）
```

### asyncio 批处理核心模式

```python
sem = asyncio.Semaphore(MAX_CONCURRENCY)   # 限制并发数

async def process_one(item):
    async with sem:                         # 等待令牌
        return await call_llm(item)         # I/O 等待期间释放事件循环

results = await asyncio.gather(             # 并发执行所有任务
    *[process_one(item) for item in items]
)
```

### 批处理 vs Batch API 选型

```
需要分钟内完成 + 所有 Provider 兼容  → asyncio 并发（方式 A）
可以等待数小时 + OpenAI/Anthropic    → Batch API（方式 B，50% 折扣）
```

---

## 六、实践任务

- [ ] 准备 20 条商品描述（可以手写或用 ChatGPT 生成），先用串行版本跑完，记录总耗时
- [ ] 实现 `batch_label()` 异步版本，用 `MAX_CONCURRENCY=10` 跑同样 20 条，记录总耗时
- [ ] 打印对比报告：串行耗时 / 批处理耗时 / 加速比（预期 5–10x）
- [ ] 把 `MAX_CONCURRENCY` 从 3 调到 20，观察耗时变化：找出边际收益递减的拐点（当并发数超过 API 限速时，总耗时因为重试反而变长）
- [ ] 给失败条目实现指数退避重试（最多 3 次），故意把一条描述改成空字符串触发 API 错误，验证其他条目不受影响

**产出标准**：一份对比数据表（串行 vs 批处理的总耗时和加速比），以及批处理的错误处理验证截图 / 日志。

---

## 七、下一步预告

Day 47 进入**模型分级路由**：批处理解决"同时跑多个任务"，路由解决"跑每个任务该用什么模型"。当系统同时面对"北京今天天气"（简单查询）和"帮我分析这份 50 页合同的法律风险"（复杂推理）时，两者都用 GPT-4 / DeepSeek-chat 是浪费——路由器根据问题的复杂度指标（长度、工具需求、历史失败率）自动把请求分发到合适的模型档位，让 Token 成本按需分配，同时维持回答质量。
