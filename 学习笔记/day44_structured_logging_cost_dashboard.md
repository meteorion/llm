# Day 44：结构化日志与成本监控面板

> 学习目标：理解为什么日志字段必须结构化而不是纯文本；在 Day 28 的日志系统基础上加上 `trace_id` / `tokens` / `cost` / `latency` 结构化字段；写一个聚合脚本，把最近 N 次请求汇总成"按天 / 按功能"的成本报表——从"知道花了多少"到"知道哪里花多了"
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 44
>
> 🧭 导航：[← Day 43 · 可观测性基础：接入 LangFuse/LangSmith](day43_observability_langfuse.md) → Day 45 · Prompt / 结果缓存（待更新）

---

## 目录

- [一、为什么日志必须结构化](#一为什么日志必须结构化)
  - [1.1 纯文本日志的致命缺陷](#11-纯文本日志的致命缺陷)
  - [1.2 结构化日志的核心字段](#12-结构化日志的核心字段)
- [二、字段设计详解](#二字段设计详解)
  - [2.1 trace_id：关联一次请求的所有记录](#21-trace_id关联一次请求的所有记录)
  - [2.2 tokens 和 cost：成本的原子单位](#22-tokens-和-cost成本的原子单位)
  - [2.3 latency：耗时的三个维度](#23-latency耗时的三个维度)
  - [2.4 function_name：成本归因的关键](#24-function_name成本归因的关键)
- [三、给 Day 28 日志系统加结构化字段](#三给-day-28-日志系统加结构化字段)
  - [3.1 原有 Day 28 日志方案回顾](#31-原有-day-28-日志方案回顾)
  - [3.2 升级后的结构化日志模块](#32-升级后的结构化日志模块)
  - [3.3 在 Agent 调用点埋点](#33-在-agent-调用点埋点)
- [四、成本聚合脚本](#四成本聚合脚本)
  - [4.1 日志文件格式约定](#41-日志文件格式约定)
  - [4.2 聚合脚本实现](#42-聚合脚本实现)
  - [4.3 成本报表输出示例](#43-成本报表输出示例)
- [五、LangFuse 与本地日志的分工](#五langfuse-与本地日志的分工)
- [六、Day 44 知识速查](#六day-44-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么日志必须结构化

### 1.1 纯文本日志的致命缺陷

Day 28 的日志长这样：

```
2026-08-24 10:23:41 INFO  [weather_agent] 用户输入：帮我规划上海行程
2026-08-24 10:23:48 INFO  [weather_agent] 完成，耗时 7.3s，tokens: prompt=312 completion=535
2026-08-24 10:24:01 INFO  [weather_agent] 用户输入：北京今天天气
2026-08-24 10:24:03 INFO  [weather_agent] 完成，耗时 2.1s，tokens: prompt=98 completion=45
```

看起来信息完整，但对机器来说是不透明的。当你想回答"上周这个功能总共花了多少钱"时，必须：

1. grep 过滤出相关行（`grep "weather_agent"` 只是开始）
2. 写正则提取 tokens 数字（`re.search(r"prompt=(\d+)", line)` 每次写法不同）
3. 手动累加（写一次性脚本，下次同样的需求要重写）

每次分析都是一次临时工程。而且这些日志还有更深层的问题：

| 问题 | 后果 |
|-----|------|
| 字段没有统一名称 | 有时写 `tokens:`，有时写 `token_count:`，grep 和正则都要多写分支 |
| 数值和文本混在同一行 | 无法直接用标准库解析，必须自定义正则 |
| 多次请求的日志交错 | 多线程下 A 请求的 "完成" 行可能出现在 B 请求的 "开始" 行后面 |
| 无关联 ID | 无法把"开始"和"完成"两行对应到同一次请求 |

### 1.2 结构化日志的核心字段

结构化日志把每条记录存成 JSON，一行一个完整事件：

```json
{
  "timestamp": "2026-08-24T10:23:48.312Z",
  "trace_id": "abc-123",
  "function_name": "weather_agent",
  "event": "request_complete",
  "latency_ms": 7312,
  "tokens_input": 312,
  "tokens_output": 535,
  "cost_usd": 0.000934,
  "status": "success"
}
```

这条记录可以直接被任何 JSON 解析器读取，不需要正则，任何字段都可以作为过滤条件。

---

## 二、字段设计详解

### 2.1 trace_id：关联一次请求的所有记录

一次完整的 Agent 执行可能产生多条日志（请求开始、工具调用、模型调用、请求结束）。`trace_id` 把这些分散的记录串联成一次请求的完整故事：

```json
// 同一个 trace_id = 同一次用户请求
{"trace_id": "abc-123", "event": "request_start",   "input": "帮我规划上海行程"}
{"trace_id": "abc-123", "event": "tool_call",        "tool": "get_weather", "args": {"city": "上海"}}
{"trace_id": "abc-123", "event": "tool_call",        "tool": "get_exchange_rate", "args": {...}}
{"trace_id": "abc-123", "event": "request_complete", "latency_ms": 7312, "tokens_input": 312}
```

查某次请求的完整链路只需要 `grep "abc-123"` 或 `filter(trace_id="abc-123")`，不需要靠时间戳对齐。

**生成方式**：

```python
import uuid

def new_trace_id() -> str:
    return str(uuid.uuid4())[:8]  # 取前 8 位已经有足够低的碰撞概率
```

### 2.2 tokens 和 cost：成本的原子单位

Token 消耗要分 input 和 output 分开记录，因为两者的定价不同（通常 output 比 input 贵 3-4 倍）：

```python
# DeepSeek 定价示例（价格随时调整，请以官网为准）
PRICE_PER_1M_TOKENS = {
    "deepseek-chat": {"input": 0.14, "output": 0.28},  # USD
}

def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICE_PER_1M_TOKENS.get(model, {"input": 0, "output": 0})
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
```

记录时同时存 tokens 原始值和换算后的美元成本——tokens 用来排查"哪次请求 Prompt 太长"，cost 用来聚合"这周总花了多少钱"。

### 2.3 latency：耗时的三个维度

只记总耗时无法排查性能瓶颈。生产日志应记三个层级：

| 字段 | 含义 | 用途 |
|-----|------|------|
| `latency_total_ms` | 从用户输入到返回答案的总耗时 | 用户体验指标 |
| `latency_llm_ms` | 所有 LLM API 调用的耗时之和 | 判断瓶颈是模型还是工具 |
| `latency_tool_ms` | 所有工具调用的耗时之和 | 判断哪个工具最慢 |

`latency_total_ms ≈ latency_llm_ms + latency_tool_ms + 业务逻辑耗时`

### 2.4 function_name：成本归因的关键

同一个 Agent 可能有多个功能入口（天气查询 / 行程规划 / 汇率换算）。按 `function_name` 分组才能知道"哪个功能最贵"：

```
按 function_name 聚合（最近 7 天）：
  travel_planner:   $0.82  (47 次，平均 $0.017/次)
  weather_query:    $0.23  (158 次，平均 $0.0015/次)
  exchange_rate:    $0.04  (61 次，平均 $0.00066/次)
  
→ travel_planner 只有 47 次却占了总成本的 75%，优化重点明确
```

---

## 三、给 Day 28 日志系统加结构化字段

### 3.1 原有 Day 28 日志方案回顾

Day 28 的日志模块使用 Python 标准库 `logging`，格式为纯文本。核心调用点：

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("weather_agent")

logger.info(f"用户输入：{user_input}")
logger.info(f"完成，耗时 {elapsed:.1f}s，tokens: {usage}")
```

### 3.2 升级后的结构化日志模块

新建 `structured_logger.py`，在原有 `logging` 基础上并行输出 JSON 格式到单独的文件：

```python
import json
import logging
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

# JSON 日志文件路径
LOG_FILE = Path("logs/requests.jsonl")   # JSONL = JSON Lines，每行一个 JSON 对象

# DeepSeek 定价（USD / 1M tokens，按需更新）
_PRICE = {
    "deepseek-chat": {"input": 0.14, "output": 0.28},
}


def _calc_cost(model: str, input_tok: int, output_tok: int) -> float:
    p = _PRICE.get(model, {"input": 0.0, "output": 0.0})
    return (input_tok * p["input"] + output_tok * p["output"]) / 1_000_000


def new_trace_id() -> str:
    return str(uuid.uuid4())[:8]


def log_request(
    *,
    trace_id: str,
    function_name: str,
    event: str,                # "request_start" | "tool_call" | "request_complete" | "error"
    model: str = "",
    tokens_input: int = 0,
    tokens_output: int = 0,
    latency_total_ms: int = 0,
    latency_llm_ms: int = 0,
    latency_tool_ms: int = 0,
    status: str = "success",
    extra: dict | None = None,
) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "function_name": function_name,
        "event": event,
        "model": model,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "cost_usd": _calc_cost(model, tokens_input, tokens_output),
        "latency_total_ms": latency_total_ms,
        "latency_llm_ms": latency_llm_ms,
        "latency_tool_ms": latency_tool_ms,
        "status": status,
        **(extra or {}),
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

### 3.3 在 Agent 调用点埋点

在主处理函数的入口和出口各加一条结构化日志，工具调用处加 span 记录：

```python
import time
from structured_logger import new_trace_id, log_request

def handle_request(user_input: str, function_name: str = "weather_agent") -> str:
    trace_id = new_trace_id()
    t_start = time.monotonic()

    # 请求开始事件
    log_request(
        trace_id=trace_id,
        function_name=function_name,
        event="request_start",
        extra={"input_preview": user_input[:80]},
    )

    llm_ms = 0
    tool_ms = 0

    try:
        # --- 工具调用（示例） ---
        t_tool = time.monotonic()
        weather_result = get_weather("上海")
        tool_ms += int((time.monotonic() - t_tool) * 1000)

        log_request(
            trace_id=trace_id,
            function_name=function_name,
            event="tool_call",
            extra={"tool": "get_weather", "args": {"city": "上海"},
                   "latency_ms": int((time.monotonic() - t_tool) * 1000)},
        )

        # --- LLM 调用 ---
        t_llm = time.monotonic()
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
        )
        llm_ms += int((time.monotonic() - t_llm) * 1000)
        usage = response.usage

        # 请求完成事件
        log_request(
            trace_id=trace_id,
            function_name=function_name,
            event="request_complete",
            model="deepseek-chat",
            tokens_input=usage.prompt_tokens,
            tokens_output=usage.completion_tokens,
            latency_total_ms=int((time.monotonic() - t_start) * 1000),
            latency_llm_ms=llm_ms,
            latency_tool_ms=tool_ms,
            status="success",
        )
        return response.choices[0].message.content

    except Exception as e:
        log_request(
            trace_id=trace_id,
            function_name=function_name,
            event="error",
            latency_total_ms=int((time.monotonic() - t_start) * 1000),
            status="error",
            extra={"error_type": type(e).__name__, "error_msg": str(e)[:200]},
        )
        raise
```

---

## 四、成本聚合脚本

### 4.1 日志文件格式约定

`logs/requests.jsonl` 是标准 JSONL 格式：每行一个独立的 JSON 对象，用文本编辑器和 `jq` 都能直接读。

```bash
# 用 jq 快速查看最近 5 条记录
tail -5 logs/requests.jsonl | jq .

# 用 jq 过滤出所有 error 事件
jq 'select(.status == "error")' logs/requests.jsonl
```

### 4.2 聚合脚本实现

新建 `cost_report.py`：

```python
"""
用法：
  python cost_report.py              # 最近 7 天，按天统计
  python cost_report.py --days 30    # 最近 30 天
  python cost_report.py --by func    # 按功能统计
"""
import json
import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOG_FILE = Path("logs/requests.jsonl")


def load_records(days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = []
    if not LOG_FILE.exists():
        return records
    with LOG_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # 只统计 request_complete 事件（包含完整成本信息）
            if rec.get("event") != "request_complete":
                continue
            ts = datetime.fromisoformat(rec["timestamp"])
            if ts < cutoff:
                continue
            records.append(rec)
    return records


def report_by_day(records: list[dict]) -> None:
    buckets: dict[str, dict] = defaultdict(lambda: {"count": 0, "cost": 0.0,
                                                     "tokens_in": 0, "tokens_out": 0,
                                                     "latency_sum": 0})
    for r in records:
        day = r["timestamp"][:10]   # "2026-08-24"
        b = buckets[day]
        b["count"] += 1
        b["cost"] += r.get("cost_usd", 0.0)
        b["tokens_in"] += r.get("tokens_input", 0)
        b["tokens_out"] += r.get("tokens_output", 0)
        b["latency_sum"] += r.get("latency_total_ms", 0)

    print(f"\n{'日期':<12} {'请求数':>6} {'总成本(USD)':>12} {'输入Token':>10} {'输出Token':>10} {'均耗时(ms)':>10}")
    print("-" * 65)
    total_cost = 0.0
    for day in sorted(buckets):
        b = buckets[day]
        avg_lat = b["latency_sum"] // b["count"] if b["count"] else 0
        print(f"{day:<12} {b['count']:>6} {b['cost']:>12.6f} {b['tokens_in']:>10} {b['tokens_out']:>10} {avg_lat:>10}")
        total_cost += b["cost"]
    print("-" * 65)
    print(f"{'合计':<12} {sum(b['count'] for b in buckets.values()):>6} {total_cost:>12.6f}\n")


def report_by_func(records: list[dict]) -> None:
    buckets: dict[str, dict] = defaultdict(lambda: {"count": 0, "cost": 0.0,
                                                     "latency_sum": 0, "errors": 0})
    # 同时统计 error 事件
    LOG_FILE_AGAIN = LOG_FILE
    with LOG_FILE_AGAIN.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") == "error":
                buckets[rec.get("function_name", "unknown")]["errors"] += 1

    for r in records:
        fn = r.get("function_name", "unknown")
        b = buckets[fn]
        b["count"] += 1
        b["cost"] += r.get("cost_usd", 0.0)
        b["latency_sum"] += r.get("latency_total_ms", 0)

    print(f"\n{'功能名称':<24} {'请求数':>6} {'错误数':>6} {'总成本(USD)':>12} {'均成本(USD)':>12} {'均耗时(ms)':>10}")
    print("-" * 75)
    for fn in sorted(buckets, key=lambda k: -buckets[k]["cost"]):
        b = buckets[fn]
        avg_cost = b["cost"] / b["count"] if b["count"] else 0
        avg_lat = b["latency_sum"] // b["count"] if b["count"] else 0
        print(f"{fn:<24} {b['count']:>6} {b['errors']:>6} {b['cost']:>12.6f} {avg_cost:>12.6f} {avg_lat:>10}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="统计最近 N 天（默认 7）")
    parser.add_argument("--by", choices=["day", "func"], default="day", help="分组维度")
    args = parser.parse_args()

    records = load_records(args.days)
    print(f"共加载 {len(records)} 条 request_complete 记录（最近 {args.days} 天）")

    if args.by == "day":
        report_by_day(records)
    else:
        report_by_func(records)


if __name__ == "__main__":
    main()
```

### 4.3 成本报表输出示例

```
共加载 266 条 request_complete 记录（最近 7 天）

日期           请求数     总成本(USD)    输入Token    输出Token   均耗时(ms)
-----------------------------------------------------------------
2026-08-18         31     0.004821       12431         8234       3412
2026-08-19         38     0.006213       15821        11023       3891
2026-08-20         42     0.007102       18234        12891       4021
2026-08-21         29     0.003911        9823         7012       2983
2026-08-22         56     0.009234       24021        16234       4234
2026-08-23         47     0.007892       19823        13012       3912
2026-08-24         23     0.003421        9123         6012       3021
-----------------------------------------------------------------
合计              266     0.042594
```

```bash
# 按功能统计
python cost_report.py --by func --days 30
```

```
功能名称                 请求数  错误数    总成本(USD)    均成本(USD)   均耗时(ms)
---------------------------------------------------------------------------
travel_planner              47      3     0.082341      0.001752       7823
weather_query              158      1     0.023412      0.000148       2134
exchange_rate               61      0     0.004123      0.000068       1023
```

---

## 五、LangFuse 与本地日志的分工

Day 43 接入了 LangFuse，今天又建了本地结构化日志，两者看起来有重叠——实际上分工互补：

| 维度 | LangFuse Dashboard | 本地结构化日志（JSONL） |
|-----|--------------------|--------------------|
| **细粒度** | 每个 Span 的完整 Prompt 和输出 | 请求级聚合（总 Token、总耗时） |
| **查询方式** | Web UI，点选过滤 | 脚本或 `jq`，可自定义聚合逻辑 |
| **成本报表** | 有，但格式固定 | 自定义（按天 / 按功能 / 按模型） |
| **离线分析** | 需要 API 导出 | 文件直接可读，无网络依赖 |
| **数据保留** | 受账号计划限制 | 自己控制，可永久保留 |
| **适合场景** | 调试单次请求、看调用链路 | 成本趋势分析、生成运营报表 |

**结论**：两者同时运行。LangFuse 用于实时调试（"这次请求为什么慢？"），本地日志用于批量分析（"这周哪个功能最贵？"）。

---

## 六、Day 44 知识速查

### 结构化日志必备字段

```python
{
    "timestamp":        str,   # ISO 8601，含时区，便于跨时区对比
    "trace_id":         str,   # 关联同一次请求的所有日志行
    "function_name":    str,   # 成本归因的关键维度
    "event":            str,   # request_start | tool_call | request_complete | error
    "model":            str,   # 用于查对应定价
    "tokens_input":     int,   # Prompt 消耗
    "tokens_output":    int,   # Completion 生成
    "cost_usd":         float, # 已换算的美元成本
    "latency_total_ms": int,   # 端到端耗时
    "latency_llm_ms":   int,   # LLM 调用耗时（排查模型延迟用）
    "latency_tool_ms":  int,   # 工具调用耗时（排查工具瓶颈用）
    "status":           str,   # success | error
}
```

### 纯文本 vs 结构化日志对比

| 能力 | 纯文本日志 | 结构化 JSONL |
|-----|-----------|------------|
| 人工阅读 | ✅ 直观 | ⚠️ 需要格式化工具（`jq`）|
| 程序解析 | ❌ 必须写正则，字段格式不一致 | ✅ `json.loads()` 直接解析 |
| 多字段过滤 | ❌ 多次 grep，不可靠 | ✅ `jq 'select(.function_name == "x")'` |
| 数值聚合 | ❌ 提取后手动累加 | ✅ 直接 sum/mean |
| 多线程安全 | ❌ 日志行可能交错 | ✅ 每行是独立完整的 JSON 对象 |

### 成本计算公式

```
cost = (tokens_input × price_input + tokens_output × price_output) / 1_000_000
```

---

## 七、实践任务

- [ ] 新建 `structured_logger.py`，实现 `new_trace_id()` 和 `log_request()` 函数；在 `logs/` 目录生成一条 `request_complete` JSON 记录，用 `jq .` 验证格式正确
- [ ] 在现有 Agent 入口函数加上结构化日志埋点（request_start / tool_call / request_complete），跑 5 次不同类型的请求（单工具 / 多步骤 / 边界拒绝），检查 `logs/requests.jsonl` 里的 5 条记录
- [ ] 运行 `python cost_report.py --by day`，验证能输出按天汇总的报表；再运行 `--by func`，对比各功能的单次均成本
- [ ] 找出成本最高的功能，检查它对应的 `tokens_input` 是否明显偏大（Prompt 过长）或 `tokens_output` 偏大（回答冗长），记录优化方向

**产出标准**：能打印出一张"按天 / 按功能"统计的成本报表，包含请求数、总成本、平均单次成本、平均耗时，数据来源于真实的 5 次以上请求日志。

---

## 八、下一步预告

Day 45 进入**Prompt / 结果缓存**：今天的日志分析告诉你"哪里贵"，Day 45 要做的是"让常见请求不再重复花钱"。通过精确匹配缓存（完全相同的请求直接返回缓存结果）和语义缓存（语义相似的请求复用历史结果），把高频重复问题的 Token 消耗降到零——以及弄清楚精确缓存和语义缓存各自适合什么场景，什么时候该让缓存过期。
