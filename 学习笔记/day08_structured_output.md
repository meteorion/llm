# Day 8：结构化输出

> 学习目标：系统掌握让大模型稳定输出 JSON 的方法，学会用 JSON Schema 精确描述字段类型和必填项，掌握 Pydantic 模型与 LLM 输出的集成方式，改造 Day 6 的信息抽取脚本使其具备"可入库、可被程序消费"的严格结构化能力
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 8
>
> 🧭 导航：[← Day 7 · 第 1 周复盘](day07_week1_review.md) → [Day 9 · 输出校验与异常处理](day09_error_handling.md)

---

## 目录

- [一、结构化输出的核心概念](#一结构化输出的核心概念)
  - [1.1 为什么"大概像 JSON"不够用](#11-为什么大概像-json不够用)
  - [1.2 三种约束强度：Prompt / API 参数 / Schema](#12-三种约束强度prompt--api-参数--schema)
  - [1.3 结构化输出的完整链路](#13-结构化输出的完整链路)
- [二、JSON Schema 精确约束字段](#二json-schema-精确约束字段)
  - [2.1 JSON Schema 基本语法](#21-json-schema-基本语法)
  - [2.2 类型、必填项与枚举约束](#22-类型必填项与枚举约束)
  - [2.3 嵌套结构与数组约束](#23-嵌套结构与数组约束)
- [三、Pydantic 模型与 LLM 输出集成](#三pydantic-模型与-llm-输出集成)
  - [3.1 为什么用 Pydantic 而不是手写校验](#31-为什么用-pydantic-而不是手写校验)
  - [3.2 定义抽取模型](#32-定义抽取模型)
  - [3.3 用 Pydantic 自动生成 Prompt 约束](#33-用-pydantic-自动生成-prompt-约束)
- [四、改造信息抽取脚本](#四改造信息抽取脚本)
  - [4.1 Day 6 版本的局限](#41-day-6-版本的局限)
  - [4.2 Day 8 增强版：Schema + Pydantic 双重校验](#42-day-8-增强版schema--pydantic-双重校验)
  - [4.3 批量抽取与失败重试](#43-批量抽取与失败重试)
- [五、大规模场景下的格式一致性](#五大规模场景下的格式一致性)
  - [5.1 常见规模化痛点](#51-常见规模化痛点)
  - [5.2 稳定性工程手段](#52-稳定性工程手段)
- [六、Day 8 知识速查](#六day-8-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、结构化输出的核心概念

### 1.1 为什么"大概像 JSON"不够用

Day 6 的信息抽取已经能输出 JSON，但那是**弱约束**：靠一句"只输出 JSON"的提示词 + `response_format={"type": "json_object"}`，只能保证"这是一段合法 JSON 文本"，**不能保证字段名对、类型对、必填字段没漏**。

```
┌───────────────────────────────────────────────────────────────────┐
│              Day 6 vs Day 8：结构化程度的差异                        │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Day 6（弱约束）：                                                   │
│  模型输出 → json.loads() 能解析就算成功                              │
│  {"name": "张伟", "age": "28岁"}   ← age 应该是 int，却输出了字符串   │
│  {"nmae": "张伟"}                  ← 字段名拼写错误，程序读不到       │
│                                                                     │
│  Day 8（强约束）：                                                   │
│  模型输出 → json.loads() → Schema 校验 → Pydantic 类型转换/校验      │
│  {"name": "张伟", "age": 28}       ← 类型正确，字段名正确，才算成功    │
│  校验失败 → 明确知道哪个字段、哪种错误 → 可针对性重试                  │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

**核心区别**：Day 6 关心"能不能解析成 JSON"，Day 8 关心"解析出来的 JSON 能不能安全地喂给下游代码（入库、传给前端 API、传给另一个函数）"。当抽取结果需要写入数据库表、需要被强类型语言消费时，字段类型和结构必须**可验证**，而不是"看起来差不多"。

### 1.2 三种约束强度：Prompt / API 参数 / Schema

```
┌────────────────────────────────────────────────────────────────────────┐
│                     结构化输出的三层约束（由弱到强）                       │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  第 1 层：Prompt 层约束（软约束）                                         │
│  "请输出 JSON，包含 name、age 字段"                                       │
│  → 模型可能遵守，也可能输出多余文字或漏字段                                │
│                                                                          │
│  第 2 层：API 参数约束（中约束）                                          │
│  response_format={"type": "json_object"}                               │
│  → 保证输出是合法 JSON，但不保证字段名、类型、是否必填                     │
│                                                                          │
│  第 3 层：Schema 校验（硬约束，应用层实现）                                │
│  json.loads() 之后再用 JSON Schema / Pydantic 校验一遍                   │
│  → 类型错误、缺字段、多字段 全部能在应用层拦截，失败可重试                  │
│                                                                          │
│  结论：三层要叠加使用，缺一不可。API 层只能保证"合法 JSON"，              │
│  字段级别的正确性必须靠应用层校验兜底。                                    │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.3 结构化输出的完整链路

```
┌──────────────────────────────────────────────────────────────────────┐
│                  结构化输出完整链路（Day 8 目标形态）                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   定义 Schema（Pydantic 模型）                                         │
│         │                                                            │
│         ▼                                                            │
│   自动生成 Prompt 约束（字段名 + 类型 + 说明）                          │
│         │                                                            │
│         ▼                                                            │
│   调用 API（response_format=json_object）                              │
│         │                                                            │
│         ▼                                                            │
│   json.loads() 解析                    ── 失败 → 重试 ──┐             │
│         │ 成功                                          │             │
│         ▼                                                │             │
│   Pydantic 模型校验（类型转换 + 必填校验）── 失败 → 重试 ──┤             │
│         │ 成功                                          │             │
│         ▼                                                │             │
│   得到强类型对象，安全传给下游（入库 / API / 前端）  ◄─────┘             │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 二、JSON Schema 精确约束字段

### 2.1 JSON Schema 基本语法

JSON Schema 是描述 JSON 数据结构的标准格式，用 JSON 本身来描述"另一份 JSON 应该长什么样"。

```python
resume_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "候选人姓名"},
        "age": {"type": "integer", "description": "年龄，整数"},
        "email": {"type": "string", "description": "邮箱地址"},
    },
    "required": ["name", "age", "email"],
    "additionalProperties": False,  # 不允许模型编造 schema 之外的字段
}
```

| 关键字 | 作用 |
|--------|------|
| `type` | 数据类型：`object` / `array` / `string` / `integer` / `number` / `boolean` / `null` |
| `properties` | 定义 object 内每个字段的类型和说明 |
| `required` | 必填字段列表，缺失即视为校验失败 |
| `additionalProperties` | 设为 `False` 禁止模型输出 Schema 之外的多余字段 |
| `description` | 字段说明，会被模型用作理解字段含义的依据 |
| `enum` | 限定取值范围 |

### 2.2 类型、必填项与枚举约束

```python
feedback_schema = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["咨询", "投诉", "建议", "故障"],   # 只能是这 4 个值之一
            "description": "反馈类型",
        },
        "urgency": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
            "description": "紧急程度，1 最低，5 最高",
        },
        "resolved": {
            "type": "boolean",
            "description": "是否已解决",
        },
    },
    "required": ["category", "urgency", "resolved"],
    "additionalProperties": False,
}
```

```
┌───────────────────────────────────────────────────────────────┐
│           enum 约束前后对比（分类任务）                           │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  无 enum：                                                      │
│  "这是一条投诉信息" / "投诉类" / "complaint"  ← 模型自由发挥       │
│  下游代码用 if category == "投诉" 判断，命中率不稳定               │
│                                                                 │
│  有 enum + Prompt 提示"必须是以下之一"：                          │
│  "投诉"  ← 稳定命中枚举值，下游判断逻辑可靠                        │
│                                                                 │
└───────────────────────────────────────────────────────────────┘
```

### 2.3 嵌套结构与数组约束

真实业务数据经常是嵌套的（比如一份简历里有多段工作经历），JSON Schema 支持 `array` + 嵌套 `object`：

```python
resume_schema_nested = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "技能列表",
        },
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "years": {"type": "number"},
                },
                "required": ["company", "years"],
            },
            "description": "工作经历列表，每项包含公司和年限",
        },
    },
    "required": ["name", "skills", "experiences"],
}
```

```
{
  "name": "张伟",
  "skills": ["Python", "Go"],
  "experiences": [
    {"company": "字节跳动", "years": 3},
    {"company": "腾讯", "years": 2}
  ]
}
```

---

## 三、Pydantic 模型与 LLM 输出集成

### 3.1 为什么用 Pydantic 而不是手写校验

手写 JSON Schema 校验需要额外引入 `jsonschema` 库，且写起来啰嗦；Python 生态里更常见的做法是用 **Pydantic** 模型同时承担三个职责：

```
┌────────────────────────────────────────────────────────────────┐
│                Pydantic 模型的三重身份                            │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 数据结构定义   —— class 字段就是 Schema                       │
│  2. 类型校验器     —— 自动做类型转换/校验，失败抛 ValidationError  │
│  3. Prompt 约束来源 —— 可以从模型自动生成字段说明喂给 Prompt        │
│                                                                  │
│  一份定义，三处复用，避免 Schema 和代码"两处维护、容易失步"          │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

安装：

```bash
pip install pydantic
```

### 3.2 定义抽取模型

```python
from pydantic import BaseModel, Field
from typing import Optional

class ResumeInfo(BaseModel):
    name: str = Field(description="候选人姓名")
    age: Optional[int] = Field(default=None, description="年龄，未提及则为 null")
    company: Optional[str] = Field(default=None, description="最近工作的公司")
    skills: list[str] = Field(default_factory=list, description="技能列表")
    email: Optional[str] = Field(default=None, description="邮箱地址")
```

拿到模型输出的 JSON 字符串后，用 Pydantic 一步完成"解析 + 校验 + 类型转换"：

```python
import json

raw_json = '{"name": "张伟", "age": "28", "skills": ["Python", "Go"], "email": "wei@example.com"}'
data = json.loads(raw_json)
resume = ResumeInfo(**data)

print(resume.age, type(resume.age))
# 28 <class 'int'>   ← Pydantic 自动把字符串 "28" 转成 int
```

如果类型无法转换或缺少必填字段，Pydantic 会抛出结构化的 `ValidationError`，可以精确定位是哪个字段出了问题：

```python
from pydantic import ValidationError

try:
    ResumeInfo(name="张伟", age="二十八")   # "二十八" 无法转成 int
except ValidationError as e:
    for err in e.errors():
        print(err["loc"], err["msg"])
    # ('age',) Input should be a valid integer, unable to parse string as an integer
```

### 3.3 用 Pydantic 自动生成 Prompt 约束

Pydantic 模型自带 `model_json_schema()`，可以直接导出 JSON Schema，避免手写两份重复的定义：

```python
schema = ResumeInfo.model_json_schema()
print(json.dumps(schema, ensure_ascii=False, indent=2))
```

```json
{
  "properties": {
    "name": {"description": "候选人姓名", "title": "Name", "type": "string"},
    "age": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": null, "description": "年龄，未提及则为 null"},
    "company": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "description": "最近工作的公司"},
    "skills": {"items": {"type": "string"}, "type": "array", "description": "技能列表"},
    "email": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "description": "邮箱地址"}
  },
  "required": ["name"],
  "title": "ResumeInfo",
  "type": "object"
}
```

把这份 Schema 直接拼进 Prompt，就能让模型"看到"精确的字段类型定义，而不是靠自然语言重复描述一遍：

```python
def build_prompt(text: str, model_cls: type[BaseModel]) -> str:
    schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
    return (
        f"从以下文本中抽取信息，严格按照这个 JSON Schema 输出：\n{schema}\n\n"
        "规则：只输出 JSON 对象，不要输出 Schema 本身；找不到的字段用 null；"
        "不要输出 Schema 之外的字段。\n\n"
        f"文本：\n{text}"
    )
```

---

## 四、改造信息抽取脚本

### 4.1 Day 6 版本的局限

Day 6 的 `extract()` 函数只做了 `json.loads()` + `setdefault` 兜底，没有类型校验：

```python
# Day 6 版本 —— 只保证"是 JSON"，不保证"字段类型对"
data = json.loads(response.choices[0].message.content)
for key in fields:
    data.setdefault(key, None)
return data   # age 可能是 "28" 也可能是 28，调用方无法确定
```

### 4.2 Day 8 增强版：Schema + Pydantic 双重校验

```python
import os
import json
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)


class ResumeInfo(BaseModel):
    name: str = Field(description="候选人姓名")
    age: Optional[int] = Field(default=None, description="年龄，未提及则为 null")
    company: Optional[str] = Field(default=None, description="最近工作的公司")
    skills: list[str] = Field(default_factory=list, description="技能列表")
    email: Optional[str] = Field(default=None, description="邮箱地址")


def build_prompt(text: str, model_cls: type[BaseModel]) -> str:
    schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
    return (
        f"从以下文本中抽取信息，严格按照这个 JSON Schema 输出：\n{schema}\n\n"
        "规则：\n"
        "1. 只输出符合 Schema 的 JSON 对象，不要输出 Schema 本身\n"
        "2. 找不到的字段用 null（数组类字段用空数组 []）\n"
        "3. 不要输出 Schema 之外的字段\n"
        "4. 不要输出 markdown 代码块标记\n\n"
        f"文本：\n{text}"
    )


def extract_structured(text: str, model_cls: type[BaseModel], max_retries: int = 2) -> BaseModel:
    prompt = build_prompt(text, model_cls)
    last_error = None

    for attempt in range(1, max_retries + 1):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content

        try:
            data = json.loads(raw)
            return model_cls(**data)   # 类型校验 + 转换，一步到位
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            print(f"第 {attempt} 次尝试失败：{e}")
            continue

    raise RuntimeError(f"抽取失败，已重试 {max_retries} 次，最后一次错误：{last_error}")


if __name__ == "__main__":
    resume_text = "张伟，28岁，曾在字节跳动工作 3 年，擅长 Python 和 Go，邮箱 wei@example.com"
    result = extract_structured(resume_text, ResumeInfo)
    print(result.model_dump_json(indent=2))
    print(f"\n类型检查：age={result.age} ({type(result.age).__name__})")
```

```
第一次尝试正常时的输出：
{
  "name": "张伟",
  "age": 28,
  "company": "字节跳动",
  "skills": ["Python", "Go"],
  "email": "wei@example.com"
}

类型检查：age=28 (int)
```

**关键改进点**：

- `build_prompt` 从 Pydantic 模型自动生成 Schema 说明，不需要手写字段描述文本
- `model_cls(**data)` 一步完成类型转换和必填校验，校验失败直接抛 `ValidationError`
- `max_retries` 让"格式不对"这类可恢复错误自动重试，而不是让程序崩溃

### 4.3 批量抽取与失败重试

真实场景往往需要批量处理多条文本，且要能区分"哪些成功、哪些失败"：

```python
def batch_extract(texts: list[str], model_cls: type[BaseModel]) -> dict:
    results, failures = [], []

    for i, text in enumerate(texts):
        try:
            results.append(extract_structured(text, model_cls))
        except RuntimeError as e:
            failures.append({"index": i, "text": text, "error": str(e)})

    return {"success": results, "failed": failures}


if __name__ == "__main__":
    texts = [
        "张伟，28岁，曾在字节跳动工作 3 年，擅长 Python 和 Go",
        "李明，前端工程师，会 Vue 和 React，邮箱 li@example.com",
        "王芳",  # 信息很少，用于测试兜底能力
    ]
    report = batch_extract(texts, ResumeInfo)
    print(f"成功 {len(report['success'])} 条，失败 {len(report['failed'])} 条")
```

---

## 五、大规模场景下的格式一致性

### 5.1 常见规模化痛点

```
┌──────────────────────────────────────────────────────────────────┐
│              批量抽取上千条数据时的典型问题                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ① 偶发格式错误   —— 1000 条里有 5-10 条输出多余文字或漏字段         │
│  ② 字段类型漂移   —— 同一字段有时是 "28"，有时是 28                 │
│  ③ 枚举值跑偏     —— category 输出了 "投诉建议" 这种复合值           │
│  ④ 长文本截断     —— max_tokens 不够，JSON 输出到一半被截断          │
│  ⑤ 成本失控       —— 每条都无脑重试 3 次，成本和延迟同时爆炸          │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 稳定性工程手段

| 手段 | 说明 |
|------|------|
| **temperature=0** | 抽取任务始终用最低随机性，减少格式漂移 |
| **response_format=json_object** | API 层强制合法 JSON，减少"输出了一句解释"的情况 |
| **Pydantic 校验 + 精确重试** | 只有校验失败的记录才重试，不重试已成功的 |
| **max_tokens 留足余量** | 按字段数量估算，避免长结构被截断 |
| **枚举值二次映射** | 校验后对枚举字段做一次"最相似匹配"兜底（如模糊匹配到最近的合法值） |
| **失败记录落盘** | 把 `failed` 列表单独保存，人工或离线批次二次处理，而不是卡住整个批量任务 |
| **限流并发** | 批量调用时控制并发数，避免触发 429 限流 |

```python
def normalize_enum(value: str, allowed: list[str]) -> Optional[str]:
    """枚举值兜底：找不到精确匹配时，退化为包含关系匹配"""
    if value in allowed:
        return value
    for option in allowed:
        if option in value:
            return option
    return None
```

**核心结论**：规模化场景下，"让模型输出更规范"和"让代码更能容错"同样重要。前者靠 Prompt + Schema，后者靠 Pydantic 校验 + 重试 + 失败隔离，两者缺一都会在数据量变大后暴露问题。

---

## 六、Day 8 知识速查

### 三层约束速查

| 层级 | 手段 | 解决的问题 |
|------|------|-----------|
| Prompt 层 | 文字描述 + Schema 拼接 | 让模型"知道"该输出什么结构 |
| API 参数层 | `response_format={"type": "json_object"}` | 保证输出是合法 JSON |
| 应用层 | Pydantic 模型校验 | 保证字段类型、必填项、无多余字段 |

### 常用 Pydantic 写法速查

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Optional

class Model(BaseModel):
    required_field: str = Field(description="必填字段说明")
    optional_field: Optional[int] = Field(default=None, description="可选字段")
    list_field: list[str] = Field(default_factory=list)

# 生成 Schema
schema = Model.model_json_schema()

# 解析并校验
try:
    obj = Model(**json.loads(raw_json))
except ValidationError as e:
    print(e.errors())

# 导出
obj.model_dump()        # dict
obj.model_dump_json()   # JSON 字符串
```

### Day 8 最小模板

```
定义 Pydantic 模型 → model_json_schema() 生成约束 → 拼进 Prompt
→ API 调用（temperature=0 + json_object）→ json.loads()
→ Model(**data) 校验 → 成功则得到强类型对象，失败则重试/记入失败列表
```

---

## 七、实践任务

- [ ] 把 Day 6 的简历抽取脚本改造为使用 Pydantic 模型 + `model_json_schema()`
- [ ] 给抽取结果加上失败重试逻辑，重试 2 次仍失败则记录到失败列表
- [ ] 设计一个带 `enum` 约束的分类场景（如客服反馈分类），验证枚举值是否稳定命中
- [ ] 用一批（至少 5 条）真实/构造文本跑通批量抽取，统计成功率
- [ ] 故意构造一条会导致类型错误的输入（如年龄写成"二十八岁"），验证 `ValidationError` 能被正确捕获

**产出标准**：

- 至少成功解析 5 组结构化 JSON 输出，且每组都通过 Pydantic 类型校验
- 一份改造后的抽取脚本，包含 Schema 定义、Prompt 生成、重试逻辑三个部分

---

## 八、下一步预告

**Day 9：增加输出校验与异常处理**

Day 8 已经用 Pydantic 拦住了大部分格式问题，但校验失败之后"怎么办"还需要更系统的设计：

- JSON 解析失败、Schema 校验失败应该分别如何处理
- 重试机制的退避策略（立即重试 vs 指数退避）
- 空字段、部分字段缺失时的业务兜底策略（用默认值？标记为待人工复核？）

核心问题：当抽取脚本要跑在生产环境、面对成千上万条真实数据时，"程序不能因为一条脏数据而崩溃"是底线要求，Day 9 会把这个底线补齐。
