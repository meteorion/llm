# Day 13：配置管理和日志

> 学习目标：把项目从"能跑的脚本"变成"能维护的项目"——用环境变量和 `.env` 彻底移除硬编码密钥，学会用 Python 标准库 `logging` 记录必要的运行信息，理解"为什么机制比人的自律更可靠"这条工程原则
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 13
>
> 🧭 导航：[← Day 12 · 建立成本意识](day12_cost_awareness.md) [→ Day 14 · 第 2 周复盘](day14_week2_review.md)

---

## 目录

- [一、为什么需要配置管理](#一为什么需要配置管理)
  - [1.1 硬编码密钥的风险](#11-硬编码密钥的风险)
  - [1.2 配置与代码分离的原则](#12-配置与代码分离的原则)
  - [1.3 配置的三种来源及优先级](#13-配置的三种来源及优先级)
- [二、环境变量与 .env 文件](#二环境变量与-env-文件)
  - [2.1 用 python-dotenv 管理 .env](#21-用-python-dotenv-管理-env)
  - [2.2 .gitignore 的正确配置](#22-gitignore-的正确配置)
  - [2.3 用 dataclass 封装配置对象](#23-用-dataclass-封装配置对象)
- [三、Python logging 基础](#三python-logging-基础)
  - [3.1 为什么不用 print](#31-为什么不用-print)
  - [3.2 logging 模块的五个级别](#32-logging-模块的五个级别)
  - [3.3 格式化与输出目标](#33-格式化与输出目标)
- [四、给 LLM 项目加上实用日志](#四给-llm-项目加上实用日志)
  - [4.1 启动日志：记录关键配置](#41-启动日志记录关键配置)
  - [4.2 请求日志：耗时与 Token 消耗](#42-请求日志耗时与-token-消耗)
  - [4.3 错误日志：异常链与上下文](#43-错误日志异常链与上下文)
- [五、完整实现：可维护的 LLM 客户端](#五完整实现可维护的-llm-客户端)
- [六、Day 13 知识速查](#六day-13-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么需要配置管理

### 1.1 硬编码密钥的风险

在 Day 3 就强调过 API Key 不能写进代码，Day 13 正式把这件事做彻底。先看反面教材：

```python
# 错误示例——千万不要这样写
client = OpenAI(
    api_key="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",   # 这行一旦提交到 Git，密钥就公开了
    base_url="https://api.deepseek.com/v1",
)
```

**风险链条**：

```
代码里写死 Key
    → 提交到 Git（哪怕是私有仓库，成员都能看到）
    → 偶然 push 到公开仓库（GitHub 会秒扫描并通知平台）
    → Key 被吊销或者被盗用，账单暴增
```

这不是"只要小心就能避免"的问题——在代码里放密钥，就等于在设计上选择了依赖每个开发者的自律，而不是用机制来保障。工程上有一条基本原则：**能用机制保证的事情，就不要依赖人的自律**。配置管理就是把"不提交密钥"从习惯变成机制。

### 1.2 配置与代码分离的原则

12-Factor App（业界广泛认可的云原生应用设计方法论）第三条原则明确说：**配置应该存储在环境中，而不是代码里**。"配置"指的是在不同部署环境（开发、测试、生产）之间会变化的所有值：

```
会变化的值（应该放配置）：
  - API Key
  - 模型名称（dev 用便宜的，prod 用旗舰版）
  - 服务地址（本地 vs 云端）
  - 日志级别（dev DEBUG，prod WARNING）
  - 超时时间、重试次数

不会变化的值（可以写代码里）：
  - 业务逻辑、算法
  - Prompt 模板（如果是固定的）
  - 数据结构定义
```

**判断一个值该不该放配置的最简测试**：如果同一套代码需要在两台机器上用不同的值运行，那个值就应该放配置。

### 1.3 配置的三种来源及优先级

```
优先级：命令行参数 > 环境变量 > .env 文件 > 代码默认值

┌─────────────────────────────────────────────────────────┐
│  命令行参数  --model deepseek-chat                       │  最高优先级
│  (python main.py --model deepseek-chat)                  │  临时覆盖，不持久
├─────────────────────────────────────────────────────────┤
│  环境变量   export DEEPSEEK_API_KEY=sk-xxx               │  当前 shell 生效
│             set DEEPSEEK_API_KEY=sk-xxx (Windows)        │  适合 CI/CD 注入密钥
├─────────────────────────────────────────────────────────┤
│  .env 文件  DEEPSEEK_API_KEY=sk-xxx                      │  本地开发用
│             （不提交到 Git）                               │  每个人有自己的副本
├─────────────────────────────────────────────────────────┤
│  代码默认值 model = os.getenv("MODEL", "deepseek-chat")  │  最低优先级
│             （用于非必填项的合理默认值）                    │  方便快速运行
└─────────────────────────────────────────────────────────┘
```

---

## 二、环境变量与 .env 文件

### 2.1 用 python-dotenv 管理 .env

`python-dotenv` 会读取 `.env` 文件并把其中的键值对注入到 `os.environ`，之后用 `os.getenv()` 取值即可：

```bash
# 安装
pip install python-dotenv
```

`.env` 文件格式（放在项目根目录，**不提交到 Git**）：

```dotenv
# .env
DEEPSEEK_API_KEY=sk-your-actual-key-here
MODEL_NAME=deepseek-chat
BASE_URL=https://api.deepseek.com/v1
LOG_LEVEL=DEBUG
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

Python 中加载：

```python
import os
from dotenv import load_dotenv

load_dotenv()  # 从当前目录向上查找 .env 文件，找到就加载

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY 未设置，请检查 .env 文件")
```

**`load_dotenv()` 的行为**：
- 如果环境变量已经存在（比如 CI 注入的），默认不会覆盖——优先级自然对了
- 用 `load_dotenv(override=True)` 可以强制用 `.env` 覆盖已有环境变量（测试环境有时需要）
- 找不到 `.env` 文件时不报错，静默跳过

### 2.2 .gitignore 的正确配置

`.env` 文件必须加入 `.gitignore`，这是"机制"的关键一步：

```gitignore
# .gitignore
.env
.env.local
.env.*.local

# 如果有多个环境的配置
.env.development
.env.production
```

同时提供一份 `.env.example`（**提交到 Git**），供团队成员参考应该设哪些变量：

```dotenv
# .env.example — 提交到 Git，只包含变量名和示例格式，不含真实值
DEEPSEEK_API_KEY=sk-your-key-here
MODEL_NAME=deepseek-chat
BASE_URL=https://api.deepseek.com/v1
LOG_LEVEL=INFO
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

```
项目目录结构：
  .env            ← 本地真实配置，已加入 .gitignore，不提交
  .env.example    ← 配置模板，提交到 Git，方便新成员参考
```

### 2.3 用 dataclass 封装配置对象

散落的 `os.getenv()` 调用遍布代码各处，后期很难维护。用一个 `dataclass` 把所有配置集中管理，同时在加载时做类型转换和合法性校验：

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    api_key: str
    model_name: str
    base_url: str
    log_level: str
    max_retries: int
    request_timeout: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
        return cls(
            api_key=api_key,
            model_name=os.getenv("MODEL_NAME", "deepseek-chat"),
            base_url=os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        )
```

**为什么用 `@classmethod` 而不是直接在 `__init__` 里读环境变量**：保持 `dataclass` 可测试性——单元测试时可以直接 `AppConfig(api_key="test-key", ...)` 构造对象，不需要设置真实环境变量。

---

## 三、Python logging 基础

### 3.1 为什么不用 print

前几天的代码大量使用 `print()` 输出调试信息，这在脚本阶段无妨，但在项目中有明显缺点：

```
print() 的问题：
  - 无法区分严重程度（调试信息和错误信息长得一样）
  - 无法控制输出（想关闭调试信息时只能一行行注释）
  - 无时间戳（日志到底是什么时候打的？）
  - 无法同时输出到文件和控制台
  - 无法按模块/包过滤

logging 解决了这些问题：
  - 有级别（DEBUG / INFO / WARNING / ERROR / CRITICAL）
  - 一行配置就能控制哪些级别的日志输出
  - 自动带时间戳、文件名、行号
  - 同时写控制台和日志文件只需加 Handler
  - 按 logger name（通常是模块名）过滤
```

### 3.2 logging 模块的五个级别

```
CRITICAL (50) ─── 程序即将崩溃的灾难性错误
ERROR    (40) ─── 当前操作失败，但程序可以继续运行
WARNING  (30) ─── 出现了不寻常的情况，但还不是错误
INFO     (20) ─── 正常运行信息（启动、请求完成、耗时）
DEBUG    (10) ─── 开发阶段的详细诊断信息

设置 level=INFO 时：INFO / WARNING / ERROR / CRITICAL 都输出，DEBUG 被过滤
设置 level=DEBUG 时：全部输出（开发阶段用）
```

| 级别 | 典型用途 | 举例 |
|------|---------|------|
| DEBUG | 开发调试，生产不显示 | 打印完整的 messages 列表、原始响应 |
| INFO | 记录正常里程碑 | "模型调用完成，耗时 1.2s，消耗 320 Token" |
| WARNING | 不影响结果但值得注意 | "输出 Token 达到 max_tokens 上限，回答可能被截断" |
| ERROR | 某次操作失败，需要关注 | "JSON 解析失败，尝试重试 (1/3)" |
| CRITICAL | 程序无法继续 | "API Key 无效，程序退出" |

### 3.3 格式化与输出目标

```python
import logging
import sys

def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt))

    # 文件 Handler（追加模式）
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))

    logging.basicConfig(level=log_level, handlers=[console_handler, file_handler])
```

在每个模块顶部用模块名创建 logger，而不是用 root logger：

```python
# 在 llm_client.py 顶部
import logging
logger = logging.getLogger(__name__)   # __name__ = "llm_client"

# 使用
logger.info("开始调用 DeepSeek API")
logger.debug("消息列表：%s", messages)   # 用 %s 而非 f-string，不触发时不计算
logger.error("请求失败：%s", e)
```

**用 `%s` 而非 f-string 的原因**：`logger.debug("msg: %s", data)` 在 DEBUG 被过滤时不会执行字符串拼接，`logger.debug(f"msg: {data}")` 无论是否过滤都会先计算 f-string——大数据对象时性能差异明显。

---

## 四、给 LLM 项目加上实用日志

### 4.1 启动日志：记录关键配置

程序启动时应该打一条 INFO 日志，让运维/排查时知道当前生效的配置是什么：

```python
def log_startup_info(config: AppConfig) -> None:
    logger.info("=" * 50)
    logger.info("LLM 客户端启动")
    logger.info("  模型：%s", config.model_name)
    logger.info("  API Base URL：%s", config.base_url)
    logger.info("  最大重试：%d 次", config.max_retries)
    logger.info("  请求超时：%d 秒", config.request_timeout)
    logger.info("  日志级别：%s", config.log_level)
    # API Key 只打印前8位，足够核对是否是正确的 Key，不暴露完整密钥
    logger.info("  API Key：%s...", config.api_key[:8])
    logger.info("=" * 50)
```

**为什么要打 API Key 前 8 位**：排查时经常需要确认"用的是哪个 Key"，完全隐藏（`***`）没有帮助，但打完整的 Key 不安全——只打前 8 位是一个常见的折中方式，能区分不同 Key 但不泄露完整内容。

### 4.2 请求日志：耗时与 Token 消耗

把 Day 12 的成本记录和日志结合起来，每次 API 调用后自动记录关键指标：

```python
import time
import logging

logger = logging.getLogger(__name__)


def call_with_logging(client, messages: list, model: str, label: str = "") -> dict:
    start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        elapsed = time.monotonic() - start
        usage = response.usage

        logger.info(
            "[%s] 完成 | 耗时 %.2fs | 输入 %d Token | 输出 %d Token",
            label or model,
            elapsed,
            usage.prompt_tokens,
            usage.completion_tokens,
        )
        return {
            "content": response.choices[0].message.content,
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "elapsed": elapsed,
        }
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("[%s] 失败 | 耗时 %.2fs | 错误：%s", label or model, elapsed, e)
        raise
```

日志输出示例：

```
2026-08-16 10:23:45  INFO      llm_client  [文章摘要] 完成 | 耗时 1.83s | 输入 620 Token | 输出 85 Token
2026-08-16 10:23:48  INFO      llm_client  [信息抽取] 完成 | 耗时 0.92s | 输入 45 Token | 输出 32 Token
2026-08-16 10:23:50  ERROR     llm_client  [文本分类] 失败 | 耗时 30.01s | 错误：ConnectTimeout
```

### 4.3 错误日志：异常链与上下文

日志最重要的价值在出问题时——让你不用在本地复现就能判断出了什么问题：

```python
import json
import logging

logger = logging.getLogger(__name__)


def parse_json_with_logging(raw: str, label: str = "") -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(
            "[%s] JSON 解析失败 | 错误位置 line %d col %d | 原始内容前 200 字符：%s",
            label,
            e.lineno,
            e.colno,
            raw[:200],
        )
        raise
```

**`logger.exception()` vs `logger.error()`**：

```python
try:
    risky_operation()
except Exception as e:
    logger.exception("操作失败")   # 等价于 logger.error("...", exc_info=True)
                                    # 自动附加完整 traceback，排查最方便
    logger.error("操作失败：%s", e) # 只记录错误信息，不含 traceback（日志更简洁）
```

在 ERROR 级别的日志里，优先用 `logger.exception()`——完整 traceback 在排查线上问题时价值极高，多占几行日志是值得的。

---

## 五、完整实现：可维护的 LLM 客户端

把配置管理 + 日志整合进 Day 9 的健壮客户端，形成一个完整可用的项目骨架：

```python
import os
import time
import logging
import sys
from dataclasses import dataclass
from openai import OpenAI, APIStatusError, APIConnectionError, RateLimitError
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    api_key: str
    model_name: str
    base_url: str
    log_level: str
    max_retries: int
    request_timeout: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
        return cls(
            api_key=api_key,
            model_name=os.getenv("MODEL_NAME", "deepseek-chat"),
            base_url=os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        )


def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt))
    logging.basicConfig(level=log_level, handlers=[console_handler])


logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        logger.info(
            "客户端初始化 | 模型：%s | Key：%s...",
            config.model_name,
            config.api_key[:8],
        )

    def chat(self, messages: list, label: str = "") -> dict:
        for attempt in range(1, self.config.max_retries + 1):
            start = time.monotonic()
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    temperature=0.3,
                    timeout=self.config.request_timeout,
                )
                elapsed = time.monotonic() - start
                usage = response.usage
                logger.info(
                    "[%s] 完成 | 耗时 %.2fs | 输入 %d | 输出 %d Token",
                    label or self.config.model_name,
                    elapsed,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                )
                return {
                    "content": response.choices[0].message.content,
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                }
            except RateLimitError as e:
                wait = 2 ** attempt
                logger.warning("限速，%d 秒后重试 (%d/%d)", wait, attempt, self.config.max_retries)
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
        raise RuntimeError(f"达到最大重试次数 {self.config.max_retries}，请求失败")


if __name__ == "__main__":
    config = AppConfig.from_env()
    setup_logging(config.log_level)

    client = LLMClient(config)
    result = client.chat(
        messages=[{"role": "user", "content": "用一句话解释什么是 RAG"}],
        label="RAG 解释",
    )
    print(result["content"])
```

---

## 六、Day 13 知识速查

### 配置管理速查

| 实践 | 怎么做 | 为什么 |
|------|--------|--------|
| 密钥放环境变量 | `.env` + `os.getenv()` | 不进 Git，不进代码 |
| `.env` 加入 `.gitignore` | 写入 `.gitignore`，提供 `.env.example` | 防止意外提交 |
| 配置对象化 | `@dataclass` + `from_env()` | 集中校验，可测试 |
| 非必填项设默认值 | `os.getenv("KEY", "default")` | 快速启动不报错 |

### logging 速查

| 场景 | 用哪个级别 | 示例 |
|------|-----------|------|
| 每次 API 调用完成 | INFO | 耗时 + Token 数 |
| 配置加载时打印当前值 | INFO | 模型名、Key 前 8 位 |
| 重试、限速等临时问题 | WARNING | 第几次重试 |
| 操作失败但程序继续 | ERROR | JSON 解析失败 |
| 带完整 traceback | `logger.exception()` | 在 except 块中用 |

### 最小模板

```python
# 项目入口固定套路
from dotenv import load_dotenv
import logging, os

load_dotenv()
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

---

## 七、实践任务

- [ ] 在前几天的任意一个脚本中，把所有 `print()` 替换成对应级别的 `logging` 调用
- [ ] 创建 `.env` 文件，把 API Key、模型名、日志级别都移入其中；确认 `.env` 已加入 `.gitignore`
- [ ] 提供 `.env.example`，包含全部变量名和占位符值
- [ ] 用 `AppConfig.from_env()` 替代代码中散落的 `os.getenv()` 调用
- [ ] 在 LLMClient 中加入请求日志，确认日志能同时输出到控制台，格式包含时间戳和模块名

**产出标准**：

- 项目中不存在任何硬编码的 API Key（可用 `grep -r "sk-" .` 验证）
- 运行任意脚本时，控制台能看到带时间戳的 INFO 日志，包含模型名和每次请求的耗时/Token 数

---

## 八、下一步预告

**Day 14：第 2 周复盘**

Day 8–13 这六天补全了"工程基本功"的完整闭环：结构化输出 → 异常处理与重试 → 文本分类 → Prompt 优化 → 成本意识 → 配置与日志。Day 14 的复盘问题将是：

- 什么样的 Prompt 真正更稳定（Day 11 的实验结论）
- 为什么输出校验比"提示模型小心点"更可靠（Day 9 的工程哲学）
- 为什么 Demo 要尽早引入日志和配置（Day 13 的今天的答案）

产出是一份**可复用的 Prompt 模板库**，整合第 2 周所有场景的最终 Prompt 版本。