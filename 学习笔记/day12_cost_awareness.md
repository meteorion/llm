# Day 12：建立成本意识

> 学习目标：把 Token 消耗从"抽象概念"变成"可以拿数字说话的工程指标"——理解输入/输出 Token 的计费差异、上下文长度增长对成本的放大效应，学会给真实请求记录 Token 用量并估算成本，并能在"效果提升"和"成本增加"之间做量化权衡（呼应 Day 11 的 Prompt 优化实验）
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 12
>
> 🧭 导航：[← Day 11 · Prompt 优化](day11_prompt_optimization.md) [→ Day 13 · 配置管理和日志](day13_config_and_logging.md)

---

## 目录

- [一、Token 与成本的关系回顾与深化](#一token-与成本的关系回顾与深化)
  - [1.1 计费公式回顾](#11-计费公式回顾)
  - [1.2 输入 Token 与输出 Token 的价格差异](#12-输入-token-与输出-token-的价格差异)
  - [1.3 Token 消耗的常见来源](#13-token-消耗的常见来源)
- [二、上下文长度对成本的放大效应](#二上下文长度对成本的放大效应)
  - [2.1 多轮对话的 Token 累积增长模型](#21-多轮对话的-token-累积增长模型)
  - [2.2 长输入 vs 长输出：成本结构对比](#22-长输入-vs-长输出成本结构对比)
  - [2.3 RAG 场景下的成本放大效应](#23-rag-场景下的成本放大效应)
- [三、成本记录与估算实践](#三成本记录与估算实践)
  - [3.1 设计一张成本记录表](#31-设计一张成本记录表)
  - [3.2 用代码统计 Token 用量与成本](#32-用代码统计-token-用量与成本)
  - [3.3 三个常见请求的实测记录](#33-三个常见请求的实测记录)
- [四、成本优化策略](#四成本优化策略)
  - [4.1 精简 system prompt](#41-精简-system-prompt)
  - [4.2 历史截断与摘要压缩](#42-历史截断与摘要压缩)
  - [4.3 Prompt 优化的成本权衡：重新审视 Day 11](#43-prompt-优化的成本权衡重新审视-day-11)
  - [4.4 模型分级路由](#44-模型分级路由)
- [五、Day 12 知识速查](#五day-12-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、Token 与成本的关系回顾与深化

### 1.1 计费公式回顾

Day 7 已经推导过基础计费公式，Day 12 把它落到"每一次真实请求都要算一遍"的工程习惯上：

```
单次请求成本 = 输入 Token 数 × 输入单价 + 输出 Token 数 × 输出单价
```

关键点：**这是两个独立的计费维度**，输入和输出必须分开统计，不能只看"这次对话感觉挺长的"这种模糊印象。API 响应体里的 `usage` 字段就是为了让你精确拿到这两个数字：

```python
response = client.chat.completions.create(model="deepseek-chat", messages=messages)

usage = response.usage
print(f"输入 Token：{usage.prompt_tokens}")
print(f"输出 Token：{usage.completion_tokens}")
print(f"总 Token：{usage.total_tokens}")
```

不要自己用字符数估算成本——`usage` 字段是模型服务端真实计费依据，任何本地估算（无论是字符数除以 2 还是用 `tiktoken`）都只能用于**下单前的预估**，真实扣费永远以 `usage` 为准。

### 1.2 输入 Token 与输出 Token 的价格差异

多数大模型 API 的输出单价明显高于输入单价（生成每个 Token 都需要一次完整的前向推理，而输入是一次性编码），下表是一个**示例价格结构**（具体数字请以你使用的平台官网当前价格为准，此处只演示"差异有多大"这件事）：

| 类型 | 相对倍率（示意） | 原因 |
|------|-----------------|------|
| 输入 Token（缓存未命中） | 1× | 一次性编码，计算量相对小 |
| 输入 Token（命中缓存，部分平台支持） | 0.1×～0.5× | 重复的 system prompt / 历史前缀可以复用计算结果 |
| 输出 Token | 2×～4× | 逐 Token 自回归生成，每个 Token 都要过一次完整前向计算 |

```
┌──────────────────────────────────────────────────────────────────┐
│                  为什么"控制输出长度"是最直接的降本手段              │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  同样是节省 100 个 Token：                                         │
│                                                                    │
│  精简 system prompt 100 Token  → 省 100 × 输入单价                  │
│  让模型少输出 100 Token         → 省 100 × 输出单价（通常贵 2-4 倍） │
│                                                                    │
│  结论：Day 5 讲的"max_tokens 兜底 + 输出长度约束"                    │
│  不仅是为了控制格式，也是最有性价比的成本优化手段之一                  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 Token 消耗的常见来源

Day 7（Q36）已经列过四个来源，Day 12 用一张更完整的责任表把它们和"谁该优化"对应起来：

| 来源 | 占比特点 | 谁来控制 | 对应 Day |
|------|---------|---------|---------|
| system prompt | 每次请求固定重复计费 | Prompt 设计者 | Day 4 |
| 消息历史 | 随对话轮数线性增长 | 历史管理策略 | Day 4 |
| Few-shot 示例 | 一次性但持续存在于每次请求 | Prompt 设计者 | Day 11 |
| 输入文档/检索片段 | RAG 场景下可能占输入 80%+ | 切分与检索策略 | Day 15+（预告） |
| 输出长度 | 未加约束时不可控 | max_tokens + 输出约束 | Day 5 |

---

## 二、上下文长度对成本的放大效应

### 2.1 多轮对话的 Token 累积增长模型

Day 4 讲过"每次请求都要传完整历史"，这个设计决定了多轮对话的成本增长曲线不是线性的，而是**近似平方级**：

```
第 1 轮：messages 长度 = L（system + 第1轮 user）        输入 Token ≈ L
第 2 轮：messages 长度 = L + 2 条（上轮 assistant + 本轮 user）  输入 Token ≈ 2L
第 3 轮：messages 长度 ≈ 3L                                    输入 Token ≈ 3L
...
第 N 轮：输入 Token ≈ N × L

N 轮对话的总输入 Token 消耗 = L + 2L + 3L + ... + NL = L × N(N+1)/2
```

```python
def total_input_tokens(per_turn_tokens: int, n_turns: int) -> int:
    """N 轮对话中，输入 Token 的总消耗（不含输出），近似 O(N^2) 增长"""
    return per_turn_tokens * n_turns * (n_turns + 1) // 2

print(total_input_tokens(100, 5))    # 1500
print(total_input_tokens(100, 20))   # 21000  ← 轮数翻 4 倍，总消耗翻 14 倍
```

**核心结论**：多轮对话的总成本不是"每轮成本 × 轮数"，而是随轮数呈平方级增长——这正是 Day 4 讲的滑动窗口、Day 9 讲的历史截断在成本层面的真正意义：不截断的话，对话进行到第 50 轮时，单轮的输入 Token 消耗可能已经是第 1 轮的 50 倍。

### 2.2 长输入 vs 长输出：成本结构对比

```
┌───────────────────────────────────────────────────────────────────┐
│              两种"变贵"的方式，优化思路完全不同                        │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  场景 A：长输入，短输出（如文档问答、长文摘要）                          │
│  输入 5000 Token + 输出 200 Token                                   │
│  → 成本主要由输入决定，优化方向：减少输入（切分、检索、只喂相关片段）      │
│                                                                     │
│  场景 B：短输入，长输出（如代码生成、长文写作）                          │
│  输入 200 Token + 输出 3000 Token                                   │
│  → 成本主要由输出决定，优化方向：约束输出长度、拆分任务分步生成            │
│                                                                     │
│  场景 C：长输入 + 长输出（如带大量历史的多轮技术讨论）                    │
│  → 两头都要控制，是成本最容易失控的场景                                │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

判断一个请求"贵在哪"，第一步永远是拆开看 `prompt_tokens` 和 `completion_tokens` 各自的数值，而不是只看 `total_tokens`——两种场景的优化方向完全不同，混在一起看容易用错力气。

### 2.3 RAG 场景下的成本放大效应

Day 12 虽然还没正式进入 RAG（Day 15 起），但成本视角提前预警一个后续会遇到的坑：RAG 把"检索到的文档片段"也塞进了输入，如果检索策略不当（比如 Top-K 设得过大、Chunk 切得过长），**输入 Token 会远超预期**：

```
一次 RAG 请求的输入构成：
system prompt（200） + 检索片段 Top-5 × 每片段 500 Token（2500） + 用户问题（50）
= 输入 Token ≈ 2750，是普通问答请求的 10 倍以上
```

这是 Day 15 之后要重点权衡的问题（Top-K 数量、Chunk 大小都直接影响成本），Day 12 先建立"输入 Token 大头往往在检索片段而不在用户问题本身"这个直觉。

---

## 三、成本记录与估算实践

### 3.1 设计一张成本记录表

用于沉淀"日常请求到底花多少钱"的最小字段集合：

| 字段 | 说明 | 示例 |
|------|------|------|
| 请求类型 | 属于哪个功能场景 | 摘要 / 抽取 / 多轮对话 |
| 输入 Token | `usage.prompt_tokens` | 320 |
| 输出 Token | `usage.completion_tokens` | 150 |
| 输入单价 | 每百万 Token 价格 | ¥1 / 百万 Token |
| 输出单价 | 每百万 Token 价格 | ¥2 / 百万 Token |
| 单次成本 | 按公式计算 | ¥0.00062 |
| 备注 | 是否命中缓存、是否多轮等 | 首轮，无历史 |

### 3.2 用代码统计 Token 用量与成本

```python
import os
import json
from dataclasses import dataclass, field
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

# 价格以官网当前公布的价格为准，这里用一组示例数字演示计算方式
PRICING = {
    "deepseek-chat": {
        "input_per_million": 1.0,   # 元 / 百万 Token
        "output_per_million": 2.0,
    }
}


@dataclass
class CostRecord:
    label: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float = field(init=False)

    def __post_init__(self):
        price = PRICING[self.model]
        self.cost = (
            self.input_tokens * price["input_per_million"] / 1_000_000
            + self.output_tokens * price["output_per_million"] / 1_000_000
        )


def call_and_record(label: str, messages: list, model: str = "deepseek-chat") -> CostRecord:
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    usage = response.usage
    record = CostRecord(
        label=label,
        model=model,
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
    )
    return record


def print_cost_table(records: list[CostRecord]):
    print(f"{'请求类型':<12}{'输入Token':>10}{'输出Token':>10}{'成本(元)':>12}")
    total = 0.0
    for r in records:
        print(f"{r.label:<12}{r.input_tokens:>10}{r.output_tokens:>10}{r.cost:>12.6f}")
        total += r.cost
    print("-" * 44)
    print(f"{'合计':<32}{total:>12.6f}")
```

这个最小实现和 Day 8/9 的思路一致：用 `dataclass` 把"一次请求的成本"变成一个结构化对象，而不是散落的几个变量，方便后续批量统计和写入 CSV / 数据库做长期观测。

### 3.3 三个常见请求的实测记录

选择前几天做过的三类典型请求，实际跑一遍并记录 `usage`：

```python
if __name__ == "__main__":
    records = []

    # 场景 1：多轮聊天（Day 4）——历史逐轮累积
    chat_messages = [
        {"role": "system", "content": "你是一个乐于助人的助手。"},
        {"role": "user", "content": "帮我解释一下装饰器"},
    ]
    records.append(call_and_record("多轮聊天-第1轮", chat_messages))

    # 场景 2：文章摘要（Day 5）——长输入，短输出
    article = "（此处替换为一篇 800 字左右的新闻文章正文）" * 1
    summarize_messages = [
        {"role": "user", "content": f"用 100 字以内总结以下文章的核心内容：\n\n{article}"}
    ]
    records.append(call_and_record("文章摘要", summarize_messages))

    # 场景 3：信息抽取（Day 6）——短输入，结构化短输出
    resume_text = "张伟，28岁，5年 Python 开发经验，电话 138xxxx1234"
    extract_messages = [
        {
            "role": "user",
            "content": (
                "从以下文本抽取姓名、年龄、电话，只输出 JSON：\n\n" + resume_text
            ),
        }
    ]
    records.append(call_and_record("信息抽取", extract_messages))

    print_cost_table(records)
```

一次典型运行的记录示例（数值会因模型实际输出长度有所浮动，重点是**表格结构和数量级**，而不是死记具体数字）：

```
请求类型      输入Token   输出Token     成本(元)
多轮聊天-第1轮      28        180    0.000388
文章摘要           620        85    0.000790
信息抽取            45        32    0.000109
--------------------------------------------
合计                                 0.001287
```

从这张表能直接读出结论：**文章摘要这类"长输入任务"的成本主要由输入 Token 决定**（620 输入 vs 85 输出），而**信息抽取这类"短输入短输出任务"整体成本最低**——这与 2.2 节的理论分析完全对应，实测数据把抽象的成本模型变成了可以拿给团队看的具体数字。

---

## 四、成本优化策略

### 4.1 精简 system prompt

```
┌─────────────────────────────────────────────────────────────────┐
│                  system prompt 是"隐藏的固定成本"                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  冗长版（180 Token）：                                             │
│  "你是一个非常专业、经验丰富、态度友善、乐于助人的智能助手，              │
│  请你在回答问题时始终保持耐心和专业，尽量提供详尽的解释，                │
│  同时注意语言简洁，避免啰嗦，如果遇到你不知道的问题，请诚实告知..."       │
│                                                                   │
│  精简版（20 Token）：                                              │
│  "你是专业助手，回答准确简洁，不确定时明确说明。"                       │
│                                                                   │
│  差异：多轮对话中 system prompt 每轮都重复计费，                       │
│  100 轮对话下，160 Token 的差异会被放大成 16000 Token 的累积浪费        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 历史截断与摘要压缩

直接复用 Day 4/Day 9 已经实现的截断策略，Day 12 只是换一个视角重新看它——**它首先是成本控制手段，其次才是"防止超出上下文窗口"的兜底手段**：

```python
def truncate_messages(messages: list, max_turns: int = 6) -> list:
    system = [m for m in messages if m["role"] == "system"]
    others = [m for m in messages if m["role"] != "system"]
    return system + others[-(max_turns * 2):]
```

结合 2.1 节的平方级增长模型，`max_turns=6` 相比不截断，在第 30 轮时能把输入 Token 消耗从 `30 × L` 压到固定的 `6 × L` 左右，节省幅度随对话变长而越来越显著。

### 4.3 Prompt 优化的成本权衡：重新审视 Day 11

Day 11 的 V1 → V2 → V3 实验只看了准确率和稳定性两个维度，Day 12 补上第三个维度——**成本**，才能看到完整权衡：

| 版本 | 平均输入 Token（估算） | 准确率 | 稳定性 | 每次提升花费的 Token |
|------|----------------------|--------|--------|---------------------|
| V1（极简） | 40 | 40% | 60% | 基准 |
| V2（+角色+规则） | 120（+80） | 80%（+40pp） | 87%（+27pp） | 80 Token 换 40pp 准确率提升，性价比高 |
| V3（+Few-shot） | 220（+100） | 100%（+20pp） | 100%（+13pp） | 100 Token 换 20pp 准确率提升，性价比降低但仍值得 |

```python
def cost_per_accuracy_point(extra_tokens: int, accuracy_gain_pp: float) -> float:
    """每提升 1 个百分点准确率，需要额外付出多少 Token —— 数值越小，这次优化的性价比越高"""
    return extra_tokens / accuracy_gain_pp if accuracy_gain_pp > 0 else float("inf")

print(cost_per_accuracy_point(80, 40))   # V1→V2：2.0 Token/pp
print(cost_per_accuracy_point(100, 20))  # V2→V3：5.0 Token/pp
```

**结论**：V1→V2 的性价比明显高于 V2→V3。如果这是一个成本极度敏感、允许 90% 左右准确率的场景（比如粗筛工单优先级），停在 V2 可能是更合理的工程决策；如果这是一个错误代价很高的场景（比如资金相关的紧急程度判断），V3 那额外的 100 Token 换来的最后 20 个百分点准确率仍然值得付出。**是否要为最后一点准确率提升买单，取决于这个任务出错的业务代价，而不是"能不能再优化一点"。**

### 4.4 模型分级路由

成本优化的另一个维度是"用最便宜、够用的模型处理简单任务"：

```
┌───────────────────────────────────────────────────────────────────┐
│                      按任务难度分级选模型                              │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  简单任务（分类、简单抽取、格式转换）                                    │
│  → 用轻量/低价模型（如 xxx-mini 系列），成本可能只有旗舰模型的 1/10-1/20  │
│                                                                     │
│  复杂任务（多步推理、代码生成、创意写作）                                 │
│  → 用旗舰模型，为效果买单                                              │
│                                                                     │
│  实践做法：先用轻量模型跑一遍，输出附带置信度（参考 Day 10 的                │
│  Self-Consistency），低置信度的样本再升级到旗舰模型复核 ——              │
│  这是生产级系统常用的"模型路由"思路的最小雏形                            │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

---

## 五、Day 12 知识速查

### 成本构成速查

| 概念 | 关键公式/结论 |
|------|--------------|
| 单次请求成本 | 输入 Token × 输入单价 + 输出 Token × 输出单价 |
| 输出通常更贵 | 输出单价常是输入单价的 2-4 倍，控制输出长度是高性价比优化 |
| N 轮对话总输入消耗 | 近似 `L × N(N+1)/2`，平方级增长，必须靠截断/压缩控制 |
| Prompt 优化的成本视角 | 额外 Token / 准确率提升百分点，越小性价比越高 |

### 优化手段速查

| 手段 | 对应环节 | 收益类型 |
|------|---------|---------|
| 精简 system prompt | 固定输入成本 | 每轮都省 |
| 历史截断/摘要压缩 | 随轮数增长的输入成本 | 长对话中收益指数放大 |
| 输出长度约束（Prompt + max_tokens） | 输出成本（通常更贵） | 单次收益最直接 |
| 模型分级路由 | 简单任务的整体成本 | 大规模批量场景收益最明显 |

### 最小模板

```python
@dataclass
class CostRecord:
    input_tokens: int
    output_tokens: int
    cost: float = field(init=False)
    def __post_init__(self):
        self.cost = self.input_tokens * IN_PRICE / 1e6 + self.output_tokens * OUT_PRICE / 1e6
# 每次调用后用 response.usage 填充，累积记录成本记录表
```

---

## 六、实践任务

- [ ] 选择 3 个此前做过的真实请求场景（如聊天、摘要、抽取），实际调用并读取 `response.usage`，记录输入/输出 Token
- [ ] 用当前使用平台官网公布的最新价格，计算这 3 个请求各自的单次成本
- [ ] 用 2.1 节的公式，估算一次 20 轮不截断的多轮对话总输入 Token 消耗，并对比加上 `max_turns=6` 截断后的消耗差异
- [ ] 结合 Day 11 的 V1/V2/V3 实验数据，计算每个版本"每提升 1 个百分点准确率所需的额外 Token"，判断哪个版本性价比最高
- [ ] 整理成一张成本记录表（至少包含请求类型、输入/输出 Token、单次成本三列）

**产出标准**：

- 一张至少覆盖 3 类真实请求的成本记录表，附带简单结论（哪类请求最贵、贵在输入还是输出）

---

## 七、下一步预告

**Day 13：补配置管理和日志**

Day 12 建立了"用数字衡量成本"的意识，Day 13 会补上另一块容易被忽视的工程基本功——把项目从"能跑的脚本"变成"能维护的项目"：

- 用环境变量和 `.env` 彻底移除代码里硬编码的 API Key
- 程序启动时输出必要的日志（模型名、关键配置、请求耗时）
- 为什么"输出校验"比"提示模型小心点"更可靠这件事，同样适用于"配置管理"——不能靠人记住不要把 Key 提交到 Git，而要靠 `.gitignore` 和环境变量在机制上杜绝这个风险

核心问题：Day 12 学会了"记录成本"，Day 13 要解决"这些记录（日志、Token 统计、配置）应该沉淀在哪里、以什么形式留存，才能在项目变大之后仍然可维护"。
