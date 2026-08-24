# Day 48：模型网关：统一接口层与多 Provider 适配

> 学习目标：理解在应用代码和模型 Provider 之间加一层网关的价值；手写一个最小网关层，让换 Provider 只改配置、业务代码零改动；了解 LiteLLM 的设计思路，判断自研网关和 LiteLLM 各自的适用场景
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 48
>
> 🧭 导航：[← Day 47 · 模型分级路由](day47_model_routing.md) → Day 49 · 限流与配额（待更新）

---

## 目录

- [一、为什么需要模型网关](#一为什么需要模型网关)
  - [1.1 没有网关时的痛点](#11-没有网关时的痛点)
  - [1.2 网关的职责边界](#12-网关的职责边界)
- [二、手写最小模型网关](#二手写最小模型网关)
  - [2.1 Provider 配置设计](#21-provider-配置设计)
  - [2.2 统一请求 / 响应结构](#22-统一请求--响应结构)
  - [2.3 网关核心实现](#23-网关核心实现)
  - [2.4 验证：换 Provider 只改配置](#24-验证换-provider-只改配置)
- [三、网关层承载的横切关注点](#三网关层承载的横切关注点)
  - [3.1 统一日志（对接 Day 44）](#31-统一日志对接-day-44)
  - [3.2 统一路由（对接 Day 47）](#32-统一路由对接-day-47)
  - [3.3 统一重试](#33-统一重试)
- [四、LiteLLM：开源模型网关](#四litellm开源模型网关)
  - [4.1 LiteLLM 解决什么](#41-litellm-解决什么)
  - [4.2 LiteLLM 核心用法](#42-litellm-核心用法)
  - [4.3 自研网关 vs LiteLLM 选型指南](#43-自研网关-vs-litellm-选型指南)
- [五、Day 48 知识速查](#五day-48-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、为什么需要模型网关

### 1.1 没有网关时的痛点

随着项目演进，往往会出现以下情况：

```python
# weather_agent.py
from openai import OpenAI
client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")

# summary_tool.py
from anthropic import Anthropic
client = Anthropic(api_key=ANTHROPIC_KEY)

# translation_service.py
import openai
openai.api_key = OPENAI_KEY
```

三个文件，三种 SDK，三套鉴权方式。当需要切换 Provider（如 DeepSeek → OpenAI）时，必须修改所有业务文件。当需要统一加日志、加重试、加限流时，每个调用点都要改。

**没有网关的问题汇总**：

| 问题 | 后果 |
|-----|------|
| Provider SDK 散落在各业务文件 | 换 Provider 时需要改 N 个文件 |
| 鉴权逻辑重复 | API Key 管理混乱，容易泄露 |
| 日志 / 重试 / 限流各自实现 | 行为不一致，维护成本高 |
| 无统一的成本统计入口 | 难以聚合所有调用的 Token 消耗 |

### 1.2 网关的职责边界

模型网关是**应用代码和 Provider SDK 之间的适配层**：

```
业务代码
    ↓ 统一接口调用（不感知具体 Provider）
模型网关层
    ├── 鉴权：按 Provider 选择对应的 API Key
    ├── 路由：选择模型档位（对接 Day 47 的分级路由）
    ├── 重试：统一的退避策略
    ├── 日志：统一写结构化日志（对接 Day 44）
    └── 限流：按用户或来源控制速率（对接 Day 49）
    ↓ 分发到具体 Provider
DeepSeek / OpenAI / Anthropic / ...
```

**网关不做什么**：不实现业务逻辑，不解析 LLM 的输出内容，不做 Prompt 工程。它是纯粹的基础设施层。

---

## 二、手写最小模型网关

### 2.1 Provider 配置设计

把所有 Provider 的差异（base_url / api_key / 默认模型）收拢到一个配置文件：

```python
# gateway/config.py
import os
from dataclasses import dataclass

@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str        # 所有 Provider 都兼容 OpenAI 接口格式
    default_model: str

PROVIDERS: dict[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        name="deepseek",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
    ),
    "openai": ProviderConfig(
        name="openai",
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
    ),
    "moonshot": ProviderConfig(
        name="moonshot",
        api_key=os.environ.get("MOONSHOT_API_KEY", ""),
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
    ),
}

# 当前激活的 Provider，只改这一行就能切换
ACTIVE_PROVIDER = "deepseek"
```

### 2.2 统一请求 / 响应结构

定义网关的统一输入/输出，与具体 Provider 解耦：

```python
# gateway/types.py
from dataclasses import dataclass, field

@dataclass
class GatewayRequest:
    messages: list[dict]
    system_prompt: str = ""
    model: str = ""          # 留空则用 Provider 的 default_model
    temperature: float = 0.0
    max_tokens: int = 2048
    user_id: str = ""        # 用于限流和日志
    trace_id: str = ""       # 用于日志关联

@dataclass
class GatewayResponse:
    content: str
    model: str               # 实际使用的模型 ID
    provider: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_ms: int
    status: str              # "success" | "error"
    error: str = ""
```

### 2.3 网关核心实现

```python
# gateway/gateway.py
import time
import uuid
from openai import OpenAI

from .config import PROVIDERS, ACTIVE_PROVIDER, ProviderConfig
from .types import GatewayRequest, GatewayResponse

# 模型定价表（USD / 1M tokens）
_PRICING: dict[str, dict] = {
    "deepseek-chat":     {"input": 0.14,  "output": 0.28},
    "deepseek-reasoner": {"input": 0.55,  "output": 2.19},
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
    "gpt-4o":            {"input": 2.50,  "output": 10.00},
    "moonshot-v1-8k":    {"input": 0.012, "output": 0.012},
}

def _calc_cost(model: str, inp: int, out: int) -> float:
    p = _PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (inp * p["input"] + out * p["output"]) / 1_000_000


class ModelGateway:
    def __init__(self, provider_name: str = ACTIVE_PROVIDER):
        cfg: ProviderConfig = PROVIDERS[provider_name]
        self._provider = provider_name
        self._cfg = cfg
        self._client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    def complete(self, req: GatewayRequest) -> GatewayResponse:
        model = req.model or self._cfg.default_model
        trace_id = req.trace_id or str(uuid.uuid4())[:8]

        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.extend(req.messages)

        t0 = time.monotonic()
        try:
            resp = self._client.chat.completions.create(
                model=model,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                messages=messages,
            )
            usage = resp.usage
            return GatewayResponse(
                content=resp.choices[0].message.content,
                model=model,
                provider=self._provider,
                tokens_input=usage.prompt_tokens,
                tokens_output=usage.completion_tokens,
                cost_usd=_calc_cost(model, usage.prompt_tokens, usage.completion_tokens),
                latency_ms=int((time.monotonic() - t0) * 1000),
                status="success",
            )
        except Exception as e:
            return GatewayResponse(
                content="",
                model=model,
                provider=self._provider,
                tokens_input=0,
                tokens_output=0,
                cost_usd=0.0,
                latency_ms=int((time.monotonic() - t0) * 1000),
                status="error",
                error=str(e)[:300],
            )

# 全局单例（业务代码直接 import 使用）
gateway = ModelGateway()
```

### 2.4 验证：换 Provider 只改配置

业务代码始终保持不变：

```python
# weather_agent.py（业务代码，永远不碰）
from gateway.gateway import gateway
from gateway.types import GatewayRequest

def ask_weather(city: str) -> str:
    req = GatewayRequest(
        messages=[{"role": "user", "content": f"{city}今天天气怎么样？"}],
        system_prompt="你是一个天气助手，只提供天气信息。",
    )
    resp = gateway.complete(req)
    return resp.content if resp.status == "success" else f"Error: {resp.error}"
```

切换 Provider 时：

```python
# gateway/config.py —— 只改这一行
ACTIVE_PROVIDER = "openai"   # 从 "deepseek" 改为 "openai"
```

`weather_agent.py` 零改动，仍然正常运行。

---

## 三、网关层承载的横切关注点

### 3.1 统一日志（对接 Day 44）

把 Day 44 的结构化日志写入点统一到网关的 `complete()` 方法里，业务代码不再需要单独埋点：

```python
# gateway/gateway.py（在 complete() 里追加）
from ..structured_logger import log_request, new_trace_id

def complete(self, req: GatewayRequest) -> GatewayResponse:
    trace_id = req.trace_id or new_trace_id()
    log_request(trace_id=trace_id, function_name=req.user_id or "unknown",
                event="request_start")

    # ... 调用逻辑 ...

    log_request(
        trace_id=trace_id,
        function_name=req.user_id or "unknown",
        event="request_complete",
        model=resp.model,
        tokens_input=resp.tokens_input,
        tokens_output=resp.tokens_output,
        latency_total_ms=resp.latency_ms,
        status=resp.status,
    )
    return resp
```

### 3.2 统一路由（对接 Day 47）

在网关的 `complete()` 里调用 Day 47 的路由器，自动选择模型档位：

```python
from ..router import route   # Day 47 的路由模块

def complete(self, req: GatewayRequest) -> GatewayResponse:
    if not req.model:
        # 从用户消息里提取文本做路由判断
        user_text = " ".join(m["content"] for m in req.messages if m["role"] == "user")
        tier, score = route(user_text)
        req = GatewayRequest(**{**req.__dict__, "model": tier.model_id})
    # ...
```

### 3.3 统一重试

在网关层统一实现指数退避重试，业务代码无需关心：

```python
import time

def complete_with_retry(self, req: GatewayRequest, max_retries: int = 3) -> GatewayResponse:
    for attempt in range(max_retries):
        resp = self.complete(req)
        if resp.status == "success":
            return resp
        if attempt < max_retries - 1:
            wait = 2 ** attempt   # 1s, 2s, 4s
            time.sleep(wait)
    return resp   # 最后一次失败结果
```

---

## 四、LiteLLM：开源模型网关

### 4.1 LiteLLM 解决什么

LiteLLM 是目前最主流的开源模型网关库，用一行代码支持 100+ 个 Provider：

```bash
pip install litellm
```

核心价值：**把所有 Provider 的 API 统一成 OpenAI 格式**——不管调 Anthropic、Gemini、Cohere 还是本地 Ollama，代码格式完全一样：

```python
from litellm import completion

# 调 DeepSeek
resp = completion(model="deepseek/deepseek-chat", messages=[...])

# 调 Anthropic Claude（格式完全相同！）
resp = completion(model="anthropic/claude-3-5-sonnet-20241022", messages=[...])

# 调本地 Ollama
resp = completion(model="ollama/llama3", messages=[...], api_base="http://localhost:11434")
```

### 4.2 LiteLLM 核心用法

```python
import litellm
import os

# 设置各 Provider 的 Key（LiteLLM 按模型前缀自动选择）
os.environ["DEEPSEEK_API_KEY"] = "..."
os.environ["ANTHROPIC_API_KEY"] = "..."

# 统一调用接口
response = litellm.completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "北京今天天气？"}],
    temperature=0,
)
print(response.choices[0].message.content)

# 内置成本追踪
cost = litellm.completion_cost(completion_response=response)
print(f"成本: ${cost:.6f}")

# 内置回退：主模型失败时自动切换备用模型
response = litellm.completion(
    model="deepseek/deepseek-chat",
    messages=[...],
    fallbacks=["openai/gpt-4o-mini"],
)
```

**LiteLLM Proxy**（进阶）：作为独立进程运行，提供统一的 HTTP API：

```bash
litellm --model deepseek/deepseek-chat --port 4000
# 现在任何能调 OpenAI 的代码都能指向 localhost:4000
```

### 4.3 自研网关 vs LiteLLM 选型指南

| 维度 | 自研网关（手写） | LiteLLM |
|-----|--------------|---------|
| **Provider 覆盖** | 只支持手动接入的 Provider（几个） | 100+ Provider 开箱即用 |
| **控制精度** | 完全掌控每行逻辑 | 依赖 LiteLLM 实现，调试需查源码 |
| **新增依赖** | 无额外依赖（只用 openai SDK） | 引入 litellm 包（较大） |
| **内置功能** | 需要自己实现路由/重试/成本统计 | 路由 / 回退 / 成本统计 / 缓存开箱即用 |
| **学习成本** | 低（自己写，完全理解） | 需要阅读 LiteLLM 文档 |
| **社区支持** | 无 | 活跃社区，Bug 修复快 |

**选型判断标准**：

```
满足以下任一条件 → 用 LiteLLM：
  ✅ 需要同时对接 3 个以上 Provider
  ✅ 需要内置的成本追踪和 Provider 回退
  ✅ 团队规模大，希望标准化而非自研

满足以下任一条件 → 自研网关：
  ✅ Provider 固定（只用 1-2 个）且长期不变
  ✅ 需要深度定制路由逻辑（与业务强耦合）
  ✅ 极端控制依赖（嵌入式 / 边缘部署场景）
  ✅ 学习目的：理解网关层的设计原理
```

**本路线的建议**：学习阶段先手写网关（今天），理解原理后按需引入 LiteLLM。

---

## 五、Day 48 知识速查

### 网关层的职责清单

```
✅ 统一 Provider 接口（换 Provider 只改配置）
✅ 集中鉴权（API Key 只在网关层出现）
✅ 统一日志（对接 Day 44 结构化日志）
✅ 统一路由（对接 Day 47 分级路由）
✅ 统一重试（指数退避，业务代码无感知）
✅ 为 Day 49 的限流预留接入点

❌ 业务逻辑（不在网关里处理）
❌ Prompt 工程（不在网关里做）
❌ 输出解析（不在网关里做）
```

### Provider 切换方式对比

```python
# 没有网关：改 N 个文件
# weather_agent.py: from openai import OpenAI; client = OpenAI(key=DEEPSEEK_KEY, base=DEEPSEEK_URL)
# summary.py:       from openai import OpenAI; client = OpenAI(key=DEEPSEEK_KEY, base=DEEPSEEK_URL)
# translation.py:   from openai import OpenAI; client = OpenAI(key=DEEPSEEK_KEY, base=DEEPSEEK_URL)

# 有网关：改 1 行
# gateway/config.py: ACTIVE_PROVIDER = "openai"   ← 只改这里
```

### LiteLLM 核心模式

```python
# 统一调用格式（不管什么 Provider）
litellm.completion(model="provider/model-id", messages=[...])

# 内置回退
litellm.completion(model="primary", messages=[...], fallbacks=["backup"])

# 成本统计
litellm.completion_cost(completion_response=resp)
```

---

## 六、实践任务

- [ ] 新建 `gateway/` 目录，实现 `config.py`（Provider 配置）、`types.py`（统一请求/响应结构）、`gateway.py`（ModelGateway 类）
- [ ] 把现有的 `weather_agent.py` 改为通过 `gateway.complete()` 调用，验证功能正常
- [ ] 在 `gateway/config.py` 里把 `ACTIVE_PROVIDER` 从 `"deepseek"` 改为另一个你有 Key 的 Provider（如 moonshot），验证 `weather_agent.py` 无需任何改动即可运行
- [ ] 在 `ModelGateway.complete()` 里集成 Day 44 的结构化日志，跑 3 次请求，验证日志里的 `provider` 字段正确反映当前 Provider
- [ ] 安装 `litellm`，用 `litellm.completion(model="deepseek/deepseek-chat", messages=[...])` 复现同样的天气查询，对比和自研网关的代码量差异

**产出标准**：能演示"只改 `ACTIVE_PROVIDER` 配置，所有业务代码零改动、功能照常运行"；输出自研网关 vs LiteLLM 的优劣对比笔记（3–5 条关键差异）。

---

## 七、下一步预告

Day 49 进入**限流与配额（应用层实现）**：网关层已经是所有 LLM 调用的必经之路，今天在这里加一个限流中间件——当某个用户在固定时间窗口内的请求数超过配额时，网关直接拒绝并返回明确提示，而不是让请求透传到 Provider 导致成本爆炸。理解固定窗口、滑动窗口、令牌桶三种算法的差异，选其中一种实现，并测试超限行为。
