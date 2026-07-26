# Day 9：输出校验与异常处理

> 学习目标：把 Day 8 的"能校验类型"升级为"能在生产环境稳定运行"——建立完整的异常分类体系，区分可重试与不可重试错误，设计指数退避重试策略，并为空字段/部分缺失的抽取结果设计业务兜底策略，确保程序面对成千上万条真实数据、脏数据时不会崩溃
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 9
>
> 🧭 导航：[← Day 8 · 结构化输出](day08_structured_output.md) → [Day 10 · 做一个文本分类器](day10_text_classifier.md)

---

## 目录

- [一、异常处理的核心概念](#一异常处理的核心概念)
  - [1.1 为什么"能跑通"不等于"能上线"](#11-为什么能跑通不等于能上线)
  - [1.2 大模型调用链路中的异常分类](#12-大模型调用链路中的异常分类)
  - [1.3 异常处理的分层设计](#13-异常处理的分层设计)
- [二、JSON 解析失败与校验失败的分层处理](#二json-解析失败与校验失败的分层处理)
  - [2.1 json.JSONDecodeError：格式层面的失败](#21-jsonjsondecodeerror格式层面的失败)
  - [2.2 pydantic.ValidationError：字段层面的失败](#22-pydanticvalidationerror字段层面的失败)
  - [2.3 统一异常处理：一个包装函数分流两类错误](#23-统一异常处理一个包装函数分流两类错误)
- [三、重试机制设计](#三重试机制设计)
  - [3.1 立即重试 vs 指数退避](#31-立即重试-vs-指数退避)
  - [3.2 实现一个通用的指数退避重试装饰器](#32-实现一个通用的指数退避重试装饰器)
  - [3.3 可重试异常 vs 不可重试异常](#33-可重试异常-vs-不可重试异常)
- [四、空字段与部分缺失的业务兜底策略](#四空字段与部分缺失的业务兜底策略)
  - [4.1 三种兜底策略对比](#41-三种兜底策略对比)
  - [4.2 按字段重要性分级处理](#42-按字段重要性分级处理)
  - [4.3 结果三态：success / needs_review / failed](#43-结果三态success--needs_review--failed)
- [五、完整实现：健壮的信息抽取器](#五完整实现健壮的信息抽取器)
- [六、Day 9 知识速查](#六day-9-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、异常处理的核心概念

### 1.1 为什么"能跑通"不等于"能上线"

Day 8 的 `extract_structured` 已经能做类型校验和简单重试，但它是在"理想输入"下写的：网络稳定、API 一直可用、`max_retries` 次重试后要么成功要么直接 `raise`。放到真实场景里，这个假设会全面失效：

```
┌───────────────────────────────────────────────────────────────────┐
│              "能跑通"和"能上线"之间缺的东西                          │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Day 8 的假设：                                                     │
│  调用 API → 要么成功 → 要么重试几次后 raise，程序退出                │
│                                                                     │
│  真实场景会发生什么：                                                │
│  • 网络抖动 / 超时 —— 偶发，重试通常能恢复                            │
│  • 触发限流（429）—— 需要等待后重试，而不是立刻重试                   │
│  • API Key 失效（401）—— 重试没有意义，必须立刻停止并报警            │
│  • 模型输出格式污染 —— json.loads() 直接抛异常                       │
│  • 字段类型/必填项不对 —— Pydantic 抛 ValidationError                │
│  • 1000 条数据里有 5 条"怎么重试都失败" —— 不能让这 5 条拖垮整批任务   │
│                                                                     │
│  Day 9 要解决的核心问题：                                            │
│  "程序不能因为一条脏数据而崩溃"，且要能清楚地分辨——                   │
│  哪些错误该重试、哪些不该重试、哪些该标记为"待人工复核"                │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

### 1.2 大模型调用链路中的异常分类

一次完整的"抽取请求"要经过多个环节，每个环节都有自己特有的失败方式：

```
┌──────────────────────────────────────────────────────────────────────┐
│                  大模型调用链路的异常来源                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   发起 HTTP 请求                                                       │
│      │                                                                │
│      ├─ 网络异常：ConnectionError / Timeout          ← 可重试          │
│      │                                                                │
│      ▼                                                                │
│   服务端返回状态码                                                      │
│      │                                                                │
│      ├─ 401 未授权 / 403 无权限                       ← 不可重试        │
│      ├─ 404 模型名不存在                              ← 不可重试        │
│      ├─ 429 限流                                     ← 可重试（需等待） │
│      ├─ 500/503 服务端错误                            ← 可重试          │
│      ▼                                                                │
│   拿到 response.choices[0].message.content（一段字符串）                │
│      │                                                                │
│      ├─ json.JSONDecodeError（不是合法 JSON）          ← 可重试         │
│      ▼                                                                │
│   json.loads() 成功，得到 dict                                         │
│      │                                                                │
│      ├─ pydantic.ValidationError（类型错/缺必填项）     ← 视情况重试     │
│      ▼                                                                │
│   得到强类型对象                                                       │
│      │                                                                │
│      └─ 业务校验失败（字段值不合理，如年龄=200）        ← 不重试，走兜底  │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

**关键认知**：不是所有异常都该用同一种方式处理。"重试"只对**偶发性、可恢复**的错误有意义；对**确定性错误**（Key 错了、模型名错了）无脑重试只会浪费时间和 Token，还会掩盖真正的问题。

### 1.3 异常处理的分层设计

```
┌────────────────────────────────────────────────────────────────────────┐
│                     异常处理的三层职责划分                                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  第 1 层：捕获层（哪里可能抛异常，就在哪里 try/except）                   │
│  职责：把"可能失败的操作"用最小粒度的 try/except 包起来                  │
│                                                                          │
│  第 2 层：分类层（这个异常是什么类型，该不该重试）                        │
│  职责：把异常归到"可重试 / 不可重试 / 需人工介入"三类之一                  │
│                                                                          │
│  第 3 层：策略层（根据分类结果，决定下一步动作）                          │
│  职责：可重试 → 退避后重试；不可重试 → 立即终止并记录；                   │
│        需人工介入 → 记录到失败列表，不阻塞其他数据的处理                  │
│                                                                          │
│  三层职责分离的好处：新增一种异常类型时，只需要在"分类层"加一条判断，       │
│  不需要改动重试逻辑本身                                                  │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 二、JSON 解析失败与校验失败的分层处理

### 2.1 json.JSONDecodeError：格式层面的失败

即使加了 `response_format={"type": "json_object"}`，模型偶尔仍会输出被截断的 JSON（`max_tokens` 不够）或掺杂了非 JSON 字符：

```python
import json

raw = '{"name": "张伟", "age": 28'   # 被截断，缺少结尾的 }

try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"JSON 解析失败：{e.msg}，位置：行 {e.lineno} 列 {e.colno}")
    # JSON 解析失败：Expecting ',' delimiter，位置：行 1 列 28
```

`JSONDecodeError` 属于**格式层面**的失败——说明模型这次回复本身就不完整或不合法，通常**值得重试**（换一次生成大概率能拿到完整 JSON）。

### 2.2 pydantic.ValidationError：字段层面的失败

`json.loads()` 成功不代表数据可用。字段名错、类型错、必填项缺失，都是**语义层面**的失败：

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Optional

class ResumeInfo(BaseModel):
    name: str
    age: Optional[int] = Field(default=None)

try:
    ResumeInfo(**{"nmae": "张伟", "age": "二十八"})   # 字段名拼错 + 类型不可转换
except ValidationError as e:
    for err in e.errors():
        print(f"字段：{err['loc']}，错误：{err['type']}，信息：{err['msg']}")
    # 字段：('name',) 错误：missing 信息：Field required
    # 字段：('age',) 错误：int_parsing 信息：Input should be a valid integer...
```

`ValidationError.errors()` 返回结构化的错误列表，可以精确定位是"缺字段"还是"类型错"，这决定了后续要不要重试：

| 错误类型 | 典型场景 | 是否值得重试 |
|---------|---------|------------|
| `missing`（缺必填字段） | 模型漏输出了某个 key | 值得重试，模型下次可能补上 |
| `int_parsing` / `string_type` 等（类型不匹配） | `age` 输出了"二十八"这种无法转换的文本 | 值得重试 1-2 次，仍失败则走兜底 |
| `extra_forbidden`（多余字段，配合 `additionalProperties`） | 模型自作主张多加了字段 | 值得重试，通常是 Prompt 不够清晰导致 |

### 2.3 统一异常处理：一个包装函数分流两类错误

把"调用 API + 解析 + 校验"这一整条链路包一层，统一捕获两类异常，输出一个结构化的结果，而不是让异常直接向上抛：

```python
from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class ParseResult:
    ok: bool
    data: Optional[BaseModel] = None
    error_type: Optional[str] = None   # "json_error" / "validation_error"
    error_detail: Optional[str] = None


def parse_and_validate(raw: str, model_cls: type[BaseModel]) -> ParseResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return ParseResult(ok=False, error_type="json_error", error_detail=str(e))

    try:
        obj = model_cls(**data)
    except ValidationError as e:
        return ParseResult(ok=False, error_type="validation_error", error_detail=str(e))

    return ParseResult(ok=True, data=obj)
```

调用方只需要判断 `result.ok`，不需要关心内部具体抛了哪种异常——异常被**收敛**成了一个统一的返回值，这是"让程序不崩溃"的第一步。

---

## 三、重试机制设计

### 3.1 立即重试 vs 指数退避

```
┌───────────────────────────────────────────────────────────────────┐
│              立即重试 vs 指数退避（Exponential Backoff）             │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  立即重试：                                                          │
│  失败 → 0 秒后重试 → 失败 → 0 秒后重试 → 失败 → ...                  │
│  问题：如果是限流（429）导致的失败，立刻重试等于继续触发限流，          │
│        大批量任务并发时会形成"重试风暴"，让限流问题更严重              │
│                                                                     │
│  指数退避：                                                          │
│  失败 → 等 1 秒 → 失败 → 等 2 秒 → 失败 → 等 4 秒 → 失败 → 等 8 秒     │
│  等待时间随失败次数指数增长，给服务端恢复的时间，也降低了               │
│  "同一时刻大量请求同时重试"的概率                                     │
│                                                                     │
│  实践中通常再加一点随机抖动（jitter），避免多个客户端在同一时刻          │
│  集中重试：等待时间 = base * 2^attempt + random(0, 1)                │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

### 3.2 实现一个通用的指数退避重试装饰器

```python
import time
import random
import functools


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0,
                        retryable_exceptions: tuple = (Exception,)):
    """指数退避重试装饰器：失败后等待 base_delay * 2^attempt + 随机抖动 再重试"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        break
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"第 {attempt + 1} 次失败：{e}，{delay:.1f}s 后重试...")
                    time.sleep(delay)
            raise RuntimeError(f"重试 {max_retries} 次后仍失败：{last_error}")
        return wrapper
    return decorator


# 使用示例
import requests

@retry_with_backoff(max_retries=3, base_delay=1.0,
                     retryable_exceptions=(requests.exceptions.Timeout,
                                           requests.exceptions.ConnectionError))
def call_api(url, payload):
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()
```

`retryable_exceptions` 参数是关键——只对指定的异常类型重试，其他异常（比如 `ValueError` 说明是代码逻辑本身写错了）会直接向上抛出，不会被"重试"掩盖。

### 3.3 可重试异常 vs 不可重试异常

```python
class NonRetryableError(Exception):
    """明确不该重试的错误：重试了也不会成功，只会浪费时间和 Token"""
    pass


def classify_http_error(status_code: int) -> str:
    if status_code == 429:
        return "retryable"       # 限流，等待后重试大概率成功
    if status_code in (500, 502, 503, 504):
        return "retryable"       # 服务端临时故障
    if status_code in (401, 403):
        return "fatal"           # Key 无效/无权限，重试无意义
    if status_code == 404:
        return "fatal"           # 模型名或路径错误，重试无意义
    return "unknown"


def call_llm_safely(prompt: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            if status_code and classify_http_error(status_code) == "fatal":
                raise NonRetryableError(f"不可恢复错误（{status_code}），停止重试：{e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

| 错误场景 | 分类 | 处理策略 |
|---------|------|---------|
| 429 限流 | 可重试 | 指数退避后重试 |
| 500/502/503 服务端错误 | 可重试 | 指数退避后重试 |
| 网络超时/连接错误 | 可重试 | 短暂等待后重试 |
| 401/403（Key 错误） | **不可重试** | 立即终止整个任务，记录日志/告警，不浪费重试次数 |
| 404（模型名错误） | **不可重试** | 立即终止，这是配置问题，重试无法自愈 |
| JSON 解析失败 | 可重试 | 换一次生成大概率能拿到合法 JSON |
| Pydantic 校验失败 | 视情况重试 1-2 次 | 仍失败则不再重试，转入业务兜底 |

---

## 四、空字段与部分缺失的业务兜底策略

### 4.1 三种兜底策略对比

抽取 1000 条真实数据时，总会有一部分文本信息本来就不完整（比如简历里没写邮箱），这**不是错误**，需要区分"程序错误"和"数据本身信息不全"：

| 策略 | 做法 | 适用场景 | 风险 |
|------|------|---------|------|
| 默认值填充 | 缺失字段直接填 `null` / 空字符串 / 0 | 该字段本来就允许为空，下游能处理 null | 若下游误把 null 当作"0"或"未设置"会产生歧义 |
| 标记待人工复核 | 记录到 `needs_review` 列表，附带原因 | 缺失的是重要字段（如身份证号），需要人工确认 | 增加人工成本，不能大规模使用 |
| 直接丢弃记录 | 该条数据完全跳过，不写入结果 | 抽取结果必须字段齐全才有意义（如入库主键缺失） | 会丢失部分可用信息，需要监控丢弃比例 |

**核心原则**：不要用同一种策略处理所有缺失字段，应该按字段的重要性分级。

### 4.2 按字段重要性分级处理

```python
from enum import Enum

class FieldLevel(Enum):
    REQUIRED = "required"   # 缺失即整条记录不可用
    IMPORTANT = "important" # 缺失可用，但要标记复核
    OPTIONAL = "optional"   # 缺失属于正常情况，默认值即可


FIELD_LEVELS = {
    "name": FieldLevel.REQUIRED,
    "phone": FieldLevel.IMPORTANT,
    "email": FieldLevel.OPTIONAL,
    "skills": FieldLevel.OPTIONAL,
}


def assess_completeness(data: dict, field_levels: dict) -> str:
    """根据缺失字段的等级，判断这条记录该归为哪一类"""
    missing_required = [k for k, lv in field_levels.items()
                         if lv == FieldLevel.REQUIRED and not data.get(k)]
    missing_important = [k for k, lv in field_levels.items()
                          if lv == FieldLevel.IMPORTANT and not data.get(k)]

    if missing_required:
        return "failed"          # 关键字段缺失，记录不可用
    if missing_important:
        return "needs_review"    # 重要字段缺失，但记录仍有部分价值
    return "success"             # 只是可选字段缺失，属于正常情况
```

### 4.3 结果三态：success / needs_review / failed

把"抽取成功与否"从二元判断（成功/失败）升级为三态判断，是让批量任务更贴近真实业务的关键改进：

```
┌──────────────────────────────────────────────────────────────────┐
│                     抽取结果的三态划分                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│   success        —— 所有 required/important 字段齐全，直接入库      │
│        │                                                          │
│   needs_review    —— important 字段缺失，先入库但打上待复核标记，     │
│                      人工可以补录，不阻塞主流程                       │
│        │                                                          │
│   failed          —— required 字段缺失，或重试后仍无法解析/校验，     │
│                      单独落盘，不进入正常数据流，避免污染下游           │
│                                                                    │
│   三态的意义：批量任务的"成功率"不再是非黑即白，而是能清楚回答          │
│   "有多少可以直接用、多少需要人工看一眼、多少彻底失败"                 │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 五、完整实现：健壮的信息抽取器

把前面四节的能力（分类异常、指数退避重试、字段分级、结果三态）整合进一个可直接复用的抽取器：

```python
import os
import json
import time
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)


class FieldLevel(Enum):
    REQUIRED = "required"
    IMPORTANT = "important"
    OPTIONAL = "optional"


class NonRetryableError(Exception):
    pass


@dataclass
class ExtractionRecord:
    status: str                       # "success" / "needs_review" / "failed"
    data: Optional[dict] = None
    reason: Optional[str] = None
    retries_used: int = 0


def call_llm_with_backoff(prompt: str, max_retries: int = 3, base_delay: float = 1.0) -> str:
    """封装 API 调用：区分可重试/不可重试错误，指数退避"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            if status_code in (401, 403, 404):
                raise NonRetryableError(f"不可恢复错误（{status_code}）：{e}")
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
    raise RuntimeError("不应到达此处")


def parse_and_validate(raw: str, model_cls: type[BaseModel]):
    """把 JSON 解析和 Pydantic 校验的异常收敛成统一返回值"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"json_error: {e}"

    try:
        obj = model_cls(**data)
    except ValidationError as e:
        return None, f"validation_error: {e.errors()}"

    return obj, None


def assess_completeness(data: dict, field_levels: dict) -> tuple[str, Optional[str]]:
    """按字段等级判断结果应归入 success / needs_review / failed"""
    missing_required = [k for k, lv in field_levels.items()
                         if lv == FieldLevel.REQUIRED and not data.get(k)]
    missing_important = [k for k, lv in field_levels.items()
                          if lv == FieldLevel.IMPORTANT and not data.get(k)]

    if missing_required:
        return "failed", f"缺失必填字段：{missing_required}"
    if missing_important:
        return "needs_review", f"缺失重要字段：{missing_important}"
    return "success", None


def extract_robust(text: str, model_cls: type[BaseModel], field_levels: dict,
                    build_prompt_fn, max_parse_retries: int = 2) -> ExtractionRecord:
    prompt = build_prompt_fn(text, model_cls)

    for attempt in range(max_parse_retries):
        try:
            raw = call_llm_with_backoff(prompt)
        except NonRetryableError as e:
            return ExtractionRecord(status="failed", reason=str(e), retries_used=attempt)

        obj, error = parse_and_validate(raw, model_cls)
        if obj is not None:
            status, reason = assess_completeness(obj.model_dump(), field_levels)
            return ExtractionRecord(status=status, data=obj.model_dump(),
                                     reason=reason, retries_used=attempt)
        # 解析/校验失败，进入下一次重试
        last_error = error

    return ExtractionRecord(status="failed", reason=f"解析/校验重试耗尽：{last_error}",
                             retries_used=max_parse_retries)


def batch_extract_robust(texts: list[str], model_cls: type[BaseModel],
                          field_levels: dict, build_prompt_fn) -> dict:
    buckets = {"success": [], "needs_review": [], "failed": []}
    for i, text in enumerate(texts):
        record = extract_robust(text, model_cls, field_levels, build_prompt_fn)
        buckets[record.status].append({"index": i, "text": text, "record": record})
    return buckets


if __name__ == "__main__":
    from typing import Optional as Opt

    class ResumeInfo(BaseModel):
        name: str
        phone: Opt[str] = None
        email: Opt[str] = None
        skills: list[str] = []

    def build_prompt(text: str, model_cls: type[BaseModel]) -> str:
        schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
        return (f"从以下文本抽取信息，严格按 Schema 输出 JSON：\n{schema}\n\n"
                f"找不到的字段用 null。\n\n文本：\n{text}")

    field_levels = {
        "name": FieldLevel.REQUIRED,
        "phone": FieldLevel.IMPORTANT,
        "email": FieldLevel.OPTIONAL,
        "skills": FieldLevel.OPTIONAL,
    }

    texts = [
        "张伟，13800001111，擅长 Python 和 Go，邮箱 wei@example.com",
        "李明，会 Vue，邮箱 li@example.com",       # 缺电话 -> needs_review
        "王芳",                                    # 只有姓名，其余全缺，仍算 success（都不是 required）
    ]

    report = batch_extract_robust(texts, ResumeInfo, field_levels, build_prompt)
    for status, records in report.items():
        print(f"{status}: {len(records)} 条")
```

```
运行输出示例：
success: 2 条
needs_review: 1 条
failed: 0 条
```

**这个实现体现的核心设计**：

1. `call_llm_with_backoff` 只负责"调用 + 网络层重试"，遇到不可恢复错误立刻抛出，不浪费重试次数
2. `parse_and_validate` 把两类解析异常收敛成统一的 `(obj, error)` 返回值，调用方不需要写多层 `try/except`
3. `assess_completeness` 把"数据不完整"和"程序出错"彻底分开处理，避免把正常的业务缺失当成异常
4. `batch_extract_robust` 用三个桶（`success` / `needs_review` / `failed`）替代简单的"成功/失败"二分，让批量任务的结果可观测、可复盘

---

## 六、Day 9 知识速查

### 异常分类速查

| 异常/状态码 | 层面 | 是否可重试 |
|------------|------|----------|
| `ConnectionError` / `Timeout` | 网络层 | 是 |
| 429 | HTTP 层（限流） | 是（需退避） |
| 500/502/503 | HTTP 层（服务端） | 是 |
| 401/403/404 | HTTP 层（配置错误） | 否，立即终止 |
| `json.JSONDecodeError` | 解析层 | 是 |
| `pydantic.ValidationError` | 校验层 | 视情况，1-2 次后转兜底 |

### 指数退避公式

```
delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
```

### 结果三态速查

| 状态 | 触发条件 | 后续动作 |
|------|---------|---------|
| `success` | 必填/重要字段齐全 | 直接入库/下游消费 |
| `needs_review` | 重要字段缺失 | 入库但打标记，等待人工复核 |
| `failed` | 必填字段缺失 或 重试耗尽仍无法解析/校验 | 单独落盘，不进入主流程 |

### 最小模板

```
调用 API（区分可/不可重试异常，指数退避）
  → json.loads()（失败可重试）
  → Pydantic 校验（失败可重试 1-2 次）
  → 按字段等级判断 success/needs_review/failed
  → 分桶落盘，批量任务不因单条数据失败而中断
```

---

## 七、实践任务

- [ ] 给 Day 8 的抽取脚本加上区分"可重试/不可重试"异常的逻辑
- [ ] 实现一个通用的指数退避重试装饰器，并用人为制造超时/连接错误验证退避时间确实在增长
- [ ] 定义至少一组字段等级（`REQUIRED` / `IMPORTANT` / `OPTIONAL`），实现 `assess_completeness`
- [ ] 用一批（至少 8 条，包含完整数据、部分缺失数据、故意构造的脏数据）跑通 `batch_extract_robust`，统计三态分布
- [ ] 故意让程序遇到一次"不可恢复错误"（如临时改错 API Key），验证程序会立即终止而不是无意义地重试

**产出标准**：

- 程序在任意一条输入异常（网络错误、格式错误、字段缺失）时都不会直接崩溃退出
- 有明确的日志能看出：这条数据重试了几次、最终落在哪个状态桶

---

## 八、下一步预告

**Day 10：做一个文本分类器**

Day 9 解决的是"抽取结果如何稳妥落地"，Day 10 会转向一个新的任务类型——**分类**：

- 分类任务的 Prompt 设计和信息抽取有何不同
- 如何用 `enum` 约束把标签集合锁死在固定类别里
- 分类结果的置信度问题：模型给出的类别本身是否可靠，如何验证

核心问题：把"用户反馈"这类自由文本，稳定地映射到"咨询/投诉/建议/故障"这样的固定标签集合，背后需要哪些和抽取任务不一样的设计考虑。
