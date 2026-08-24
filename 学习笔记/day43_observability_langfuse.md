# Day 43：可观测性基础：接入 LangFuse/LangSmith

> 学习目标：理解 Trace / Span 的概念及为何"能跑"和"能被观测"是两件事；把项目的 Python logging 升级成可在 Dashboard 搜索调用链、按 span 看耗时分布的专业可观测性；掌握 LangFuse 的接入方式，能在 Dashboard 里定位一次具体请求的完整执行细节
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 43
>
> 🧭 导航：[← Day 42 · 阶段项目整合 + 第 6 周复盘](day42_week6_review_and_integration.md) → Day 44 · 结构化日志与成本监控面板（待更新）

---

## 目录

- [一、为什么"能跑"不等于"能被观测"](#一为什么能跑不等于能被观测)
  - [1.1 Python logging 的局限](#11-python-logging-的局限)
  - [1.2 LLM 应用的可观测性需求](#12-llm-应用的可观测性需求)
- [二、Trace 和 Span：调用链的两个核心概念](#二trace-和-span调用链的两个核心概念)
  - [2.1 Trace：一次请求的完整故事](#21-trace一次请求的完整故事)
  - [2.2 Span：故事里的每一章](#22-span故事里的每一章)
  - [2.3 Trace / Span 在 LLM 应用里的对应关系](#23-trace--span-在-llm-应用里的对应关系)
- [三、LangFuse vs LangSmith：选哪个](#三langfuse-vs-langsmith选哪个)
- [四、接入 LangFuse：三种方式](#四接入-langfuse三种方式)
  - [4.1 方式一：OpenAI SDK 拦截（最少改动）](#41-方式一openai-sdk-拦截最少改动)
  - [4.2 方式二：手动 SDK 埋点（最灵活）](#42-方式二手动-sdk-埋点最灵活)
  - [4.3 方式三：LangChain 回调（已有 LangChain 项目）](#43-方式三langchain-回调已有-langchain-项目)
- [五、在 Dashboard 里能看到什么](#五在-dashboard-里能看到什么)
  - [5.1 Trace 列表视图](#51-trace-列表视图)
  - [5.2 单条 Trace 详情](#52-单条-trace-详情)
  - [5.3 用 Dashboard 定位 Day 42 评估中的 multi_step 失败](#53-用-dashboard-定位-day-42-评估中的-multi_step-失败)
- [六、给 LangGraph Agent 加可观测性](#六给-langgraph-agent-加可观测性)
- [七、Day 43 知识速查](#七day-43-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、为什么"能跑"不等于"能被观测"

### 1.1 Python logging 的局限

Day 13 / Day 28 加的 `logging` 已经能打印每次请求的基本信息。但看一下实际日志长什么样：

```
2026-08-24 10:23:41 INFO  用户输入：帮我规划上海商务行程
2026-08-24 10:23:42 INFO  调用模型...
2026-08-24 10:23:45 INFO  工具调用：get_weather(city=上海)
2026-08-24 10:23:46 INFO  工具调用：get_exchange_rate(from=USD, to=CNY)
2026-08-24 10:23:48 INFO  回答生成完成
```

这些日志能告诉你"发生了什么"，但无法回答：

| 问题 | logging 能否回答 |
|-----|---------------|
| 这次请求总共花了多少时间？ | ❌ 需要手算时间戳差值 |
| 哪一步最慢？ | ❌ 无法按步骤拆分耗时 |
| 这次请求用了多少 Token，花了多少钱？ | ❌ 需要解析多行日志才能关联 |
| 上周一共发生了多少次类似的失败？ | ❌ 无法聚合查询 |
| 某次失败请求的完整上下文是什么？ | ❌ 需要肉眼扫描日志文件 |

日志是"流水账"，可观测性系统是"有索引、可搜索、可聚合的结构化数据库"。

### 1.2 LLM 应用的可观测性需求

LLM 应用相比普通 Web 服务有三个额外的可观测性需求：

| 需求 | 原因 |
|-----|------|
| **Token 和成本追踪** | 每次请求有不同的 Token 消耗，成本是变量；不追踪就无法做成本优化 |
| **Prompt 版本管理** | 同一个请求在不同 Prompt 版本下结果可能差异巨大；需要关联"哪次请求用了哪个 Prompt 版本" |
| **工具调用链路** | 一次 Agent 执行可能有 3-5 次工具调用；需要看清每次工具调用的入参、出参、耗时 |

---

## 二、Trace 和 Span：调用链的两个核心概念

### 2.1 Trace：一次请求的完整故事

**Trace** 是一次用户请求从进入系统到返回结果的**完整记录**，有唯一的 `trace_id`。

```
Trace: "帮我规划上海商务行程"
  trace_id: "abc-123"
  开始时间: 10:23:41.000
  结束时间: 10:23:48.312
  总耗时: 7.312s
  总 Token: 847 (input: 312, output: 535)
  总成本: ¥0.0068
```

Trace 是最高层的视角：这次请求成功了吗？花了多久？花了多少钱？

### 2.2 Span：故事里的每一章

**Span** 是 Trace 里的一个步骤，记录某一个具体操作的开始、结束、输入、输出。

```
Trace: "帮我规划上海商务行程"（7.312s）
  ├── Span: call_model [1.2s, 312 tokens input]
  │     输入: System Prompt + 用户消息
  │     输出: 决定调用 get_weather
  ├── Span: tool_call:get_weather [0.045s]
  │     输入: city="上海"
  │     输出: "多云，26°C，湿度 72%"
  ├── Span: tool_call:get_exchange_rate [0.038s]
  │     输入: from="USD", to="CNY"
  │     输出: "1 USD = 7.25 CNY"
  └── Span: call_model [5.029s, 535 tokens output]
        输入: System Prompt + 消息历史 + 工具结果
        输出: 最终回答文本
```

Span 是细粒度视角：哪一步最慢？工具调用的入参是什么？模型生成了多少 Token？

### 2.3 Trace / Span 在 LLM 应用里的对应关系

| LLM 应用操作 | 对应层级 |
|------------|---------|
| 一次用户对话轮次 | Trace |
| 一次 LLM API 调用（`chat.completions.create`） | Span（Generation） |
| 一次工具调用（`get_weather`） | Span（Event） |
| LangGraph 的一个 Node 执行 | Span |
| 整个 Planner → Executor → Critic 链路 | Trace 下的多个 Span |

---

## 三、LangFuse vs LangSmith：选哪个

| | LangFuse | LangSmith |
|--|--|--|
| **开源** | ✅ 可自部署 | ❌ 闭源（有云版） |
| **免费额度** | 慷慨（适合个人项目） | 有限制 |
| **SDK 支持** | Python / JS，支持 OpenAI / LangChain / LangGraph | 主要针对 LangChain 生态 |
| **Dashboard** | 调用链 / Token 成本 / Prompt 版本 | 调用链 / 评估 / Prompt Hub |
| **适合场景** | 任何 LLM 应用（不依赖 LangChain） | 深度使用 LangChain 的项目 |
| **国内访问** | ✅ 官方云版可访问 | 有时不稳定 |

**今天用 LangFuse**：开源、SDK 对原生 OpenAI 调用支持好（直接拦截 client，不需要改业务代码），免费额度适合学习项目。

---

## 四、接入 LangFuse：三种方式

### 4.1 方式一：OpenAI SDK 拦截（最少改动）

LangFuse 提供 `observe_openai` 包装器，拦截 OpenAI client 的所有调用，自动记录每次 `chat.completions.create` 的输入、输出、Token 用量：

```bash
pip install langfuse
```

```python
# 在项目入口处（如 main.py 顶部）加这几行，不需要改其他代码
import os
from langfuse.openai import openai   # 用 langfuse 的 openai 替换原 openai

# LangFuse 配置（从环境变量读取）
# LANGFUSE_SECRET_KEY / LANGFUSE_PUBLIC_KEY / LANGFUSE_HOST
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"

# 之后正常创建 client，LangFuse 自动拦截
client = openai.OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

# 以下代码完全不需要改
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "北京天气？"}],
)
```

效果：每次 `create` 调用自动变成一个 Span，自动记录输入 messages、输出 content、Token 用量、耗时。

**给 Trace 加业务名称**（推荐，方便在 Dashboard 过滤）：

```python
from langfuse.decorators import langfuse_context, observe

@observe()  # 用 @observe 装饰的函数自动成为一个 Trace
def handle_user_request(user_input: str) -> str:
    langfuse_context.update_current_trace(
        name="weather_assistant",       # Trace 的业务名称
        user_id="user_001",             # 关联用户（用于按用户过滤）
        tags=["multi_step"],            # 标签（用于按场景过滤）
    )
    # ... 业务逻辑
    return response
```

### 4.2 方式二：手动 SDK 埋点（最灵活）

当需要精确控制每个 Span 的边界（如给工具调用单独记录一个 Span）时，用手动埋点：

```python
from langfuse import Langfuse

lf = Langfuse()

def run_agent(user_input: str) -> str:
    # 1. 创建 Trace（一次用户请求）
    trace = lf.trace(
        name="agent_run",
        input={"user_input": user_input},
    )

    # 2. 创建 Span：LLM 调用
    generation = trace.generation(
        name="call_model",
        model="deepseek-chat",
        input=messages,
    )
    response = client.chat.completions.create(...)
    generation.end(
        output=response.choices[0].message.content,
        usage={"input": response.usage.prompt_tokens,
               "output": response.usage.completion_tokens},
    )

    # 3. 创建 Span：工具调用
    tool_span = trace.span(
        name="tool_call:get_weather",
        input={"city": "上海"},
    )
    result = get_weather("上海")
    tool_span.end(output={"result": result})

    # 4. 结束 Trace
    trace.update(output={"answer": final_answer})
    lf.flush()   # 确保数据发送
    return final_answer
```

### 4.3 方式三：LangChain 回调（已有 LangChain 项目）

对于 Day 31-32 的 LangChain LCEL 链，LangFuse 提供回调处理器，零代码改动：

```python
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler()

# 在 chain.invoke 时传入 config
chain.invoke(
    {"question": "北京天气？"},
    config={"callbacks": [langfuse_handler]},
)
```

LangFuse 自动把 LCEL 链的每个 Runnable 步骤记录成一个 Span。

---

## 五、在 Dashboard 里能看到什么

### 5.1 Trace 列表视图

Dashboard 首页显示所有 Trace 的列表，每行包含：
- Trace 名称（如 `weather_assistant`）
- 开始时间 + 总耗时
- 总 Token 用量（input + output）
- 总成本（按模型定价自动计算）
- 状态（成功 / 错误）
- 标签（如 `multi_step`）

可以按时间范围、标签、用户 ID 过滤，快速找到"上周所有 multi_step 任务里哪些失败了"。

### 5.2 单条 Trace 详情

点进一条 Trace，看到瀑布图（Waterfall）：

```
Trace: agent_run [7.312s]
├── Generation: call_model        ████░░░░░░░░   1.2s   312 tokens
├── Span: tool_call:get_weather   █             0.045s
├── Span: tool_call:exchange_rate █             0.038s
└── Generation: call_model        ████████████  5.029s  535 tokens
                                       ↑
                              这步占了 68% 的总耗时
```

关键信息：
- **哪一步最慢**：第二次 LLM 调用占 68% 的时间（有优化空间）
- **工具调用入参**：`city="上海"`（可以验证参数是否正确）
- **完整 Prompt**：点进 Generation Span 看到完整的 messages 数组
- **Token 分布**：每个 Generation Span 的 input / output Token 分开显示

### 5.3 用 Dashboard 定位 Day 42 评估中的 multi_step 失败

Day 42 评估报告里，`m03`（"同时告诉我北京和上海的天气"）工具调用失败——接入 LangFuse 后，找到这次 Trace，展开 Span，能直接看到：

- Planner 的输出 JSON（看拆了几个子任务）
- Executor 的工具调用次数（是不是只调了一次 `get_weather`）
- 哪个 Span 产生了 `status=failed`

这就是从"猜测是 Planner 的问题"到"确认是 Planner 只输出了一个子任务"的跨越——日志只能告诉你出错了，Dashboard 告诉你在哪里出错了。

---

## 六、给 LangGraph Agent 加可观测性

LangGraph 没有原生的 LangFuse 集成，需要在 Node 函数里手动埋点，或者用 `@observe` 装饰每个 Node：

```python
from langfuse.decorators import observe

@observe(name="planner_node")
def planner_node(state: AgentState) -> dict:
    langfuse_context.update_current_observation(
        input={"user_request": state["user_request"]},
    )
    tasks = plan(state["user_request"])
    langfuse_context.update_current_observation(
        output={"tasks": tasks},
    )
    return {"tasks": tasks}

@observe(name="executor_node")
def executor_node(state: AgentState) -> dict:
    results = execute(state["tasks"])
    return {"results": results}

@observe(name="critic_node")
def critic_node(state: AgentState) -> dict:
    verdict = critique(state["user_request"], state["tasks"], state["results"])
    return {"verdict": verdict}
```

整个 LangGraph 图的一次执行作为一个 Trace，每个 Node 是一个 Span，嵌套关系自动保留。

**最终效果**：Dashboard 里看到的是：

```
Trace: langgraph_agent_run [8.1s]
├── Span: planner_node            ██      1.5s
├── Span: executor_node           ██████  4.2s
│   ├── Event: tool:get_weather   █       0.04s
│   └── Event: tool:exchange_rate █       0.03s
└── Span: critic_node             ██      2.4s
```

---

## 七、Day 43 知识速查

### Trace / Span 核心概念

```
Trace  = 一次用户请求的完整记录（有唯一 trace_id）
Span   = Trace 里的一个步骤（有开始时间、结束时间、输入、输出）
Generation = LLM API 调用的 Span（额外记录 Token 用量）
Event  = 瞬时操作的 Span（如工具调用）
```

### LangFuse 三种接入方式速查

| 方式 | 代码改动量 | 适合场景 |
|-----|----------|---------|
| `langfuse.openai` 拦截 | 换一行 import | 快速接入，自动记录所有 LLM 调用 |
| `@observe` 装饰器 | 加装饰器 + `update_current_trace` | 需要加业务语义（名称、用户 ID、标签） |
| 手动 SDK 埋点 | 较多 | 精确控制每个 Span 边界 |
| LangChain 回调 | 加 `config={"callbacks": [...]}` | 已有 LangChain LCEL 链 |

### LangFuse vs logging 对比

| 能力 | Python logging | LangFuse |
|-----|---------------|---------|
| 记录发生了什么 | ✅ | ✅ |
| 按 trace_id 关联一次请求的所有日志 | ❌ | ✅ |
| 按步骤看耗时分布 | ❌ | ✅ |
| Token 和成本自动统计 | ❌ | ✅ |
| Dashboard 搜索和过滤 | ❌ | ✅ |
| 完整 Prompt 历史查看 | ❌ | ✅ |

---

## 八、实践任务

- [ ] 注册 LangFuse 账号（cloud.langfuse.com），创建项目，获取 `LANGFUSE_SECRET_KEY` 和 `LANGFUSE_PUBLIC_KEY`，写入 `.env`
- [ ] 用方式一（`langfuse.openai` 替换 import）接入项目，跑 3 次请求（一次单工具调用、一次多步工具调用、一次边界拒绝），在 Dashboard Trace 列表里验证三次请求都出现了
- [ ] 点进多步工具调用的 Trace，查看瀑布图——找出耗时最长的 Span，记录它占总耗时的百分比
- [ ] 给 `handle_user_request` 加 `@observe` 装饰器和 `langfuse_context.update_current_trace(name=..., tags=[...])`，重新跑请求，验证 Dashboard 里 Trace 有了业务名称和标签

**产出标准**：在 LangFuse Dashboard 里能找到某一次具体请求，展开看到至少 2 个 Span（LLM 调用 + 工具调用），能读出该 Span 的耗时和 Token 用量。

---

## 九、下一步预告

Day 44 进入**结构化日志与成本监控面板**：今天 LangFuse 已经能自动追踪每次请求的 Token 和成本，但这是"看单次"。Day 44 要做的是"看趋势"——设计结构化日志字段（`trace_id` / `tokens` / `cost` / `latency`），写一个小脚本把最近 N 次请求的数据聚合成"按天 / 按功能"的成本报表，让成本变化一眼可见——这是从"知道花了多少"到"知道哪里花多了"的跨越。
