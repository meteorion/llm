# Day 28：补工程细节

> 学习目标：在 Day 27 完整项目的基础上，补全四项基础工程能力——异常处理、日志、配置验证、输出校验，让项目从"能跑"升级到"稳定跑"，具备基础可维护性
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 28
>
> 🧭 导航：[← Day 27 · 整合成完整作品](day27_complete_project.md) [→ Day 29 · 测试和优化](day29_testing_and_optimization.md)

---

## 目录

- [一、工程细节的价值](#一工程细节的价值)
  - [1.1 "能跑"和"稳定跑"的差距](#11-能跑和稳定跑的差距)
  - [1.2 四件套：异常处理 / 日志 / 配置验证 / 输出校验](#12-四件套异常处理--日志--配置验证--输出校验)
- [二、异常处理：分层设计](#二异常处理分层设计)
  - [2.1 LLM 项目的异常分类](#21-llm-项目的异常分类)
  - [2.2 工具层异常处理（返回 dict，不抛异常）](#22-工具层异常处理返回-dict不抛异常)
  - [2.3 工作流层异常处理（捕获 API 错误，graceful degradation）](#23-工作流层异常处理捕获-api-错误graceful-degradation)
  - [2.4 UI 层异常处理（用户友好的错误提示）](#24-ui-层异常处理用户友好的错误提示)
- [三、日志：三类关键信息](#三日志三类关键信息)
  - [3.1 启动日志：验证配置已就绪](#31-启动日志验证配置已就绪)
  - [3.2 请求日志：耗时与 Token 消耗](#32-请求日志耗时与-token-消耗)
  - [3.3 错误日志：异常链路与上下文](#33-错误日志异常链路与上下文)
  - [3.4 日志配置的正确初始化方式](#34-日志配置的正确初始化方式)
- [四、配置验证：Fail-Fast 原则](#四配置验证fail-fast-原则)
  - [4.1 什么是 fail-fast](#41-什么是-fail-fast)
  - [4.2 启动时配置验证实现](#42-启动时配置验证实现)
  - [4.3 不同类型的配置项验证策略](#43-不同类型的配置项验证策略)
- [五、输出校验：防止脏数据传播](#五输出校验防止脏数据传播)
  - [5.1 工具返回值校验](#51-工具返回值校验)
  - [5.2 LLM 输出格式校验](#52-llm-输出格式校验)
  - [5.3 工作流整体输出校验](#53-工作流整体输出校验)
- [六、完整工程化改造示例](#六完整工程化改造示例)
- [七、Day 28 知识速查](#七day-28-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、工程细节的价值

### 1.1 "能跑"和"稳定跑"的差距

Day 27 的项目"能跑"，但面对以下情况就会出问题：

```
测试场景 1：API Key 填错了
  能跑但未做配置验证：程序启动成功，用户发第一条消息时才崩溃
  做了 fail-fast：程序启动时立即报错，告诉用户哪里填错了

测试场景 2：网络抖动，API 超时
  能跑但未做异常处理：Gradio 界面显示红色报错堆栈，用户不理解
  做了异常处理：界面显示"网络暂时不稳定，请稍后再试"

测试场景 3：用户输入了奇怪的问题导致工具参数解析失败
  能跑但未做输出校验：工具崩溃，整个工作流中断
  做了输出校验：捕获异常，返回 {"error": True, "message": "..."}，模型解释给用户

测试场景 4：线上运行出了问题，需要排查
  能跑但没有日志：只能加 print 重新运行，猜测原因
  有日志：翻日志文件，直接看出是哪次请求、哪个工具出了什么问题
```

### 1.2 四件套：异常处理 / 日志 / 配置验证 / 输出校验

```
四件套的职责分工：

  配置验证（fail-fast）
  ─────────────────────
  时机：程序启动时
  目的：第一时间发现配置错误，不让错误延迟到运行时

  异常处理（分层 graceful degradation）
  ──────────────────────────────────────
  时机：运行时各层
  目的：不让局部错误传播成全局崩溃

  输出校验（防止脏数据）
  ────────────────────────
  时机：工具执行后、LLM 回答后
  目的：不让格式错误的数据传入下一层

  日志（可观测）
  ─────────────────────
  时机：贯穿全生命周期
  目的：问题排查和性能监控的基础
```

---

## 二、异常处理：分层设计

### 2.1 LLM 项目的异常分类

```
┌─────────────────────────────────────────────────────┐
│                LLM 项目异常分类                       │
├─────────────────┬─────────────┬─────────────────────┤
│ 异常类型         │ 典型原因     │ 处理策略            │
├─────────────────┼─────────────┼─────────────────────┤
│ 网络/API 错误   │ 超时、限流   │ 重试 + 指数退避      │
│ 认证错误        │ Key 无效    │ fail-fast，启动时检查 │
│ 工具参数错误    │ 模型填错参数 │ 返回 error dict     │
│ 工具执行错误    │ 外部 API 挂  │ 返回 error dict     │
│ 输出格式错误    │ 模型未按格式 │ 重试或降级回答       │
│ 上下文超限      │ 对话太长    │ 截断历史             │
└─────────────────┴─────────────┴─────────────────────┘
```

**分层原则**：每层只处理自己能解决的异常，不能解决的往上抛或降级。

### 2.2 工具层异常处理（返回 dict，不抛异常）

工具函数遇到错误时，**返回错误 dict** 而非抛异常，让模型能看到错误信息并生成友好提示：

```python
def get_weather(city: str, unit: str = "celsius") -> dict:
    # 参数验证
    if not city or not city.strip():
        return {"error": True, "message": "城市名称不能为空"}
    
    city = city.strip()
    if city not in _MOCK:
        return {
            "error": True,
            "message": f"暂无 '{city}' 的天气数据，支持：{'、'.join(_MOCK)}"
        }
    
    # 正常流程中的异常也要捕获（比如真实 API 调用时）
    try:
        data = fetch_from_api(city)   # 假设有真实 API
    except TimeoutError:
        return {"error": True, "message": f"获取 '{city}' 天气超时，请稍后重试"}
    except Exception as e:
        return {"error": True, "message": f"查询失败：{str(e)}"}
    
    return {..., "summary": "..."}
```

**为什么不抛异常**：工具的调用方是多步工作流的 `dispatch` 函数，如果工具抛异常，工作流会中断；返回 `{"error": True, ...}` 让模型继续运行，模型能基于错误信息生成"城市名有误，您是想查哪个城市？"这样的自然语言回复。

### 2.3 工作流层异常处理（捕获 API 错误，graceful degradation）

```python
import time
from openai import APITimeoutError, APIConnectionError, RateLimitError, AuthenticationError

def run(user_input: str, messages: list) -> tuple[WorkflowResult, list]:
    wf = WorkflowResult()
    messages = messages + [{"role": "user", "content": user_input}]
    
    for attempt in range(CFG.max_iterations):
        try:
            msg = get_client().chat.completions.create(
                model=CFG.model, messages=messages,
                tools=ALL_TOOLS, tool_choice="auto", temperature=CFG.temperature,
            ).choices[0].message
        except AuthenticationError:
            # 认证错误不应该重试，直接返回用户友好提示
            wf.final_answer = "API 密钥验证失败，请检查配置。"
            wf.terminated_by = "auth_error"
            return wf, messages
        except RateLimitError:
            # 限流：稍等后重试（最多 2 次）
            logger.warning("API 限流，等待 5 秒后重试...")
            time.sleep(5)
            continue
        except (APITimeoutError, APIConnectionError) as e:
            logger.error("API 连接失败：%s", e)
            wf.final_answer = "网络暂时不稳定，请稍后再试。"
            wf.terminated_by = "connection_error"
            return wf, messages
        
        if not msg.tool_calls:
            wf.final_answer = msg.content
            messages.append({"role": "assistant", "content": msg.content})
            break
        
        # 工具执行（dispatch 已经在内部做了异常处理）
        messages.append(msg)
        for tc in msg.tool_calls:
            result = dispatch(tc.function.name, json.loads(tc.function.arguments))
            wf.steps.append(ToolStep(name=tc.function.name, result=result))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    
    return wf, messages
```

### 2.4 UI 层异常处理（用户友好的错误提示）

Gradio 界面里，用 `try/except` 包裹业务调用，把技术错误转成友好文案：

```python
def respond(user_msg, chat_history, messages_state, chain_state):
    try:
        result, messages_state = run(user_msg, messages_state or [system_msg])
        answer = result.final_answer
    except Exception as e:
        # 兜底：所有未预期的异常
        logger.exception("未预期的异常：%s", e)
        answer = "抱歉，处理您的请求时遇到了问题，请稍后重试。"
    
    chat_history.append({"role": "user", "content": user_msg})
    chat_history.append({"role": "assistant", "content": answer})
    return "", chat_history, messages_state, chain_state
```

---

## 三、日志：三类关键信息

### 3.1 启动日志：验证配置已就绪

启动时打印关键配置信息（不打印 key 本身），方便排查环境问题：

```python
import logging

logger = logging.getLogger(__name__)

def log_startup(cfg):
    logger.info("=" * 50)
    logger.info("个人助理 Demo 启动中")
    logger.info("模型：%s", cfg.model)
    logger.info("API Base URL：%s", cfg.base_url)
    logger.info("API Key：%s***（已配置）", cfg.api_key[:8] if cfg.api_key else "未配置")
    logger.info("最大迭代次数：%d", cfg.max_iterations)
    logger.info("=" * 50)
```

**注意**：API Key 绝对不能整体打印到日志，只打印前几位作为验证标识。

### 3.2 请求日志：耗时与 Token 消耗

每次 API 调用都记录耗时和 Token 消耗，方便分析性能瓶颈和成本：

```python
import time

def timed_api_call(client, **kwargs):
    t = time.monotonic()
    response = client.chat.completions.create(**kwargs)
    elapsed = time.monotonic() - t
    
    usage = response.usage
    logger.info(
        "API 调用 %.2fs | input_tokens=%d output_tokens=%d total=%d",
        elapsed, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
    )
    return response
```

**为什么要记录 Token**：
- 诊断某个问题是否导致了异常高的 Token 消耗（比如历史消息没有截断）
- 估算月账单，发现成本异常时能追溯到具体的请求

### 3.3 错误日志：异常链路与上下文

错误日志要记录**足够的上下文**，让排查时不需要重现问题：

```python
def dispatch(name: str, args: dict) -> dict:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        logger.error("工具调用失败：未知工具 '%s'，可用工具：%s",
                     name, list(TOOL_REGISTRY.keys()))
        return {"error": True, "message": f"未知工具：{name}"}
    
    try:
        result = fn(**args)
        if result.get("error"):
            logger.warning("工具 '%s' 返回错误：%s", name, result.get("message"))
        return result
    except TypeError as e:
        logger.error("工具 '%s' 参数错误：%s，收到参数：%s", name, e, args)
        return {"error": True, "message": f"工具参数错误：{e}"}
    except Exception as e:
        logger.exception("工具 '%s' 执行异常（args=%s）", name, args)
        return {"error": True, "message": f"工具执行失败：{type(e).__name__}"}
```

`logger.exception()` 会自动附上完整的 traceback，不需要手动 `traceback.format_exc()`。

### 3.4 日志配置的正确初始化方式

```python
import logging
import sys

def setup_logging(level: str = "INFO", log_file: str = None):
    """在主入口调用一次，子模块用 logging.getLogger(__name__) 继承配置。"""
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    # 降低 httpx（openai 底层）的日志级别，避免刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
```

**关键规则**：
- `logging.basicConfig` 只在**主入口文件**调用一次（`app.py` 或 `__main__.py`）
- 子模块（`core/workflow.py`、`tools/weather.py`）使用 `logger = logging.getLogger(__name__)`，不调用 `basicConfig`
- 子模块的 logger 自动继承主入口的配置

---

## 四、配置验证：Fail-Fast 原则

### 4.1 什么是 fail-fast

**Fail-fast** 指系统在检测到错误时立即停止执行，而不是等到错误扩散后再崩溃：

```
反例（fail-slow）：
  程序启动 → 用户交互 → 发第一条消息 → API Key 无效 → 报错
  问题：用户等了很久，才知道配置有问题；错误发生在深处，难以定位

正例（fail-fast）：
  程序启动 → 立即检查配置 → API Key 无效 → 立即报错并退出
  好处：5 秒内就知道配置有问题，错误位置明确，修复容易
```

**LLM 项目中 fail-fast 的价值特别高**，因为 API 调用有成本——如果错误配置在几十次请求后才暴露，可能已经损失了一些费用。

### 4.2 启动时配置验证实现

```python
import os
import sys
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    model: str
    max_iterations: int
    temperature: float

def load_config() -> Config:
    """加载并验证配置，任何错误都立即抛出 ValueError。"""
    errors = []
    
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        errors.append("DEEPSEEK_API_KEY 未设置（在 .env 文件中配置）")
    elif len(api_key) < 10:
        errors.append("DEEPSEEK_API_KEY 格式异常（长度过短，请检查是否完整复制）")
    
    max_iter_str = os.getenv("MAX_ITERATIONS", "6")
    try:
        max_iter = int(max_iter_str)
        if max_iter < 1 or max_iter > 20:
            errors.append(f"MAX_ITERATIONS 应在 1-20 之间，当前值：{max_iter}")
    except ValueError:
        errors.append(f"MAX_ITERATIONS 必须是整数，当前值：{max_iter_str!r}")
    
    if errors:
        print("❌ 配置验证失败：")
        for e in errors:
            print(f"   - {e}")
        print("请检查 .env 文件（参考 .env.example）")
        sys.exit(1)   # fail-fast：立即退出
    
    return Config(
        api_key=api_key,
        base_url=os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
        model=os.getenv("MODEL", "deepseek-chat"),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "6")),
        temperature=float(os.getenv("TEMPERATURE", "0.0")),
    )

# 模块级别加载，import 时即验证
CFG = load_config()
```

### 4.3 不同类型的配置项验证策略

| 配置项类型 | 验证方式 | 示例 |
|----------|---------|------|
| 必填字符串（API Key） | 非空检查 + 格式检查 | `len(key) > 10` |
| 整数范围 | `int()` 转换 + 范围检查 | `1 ≤ max_iter ≤ 20` |
| 浮点数 | `float()` 转换 + 范围检查 | `0.0 ≤ temperature ≤ 2.0` |
| 枚举值 | `in` 检查 | `model in SUPPORTED_MODELS` |
| 文件路径 | `os.path.exists()` | 知识库文件必须存在 |
| URL | 前缀检查 + 简单格式验证 | `base_url.startswith("https://")` |

---

## 五、输出校验：防止脏数据传播

### 5.1 工具返回值校验

工具返回 dict 后，工作流接收前可以做轻量校验：

```python
def validate_tool_result(name: str, result: dict) -> dict:
    """检查工具返回结果是否合法，不合法则返回标准化的错误 dict。"""
    if not isinstance(result, dict):
        logger.error("工具 '%s' 返回了非 dict 类型：%s", name, type(result))
        return {"error": True, "message": f"工具返回格式错误"}
    
    if result.get("error"):
        return result   # 已经是合法的错误 dict，直接透传
    
    # 校验正常返回时的必要字段
    REQUIRED_FIELDS = {
        "get_weather": ["city", "temperature", "summary"],
        "get_exchange_rate": ["from", "to", "rate", "summary"],
    }
    required = REQUIRED_FIELDS.get(name, [])
    missing = [f for f in required if f not in result]
    if missing:
        logger.warning("工具 '%s' 返回缺少字段：%s", name, missing)
        # 不是致命错误，但记录警告；模型可能生成不完整的回答
    
    return result
```

### 5.2 LLM 输出格式校验

当工作流需要模型返回结构化 JSON 时（非对话场景），用 Pydantic 校验：

```python
from pydantic import BaseModel, ValidationError

class TravelAdvice(BaseModel):
    destination: str
    weather_suitable: bool
    budget_sufficient: bool | None = None
    recommendation: str

def get_structured_advice(context: str) -> TravelAdvice:
    response = client.chat.completions.create(
        model=CFG.model,
        messages=[
            {"role": "system", "content": "请以 JSON 格式回复..."},
            {"role": "user", "content": context},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    
    raw = response.choices[0].message.content
    try:
        return TravelAdvice.model_validate_json(raw)
    except (ValidationError, ValueError) as e:
        logger.error("模型输出格式错误：%s，原始输出：%s", e, raw[:200])
        # 降级：返回默认值而不是崩溃
        return TravelAdvice(
            destination="未知",
            weather_suitable=False,
            recommendation="无法解析模型回答，请重试。"
        )
```

### 5.3 工作流整体输出校验

在工作流结束后，对 `WorkflowResult` 做简单健全性检查：

```python
def validate_workflow_result(result: WorkflowResult) -> WorkflowResult:
    if not result.final_answer or not result.final_answer.strip():
        logger.warning("工作流返回了空回答，terminated_by=%s", result.terminated_by)
        result.final_answer = "抱歉，我没有生成有效回答，请重新提问。"
    
    if len(result.final_answer) < 5:
        logger.warning("工作流回答过短：%r", result.final_answer)
    
    return result
```

---

## 六、完整工程化改造示例

把四件套整合到 Day 27 项目的关键文件里：

**`core/config.py`**（新增：配置验证 + 启动日志）：

```python
import os, sys, logging
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    model: str
    max_iterations: int
    temperature: float

def _load() -> Config:
    errors = []
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        errors.append("DEEPSEEK_API_KEY 未设置")
    if errors:
        print("❌ 配置错误：" + "；".join(errors))
        print("请参考 .env.example 配置环境变量")
        sys.exit(1)
    return Config(
        api_key=key,
        base_url=os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
        model=os.getenv("MODEL", "deepseek-chat"),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "6")),
        temperature=float(os.getenv("TEMPERATURE", "0.0")),
    )

CFG = _load()
```

**`core/workflow.py`**（新增：API 异常处理 + 请求日志 + 输出校验）：

```python
import json, logging, time
from dataclasses import dataclass, field
from openai import APITimeoutError, APIConnectionError, RateLimitError, AuthenticationError
from .config import CFG
from .client import get_client
from tools import ALL_TOOLS, dispatch

logger = logging.getLogger(__name__)

@dataclass
class ToolStep:
    name: str
    args: dict
    result: dict
    elapsed: float = 0.0

@dataclass
class WorkflowResult:
    final_answer: str = ""
    steps: list = field(default_factory=list)
    terminated_by: str = "model_done"


def _call_api(messages: list, use_tools: bool = True):
    """API 调用 + 耗时日志 + 重试（限流时）。"""
    kwargs = dict(model=CFG.model, messages=messages, temperature=CFG.temperature)
    if use_tools:
        kwargs.update(tools=ALL_TOOLS, tool_choice="auto")
    
    for attempt in range(3):
        try:
            t = time.monotonic()
            resp = get_client().chat.completions.create(**kwargs)
            elapsed = time.monotonic() - t
            u = resp.usage
            logger.info("API 调用 %.2fs | in=%d out=%d total=%d tokens",
                        elapsed, u.prompt_tokens, u.completion_tokens, u.total_tokens)
            return resp
        except RateLimitError:
            wait = 5 * (attempt + 1)
            logger.warning("API 限流，%.1fs 后重试（第 %d 次）", wait, attempt + 1)
            time.sleep(wait)
        except (APITimeoutError, APIConnectionError) as e:
            raise ConnectionError(f"网络连接失败：{e}") from e
        except AuthenticationError as e:
            raise ValueError(f"API Key 验证失败：{e}") from e
    
    raise RuntimeError("API 限流重试 3 次仍失败")


def run(user_input: str, messages: list) -> tuple[WorkflowResult, list]:
    wf = WorkflowResult()
    messages = messages + [{"role": "user", "content": user_input}]
    
    try:
        for _ in range(CFG.max_iterations):
            resp = _call_api(messages)
            msg = resp.choices[0].message
            
            if not msg.tool_calls:
                wf.final_answer = msg.content or ""
                messages.append({"role": "assistant", "content": wf.final_answer})
                break
            
            messages.append(msg)
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                t = time.monotonic()
                result = dispatch(name, args)
                wf.steps.append(ToolStep(name=name, args=args, result=result,
                                          elapsed=time.monotonic() - t))
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
        else:
            wf.terminated_by = "max_iterations"
            resp = _call_api(messages, use_tools=False)
            wf.final_answer = resp.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": wf.final_answer})
    
    except (ConnectionError, ValueError, RuntimeError) as e:
        logger.error("工作流异常：%s", e)
        wf.final_answer = str(e)
        wf.terminated_by = "error"
    except Exception as e:
        logger.exception("工作流未预期异常")
        wf.final_answer = "处理时遇到未知错误，请稍后重试。"
        wf.terminated_by = "unexpected_error"
    
    # 输出校验
    if not wf.final_answer.strip():
        wf.final_answer = "未能生成回答，请重新提问。"
    
    return wf, messages
```

---

## 七、Day 28 知识速查

### 工程四件套速查

| 件 | 位置 | 关键代码 |
|----|------|---------|
| 配置验证（fail-fast） | `core/config.py` 模块加载时 | `if not key: sys.exit(1)` |
| 工具层异常处理 | `tools/*.py` | `try/except → return {"error": True}` |
| 工作流层异常处理 | `core/workflow.py` | `except APITimeoutError / RateLimitError` |
| UI 层兜底 | `app.py` respond 函数 | `except Exception: return "请稍后重试"` |
| 日志初始化 | `app.py` 主入口 | `logging.basicConfig(...)` 调用一次 |
| 子模块日志 | 所有子模块 | `logger = logging.getLogger(__name__)` |
| Token 记录 | `_call_api` 函数 | `response.usage.total_tokens` |
| 输出校验 | `workflow.run` 末尾 | `if not wf.final_answer.strip(): ...` |

### 异常处理分层原则

```
工具层（tools/）：
  → 只返回 {"error": True, "message": "..."}, 不抛异常

工作流层（core/workflow.py）：
  → 捕获 API 异常（超时、限流、认证）
  → 可重试的用 for 循环重试，不可重试的直接返回错误文案

UI 层（app.py）：
  → 用 try/except Exception 兜底所有未预期异常
  → 把技术错误转成用户友好文案，不让 traceback 显示给用户
```

---

## 八、实践任务

- [ ] 在 `core/config.py` 加入 `_load()` 函数，测试：临时删除 `.env` 里的 API Key，确认程序启动时报友好错误并退出
- [ ] 在 `core/workflow.py` 的 `_call_api` 加入 Token 日志，运行一次对话，确认日志里能看到 `in=xxx out=xxx total=xxx tokens`
- [ ] 测试工具错误路径：在 `get_weather` 里传一个不支持的城市，确认模型基于错误 dict 给出了友好回复（而不是程序崩溃）
- [ ] 测试限流重试：把 API Key 临时改为一个会触发限流的值，或在代码里 mock `RateLimitError`，确认重试逻辑正常工作
- [ ] 在 `app.py` 的 `respond` 函数加入 `try/except`，测试：在工作流里故意抛一个 `RuntimeError`，确认 UI 显示友好提示而非红色堆栈
- [ ] 给日志加文件输出：`setup_logging(log_file="app.log")`，运行 5 次对话后查看 `app.log`，确认能追溯每次调用的耗时和 Token

**产出标准**：

- 程序启动时若 API Key 未配置，5 秒内报错退出并给出明确提示
- 运行日志里能看到每次 API 调用的耗时和 Token 消耗
- 工具错误时程序不崩溃，用户看到的是自然语言提示而非 Python traceback

---

## 九、下一步预告

**Day 29：测试和优化**

Day 28 完成了工程化加固，Day 29 进入**质量验证阶段**——系统性地测试项目，找出弱点并优化：

- **输出稳定性测试**：同一问题运行 5 次，回答是否一致？（temperature=0 应该稳定）
- **工具触发准确性**：列 20 个测试问题，统计工具触发率——该触发的都触发了吗？不该触发的触发了吗？
- **误触发案例分析**：找到触发边界不准的问题，修改 description 或 System Prompt 提高精度
- **Token 成本分析**：一轮完整对话消耗多少 Token？多步工作流的 Token 增长是否在预期范围内？
- **端到端压力测试**：连续运行 20 个问题，有没有内存泄漏或状态污染（历史消息是否正确隔离）？

Day 29 的产出：一份测试报告（触发准确率、Token 消耗、稳定性），以及基于测试结果的改进清单。
