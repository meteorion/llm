# Day 49：限流与配额（应用层实现）

> 学习目标：理解为什么 LLM 应用必须做应用层限流；掌握固定窗口、滑动窗口、令牌桶三种算法的工作原理；在 Day 48 的网关层插入限流中间件，测试超限时的正确拒绝行为
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 49
>
> 🧭 导航：[← Day 48 · 模型网关：统一接口层与多 Provider 适配](day48_model_gateway.md) → Day 50 · 上下文工程（待更新）

---

## 目录

- [一、为什么必须做应用层限流](#一为什么必须做应用层限流)
  - [1.1 不限流的后果](#11-不限流的后果)
  - [1.2 Provider 限流 vs 应用层限流](#12-provider-限流-vs-应用层限流)
- [二、三种限流算法](#二三种限流算法)
  - [2.1 固定窗口（Fixed Window）](#21-固定窗口fixed-window)
  - [2.2 滑动窗口（Sliding Window）](#22-滑动窗口sliding-window)
  - [2.3 令牌桶（Token Bucket）](#23-令牌桶token-bucket)
  - [2.4 三种算法对比](#24-三种算法对比)
- [三、在网关层接入限流中间件](#三在网关层接入限流中间件)
  - [3.1 限流配置设计](#31-限流配置设计)
  - [3.2 滑动窗口实现](#32-滑动窗口实现)
  - [3.3 集成到 Day 48 的网关层](#33-集成到-day-48-的网关层)
- [四、超限行为验证](#四超限行为验证)
  - [4.1 正确的拒绝响应](#41-正确的拒绝响应)
  - [4.2 测试脚本](#42-测试脚本)
- [五、限流的分级策略](#五限流的分级策略)
- [六、Day 49 知识速查](#六day-49-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么必须做应用层限流

### 1.1 不限流的后果

LLM API 按 Token 计费，每次调用都有真实的成本。如果不做限流：

| 场景 | 后果 |
|-----|------|
| **恶意用户循环调用** | 几分钟内消耗大量 Token，产生意外账单 |
| **爬虫或脚本滥用** | 一个来源把 Provider 的 RPM 配额打满，其他用户受影响 |
| **Bug 触发死循环** | 代码 Bug 导致重试死循环，成本指数级增长 |
| **突发流量峰值** | 大量并发请求超出 Provider 的限速，导致批量 429 错误 |

**成本失控是 LLM 应用特有的风险**——普通 Web API 的错误顶多让服务崩溃，LLM 应用的错误可能让你收到一张巨额账单。

### 1.2 Provider 限流 vs 应用层限流

Provider 端（如 DeepSeek、OpenAI）有自己的 RPM（Requests Per Minute）限制，但这解决不了应用层的问题：

| | Provider 限流 | 应用层限流 |
|--|-------------|----------|
| **触发后的响应** | 返回 429 错误，调用方需要自己处理 | 直接在网关拒绝，返回友好提示 |
| **粒度** | 按 API Key（整个账号共享） | 按用户 ID / IP / 功能模块 |
| **可定制性** | 固定，无法改变 | 完全可控（不同用户不同配额） |
| **成本保护** | 保护 Provider 资源 | 保护自己的账单 |

两者互补，不能替代：应用层限流是第一道防线，Provider 限流是兜底保障。

---

## 二、三种限流算法

### 2.1 固定窗口（Fixed Window）

**原理**：把时间切成固定大小的窗口（如 1 分钟），窗口内的请求数不超过上限。

```
时间轴: |--- 第1分钟 ---|--- 第2分钟 ---|
请求数:  ①②③④⑤(上限)   ①②③...

问题：窗口边界的突刺
  :59 发 5 个请求 → 第1分钟消耗完
  1:01 发 5 个请求 → 第2分钟重置，可以通过
  → 2秒内 10 个请求，实际承受了 2 倍上限的压力
```

```python
import time
from collections import defaultdict

class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_req = max_requests
        self.window  = window_seconds
        self._counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        # [count, window_start_timestamp]

    def is_allowed(self, key: str) -> bool:
        now = int(time.time())
        count, window_start = self._counts[key]

        # 窗口过期，重置
        if now - window_start >= self.window:
            self._counts[key] = [1, now]
            return True

        if count >= self.max_req:
            return False

        self._counts[key][0] += 1
        return True
```

**优点**：实现极简  
**缺点**：窗口边界有突刺问题（2× 上限流量能瞬间通过）

### 2.2 滑动窗口（Sliding Window）

**原理**：记录每次请求的时间戳，判断"最近 N 秒内"的请求数是否超限。窗口随时间滑动，没有固定边界。

```
时间轴: ----①②③-④⑤-----⑥-------
当前时刻: t
窗口 [t-60s, t] 内的请求数 = 实际限制

→ 没有边界突刺问题，任意 60 秒区间都不会超限
```

```python
import time
from collections import defaultdict, deque

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_req = max_requests
        self.window  = window_seconds
        self._timestamps: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        dq = self._timestamps[key]

        # 清除窗口外的旧记录
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) >= self.max_req:
            return False

        dq.append(now)
        return True

    def remaining(self, key: str) -> int:
        """返回当前窗口内还剩几次请求配额"""
        now = time.monotonic()
        cutoff = now - self.window
        dq = self._timestamps[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        return max(0, self.max_req - len(dq))

    def retry_after(self, key: str) -> float:
        """返回最早的下一次可用时刻距现在的秒数"""
        dq = self._timestamps[key]
        if not dq or len(dq) < self.max_req:
            return 0.0
        return max(0.0, dq[0] + self.window - time.monotonic())
```

**优点**：精确，无突刺，生产首选  
**缺点**：需要存储每个 key 的所有时间戳（用户多、请求多时内存占用上升）

### 2.3 令牌桶（Token Bucket）

**原理**：桶里有令牌，每次请求消耗一个令牌，令牌以固定速率补充。桶满时停止补充。允许突发（桶里有积累的令牌时可以连续通过）。

```
桶容量: 10（最多允许 10 次突发）
补充速率: 1 令牌/秒
当前令牌数: 7

请求来了 → 令牌数 -1 → 6，允许
连续 6 次请求 → 令牌数 0，下一次拒绝
等 1 秒 → 令牌数 1，可以再来 1 次
```

```python
import time

class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_rate: float):
        """
        capacity: 桶的最大容量（允许的突发量）
        refill_rate: 每秒补充的令牌数
        """
        self.capacity     = capacity
        self.refill_rate  = refill_rate
        self._buckets: dict[str, tuple[float, float]] = {}
        # key → (tokens, last_refill_time)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last_time = self._buckets.get(key, (self.capacity, now))

        # 补充令牌
        elapsed = now - last_time
        tokens = min(self.capacity, tokens + elapsed * self.refill_rate)

        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False

        self._buckets[key] = (tokens - 1.0, now)
        return True
```

**优点**：允许合理的突发流量，平滑限速  
**缺点**：实现稍复杂，突发量难以精确控制

### 2.4 三种算法对比

| 维度 | 固定窗口 | 滑动窗口 | 令牌桶 |
|-----|---------|---------|-------|
| **实现复杂度** | 低 | 中 | 中 |
| **精确性** | 低（有边界突刺） | 高（任意窗口精确） | 高（平滑） |
| **允许突发** | 有限（边界处） | 否（严格限制） | 是（可配置） |
| **内存开销** | 低 | 中（需存时间戳队列） | 低 |
| **适合场景** | 粗粒度保护，要求简单 | 精确限速，生产推荐 | 允许突发的 API 网关 |

**本路线实现滑动窗口**：精确度最高，适合 LLM 应用的按用户限速场景。

---

## 三、在网关层接入限流中间件

### 3.1 限流配置设计

不同用户等级可以有不同配额：

```python
# gateway/rate_limit_config.py
from dataclasses import dataclass

@dataclass
class QuotaConfig:
    max_requests: int      # 窗口内最大请求数
    window_seconds: int    # 窗口大小（秒）
    tier: str              # 用户等级名称

QUOTA_TIERS: dict[str, QuotaConfig] = {
    "free":    QuotaConfig(max_requests=10,  window_seconds=60,  tier="free"),
    "pro":     QuotaConfig(max_requests=60,  window_seconds=60,  tier="pro"),
    "premium": QuotaConfig(max_requests=300, window_seconds=60,  tier="premium"),
    "internal": QuotaConfig(max_requests=1000, window_seconds=60, tier="internal"),
}

DEFAULT_TIER = "free"
```

### 3.2 滑动窗口实现

```python
# gateway/rate_limiter.py
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from .rate_limit_config import QUOTA_TIERS, DEFAULT_TIER, QuotaConfig

@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int        # 当前窗口剩余配额
    retry_after: float    # 被拒绝时，多少秒后可以重试
    tier: str

class RateLimiter:
    def __init__(self):
        self._windows: dict[str, deque] = defaultdict(deque)
        # key = f"{user_id}:{tier}" → deque of timestamps

    def check(self, user_id: str, tier: str = DEFAULT_TIER) -> RateLimitResult:
        cfg: QuotaConfig = QUOTA_TIERS.get(tier, QUOTA_TIERS[DEFAULT_TIER])
        key = f"{user_id}:{tier}"
        now = time.monotonic()
        cutoff = now - cfg.window_seconds
        dq = self._windows[key]

        # 清理过期记录
        while dq and dq[0] < cutoff:
            dq.popleft()

        current_count = len(dq)

        if current_count >= cfg.max_requests:
            retry_after = round(dq[0] + cfg.window_seconds - now, 2)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=max(0.0, retry_after),
                tier=tier,
            )

        dq.append(now)
        return RateLimitResult(
            allowed=True,
            remaining=cfg.max_requests - current_count - 1,
            retry_after=0.0,
            tier=tier,
        )

# 全局单例
rate_limiter = RateLimiter()
```

### 3.3 集成到 Day 48 的网关层

在 `ModelGateway.complete()` 的最开始插入限流检查：

```python
# gateway/gateway.py（在 complete() 方法开头加入）
from .rate_limiter import rate_limiter, RateLimitResult
from .types import GatewayRequest, GatewayResponse

class ModelGateway:
    def complete(self, req: GatewayRequest) -> GatewayResponse:
        # ① 限流检查（在任何 LLM 调用之前）
        rl_result = rate_limiter.check(
            user_id=req.user_id or "anonymous",
            tier=getattr(req, "user_tier", "free"),
        )
        if not rl_result.allowed:
            return GatewayResponse(
                content="",
                model="",
                provider=self._provider,
                tokens_input=0,
                tokens_output=0,
                cost_usd=0.0,
                latency_ms=0,
                status="rate_limited",
                error=(
                    f"请求过于频繁，已超出配额（{rl_result.tier} 用户："
                    f"每 {QUOTA_TIERS[rl_result.tier].window_seconds} 秒最多 "
                    f"{QUOTA_TIERS[rl_result.tier].max_requests} 次）。"
                    f"请在 {rl_result.retry_after:.1f} 秒后重试。"
                ),
            )

        # ② 正常调用流程（同 Day 48）
        # ...
```

---

## 四、超限行为验证

### 4.1 正确的拒绝响应

限流触发时，网关返回：
- `status = "rate_limited"`（不是 `"error"`，可以被调用方精确识别）
- `error` 包含明确的原因和重试时间（用户可读的提示，而非技术栈回溯）
- `latency_ms = 0`（没有调用 LLM，零成本拒绝）

**不应该**：
- 抛出未捕获的异常（让调用方崩溃）
- 返回 HTTP 500（掩盖了限流的语义）
- 只返回 "error" 而不说明原因（用户不知道怎么办）

### 4.2 测试脚本

```python
import time
from gateway.gateway import ModelGateway
from gateway.types import GatewayRequest

gateway = ModelGateway()

def test_rate_limit():
    # free 用户：每 60 秒最多 10 次
    user_id = "test_user_free"
    allowed_count = 0
    blocked_count = 0

    print("发送 15 次请求（free 用户，配额 10/60s）：")
    for i in range(15):
        req = GatewayRequest(
            messages=[{"role": "user", "content": "ping"}],
            user_id=user_id,
        )
        resp = gateway.complete(req)

        if resp.status == "rate_limited":
            blocked_count += 1
            print(f"  请求 {i+1:2d}: ❌ 被限流 | retry_after={resp.error[-10:]}")
        else:
            allowed_count += 1
            print(f"  请求 {i+1:2d}: ✅ 通过")

    print(f"\n结果：通过 {allowed_count} 次，被限流 {blocked_count} 次")
    assert allowed_count == 10, f"期望 10 次通过，实际 {allowed_count} 次"
    assert blocked_count == 5, f"期望 5 次被限流，实际 {blocked_count} 次"
    print("✅ 限流行为符合预期")

    # 测试恢复
    print("\n等待 2 秒后再发 1 次（窗口还未过期，应该继续被限流）：")
    time.sleep(2)
    req = GatewayRequest(messages=[{"role": "user", "content": "ping"}], user_id=user_id)
    resp = gateway.complete(req)
    print(f"  状态: {resp.status}（预期 rate_limited）")

if __name__ == "__main__":
    test_rate_limit()
```

预期输出：

```
发送 15 次请求（free 用户，配额 10/60s）：
  请求  1: ✅ 通过
  请求  2: ✅ 通过
  ...
  请求 10: ✅ 通过
  请求 11: ❌ 被限流 | retry_after=57.3 秒后重试。
  请求 12: ❌ 被限流 | retry_after=57.2 秒后重试。
  ...
  请求 15: ❌ 被限流 | retry_after=57.0 秒后重试。

结果：通过 10 次，被限流 5 次
✅ 限流行为符合预期
```

---

## 五、限流的分级策略

不同用户等级、不同功能模块可以有差异化的配额：

```python
# 按用户等级：不同付费等级给不同配额
free_limiter    = RateLimiter()   # 10/min
pro_limiter     = RateLimiter()   # 60/min
premium_limiter = RateLimiter()   # 300/min

# 按功能模块：昂贵的功能有更严格的限制
FUNCTION_QUOTAS = {
    "weather_query":   QuotaConfig(max_requests=30,  window_seconds=60, tier="function"),
    "travel_planner":  QuotaConfig(max_requests=5,   window_seconds=60, tier="function"),   # 昂贵
    "batch_label":     QuotaConfig(max_requests=2,   window_seconds=60, tier="function"),   # 极昂贵
}

# 按 IP（防止未登录用户滥用）
ip_limiter = RateLimiter()   # 20/min per IP
```

**多层限流叠加**（实际生产中常见）：

```python
def check_all_limits(user_id: str, user_tier: str, function_name: str, ip: str) -> RateLimitResult:
    # 按用户 ID 检查
    result = rate_limiter.check(user_id, user_tier)
    if not result.allowed:
        return result

    # 按功能检查
    if function_name in FUNCTION_QUOTAS:
        result = rate_limiter.check(f"{user_id}:{function_name}", "function")
        if not result.allowed:
            return result

    # 按 IP 检查（匿名用户的兜底）
    if not user_id or user_id == "anonymous":
        result = rate_limiter.check(f"ip:{ip}", "free")
        if not result.allowed:
            return result

    return RateLimitResult(allowed=True, remaining=-1, retry_after=0.0, tier=user_tier)
```

---

## 六、Day 49 知识速查

### 三种算法一句话总结

```
固定窗口：简单，有边界突刺（2× 上限流量能瞬间通过）
滑动窗口：精确，任意时间段都严格限速，生产首选
令牌桶：  允许合理突发（桶里有积累令牌时），适合 API 网关场景
```

### 限流 key 的设计

```
按用户 ID：  f"{user_id}"         → 精细控制单用户
按用户+功能：f"{user_id}:{func}"  → 控制高价值功能的使用频率
按 IP：      f"ip:{ip_addr}"      → 匿名用户的兜底防护
按 API Key： f"key:{api_key}"     → B2B 场景，按租户限速
```

### 超限响应的正确格式

```python
GatewayResponse(
    status="rate_limited",        # 区别于 "error"，可被精确识别
    error="请求过于频繁，请在 X 秒后重试。",  # 用户可读，含重试指导
    cost_usd=0.0,                 # 未调用 LLM，零成本
    latency_ms=0,                 # 立即返回，不阻塞
)
```

---

## 七、实践任务

- [ ] 实现 `SlidingWindowRateLimiter`，配置 free 用户 10 次/60 秒；用单元测试验证：前 10 次允许、第 11 次拒绝、`retry_after` > 0
- [ ] 把 `rate_limiter.check()` 插入 `ModelGateway.complete()` 的开头；跑测试脚本，验证"通过 10 次、拒绝 5 次"的预期行为
- [ ] 验证超限响应的语义正确性：`status="rate_limited"` 而非 `"error"`；`error` 字段包含可读的重试提示；`cost_usd=0.0`（没有产生实际费用）
- [ ] 给 `travel_planner` 功能单独设置更严格的配额（如 3 次/60 秒），测试与用户级别配额的叠加效果
- [ ] （进阶）实现 `TokenBucketRateLimiter`，对比同样请求序列下令牌桶和滑动窗口的行为差异

**产出标准**：超限请求被正确拒绝（`status="rate_limited"`），返回包含重试时间的明确提示，且整个过程不调用 LLM（`cost_usd=0`）。

---

## 八、下一步预告

Day 50 进入**上下文工程（Context Engineering）**：今天的限流控制"谁能发请求"，Day 50 要控制"发出去的请求里装什么"。上下文窗口是稀缺资源——System Prompt、RAG 检索结果、工具返回、历史对话、用户当前消息这几类信息同时竞争同一个有限的 Token 预算。设计一个明确的上下文组装策略：固定分区顺序 + 每分区长度上限 + 超限时的裁剪规则，让每次请求的上下文既完整又不浪费。
