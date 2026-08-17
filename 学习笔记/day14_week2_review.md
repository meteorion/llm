# Day 14：第 2 周复盘

> 学习目标：系统梳理 Day 8–13 的工程基本功闭环，深度回答三个复盘问题（稳定 Prompt 的标准、输出校验的工程本质、日志与配置的必要性），整理出一份第 2 周可复用的 Prompt 模板库
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 14
>
> 🧭 导航：[← Day 13 · 配置管理和日志](day13_config_and_logging.md) [→ Day 15 · RAG 基本原理](day15_rag_from_scratch.md)

---

## 目录

- [一、第 2 周全景回顾](#一第-2-周全景回顾)
  - [1.1 Day 8–13 知识地图](#11-day-813-知识地图)
  - [1.2 本周六个主题的逻辑链](#12-本周六个主题的逻辑链)
- [二、深度复盘三大问题](#二深度复盘三大问题)
  - [2.1 什么样的 Prompt 更稳定](#21-什么样的-prompt-更稳定)
  - [2.2 为什么输出校验比"提示模型小心点"更可靠](#22-为什么输出校验比提示模型小心点更可靠)
  - [2.3 为什么 Demo 要尽早引入日志和配置](#23-为什么-demo-要尽早引入日志和配置)
- [三、可复用 Prompt 模板库](#三可复用-prompt-模板库)
  - [3.1 结构化抽取模板](#31-结构化抽取模板)
  - [3.2 文本分类模板](#32-文本分类模板)
  - [3.3 摘要生成模板](#33-摘要生成模板)
  - [3.4 通用模板调用框架](#34-通用模板调用框架)
- [四、第 2 周完整工程骨架](#四第-2-周完整工程骨架)
- [五、Day 14 知识速查](#五day-14-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、第 2 周全景回顾

### 1.1 Day 8–13 知识地图

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       第 2 周知识地图（Day 8–13）                            │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Day 8 · 结构化输出                                                        │
│  ────────────────────────────────────────────────────────────────         │
│  三层约束（Prompt / API参数 / Pydantic）→ JSON Schema → 批量抽取稳定性        │
│                           │                                                │
│                           ↓                                                │
│  Day 9 · 输出校验与异常处理                                                  │
│  ────────────────────────────────────────────────────────────────         │
│  异常分类（可重试/不可重试）→ 指数退避 → 字段分级兜底 → 结果三态              │
│                           │                                                │
│                           ↓                                                │
│  Day 10 · 文本分类器                                                       │
│  ────────────────────────────────────────────────────────────────         │
│  enum 标签约束 → 单/多标签 → Self-Consistency 置信度 → Prompt 对比实验       │
│                           │                                                │
│                           ↓                                                │
│  Day 11 · Prompt 优化                                                      │
│  ────────────────────────────────────────────────────────────────         │
│  四类手段（角色/目标/Few-shot/输出限制）→ 稳定性×准确率双维度 → 留出集验证     │
│                           │                                                │
│                           ↓                                                │
│  Day 12 · 成本意识                                                         │
│  ────────────────────────────────────────────────────────────────         │
│  输入/输出单价差异 → N² 增长模型 → 成本记录表 → 性价比量化                    │
│                           │                                                │
│                           ↓                                                │
│  Day 13 · 配置管理和日志                                                   │
│  ────────────────────────────────────────────────────────────────         │
│  .env + .gitignore → AppConfig dataclass → logging 五级别 → 请求日志       │
│                                                                            │
└───────────────────────────────────────────────────────────────────────────┘
```

### 1.2 本周六个主题的逻辑链

第 2 周的六个主题不是独立话题的堆砌，而是同一个命题的六个层面——**如何让 LLM 应用从"能跑"变成"可信赖、可维护、可扩展"**：

```
能跑（第 1 周已完成）
    ↓
输出可信赖：Day 8 的三层结构化约束 + Day 9 的校验与重试 + Day 10 的枚举标签锁定
    ↓
Prompt 可迭代：Day 11 的量化对比框架（准确率 + 稳定性）+ 留出集防过拟合
    ↓
成本可量化：Day 12 的 Token 计费模型 + 性价比公式（Token/pp）
    ↓
项目可维护：Day 13 的配置与代码分离 + 结构化日志
```

这条链路是**递进且相互依赖的**：没有 Day 8/9 的输出稳定性，Day 10 的分类准确率评估就没有意义；没有 Day 11 的量化框架，Day 12 的成本权衡就缺少效果维度；没有 Day 13 的日志，所有前面的"观测"（Token 消耗、请求耗时）都是一次性的，不能在项目中持续积累。

---

## 二、深度复盘三大问题

### 2.1 什么样的 Prompt 更稳定

"稳定"的技术定义是：同一条输入多次调用，结果完全一致的比例高（Day 11 定义）。不稳定不是模型的问题，而是 **Prompt 留了太多歧义空间**——模型每次都在合理的答案范围内随机选一个，而"合理的答案范围"就是 Prompt 没有锁定的部分。

```
不稳定 Prompt 的四类根因：
  ┌─────────────────────────────────────────────────────────┐
  │ 根因 1：任务目标模糊                                       │
  │   "分析一下这条反馈" → 分析什么？输出什么格式？            │
  │   修复：明确写出"只输出 JSON，字段为 category 和 reason"   │
  ├─────────────────────────────────────────────────────────┤
  │ 根因 2：标签/值域没有穷举                                  │
  │   "判断紧急程度" → 1-10？高中低？紧急/普通？               │
  │   修复：enum 锁定取值范围（Day 10）                        │
  ├─────────────────────────────────────────────────────────┤
  │ 根因 3：边界案例没有覆盖                                   │
  │   训练集没有"信息不足"这种情况 → 模型随机猜                │
  │   修复：Few-shot 中明确展示边界案例怎么处理（Day 11）       │
  ├─────────────────────────────────────────────────────────┤
  │ 根因 4：Temperature 设置过高                              │
  │   结构化输出任务用 0.7 → 不必要的随机性                    │
  │   修复：结构化任务一律用 temperature=0（Day 5/10）         │
  └─────────────────────────────────────────────────────────┘
```

**稳定性的实用公式**（直接从 Day 11 提取）：

```python
def stability_score(prompt_fn, test_set: list[str], n_runs: int = 3) -> float:
    stable_count = 0
    for text in test_set:
        runs = [call_llm(prompt_fn(text)) for _ in range(n_runs)]
        if len(set(runs)) == 1:   # 多次调用结果完全一致
            stable_count += 1
    return stable_count / len(test_set)
```

稳定性 < 70% 的 Prompt 不应该上生产，无论准确率看起来有多好——低稳定意味着用户会看到不一致的结果，这比"偶尔出错但始终一致"对用户体验更有破坏性。

**第 2 周积累的"稳定性提升四件套"**：

| 手段 | 解决哪类不稳定 | 对应 Day |
|------|--------------|---------|
| 角色设定 + 明确判断标准 | 任务目标模糊 | Day 11 |
| enum 类型约束（Pydantic）| 标签/值域未锁定 | Day 10 |
| Few-shot 边界示例 | 边界案例未覆盖 | Day 11 |
| `temperature=0` | 不必要的随机性 | Day 5 |

### 2.2 为什么输出校验比"提示模型小心点"更可靠

这道复盘题的答案不是技术层面的，而是**工程哲学层面**的——"提示模型小心点"是依赖 LLM 的自律，"输出校验"是在代码层面设置检查点，两者的本质差距类似于"请求开发者别提交密钥"和"用 `.gitignore` 机制阻止提交"的差距：

```
依赖"提示"的方式：
  Prompt: "请务必只输出合法 JSON，不要输出其他任何内容"
    ↓
  模型：今天心情好，输出正确 JSON ✓
        但明天可能在 JSON 前加一句"当然，以下是结果：" ✗
        输入太长时会在 JSON 后面多加解释 ✗
  
  问题：失败是随机的、不可预测的，
        且不会抛异常——程序会悄悄拿到错误数据继续运行

依赖"校验"的方式：
  三层防线（Day 8）：
    第一层：response_format={"type": "json_object"} → 模型不输出 JSON 则 API 直接报错
    第二层：json.loads(raw) → 不是合法 JSON 则抛 JSONDecodeError
    第三层：Pydantic Model(**data) → 字段类型/必填项不对则抛 ValidationError
    
  + 重试机制（Day 9）：校验失败 → 指数退避重试 → 耗尽重试返回三态结果
  
  结果：失败是确定的、可捕获的，程序知道数据不可信，
         不会把错误数据流入下游业务逻辑
```

**可视化对比**：

```
"提示模型小心点"的失败模式：
  正常请求 → JSON + 多余文字 → json.loads() 失败 → 程序崩溃（未处理）
                             或 → AttributeError（拿错误数据当正确的用）

"三层校验 + 重试"的失败模式：
  正常请求 → 输出异常 → 捕获异常 → 重试（指数退避）
           → 重试成功 → 返回有效结果 ✓
           → 重试耗尽 → 返回 {"status": "failed", "data": None} （三态）
                      → 调用方知道这条数据不可信，做相应处理
```

关键结论：**校验层不是给模型的"额外约束"，而是给应用代码的"安全网"**——模型 99% 的情况下都会按要求输出，校验层是为了处理那 1% 的意外，让系统在意外时有确定的行为，而不是随机崩溃。

### 2.3 为什么 Demo 要尽早引入日志和配置

这道题有一个常见误解：以为"日志和配置是项目变大之后才需要的"——实际上，**在 Demo 阶段不引入，就意味着项目从一开始就在积累技术债**，而且这部分债的利息是复利的：

```
不引入配置管理的代价（随时间累积）：

  第 1 天：API Key 写死在代码里，OK，就一个文件
  第 7 天：3 个文件都有 API Key，改平台时需要改 3 处
  第 30 天：Key 写进了 10 个脚本，某次不小心提交了一个文件 → 泄露
            或：换了新的 Key，有一个文件漏改了 → 生产用的还是旧 Key
  
  引入配置管理的代价（一次性）：
  第 1 天：花 10 分钟写 AppConfig.from_env() + .env + .gitignore
  此后永远：所有脚本共享同一个配置来源，改一处生效全部
```

```
不引入日志的代价（排查问题时爆发）：

  用 print() 的项目：
    出了问题找不到记录，只能在本地复现
    不知道哪次请求慢（print 没有时间戳）
    不知道哪次请求贵（print 不记录 Token 数）
    想关掉调试输出只能手动注释代码
  
  用 logging 的项目：
    生产环境 LOG_LEVEL=WARNING，只看异常
    开发环境 LOG_LEVEL=DEBUG，看所有细节
    问题发生时日志文件里有时间戳、模块名、Token 数
    不需要复现，直接看日志就能定位
```

**最小成本引入的时机**：第一次写 `client = OpenAI(api_key="sk-...")` 时，就是引入配置管理的最佳时机——此时只有一个文件，改造成本最低；同理，第一次写 `print("API 调用完成")` 时，就应该换成 `logger.info(...)`。

---

## 三、可复用 Prompt 模板库

把第 2 周各 Day 验证过的最终版 Prompt 集中整理，形成一个可以在新项目中直接复用的模板集合。

### 3.1 结构化抽取模板

经 Day 6/8/9 迭代验证的最终版抽取 Prompt（以简历抽取为例，字段可参数化替换）：

```python
EXTRACTION_SYSTEM = "你是信息抽取助手，只输出 JSON，不输出任何解释或多余文字。"

EXTRACTION_USER_TEMPLATE = """从以下文本中抽取指定字段，只输出合法 JSON。

字段要求：
{field_spec}

规则：
- 字段值必须来自原文，不得推断或捏造
- 找不到的字段输出 null，不要省略
- 不输出字段以外的任何内容

文本：
{text}"""

def build_extraction_prompt(text: str, fields: dict[str, str]) -> list[dict]:
    field_spec = "\n".join(f"- {k}（{v}）" for k, v in fields.items())
    return [
        {"role": "system", "content": EXTRACTION_SYSTEM},
        {"role": "user", "content": EXTRACTION_USER_TEMPLATE.format(
            field_spec=field_spec, text=text
        )},
    ]
```

### 3.2 文本分类模板

经 Day 10/11 迭代验证的最终版分类 Prompt（包含角色 + 判断标准 + Few-shot + 输出限制）：

```python
CLASSIFICATION_SYSTEM_TEMPLATE = """你是{role}，负责对用户反馈做分类。

分类标准：
{label_definitions}

输出规则：只输出 JSON，格式：{{"category": "<标签>"}}，不输出任何解释。"""

CLASSIFICATION_FEW_SHOT = [
    {"role": "user", "content": "我的订单到现在还没到，已经超时三天了"},
    {"role": "assistant", "content": '{"category": "投诉"}'},
    {"role": "user", "content": "请问你们支持哪些支付方式"},
    {"role": "assistant", "content": '{"category": "咨询"}'},
]

def build_classification_prompt(
    text: str,
    role: str,
    labels: dict[str, str],
    few_shot: list[dict] | None = None,
) -> list[dict]:
    label_defs = "\n".join(f"- {k}：{v}" for k, v in labels.items())
    system = CLASSIFICATION_SYSTEM_TEMPLATE.format(role=role, label_definitions=label_defs)
    messages = [{"role": "system", "content": system}]
    if few_shot:
        messages.extend(few_shot)
    messages.append({"role": "user", "content": text})
    return messages
```

### 3.3 摘要生成模板

经 Day 5/11 迭代验证的最终版多风格摘要 Prompt：

```python
SUMMARIZATION_PROMPTS = {
    "brief": (
        "用 2-3 句话总结以下文章的核心观点，保留关键数据和结论，"
        "不超过 80 字：\n\n{text}"
    ),
    "bullets": (
        "将以下文章整理成 3-5 条要点，每条以「・」开头，"
        "每条不超过 25 字，只输出要点列表：\n\n{text}"
    ),
    "structured": (
        "分析以下文章，输出 JSON：\n"
        '{"summary": "一句话摘要", "key_points": ["要点1", "要点2", "要点3"], '
        '"conclusion": "核心结论"}\n'
        "只输出 JSON：\n\n{text}"
    ),
}

def build_summarization_prompt(text: str, style: str = "brief") -> list[dict]:
    template = SUMMARIZATION_PROMPTS.get(style, SUMMARIZATION_PROMPTS["brief"])
    return [{"role": "user", "content": template.format(text=text)}]
```

### 3.4 通用模板调用框架

把三种模板统一到一个调用入口，复用 Day 9/13 的校验 + 日志 + 重试：

```python
import json
import logging
from openai import OpenAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


def llm_call(
    client: OpenAI,
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0.0,
    response_format: dict | None = None,
) -> str:
    kwargs = dict(model=model, messages=messages, temperature=temperature)
    if response_format:
        kwargs["response_format"] = response_format
    response = client.chat.completions.create(**kwargs)
    usage = response.usage
    logger.info("完成 | 输入 %d | 输出 %d Token", usage.prompt_tokens, usage.completion_tokens)
    return response.choices[0].message.content


def call_and_parse(
    client: OpenAI,
    messages: list[dict],
    schema: type[BaseModel],
    max_retries: int = 2,
) -> BaseModel | None:
    for attempt in range(1, max_retries + 1):
        raw = llm_call(client, messages, response_format={"type": "json_object"})
        try:
            return schema(**json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("解析失败 (%d/%d)：%s", attempt, max_retries, e)
    logger.error("达到最大重试次数，返回 None")
    return None
```

---

## 四、第 2 周完整工程骨架

把 Day 8–13 的所有工程能力整合进一个统一的 `week2_toolkit.py`，后续 Day 15 起的 RAG 和 Agent 功能都在这个骨架上叠加：

```python
"""
week2_toolkit.py — 第 2 周工程骨架汇总
整合了：配置管理（Day 13）/ 结构化日志（Day 13）/ Pydantic 校验（Day 8）
       / 指数退避重试（Day 9）/ 成本记录（Day 12）/ Prompt 模板（Day 11）
"""

import os
import sys
import time
import json
import logging
from dataclasses import dataclass, field
from openai import OpenAI, APIStatusError, APIConnectionError, RateLimitError
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

load_dotenv()

# ─── 配置 ────────────────────────────────────────────────────────────────────

@dataclass
class AppConfig:
    api_key: str
    model_name: str
    base_url: str
    log_level: str
    max_retries: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        key = os.getenv("DEEPSEEK_API_KEY", "")
        if not key:
            raise ValueError("DEEPSEEK_API_KEY 未设置")
        return cls(
            api_key=key,
            model_name=os.getenv("MODEL_NAME", "deepseek-chat"),
            base_url=os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
        )

# ─── 日志 ────────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

logger = logging.getLogger(__name__)

# ─── 成本记录（Day 12）──────────────────────────────────────────────────────

PRICING = {"deepseek-chat": {"input_per_million": 1.0, "output_per_million": 2.0}}

@dataclass
class CostRecord:
    label: str
    model: str
    input_tokens: int
    output_tokens: int
    elapsed: float
    cost: float = field(init=False)

    def __post_init__(self):
        price = PRICING.get(self.model, {"input_per_million": 1.0, "output_per_million": 2.0})
        self.cost = (
            self.input_tokens * price["input_per_million"] / 1_000_000
            + self.output_tokens * price["output_per_million"] / 1_000_000
        )

# ─── LLM 客户端（整合 Day 9/13）─────────────────────────────────────────────

class LLMClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self.cost_log: list[CostRecord] = []
        logger.info("初始化 | 模型：%s | Key：%s...", config.model_name, config.api_key[:8])

    def chat(self, messages: list, label: str = "", temperature: float = 0.0,
             response_format: dict | None = None) -> str:
        kwargs = dict(model=self.config.model_name, messages=messages, temperature=temperature)
        if response_format:
            kwargs["response_format"] = response_format

        for attempt in range(1, self.config.max_retries + 1):
            start = time.monotonic()
            try:
                resp = self.client.chat.completions.create(**kwargs)
                elapsed = time.monotonic() - start
                usage = resp.usage
                record = CostRecord(
                    label=label, model=self.config.model_name,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens, elapsed=elapsed,
                )
                self.cost_log.append(record)
                logger.info("[%s] 完成 | %.2fs | 输入 %d | 输出 %d Token | ¥%.6f",
                            label, elapsed, usage.prompt_tokens, usage.completion_tokens, record.cost)
                return resp.choices[0].message.content
            except RateLimitError:
                wait = 2 ** attempt
                logger.warning("限速，%ds 后重试 (%d/%d)", wait, attempt, self.config.max_retries)
                time.sleep(wait)
            except APIConnectionError as e:
                logger.warning("连接失败，重试 (%d/%d)：%s", attempt, self.config.max_retries, e)
                time.sleep(1)
            except APIStatusError as e:
                if e.status_code in (400, 401, 403):
                    logger.error("不可重试错误 %d：%s", e.status_code, e.message)
                    raise
                logger.warning("服务器错误 %d，重试 (%d/%d)", e.status_code, attempt, self.config.max_retries)
                time.sleep(2)
        raise RuntimeError(f"达到最大重试次数 {self.config.max_retries}")

    def call_structured(self, messages: list, schema: type[BaseModel],
                        label: str = "") -> BaseModel | None:
        for attempt in range(1, self.config.max_retries + 1):
            raw = self.chat(messages, label=label, response_format={"type": "json_object"})
            try:
                return schema(**json.loads(raw))
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning("[%s] 解析失败 (%d/%d)：%s", label, attempt, self.config.max_retries, e)
        return None

    def print_cost_summary(self) -> None:
        total = sum(r.cost for r in self.cost_log)
        print(f"\n{'标签':<16}{'输入Token':>10}{'输出Token':>10}{'成本(元)':>12}")
        for r in self.cost_log:
            print(f"{r.label:<16}{r.input_tokens:>10}{r.output_tokens:>10}{r.cost:>12.6f}")
        print("-" * 48)
        print(f"{'合计':<36}{total:>12.6f}")


if __name__ == "__main__":
    config = AppConfig.from_env()
    setup_logging(config.log_level)

    client = LLMClient(config)

    result = client.chat(
        messages=[{"role": "user", "content": "用一句话解释什么是 RAG"}],
        label="RAG 解释",
    )
    print(result)
    client.print_cost_summary()
```

---

## 五、Day 14 知识速查

### 第 2 周六个主题一览

| Day | 主题 | 核心产出 | 关键工具/概念 |
|-----|------|---------|-------------|
| 8 | 结构化输出 | 三层约束 + Pydantic 抽取 | JSON Schema, Pydantic |
| 9 | 异常处理 | 指数退避 + 结果三态 | `try/except`, `time.sleep` |
| 10 | 文本分类器 | enum 约束 + 置信度评估 | `Enum`, Self-Consistency |
| 11 | Prompt 优化 | 四类手段 + 量化对比框架 | 稳定性 × 准确率四象限 |
| 12 | 成本意识 | 成本记录表 + 性价比公式 | `response.usage`, `CostRecord` |
| 13 | 配置与日志 | AppConfig + 请求日志 | `dotenv`, `logging` |

### 稳定 Prompt 的判断标准

```
稳定性 ≥ 80%（n_runs=3 时，3 次结果相同率）
  且
准确率 ≥ 阶段目标（由业务容错率决定，不是越高越好）
  且
留出集表现与开发集差距 < 15%（否则视为对测试集过拟合）
```

### 工程保障三要素

```
可信赖 = Pydantic 校验 + 指数退避重试 + 结果三态
可量化 = response.usage 计费 + 稳定性/准确率双维度
可维护 = AppConfig.from_env() + logging 结构化日志
```

---

## 六、实践任务

- [ ] 回答三道复盘题：① 什么样的 Prompt 更稳定；② 为什么输出校验比"提示小心点"更可靠；③ 为什么要尽早引入日志和配置
- [ ] 整理本周做过的最佳 Prompt 版本（分类、抽取、摘要各一个），形成 `prompt_templates.py` 文件
- [ ] 把第 2 周代码整合进 `week2_toolkit.py`，确认 `AppConfig.from_env()`、`logging`、`CostRecord`、`call_structured` 均可正常调用
- [ ] 用 `week2_toolkit.py` 跑一遍本周所有场景（抽取/分类/摘要各一次），查看日志和成本汇总
- [ ] 检查项目目录：确认 `.env` 已加入 `.gitignore`，确认没有任何脚本里硬编码 API Key

**产出标准**：

- 一份可复用的 Prompt 模板库（`prompt_templates.py`，含抽取/分类/摘要三类）
- `week2_toolkit.py` 可以直接运行，输出日志 + 成本汇总表

---

## 七、下一步预告

**Day 15：理解 RAG 基本原理**

第 2 周把基础工程能力做扎实，Day 15 起进入**第二阶段：RAG 核心应用架构**。第 2 周积累的所有能力在 RAG 开发中都会用到：

- **结构化输出（Day 8/9）**：RAG 的最终回答可能需要输出"答案 + 引用片段编号"的结构化 JSON
- **成本意识（Day 12）**：RAG 场景下检索片段会大幅增加输入 Token，Day 12 预警过这个问题
- **日志（Day 13）**：RAG 各环节（检索耗时、向量化耗时、生成耗时）都需要分阶段记录，才能定位性能瓶颈

Day 15 的核心任务：画出一张 RAG 完整流程图，用自己的话解释"为什么不能直接把整个知识库塞给模型"。
