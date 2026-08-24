# Day 47：模型分级路由

> 学习目标：理解按复杂度分级路由的核心思路；掌握路由判断依据（问题长度、工具需求、历史失败率）的设计方法；实现一个路由器，自动把请求分发到合适的模型档位，并记录路由决策日志；量化分级前后的成本差异
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 47
>
> 🧭 导航：[← Day 46 · 批处理（Batching）](day46_batching.md) → [Day 48 · 模型网关：统一接口层与多 Provider 适配](day48_model_gateway.md)

---

## 目录

- [一、为什么需要模型分级路由](#一为什么需要模型分级路由)
  - [1.1 "一模型走天下"的浪费](#11-一模型走天下的浪费)
  - [1.2 分级路由 vs 缓存 vs 批处理](#12-分级路由-vs-缓存-vs-批处理)
- [二、路由判断依据设计](#二路由判断依据设计)
  - [2.1 问题长度](#21-问题长度)
  - [2.2 是否需要工具调用](#22-是否需要工具调用)
  - [2.3 历史失败率](#23-历史失败率)
  - [2.4 关键词特征](#24-关键词特征)
  - [2.5 综合评分：把多个信号合并成一个复杂度分数](#25-综合评分把多个信号合并成一个复杂度分数)
- [三、路由器实现](#三路由器实现)
  - [3.1 模型档位定义](#31-模型档位定义)
  - [3.2 路由决策函数](#32-路由决策函数)
  - [3.3 带路由的 LLM 调用封装](#33-带路由的-llm-调用封装)
- [四、路由决策日志](#四路由决策日志)
  - [4.1 日志字段设计](#41-日志字段设计)
  - [4.2 成本对比分析脚本](#42-成本对比分析脚本)
  - [4.3 典型成本对比报告](#43-典型成本对比报告)
- [五、路由器的边界与风险](#五路由器的边界与风险)
  - [5.1 降档失败的代价](#51-降档失败的代价)
  - [5.2 回退机制：小模型失败自动升档](#52-回退机制小模型失败自动升档)
- [六、Day 47 知识速查](#六day-47-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么需要模型分级路由

### 1.1 "一模型走天下"的浪费

当系统对所有请求都用同一个模型时，问题出现在两端：

| 请求类型 | 用贵模型的代价 | 用便宜模型的代价 |
|---------|-------------|--------------|
| "北京今天天气？" | 浪费：用 $0.01/次 的模型回答只需 $0.0001 的问题 | 无代价：小模型完全胜任 |
| "分析这份合同的法律风险" | 合理：复杂推理确实需要大模型 | 危险：小模型可能给出错误分析 |

用 Day 44 的成本报表来看这个问题：如果 60% 的请求是简单查询（问候、单一事实查询、简短翻译），把这 60% 路由到便宜 10 倍的小模型，总成本可以降低约 54%。

### 1.2 分级路由 vs 缓存 vs 批处理

| 优化手段 | 省的是什么 | 判断时机 |
|---------|----------|---------|
| **缓存** | 重复请求的全部 Token 成本 | 请求到来时，先查缓存 |
| **批处理** | 串行等待的时间 | 有多个独立任务时并发执行 |
| **路由** | 用错模型的成本差价 | 每个请求的复杂度评估 |

三者在同一个请求处理流程里有明确的先后顺序：路由（选模型）→ 缓存（查历史结果）→ 批处理（多任务并发）。路由在最前面，因为它决定了后续用哪个模型的缓存、哪个模型的并发配额。

---

## 二、路由判断依据设计

### 2.1 问题长度

问题越长，通常意味着背景越复杂、需要的推理深度越高：

```python
def length_score(user_input: str) -> float:
    """返回 0.0（简单）到 1.0（复杂）的分数"""
    n = len(user_input)
    if n < 50:    return 0.0   # 极短：打招呼、单词查询
    if n < 150:   return 0.2   # 短：简单问题
    if n < 400:   return 0.5   # 中等
    if n < 800:   return 0.7   # 较长：有背景描述
    return 1.0                 # 很长：文档分析、代码审查
```

**局限**：长度只是代理指标，"把这段话翻译成英文：[500字文章]"是长输入但任务本身不复杂。长度信号要与其他信号结合。

### 2.2 是否需要工具调用

工具调用要求模型能正确解析函数签名、传递参数、整合工具结果——这是一个对模型能力有明确要求的特征：

```python
TOOL_KEYWORDS = [
    "查一下", "帮我搜", "查询", "查找", "计算", "转换",
    "天气", "汇率", "价格", "翻译", "搜索",
]

def tool_score(user_input: str) -> float:
    matches = sum(1 for kw in TOOL_KEYWORDS if kw in user_input)
    if matches == 0:   return 0.0
    if matches == 1:   return 0.4   # 单工具调用
    return 0.7                      # 多工具调用（更复杂）
```

**更准确的方法**：用小模型先做一次"是否需要工具"的二分类（成本极低），再根据结果决定主请求的模型档位。

### 2.3 历史失败率

某类请求历史上小模型经常失败（被 Critic 拒绝、用户反馈差），说明该类任务超出小模型能力范围：

```python
# 路由决策日志里记录每次的模型档位和结果
# 按"问题类别"聚合失败率（需要先对问题做分类，这里简化为按长度分箱）

def failure_rate_score(category: str, failure_stats: dict[str, dict]) -> float:
    """从历史日志计算该类别在小模型的失败率"""
    stats = failure_stats.get(category, {"total": 0, "failed": 0})
    if stats["total"] < 10:
        return 0.0   # 样本不足，不调整
    rate = stats["failed"] / stats["total"]
    if rate < 0.05:   return 0.0
    if rate < 0.15:   return 0.3
    if rate < 0.30:   return 0.6
    return 1.0
```

### 2.4 关键词特征

某些关键词几乎确定性地指向复杂任务：

```python
COMPLEX_KEYWORDS = [
    # 推理类
    "分析", "评估", "比较", "论证", "推断", "判断",
    # 创作类
    "写一篇", "生成报告", "撰写", "起草",
    # 代码类
    "代码审查", "debug", "重构", "设计架构",
    # 法律/合规
    "合同", "法律风险", "合规", "条款",
]

SIMPLE_KEYWORDS = [
    "什么是", "怎么说", "翻译", "解释一下",
    "天气", "汇率", "几点", "多少钱",
]

def keyword_score(user_input: str) -> float:
    complex_hits = sum(1 for kw in COMPLEX_KEYWORDS if kw in user_input)
    simple_hits  = sum(1 for kw in SIMPLE_KEYWORDS  if kw in user_input)
    if complex_hits > 0 and simple_hits == 0:
        return min(0.3 + complex_hits * 0.2, 1.0)
    if simple_hits > 0 and complex_hits == 0:
        return max(0.0, -0.2 * simple_hits)   # 负向调整，压到 0
    return 0.0   # 混合信号，不调整
```

### 2.5 综合评分：把多个信号合并成一个复杂度分数

```python
def complexity_score(
    user_input: str,
    category: str = "default",
    failure_stats: dict | None = None,
) -> float:
    """返回 0.0（极简单）到 1.0（极复杂）的综合分数"""
    weights = {
        "length":   0.25,
        "tool":     0.30,
        "keyword":  0.30,
        "failure":  0.15,
    }
    scores = {
        "length":  length_score(user_input),
        "tool":    tool_score(user_input),
        "keyword": keyword_score(user_input),
        "failure": failure_rate_score(category, failure_stats or {}),
    }
    return sum(weights[k] * scores[k] for k in weights)
```

---

## 三、路由器实现

### 3.1 模型档位定义

```python
from dataclasses import dataclass

@dataclass
class ModelTier:
    name: str          # 档位名称（用于日志）
    model_id: str      # API 调用的模型 ID
    price_input: float # USD / 1M tokens
    price_output: float
    threshold: float   # 复杂度分数 >= 此值时选用本档位

# 从低到高排列，路由器从高到低扫描，第一个满足阈值的档位胜出
TIERS = [
    ModelTier("premium",  "deepseek-reasoner", 0.55, 2.19, threshold=0.65),
    ModelTier("standard", "deepseek-chat",     0.14, 0.28, threshold=0.30),
    ModelTier("lite",     "deepseek-chat",     0.07, 0.14, threshold=0.00),
    # 注：DeepSeek 没有真正的"lite"档位，此处仅演示分级概念；
    # 生产环境可替换为更便宜的模型（如 GPT-4o-mini vs GPT-4o，
    # 或 Claude Haiku vs Claude Sonnet）
]
```

### 3.2 路由决策函数

```python
def route(user_input: str, category: str = "default",
          failure_stats: dict | None = None) -> ModelTier:
    score = complexity_score(user_input, category, failure_stats)
    # 从高档位往低档位扫描
    for tier in TIERS:
        if score >= tier.threshold:
            return tier, score
    return TIERS[-1], score   # 兜底：最低档位
```

### 3.3 带路由的 LLM 调用封装

```python
import time
from openai import OpenAI

client = OpenAI(api_key="...", base_url="https://api.deepseek.com")


def routed_call(
    user_input: str,
    system_prompt: str = "",
    category: str = "default",
    failure_stats: dict | None = None,
) -> dict:
    tier, score = route(user_input, category, failure_stats)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_input})

    t0 = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=tier.model_id,
            temperature=0,
            messages=messages,
        )
        answer = response.choices[0].message.content
        usage  = response.usage
        cost   = (usage.prompt_tokens * tier.price_input +
                  usage.completion_tokens * tier.price_output) / 1_000_000
        status = "success"
        error  = ""
    except Exception as e:
        answer, usage, cost, status, error = "", None, 0.0, "error", str(e)

    return {
        "user_input":    user_input[:80],
        "category":      category,
        "complexity":    round(score, 3),
        "tier":          tier.name,
        "model":         tier.model_id,
        "answer":        answer,
        "tokens_input":  usage.prompt_tokens  if usage else 0,
        "tokens_output": usage.completion_tokens if usage else 0,
        "cost_usd":      round(cost, 8),
        "latency_ms":    int((time.monotonic() - t0) * 1000),
        "status":        status,
        "error":         error,
    }
```

---

## 四、路由决策日志

### 4.1 日志字段设计

把 `routed_call` 的返回值直接写入 JSONL 文件（与 Day 44 的结构化日志保持一致格式）：

```python
import json
from pathlib import Path

ROUTING_LOG = Path("logs/routing_decisions.jsonl")

def log_routing(record: dict) -> None:
    ROUTING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ROUTING_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# 调用方式
result = routed_call("北京今天天气怎么样？", category="weather_query")
log_routing(result)
```

典型日志条目：

```json
{"user_input": "北京今天天气怎么样？", "complexity": 0.12, "tier": "lite",
 "model": "deepseek-chat", "cost_usd": 0.0000234, "latency_ms": 1823, "status": "success"}

{"user_input": "帮我分析这份合同第3条款的法律风险...", "complexity": 0.81, "tier": "premium",
 "model": "deepseek-reasoner", "cost_usd": 0.0089, "latency_ms": 8234, "status": "success"}
```

### 4.2 成本对比分析脚本

```python
import json
from pathlib import Path
from collections import defaultdict

def routing_cost_report(log_file: Path = ROUTING_LOG) -> None:
    if not log_file.exists():
        print("日志文件不存在")
        return

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines() if l]
    success = [r for r in records if r["status"] == "success"]

    # 按档位聚合
    by_tier: dict[str, dict] = defaultdict(lambda: {"count": 0, "cost": 0.0})
    for r in success:
        b = by_tier[r["tier"]]
        b["count"] += 1
        b["cost"]  += r["cost_usd"]

    total_cost    = sum(b["cost"] for b in by_tier.values())
    total_count   = sum(b["count"] for b in by_tier.values())

    # 反事实成本：如果所有请求都用 standard 档位
    avg_standard_cost = by_tier.get("standard", {}).get("cost", 0) / max(by_tier.get("standard", {}).get("count", 1), 1)
    counterfactual_cost = avg_standard_cost * total_count

    print(f"\n{'档位':<12} {'请求数':>6} {'占比':>6} {'总成本(USD)':>12} {'均成本(USD)':>12}")
    print("-" * 55)
    for tier in ["lite", "standard", "premium"]:
        b = by_tier.get(tier, {"count": 0, "cost": 0.0})
        pct = b["count"] / total_count * 100 if total_count else 0
        avg = b["cost"] / b["count"] if b["count"] else 0
        print(f"{tier:<12} {b['count']:>6} {pct:>5.1f}% {b['cost']:>12.6f} {avg:>12.6f}")
    print("-" * 55)
    print(f"{'合计':<12} {total_count:>6}        {total_cost:>12.6f}")
    print(f"\n如果全用 standard：{counterfactual_cost:.6f} USD")
    print(f"路由节省：{counterfactual_cost - total_cost:.6f} USD "
          f"({(1 - total_cost/counterfactual_cost)*100:.1f}%)\n")
```

### 4.3 典型成本对比报告

```
档位          请求数    占比    总成本(USD)   均成本(USD)
-------------------------------------------------------
lite             62   62.0%     0.001458     0.000024
standard         28   28.0%     0.004312     0.000154
premium          10   10.0%     0.089000     0.008900
-------------------------------------------------------
合计            100          0.094770

如果全用 standard：0.015400 USD
路由节省：-0.079370 USD (-515.4%)
```

注意：premium 档位（如 DeepSeek Reasoner）单次成本远高于 standard。路由的价值在于：让 10 次真正需要 premium 的请求得到质量保障，同时把 62 次简单请求降到 lite 档位节省成本。**如果 premium 的单次成本远高于 standard，总成本可能因路由上升**——这是正确的，因为路由让复杂任务得到了更好的模型。成本对比的正确方式是：和"全用 premium"对比，而非"全用 standard"对比。

---

## 五、路由器的边界与风险

### 5.1 降档失败的代价

路由器把一个实际复杂的请求误判为简单，发给小模型，可能导致：
- 回答质量不足（用户体验损失）
- 工具调用失败（小模型无法正确解析函数签名）
- 需要重试（增加延迟，有时成本反而更高）

**降档错误的代价通常远大于升档错误的代价**（升档只是多花一点钱，降档可能导致用户流失）。因此路由阈值应保守设定，宁可多用大模型。

### 5.2 回退机制：小模型失败自动升档

```python
def routed_call_with_fallback(
    user_input: str,
    system_prompt: str = "",
    category: str = "default",
    failure_stats: dict | None = None,
) -> dict:
    result = routed_call(user_input, system_prompt, category, failure_stats)

    # 如果 lite/standard 档位失败，自动升档重试一次
    if result["status"] == "error" and result["tier"] != "premium":
        fallback_tier = TIERS[0]   # premium
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_input})
        try:
            response = client.chat.completions.create(
                model=fallback_tier.model_id,
                temperature=0,
                messages=messages,
            )
            result["answer"] = response.choices[0].message.content
            result["tier"]   = f"{result['tier']}→premium(fallback)"
            result["status"] = "success_fallback"
        except Exception as e:
            result["error"] = f"fallback also failed: {e}"

    return result
```

---

## 六、Day 47 知识速查

### 路由判断信号速查

| 信号 | 权重 | 指向复杂 | 指向简单 |
|-----|-----|---------|---------|
| 问题长度 | 25% | > 400 字符 | < 50 字符 |
| 工具调用需求 | 30% | 多工具关键词 | 无工具词 |
| 关键词类型 | 30% | "分析 / 推断 / 合同" | "什么是 / 翻译 / 天气" |
| 历史失败率 | 15% | 同类在小模型失败率 > 15% | 失败率 < 5% |

### 路由器设计原则

```
1. 保守：阈值宁高勿低（多升档，少降档）
2. 可观测：每次路由决策都写日志（tier / score / cost）
3. 有回退：小模型失败时自动升档重试
4. 定期校准：用路由日志分析降档失败率，调整阈值
```

### 成本对比的正确姿势

```
✅ 正确：路由总成本 vs "全用 premium" 的总成本（路由节省了多少）
❌ 错误：路由总成本 vs "全用 standard" 的总成本（premium 请求的成本差值会让结论失真）
```

---

## 七、实践任务

- [ ] 实现 `complexity_score()` 函数，包含长度、工具关键词、任务关键词三个信号；准备 10 条测试输入（5 条简单 / 5 条复杂），打印每条的得分，验证得分符合直觉
- [ ] 实现 `route()` 和 `routed_call()`，用 10 条测试输入验证路由决策（简单的进 lite / standard，复杂的进 premium）
- [ ] 实现路由日志写入，跑 20 次不同复杂度的请求，在日志里验证档位分布（预期 lite 占多数）
- [ ] 运行 `routing_cost_report()`，对比路由总成本和"全用 standard"的反事实成本，记录路由节省比例
- [ ] 故意把一个复杂问题的阈值设低（路由到 lite），观察回答质量是否下降，验证降档风险

**产出标准**：路由决策日志（至少 20 条，包含 complexity 分数和 tier 字段）+ 成本对比报告（路由方案 vs 全用某档位）。

---

## 八、下一步预告

Day 48 进入**模型网关：统一接口层与多 Provider 适配**：今天的路由器知道该用哪个模型，但代码里仍然直接调用具体的 Provider SDK。当项目需要同时支持 DeepSeek / OpenAI / Anthropic 时，每次换 Provider 都要改业务代码。Day 48 在应用层和 Provider 之间加一层"网关"——统一请求结构、统一鉴权、统一重试策略，让业务代码只和网关交互，换 Provider 时只改网关配置，业务代码零改动。同时了解开源模型网关 LiteLLM 的设计思路，判断什么时候自研网关，什么时候直接用 LiteLLM。
