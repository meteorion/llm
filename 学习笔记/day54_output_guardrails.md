# Day 54：输出护栏与内容过滤

> 学习目标：理解 Guardrails 模式的核心主张——输出前再过一层独立校验，而不是完全信任模型的自我约束；掌握敏感信息泄露、越权操作、格式不合规三类典型拦截场景；实现一层可组合的输出护栏（规则匹配 + 模型分类），并演示"违规输出被拦截，替换成安全兜底回复"的完整过程
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 54
>
> 🧭 导航：[← Day 53 · Prompt 注入攻防](day53_prompt_injection_defense.md) → [Day 55 · 反馈追踪：用户反馈信号采集与评估回流](day55_feedback_tracking.md)

---

## 目录

- [一、Guardrails 模式是什么](#一guardrails-模式是什么)
  - [1.1 为什么不能完全信任模型输出](#11-为什么不能完全信任模型输出)
  - [1.2 和 Day 53 输出校验的区别：从"防一类攻击"到"通用护栏层"](#12-和-day-53-输出校验的区别从防一类攻击到通用护栏层)
- [二、需要拦截的三类典型场景](#二需要拦截的三类典型场景)
  - [2.1 敏感信息泄露](#21-敏感信息泄露)
  - [2.2 越权操作](#22-越权操作)
  - [2.3 格式不合规](#23-格式不合规)
- [三、护栏实现方式：规则匹配 vs 模型分类](#三护栏实现方式规则匹配-vs-模型分类)
  - [3.1 规则匹配：正则与关键词](#31-规则匹配正则与关键词)
  - [3.2 模型分类：用小模型做安全审查](#32-模型分类用小模型做安全审查)
  - [3.3 两种方式的对比与组合策略](#33-两种方式的对比与组合策略)
- [四、护栏层架构设计](#四护栏层架构设计)
  - [4.1 GuardrailResult 与规则链](#41-guardrailresult-与规则链)
  - [4.2 拦截后的兜底回复策略](#42-拦截后的兜底回复策略)
- [五、完整实现：给项目加一层输出护栏](#五完整实现给项目加一层输出护栏)
- [六、验证：构造违规输出，演示拦截过程](#六验证构造违规输出演示拦截过程)
- [七、Day 54 知识速查](#七day-54-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、Guardrails 模式是什么

### 1.1 为什么不能完全信任模型输出

不管 System Prompt 写得多完善、注入防御做得多严密，模型输出始终是**概率性生成**的结果——同样的输入，模型仍然存在小概率生成不合规内容的可能。Guardrails 模式的核心主张是：**把"约束模型行为"和"校验模型输出"当作两件独立的事**，前者靠 Prompt 设计尽量降低违规概率，后者靠一层独立于模型的确定性校验兜底。

```
没有护栏的链路：
  用户输入 → 模型生成 → 直接返回给用户
  （模型是唯一的把关人，一旦生成违规内容，无人拦截）

有护栏的链路：
  用户输入 → 模型生成 → 护栏层校验 → 通过则返回 / 不通过则替换成安全兜底回复
  （护栏层是独立于模型的第二道关卡，不信任模型的自我约束）
```

### 1.2 和 Day 53 输出校验的区别：从"防一类攻击"到"通用护栏层"

Day 53 已经实现过一个 `sanitize_output()`，但那是**专门针对 Prompt 注入泄露**设计的特征匹配，只覆盖"System Prompt 被泄露"这一种违规类型。Guardrails 要解决的是更通用的问题：**任何类型的违规输出都应该有统一的拦截机制**，而不是每发现一类新风险就单独写一段校验代码。

| 维度 | Day 53 的输出校验 | Day 54 的 Guardrails 层 |
|-----|------------------|------------------------|
| 目标 | 专门拦截"System Prompt 泄露" | 通用拦截敏感信息/越权操作/格式不合规等任意类型违规 |
| 结构 | 一个函数里硬编码几条正则 | 规则可插拔、可组合的护栏链 |
| 扩展性 | 加一类新风险要改函数内部 | 加一类新风险只需要注册一条新规则 |

Day 54 做的事情是把 Day 53 那种"点状校验"升级成**架构层面的通用护栏**——Day 53 是这一层护栏最早落地的一个具体规则，今天要把它纳入统一框架。

---

## 二、需要拦截的三类典型场景

### 2.1 敏感信息泄露

模型输出里可能意外包含不该暴露的内容：

```
- System Prompt 内容原文（Day 53 已覆盖的场景）
- 用户的手机号、身份证号、邮箱等 PII（模型在总结对话历史时可能整段复述）
- 内部密钥、数据库连接串等被误放进上下文的敏感字符串
- 其他用户的会话内容（多租户场景下的隔离失效）
```

### 2.2 越权操作

模型的自然语言输出里"承诺"或"暗示"了它没有权限执行、或不应该由它单方面决定的操作：

```
- "好的，我已经帮您把订单退款了"（但实际根本没有调用退款工具，属于凭空编造）
- "我已经用管理员权限帮您重置了密码"（越权行为的话术，即使工具没被真正调用，误导用户也是风险）
- 在没有走 Day 36 人工确认流程的情况下，输出内容暗示高风险操作已经完成
```

### 2.3 格式不合规

业务场景对输出格式有严格约定（如 Day 8 的结构化输出、Day 20 的引用 JSON），一旦模型输出偏离约定格式，下游解析会直接失败或产生脏数据：

```
- 约定输出 JSON，模型却在 JSON 前后加了 markdown 代码块标记或解释性文字
- 约定的必填字段缺失，或字段类型不符合 Schema
- 长度超出业务约定的上限（如摘要要求 100 字以内，模型输出了 500 字）
```

---

## 三、护栏实现方式：规则匹配 vs 模型分类

### 3.1 规则匹配：正则与关键词

```python
# guardrail/rules/pii_leak.py
import re

PII_PATTERNS = {
    "phone": r"1[3-9]\d{9}",
    "id_card": r"\d{17}[\dXx]",
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
}

def detect_pii_leak(text: str) -> list[str]:
    """返回命中的 PII 类型列表，空列表表示没有检测到泄露"""
    hits = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            hits.append(pii_type)
    return hits
```

**优点**：确定性强、延迟低、成本几乎为零；**缺点**：只能覆盖能被显式模式描述的风险，无法识别"语义上的越权承诺"这类没有固定格式的违规。

### 3.2 模型分类：用小模型做安全审查

对于规则难以覆盖的语义类风险（如"越权操作"的自然语言表述千变万化），用一次独立的小模型调用做分类：

```python
# guardrail/rules/privilege_check.py
CLASSIFIER_PROMPT = """判断下面这段客服回复是否暗示了"已经完成了某个操作"
（如退款、重置密码、修改订单），但缺少明确的工具调用依据。
只输出 JSON：{{"has_unauthorized_claim": true/false, "reason": "..."}}

客服回复：{output}
"""

def check_unauthorized_claim(output: str, executed_tools: list[str]) -> bool:
    result = call_llm(
        model="deepseek-chat",   # 用便宜的小模型做分类，对应 Day 47 的分级路由思路
        prompt=CLASSIFIER_PROMPT.format(output=output),
        temperature=0,
    )
    verdict = json.loads(result)
    if verdict["has_unauthorized_claim"] and "refund" not in executed_tools:
        return True   # 回复里说"已退款"，但 executed_tools 里没有退款工具的调用记录
    return False
```

**优点**：能识别没有固定格式的语义类风险；**缺点**：多一次模型调用带来延迟和成本（可以复用 Day 47 分级路由，用便宜模型做分类而不是原模型）。

### 3.3 两种方式的对比与组合策略

| 维度 | 规则匹配 | 模型分类 |
|-----|---------|---------|
| 适用场景 | 格式固定、可枚举的风险（PII 格式、JSON Schema 校验） | 语义类、表述多变的风险（越权承诺、隐晦的违规暗示） |
| 延迟/成本 | 极低 | 增加一次 LLM 调用的延迟和成本 |
| 准确率 | 命中的必然是真阳性，但会漏掉规则没覆盖的变体 | 覆盖面更广，但存在误判概率 |

**组合策略**：格式类和 PII 类风险用规则匹配打底（低成本、高确定性），语义类风险（越权操作）用模型分类兜底，两层校验按顺序执行，命中任意一层都触发拦截。

---

## 四、护栏层架构设计

### 4.1 GuardrailResult 与规则链

```python
# guardrail/guardrail_chain.py
from dataclasses import dataclass
from typing import Callable

@dataclass
class GuardrailResult:
    passed: bool
    violated_rule: str | None = None
    detail: str | None = None

GuardrailRule = Callable[[str, dict], GuardrailResult]

def rule_pii_leak(output: str, context: dict) -> GuardrailResult:
    hits = detect_pii_leak(output)
    if hits:
        return GuardrailResult(passed=False, violated_rule="pii_leak", detail=f"命中类型: {hits}")
    return GuardrailResult(passed=True)

def rule_format_schema(output: str, context: dict) -> GuardrailResult:
    schema = context.get("expected_schema")
    if schema is None:
        return GuardrailResult(passed=True)
    try:
        schema.model_validate_json(output)   # Pydantic v2 校验，复用 Day 8 的模型定义
        return GuardrailResult(passed=True)
    except Exception as e:
        return GuardrailResult(passed=False, violated_rule="format_invalid", detail=str(e))

def rule_unauthorized_claim(output: str, context: dict) -> GuardrailResult:
    if check_unauthorized_claim(output, context.get("executed_tools", [])):
        return GuardrailResult(passed=False, violated_rule="unauthorized_claim", detail="回复暗示了未经工具调用的操作")
    return GuardrailResult(passed=True)

# 规则链：便宜的规则匹配放前面，昂贵的模型分类放后面，命中即短路退出
GUARDRAIL_CHAIN: list[GuardrailRule] = [rule_pii_leak, rule_format_schema, rule_unauthorized_claim]

def run_guardrails(output: str, context: dict) -> GuardrailResult:
    for rule in GUARDRAIL_CHAIN:
        result = rule(output, context)
        if not result.passed:
            return result
    return GuardrailResult(passed=True)
```

规则链的设计原则是**便宜的规则匹配排在前面、昂贵的模型分类排在后面**，一旦前面的规则命中就短路返回，避免每次都跑一遍所有规则——这和 Day 49 限流里"先查便宜的本地状态，超限才拒绝"是同一个"低成本优先"的思路。

### 4.2 拦截后的兜底回复策略

```python
FALLBACK_MESSAGES = {
    "pii_leak": "抱歉，这个回答涉及需要保护的隐私信息，我无法直接展示，请换个方式提问。",
    "format_invalid": "抱歉，系统处理这次请求时出现了格式错误，请稍后重试。",
    "unauthorized_claim": "抱歉，我需要先确认相关操作是否已经完成，请稍等或联系人工客服核实。",
}

def guarded_response(raw_output: str, context: dict) -> str:
    result = run_guardrails(raw_output, context)
    if result.passed:
        return raw_output
    # 记录一条护栏拦截日志，方便后续复盘（复用 Day 44 的结构化日志字段）
    log.warning("guardrail_blocked", extra={"rule": result.violated_rule, "detail": result.detail})
    return FALLBACK_MESSAGES.get(result.violated_rule, "抱歉，这次回答暂时无法展示，请稍后重试。")
```

**兜底回复的设计原则**：按违规类型给出不同的、对用户友好的提示，而不是统一返回一句冷冰冰的"出错了"——既要保证安全，也不能让用户完全摸不着头脑。

---

## 五、完整实现：给项目加一层输出护栏

```python
# app.py
from guardrail.guardrail_chain import guarded_response

def handle_user_query(user_input: str, executed_tools: list[str], expected_schema=None) -> str:
    raw_output = call_llm(system_prompt=SYSTEM_PROMPT, user_input=user_input)   # Day 53 的强化版 System Prompt
    context = {"executed_tools": executed_tools, "expected_schema": expected_schema}
    return guarded_response(raw_output, context)
```

只需要在原有调用链路后面加一层 `guarded_response`，业务逻辑本身不用改动——这正是护栏层作为"横切关注点"的设计目标：不侵入原有的模型调用代码，只在输出侧统一拦截。

---

## 六、验证：构造违规输出，演示拦截过程

```python
# tests/test_guardrails.py
from guardrail.guardrail_chain import run_guardrails

def test_pii_leak_blocked():
    fake_output = "根据记录，您的手机号是13812345678，订单已处理。"
    result = run_guardrails(fake_output, context={})
    assert not result.passed
    assert result.violated_rule == "pii_leak"
    print(f"✅ PII 泄露被拦截：{result.detail}")

def test_unauthorized_claim_blocked():
    fake_output = "好的，我已经帮您办理了退款，预计 3 个工作日到账。"
    context = {"executed_tools": []}   # 实际没有调用过退款工具
    result = run_guardrails(fake_output, context)
    assert not result.passed
    assert result.violated_rule == "unauthorized_claim"
    print(f"✅ 越权承诺被拦截：{result.detail}")

def test_normal_output_passes():
    fake_output = "上海今天多云，气温 28 度，建议穿薄外套。"
    result = run_guardrails(fake_output, context={})
    assert result.passed
    print("✅ 正常输出未被误拦截")
```

预期输出：

```
✅ PII 泄露被拦截：命中类型: ['phone']
✅ 越权承诺被拦截：回复暗示了未经工具调用的操作
✅ 正常输出未被误拦截
```

**完整的拦截演示**：构造一次"手机号泄露"的违规输出 → `run_guardrails` 判定 `passed=False` → `guarded_response` 记录日志并返回兜底回复"抱歉，这个回答涉及需要保护的隐私信息…" → 用户看到的是安全的兜底文案，而不是原始的违规内容。

---

## 七、Day 54 知识速查

### 三类典型拦截场景

```
敏感信息泄露 → System Prompt原文 / PII / 密钥 / 其他用户会话内容
越权操作     → 编造"已完成"的高风险操作、暗示未经确认就执行了敏感动作
格式不合规   → 该输出JSON却掺杂文字、必填字段缺失、超出长度约定
```

### 护栏实现方式选型

| 风险类型 | 推荐实现方式 |
|---------|------------|
| PII / 密钥泄露 | 规则匹配（正则，格式固定） |
| 格式 / Schema 不合规 | 规则匹配（Pydantic 校验） |
| 越权操作 / 语义类风险 | 模型分类（表述多变，规则难穷举） |

### 护栏链设计原则

```
便宜的规则匹配排前面，昂贵的模型分类排后面
命中任意一条即短路退出，不用跑完所有规则
每类违规配一条对用户友好的兜底文案，而不是统一的"出错了"
拦截事件记录日志，作为后续复盘和规则调优的依据
```

---

## 八、实践任务

- [ ] 实现 `detect_pii_leak()`，构造一条包含手机号的假输出，验证被正确识别
- [ ] 用 Pydantic Schema 校验格式合规性，构造一次"该输出 JSON 却输出了自然语言"的违规样本，验证被拦截
- [ ] 实现 `check_unauthorized_claim()`，构造一条"声称已退款但未调用退款工具"的输出，验证被识别为越权承诺
- [ ] 把三条规则组装成 `GUARDRAIL_CHAIN`，验证规则按顺序执行、命中即短路
- [ ] 跑一次正常（无违规）的输出，确认没有被误拦截——护栏的误报率也是需要关注的指标

**产出标准**：能演示一次完整的"构造违规输出 → 护栏层判定不通过 → 替换成安全兜底回复"过程，且正常输出不会被误伤。

---

## 九、下一步预告

Day 55 进入**反馈追踪：用户反馈信号采集与评估回流**：今天的护栏是"系统主动挡住已知的违规类型"，但还有一类问题护栏挡不住——回答formatted正确、没有泄露、没有越权，但用户就是觉得"答得不好"。Day 55 要建立采集这类主观反馈信号的机制，并把它们回流到评估体系里，这是 Day 43 可观测性（"系统怎么执行的"）之外，"用户觉得结果好不好"这条数据链路的起点。
