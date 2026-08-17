# Day 29：测试和优化

> 学习目标：用 10 组测试问题系统地跑一遍 Day 27–28 项目，从输出稳定性、工具触发准确率、检索准确率、成本合理性四个维度发现问题并记录改进点，产出一份可复用的测试记录表
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 29
>
> 🧭 导航：[← Day 28 · 补工程细节](day28_engineering_details.md) [→ Day 30 · 整理作品与总结](day30_project_summary.md)

---

## 目录

- [一、为什么 LLM 项目需要系统测试](#一为什么-llm-项目需要系统测试)
  - [1.1 LLM 测试 vs 普通软件测试](#11-llm-测试-vs-普通软件测试)
  - [1.2 四个测试维度](#12-四个测试维度)
  - [1.3 10 组测试用例的设计原则](#13-10-组测试用例的设计原则)
- [二、输出稳定性测试](#二输出稳定性测试)
  - [2.1 什么是"稳定性"](#21-什么是稳定性)
  - [2.2 temperature=0 时的真实稳定性](#22-temperature0-时的真实稳定性)
  - [2.3 稳定性测试实现](#23-稳定性测试实现)
- [三、工具调用准确率测试](#三工具调用准确率测试)
  - [3.1 触发准确率的定义](#31-触发准确率的定义)
  - [3.2 误触发与漏触发案例分析](#32-误触发与漏触发案例分析)
  - [3.3 工具调用准确率测试实现](#33-工具调用准确率测试实现)
  - [3.4 优化触发准确率的三个手段](#34-优化触发准确率的三个手段)
- [四、检索准确率测试（RAG 场景）](#四检索准确率测试rag-场景)
  - [4.1 检索准确率的核心问题](#41-检索准确率的核心问题)
  - [4.2 Hit Rate 与 MRR 两个指标](#42-hit-rate-与-mrr-两个指标)
  - [4.3 检索准确率测试实现](#43-检索准确率测试实现)
- [五、成本分析](#五成本分析)
  - [5.1 每轮对话的 Token 消耗结构](#51-每轮对话的-token-消耗结构)
  - [5.2 Token 消耗增长的两大陷阱](#52-token-消耗增长的两大陷阱)
  - [5.3 成本分析实现](#53-成本分析实现)
  - [5.4 四类成本优化手段](#54-四类成本优化手段)
- [六、完整测试记录表设计](#六完整测试记录表设计)
  - [6.1 测试记录表结构](#61-测试记录表结构)
  - [6.2 完整测试脚本](#62-完整测试脚本)
  - [6.3 结果分析与改进优先级](#63-结果分析与改进优先级)
- [七、Day 29 知识速查](#七day-29-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、为什么 LLM 项目需要系统测试

### 1.1 LLM 测试 vs 普通软件测试

```
普通软件：
  input → 确定性函数 → output
  相同输入 → 相同输出（可断言 assertEqual）

LLM 项目：
  input → LLM（随机采样） → output
  相同输入 → 大概率相似但不完全相同的输出
  无法用 assertEqual，只能评估"是否满足目标"
```

| 维度 | 普通软件测试 | LLM 项目测试 |
|-----|------------|------------|
| 正确性判断 | 精确匹配（assertEqual） | 语义/结构/功能匹配 |
| 稳定性 | 默认稳定 | 需要多次运行验证 |
| 评估者 | 自动化断言 | 规则检查 + 人工抽样 |
| 失败模式 | 崩溃/错误返回 | 生成了错误内容（幻觉、漏召回、误触发） |
| 边界测试 | 已知边界（数据类型、长度限制） | 未知边界（语义边界难以穷举） |

**核心结论**：LLM 项目测试的目标不是"100% 通过"，而是**量化"在预期范围内失败的概率"**，并把它降到可接受水平。

### 1.2 四个测试维度

```
┌──────────────────────────────────────────────────────────┐
│               LLM 项目四维度测试                           │
├─────────────┬──────────────────┬────────────────────────┤
│ 维度         │ 核心问题          │ 关键指标               │
├─────────────┼──────────────────┼────────────────────────┤
│ 输出稳定性   │ 相同问题答案一致？ │ 一致率（%）            │
│ 工具触发准确 │ 工具调用时机对吗？ │ 精确率 / 召回率        │
│ 检索准确率   │ 检索到对的段落？  │ Hit Rate / MRR        │
│ 成本合理性   │ Token 消耗合理？  │ 每轮 tokens / 月成本估算 │
└─────────────┴──────────────────┴────────────────────────┘
```

### 1.3 10 组测试用例的设计原则

10 组用例要**覆盖边界**，而不只测"正常情况"：

```
建议分布：
  3 道：核心功能（一定能答对的）→ 验证基线
  2 道：工具触发场景（应该调工具）→ 验证触发
  2 道：不应触发工具（纯聊天问题）→ 验证不误触发
  2 道：边界/模糊问题（需要工具但不明确）→ 测试灰色地带
  1 道：恶意/无效输入（乱码、注入尝试）→ 测试健壮性
```

---

## 二、输出稳定性测试

### 2.1 什么是"稳定性"

稳定性指**同一问题多次运行时，核心内容是否一致**：

```
问题："今天北京天气怎么样？"
  稳定的答案：每次都返回"北京今天晴，25°C"（数据来自工具，一致）
  不稳定的答案：第 1 次"北京今天是晴天，气温 25 摄氏度"
               第 2 次"我没法获取实时天气"
               （第 2 次漏触发工具，不稳定）

问题："讲个笑话"
  稳定的答案：每次都是笑话（格式正确）
  不稳定的答案：偶尔回复"作为 AI 我没有笑话可讲"（拒绝回答）
```

**稳定性 ≠ 完全相同**：措辞可以不同，但功能行为应当一致（是否调了工具、回答是否包含核心信息）。

### 2.2 temperature=0 时的真实稳定性

`temperature=0` 会让输出**接近但不完全确定性**：

```python
# temperature=0 意味着贪心解码：每步选概率最高的 token
# 相同输入 → 相同输出（前提：服务端无并发、模型版本不变）

# 但实践中仍有不稳定来源：
# 1. 工具调用参数：模型可能第 1 次传 {"city": "北京"} 第 2 次传 {"city": "Beijing"}
# 2. 多步工作流的工具结果不同时，后续生成会不同（工具本身有随机性）
# 3. DeepSeek 等商业 API 内部可能有负载均衡、模型版本差异
```

**实践建议**：稳定性测试要运行 **3–5 次**，而不是 2 次（样本太少无法判断偶发还是系统性问题）。

### 2.3 稳定性测试实现

```python
import json
from core.workflow import run
from core.config import CFG

SYSTEM_MSG = {"role": "system", "content": "你是一个智能个人助理，可以查天气和汇率。"}

def stability_test(question: str, runs: int = 3) -> dict:
    """多次运行同一问题，检查工具调用行为是否一致。"""
    results = []
    for i in range(runs):
        wf, _ = run(question, [SYSTEM_MSG])
        results.append({
            "run": i + 1,
            "tools_called": [s.name for s in wf.steps],
            "answer_length": len(wf.final_answer),
            "terminated_by": wf.terminated_by,
        })
    
    # 一致性分析
    all_tools = [tuple(r["tools_called"]) for r in results]
    is_stable = len(set(all_tools)) == 1
    
    return {
        "question": question,
        "stable": is_stable,
        "runs": results,
        "note": "工具调用行为一致" if is_stable else f"工具调用不一致：{set(all_tools)}",
    }


if __name__ == "__main__":
    tests = [
        "北京今天天气怎么样？",
        "帮我把 100 美元换成人民币",
        "你好，我想聊聊天",
    ]
    for q in tests:
        result = stability_test(q, runs=3)
        status = "✅" if result["stable"] else "❌"
        print(f"{status} {result['question']}")
        print(f"   {result['note']}")
        for r in result["runs"]:
            print(f"   Run {r['run']}: tools={r['tools_called']}, len={r['answer_length']}")
        print()
```

---

## 三、工具调用准确率测试

### 3.1 触发准确率的定义

```
精确率（Precision）= 正确触发 / 总触发次数
  → 触发的工具是不是都对的？（防误触发）

召回率（Recall）= 正确触发 / 应该触发的次数
  → 应该调工具的都调了吗？（防漏触发）

F1 = 2 × Precision × Recall / (Precision + Recall)
  → 综合指标

示例：
  10 道题中，有 6 道应该触发 get_weather
  模型触发了 5 次：其中 4 次正确，1 次错触发了 get_exchange_rate

  Precision = 4/5 = 80%
  Recall    = 4/6 = 67%
  F1        = 2×0.8×0.67 / (0.8+0.67) = 73%
```

### 3.2 误触发与漏触发案例分析

| 类型 | 例子 | 根因 | 修复方向 |
|-----|-----|------|---------|
| **误触发** | "天气真好" → 调了 get_weather | description 描述太宽泛，包含"天气"关键词就触发 | 收紧 description，加 "用户明确询问实时天气数据时才使用" |
| **漏触发** | "帮我查一下魔都今天的温度" → 没调工具 | "魔都"没有映射到北京/上海，或 description 要求"城市名" | description 加 "城市的常用别名（如魔都=上海）也适用" |
| **参数错误** | 调了正确工具但 city="上海市" 而非 "上海" | 模型没规范化参数 | 工具层对参数做规范化，或 description 说明参数格式 |
| **工具选错** | 问汇率但调了 get_weather | 多工具时 description 有歧义 | 在 description 里明确区分场景，加对比说明 |

### 3.3 工具调用准确率测试实现

```python
from dataclasses import dataclass
from core.workflow import run
from core.config import CFG

@dataclass
class ToolTestCase:
    question: str
    expected_tools: list   # 期望调用的工具列表（顺序无关）
    should_not_call: list  # 不应该调用的工具

SYSTEM_MSG = {"role": "system", "content": "你是一个智能个人助理，可以查天气和汇率。"}

TEST_CASES = [
    ToolTestCase("北京今天天气怎么样？", ["get_weather"], []),
    ToolTestCase("帮我把 100 美元换成人民币", ["get_exchange_rate"], []),
    ToolTestCase("天气真不错", [], ["get_weather"]),           # 不应触发
    ToolTestCase("你好", [], ["get_weather", "get_exchange_rate"]),  # 不应触发
    ToolTestCase("魔都今天温度多少？", ["get_weather"], []),   # 别名测试
    ToolTestCase("上海天气和汇率都告诉我", ["get_weather", "get_exchange_rate"], []),
]

def evaluate_tool_accuracy(cases: list) -> dict:
    tp = fp = fn = 0
    details = []
    
    for case in cases:
        wf, _ = run(case.question, [SYSTEM_MSG])
        called = set(s.name for s in wf.steps)
        expected = set(case.expected_tools)
        forbidden = set(case.should_not_call)
        
        hit = expected & called            # 正确触发
        missed = expected - called         # 漏触发
        wrong = called & forbidden         # 误触发
        
        tp += len(hit)
        fn += len(missed)
        fp += len(wrong)
        
        status = "✅" if (not missed and not wrong) else "❌"
        details.append({
            "status": status,
            "question": case.question,
            "expected": list(expected),
            "called": list(called),
            "missed": list(missed),
            "wrong": list(wrong),
        })
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "details": details,
    }


if __name__ == "__main__":
    result = evaluate_tool_accuracy(TEST_CASES)
    print(f"精确率：{result['precision']:.1%}")
    print(f"召回率：{result['recall']:.1%}")
    print(f"F1：{result['f1']:.1%}")
    print()
    for d in result["details"]:
        print(f"{d['status']} {d['question']}")
        if d["missed"]:
            print(f"   ⚠️  漏触发：{d['missed']}")
        if d["wrong"]:
            print(f"   ⚠️  误触发：{d['wrong']}")
```

### 3.4 优化触发准确率的三个手段

**手段 1：精化 tool description**

```python
# 差的 description（容易误触发）
"description": "获取天气信息"

# 好的 description（明确触发条件）
"description": (
    "当用户明确询问某地当前或今日天气时使用。"
    "支持中国城市，包括别名（如'魔都'=上海，'帝都'=北京）。"
    "若用户只是泛泛感叹天气好坏，不要调用此工具。"
)
```

**手段 2：在 System Prompt 里给工具调用设置护栏**

```python
SYSTEM_PROMPT = """你是智能个人助理。

工具调用规则：
- 只有用户明确需要实时数据（天气/汇率）时才调用工具
- 闲聊、解释、建议类问题直接回答，不调用工具
- 参数中的城市名统一用中文简称（如"北京"，不用"北京市"）
"""
```

**手段 3：参数规范化（在工具内部处理）**

```python
_CITY_ALIASES = {"魔都": "上海", "帝都": "北京", "羊城": "广州", "渝": "重庆"}

def get_weather(city: str, unit: str = "celsius") -> dict:
    city = _CITY_ALIASES.get(city, city).replace("市", "").strip()
    ...
```

---

## 四、检索准确率测试（RAG 场景）

### 4.1 检索准确率的核心问题

如果项目包含 RAG 组件（Day 15–20），需要测试检索阶段是否能找到相关段落：

```
用户问题："产品退货政策是什么？"
知识库中有段落："顾客可在购买后 30 天内无理由退货..."

测试问题：
  检索到这个段落了吗？（Hit Rate）
  这个段落排在第几位？（MRR）
  如果没检索到，生成的回答是否"幻觉"了一个答案？
```

### 4.2 Hit Rate 与 MRR 两个指标

```
Hit Rate（命中率）：
  查询 N 个问题，有几个能在 Top-K 结果里找到正确段落？
  Hit Rate = 命中问题数 / 总问题数
  越高越好，目标 > 80%

MRR（Mean Reciprocal Rank，平均倒数排名）：
  正确段落排在第 k 位，贡献 1/k；取所有问题的平均
  MRR = (1/N) × Σ(1/rank_i)
  排越靠前越好（第 1 位 = 1.0，第 2 位 = 0.5，第 3 位 = 0.33...）
```

### 4.3 检索准确率测试实现

```python
from typing import Callable

RAG_TEST_CASES = [
    {"question": "产品退货政策是什么？", "expected_keyword": "30 天"},
    {"question": "如何联系客服？",       "expected_keyword": "客服热线"},
    {"question": "配送时间多长？",       "expected_keyword": "3-5 个工作日"},
]

def test_retrieval(retriever: Callable, cases: list, top_k: int = 3) -> dict:
    """retriever: fn(question, k) -> list of str（段落内容）"""
    hits = 0
    reciprocal_ranks = []
    
    for case in cases:
        docs = retriever(case["question"], top_k)
        rank = None
        for i, doc in enumerate(docs):
            if case["expected_keyword"] in doc:
                rank = i + 1
                break
        
        if rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
    
    return {
        "hit_rate": hits / len(cases),
        "mrr": sum(reciprocal_ranks) / len(cases),
        "top_k": top_k,
    }
```

---

## 五、成本分析

### 5.1 每轮对话的 Token 消耗结构

```
单次 API 调用的 Token 组成：

  input_tokens = System Prompt
               + 对话历史（所有轮次累积）
               + 工具定义（ALL_TOOLS 的 JSON Schema）
               + 当前用户消息

  output_tokens = 模型回复（文字 + tool_calls JSON）

多步工作流额外消耗：
  每次工具调用后需要再次发送完整历史
  若有 2 步工具，实际发送了 3 次请求
  input_tokens 随对话轮次线性增长（×3 也是常见的）
```

**工具定义的隐性成本**：每次请求都要把所有工具的 description / parameters 发给模型，这部分 Token 容易被忽略：

```python
import json
from tools import ALL_TOOLS

tools_json = json.dumps(ALL_TOOLS)
tools_tokens = len(tools_json) // 4   # 粗估：4 字节 ≈ 1 token
print(f"工具定义每次消耗约 {tools_tokens} tokens")
# 3 个工具的 Schema 通常 300–600 tokens
```

### 5.2 Token 消耗增长的两大陷阱

**陷阱 1：未截断历史导致指数级增长**

```python
# 错误：每轮都把全部历史传入
messages = all_messages  # 第 10 轮时 input_tokens 已经翻了 10 倍

# 正确：超过阈值时截断旧消息（保留 System Prompt + 最近 N 轮）
def trim_history(messages: list, max_turns: int = 5) -> list:
    system = [m for m in messages if m["role"] == "system"]
    rest   = [m for m in messages if m["role"] != "system"]
    if len(rest) > max_turns * 2:
        rest = rest[-(max_turns * 2):]
    return system + rest
```

**陷阱 2：工作流循环未终止导致 Token 暴增**

```
正常 2 步工作流（3 次 API 调用）：
  调用 1: input=800  → 触发工具 A
  调用 2: input=1100 → 触发工具 B
  调用 3: input=1400 → 生成回答
  总计: 3300 input + 约 200 output = 3500 tokens

未设 max_iterations 的失控工作流（10 次）：
  总 input 可能超过 10000 tokens
  成本是正常工作流的 3 倍以上
```

### 5.3 成本分析实现

```python
import time
from dataclasses import dataclass, field
from core.workflow import run

# DeepSeek chat 定价（截至 2025 年，非缓存）
PRICE_PER_1M = {"input": 0.14, "output": 0.28}   # USD per 1M tokens

@dataclass
class CostRecord:
    question: str
    input_tokens: int
    output_tokens: int
    tool_steps: int
    elapsed: float

    @property
    def total_tokens(self): return self.input_tokens + self.output_tokens
    @property
    def cost_usd(self):
        return (self.input_tokens * PRICE_PER_1M["input"]
                + self.output_tokens * PRICE_PER_1M["output"]) / 1_000_000


SYSTEM_MSG = {"role": "system", "content": "你是一个智能个人助理，可以查天气和汇率。"}

def cost_test(questions: list) -> list:
    # 前置条件：需要先在 Day 28 的 WorkflowResult 中补充这两个字段：
    #   total_input_tokens: int = 0
    #   total_output_tokens: int = 0
    # 并在 run_workflow 每次调用 client.chat.completions.create 后累加：
    #   wf.total_input_tokens  += response.usage.prompt_tokens
    #   wf.total_output_tokens += response.usage.completion_tokens
    # 完成上述改动后，下面的 getattr 就能取到真实值，否则始终为 0。
    records = []
    for q in questions:
        t = time.monotonic()
        wf, _ = run(q, [SYSTEM_MSG])
        elapsed = time.monotonic() - t
        records.append(CostRecord(
            question=q,
            input_tokens=getattr(wf, "total_input_tokens", 0),
            output_tokens=getattr(wf, "total_output_tokens", 0),
            tool_steps=len(wf.steps),
            elapsed=elapsed,
        ))
    return records


def print_cost_report(records: list):
    print(f"{'问题':<30} {'步骤':>4} {'输入T':>7} {'输出T':>7} {'成本(USD)':>10} {'耗时':>6}")
    print("-" * 75)
    for r in records:
        q_short = r.question[:28] + ".." if len(r.question) > 28 else r.question
        print(f"{q_short:<30} {r.tool_steps:>4} {r.input_tokens:>7} "
              f"{r.output_tokens:>7} ${r.cost_usd:>9.6f} {r.elapsed:>5.1f}s")
    total_cost = sum(r.cost_usd for r in records)
    print("-" * 75)
    print(f"{'合计':<30} {'':>4} {sum(r.input_tokens for r in records):>7} "
          f"{sum(r.output_tokens for r in records):>7} ${total_cost:>9.6f}")
```

### 5.4 四类成本优化手段

| 优化手段 | 做法 | 节省幅度 | 副作用 |
|---------|------|---------|--------|
| **历史截断** | 保留最近 N 轮，丢弃早期消息 | 30–60%（长对话） | 可能丢失早期上下文 |
| **按需加载工具** | 根据问题类型只传相关工具 | 10–20%（工具多时） | 增加判断逻辑复杂度 |
| **System Prompt 压缩** | 去除重复说明，用紧凑表述 | 5–15% | 可能降低指令遵循度 |
| **模型分级路由** | 简单问题用小模型，复杂问题用大模型 | 40–80%（取决于分布） | 需要路由判断，实现复杂 |

---

## 六、完整测试记录表设计

### 6.1 测试记录表结构

一份好的测试记录表应该包含：

```
测试时间：2026-08-16
项目：可调用工具的个人助理（Day 27-28）
模型：deepseek-chat
temperature：0

┌─────┬──────────────────────┬──────────┬──────────┬───────┬──────────────┐
│ 编号 │ 测试问题              │ 预期行为  │ 实际行为  │ 结果  │ 问题/备注    │
├─────┼──────────────────────┼──────────┼──────────┼───────┼──────────────┤
│  1  │ 北京今天天气怎么样？   │ 调天气工具 │ 调天气工具 │  ✅   │             │
│  2  │ 天气真好              │ 不调工具  │ 调了天气  │  ❌   │ 误触发，需优化 │
│  3  │ 100 美元换人民币      │ 调汇率工具 │ 调汇率工具 │  ✅   │             │
│  4  │ 魔都今天多热？         │ 调天气工具 │ 未触发    │  ❌   │ 别名漏召回   │
│  5  │ 你好                  │ 直接回答  │ 直接回答  │  ✅   │             │
│ ... │                      │          │          │       │             │
└─────┴──────────────────────┴──────────┴──────────┴───────┴──────────────┘

汇总：
  稳定性：8/10 通过
  工具触发精确率：85%，召回率：75%，F1：80%
  平均 Token 消耗：1240 input / 180 output
  平均耗时：2.3s

主要问题：
  P1（高）：魔都等别名漏触发 → 在工具 description 里加别名说明
  P2（中）：泛泛谈天气误触发 → 在 description 里加"用户明确询问实时数据"限制
  P3（低）：多步工作流耗时偏长（4.1s）→ 可接受，暂不优化

改进计划：
  本次修复：P1（30 分钟内完成）、P2（30 分钟内完成）
  下次迭代：P3（考虑并行工具调用优化）
```

### 6.2 完整测试脚本

```python
"""
测试入口：python test_project.py
将四个维度的测试整合为一次运行。
"""
import json, time
from core.workflow import run
from core.config import CFG

SYSTEM_MSG = {"role": "system", "content": "你是一个智能个人助理，可以查天气和汇率。"}

# 定义 10 组测试用例
TEST_SUITE = [
    # (问题, 期望工具列表, 不应触发工具列表, 备注)
    ("北京今天天气怎么样？",          ["get_weather"],            [],           "核心天气功能"),
    ("帮我把 100 美元换成人民币",     ["get_exchange_rate"],      [],           "核心汇率功能"),
    ("上海天气和今日汇率都告诉我",    ["get_weather", "get_exchange_rate"], [], "多工具场景"),
    ("魔都今天多热？",                ["get_weather"],            [],           "城市别名"),
    ("帝都天气",                      ["get_weather"],            [],           "两字简称"),
    ("天气真好",                      [],                         ["get_weather"], "泛谈天气不触发"),
    ("你好，介绍一下你自己",           [],                         ["get_weather", "get_exchange_rate"], "闲聊不触发"),
    ("什么是汇率？",                  [],                         ["get_exchange_rate"], "概念解释不触发"),
    ("给我做一份旅行计划",             [],                         [],           "综合任务"),
    ("！@#￥%……&*（）",              [],                         [],           "无效输入"),
]

def run_test_suite():
    results = []
    total_input = total_output = 0
    
    print(f"开始测试（模型：{CFG.model}，temperature={CFG.temperature}）\n")
    
    for i, (question, expected_tools, forbidden_tools, note) in enumerate(TEST_SUITE):
        t = time.monotonic()
        wf, _ = run(question, [SYSTEM_MSG])
        elapsed = time.monotonic() - t
        
        called = set(s.name for s in wf.steps)
        expected = set(expected_tools)
        forbidden = set(forbidden_tools)
        
        missed = expected - called
        wrong  = called & forbidden
        passed = not missed and not wrong
        
        status = "✅" if passed else "❌"
        issues = []
        if missed:  issues.append(f"漏触发：{missed}")
        if wrong:   issues.append(f"误触发：{wrong}")
        
        results.append({
            "id": i + 1, "status": status, "question": question,
            "called": list(called), "missed": list(missed), "wrong": list(wrong),
            "elapsed": elapsed, "note": note,
        })
        
        q_short = question[:25] + ".." if len(question) > 25 else question
        issue_str = "  ⚠ " + "；".join(issues) if issues else ""
        print(f"  [{i+1:02d}] {status} {q_short:<28} ({elapsed:.1f}s){issue_str}")
    
    # 汇总
    passed_count = sum(1 for r in results if r["status"] == "✅")
    print(f"\n{'='*60}")
    print(f"通过率：{passed_count}/{len(results)}")
    print(f"失败用例：{[r['id'] for r in results if r['status'] == '❌']}")
    print(f"平均耗时：{sum(r['elapsed'] for r in results)/len(results):.1f}s")
    
    return results


if __name__ == "__main__":
    run_test_suite()
```

### 6.3 结果分析与改进优先级

测试完成后，按以下框架决定修复优先级：

```
优先级判断矩阵：

                │ 影响核心功能   │ 影响体验     │ 偶发
  ──────────────┼───────────────┼─────────────┼──────
  每次都复现     │    P0 立即修   │  P1 本次修  │  P2
  多数情况复现   │    P1 本次修   │  P2 下次    │  P3
  偶尔复现       │    P2 下次修   │  P3 记录    │  -

常见问题与快速修复：

  误触发（Precision 低）
  → 修 description："明确询问…时才使用"
  → 加 System Prompt 护栏

  漏触发（Recall 低）
  → 修 description：补充用户可能的措辞/别名
  → 工具参数加容错（别名规范化）

  输出不稳定
  → 检查 temperature 是否真的是 0
  → 检查工具结果是否有随机性（mock 数据 OK，真实 API 可能不稳定）

  成本过高
  → 检查历史是否被截断
  → 检查工具 Schema 是否过于冗长
```

---

## 七、Day 29 知识速查

### 测试维度速查

| 维度 | 核心指标 | 测试方法 | 典型目标值 |
|-----|---------|---------|-----------|
| 输出稳定性 | 一致率 | 相同问题跑 3 次，对比工具触发行为 | > 90% |
| 工具触发精确率 | Precision | (正确触发) / (总触发) | > 85% |
| 工具触发召回率 | Recall | (正确触发) / (应触发) | > 80% |
| 检索命中率 | Hit Rate@3 | Top-3 中含正确段落的比例 | > 75% |
| 成本合理性 | tokens/轮 | 平均每轮输入 Token 数 | < 2000 |

### 优化工具触发准确率的优先手段

```
1. 精化 description（最有效，最快）：
   加"何时用"和"何时不用"的说明

2. System Prompt 护栏（辅助）：
   明确工具调用规则

3. 工具内参数规范化（容错）：
   别名映射、去掉"市"后缀

4. 测试驱动迭代（闭环）：
   改完立即跑测试套件，确认指标提升
```

---

## 八、实践任务

- [ ] 设计 10 组测试用例（覆盖：核心功能 3 + 应触发 2 + 不应触发 2 + 边界 2 + 健壮性 1）
- [ ] 运行 `test_project.py`，记录每道题的通过/失败结果
- [ ] 计算工具调用精确率和召回率，记录当前基线
- [ ] 找出所有失败用例的根因（描述不准确 / 别名未处理 / 其他）
- [ ] 修复 P1 问题（高优先级），重新跑测试套件，确认指标有提升
- [ ] 记录修复前后的指标对比

**产出标准**：

```
产出物：一份测试记录（Markdown 表格 + 汇总）
内容要求：
  - 10 道测试用例全部跑完
  - 明确列出通过/失败用例
  - 工具触发精确率 + 召回率已计算
  - 至少 1 个问题被发现并修复，记录修复前后对比
```

---

## 九、下一步预告

**Day 30：整理作品与总结**

Day 29 完成系统测试，Day 30 是整个 30 天学习旅程的**最终收尾**：

- **完善项目 README**：写项目介绍、功能列表、快速开始（3 步跑起来）、示例输入输出截图
- **补充运行步骤**：`git clone` → `pip install -r requirements.txt` → 配置 `.env` → `python app.py`，每步都验证过的可运行命令
- **写示例输入输出**：3–5 个有代表性的对话截图，体现工具调用链可视化
- **项目总结回顾**：从 Day 1 到 Day 29 构建了什么，学到了什么，下一步可以怎么扩展
- **产出标准**：一个陌生人能在 5 分钟内 clone 并成功运行的仓库
