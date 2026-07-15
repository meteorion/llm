# Day 6：做一个信息抽取工具

> 学习目标：掌握结构化信息抽取技巧，学会通过 Prompt 约束模型输出稳定的 JSON 字段，完成可在多个场景复用的抽取工具
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 6
>
> 🧭 导航：[← Day 5 · 文章摘要器](day05_text_summarizer.md) → Day 7 · 第 1 周复盘（待更新）

---

## 目录

- [一、结构化抽取的核心概念](#一结构化抽取的核心概念)
  - [1.1 什么是信息抽取](#11-什么是信息抽取)
  - [1.2 为什么要求输出 JSON](#12-为什么要求输出-json)
  - [1.3 抽取 vs 摘要的核心差异](#13-抽取-vs-摘要的核心差异)
- [二、输出格式约束](#二输出格式约束)
  - [2.1 字段定义的写法](#21-字段定义的写法)
  - [2.2 让模型只输出 JSON](#22-让模型只输出-json)
  - [2.3 字段为空时的兜底策略](#23-字段为空时的兜底策略)
- [三、信息抽取工具实现](#三信息抽取工具实现)
  - [3.1 简历信息抽取](#31-简历信息抽取)
  - [3.2 客服对话抽取](#32-客服对话抽取)
  - [3.3 通用抽取器](#33-通用抽取器)
- [四、抽取稳定性提升](#四抽取稳定性提升)
  - [4.1 常见失败模式](#41-常见失败模式)
  - [4.2 Few-shot 示例增强稳定性](#42-few-shot-示例增强稳定性)
  - [4.3 结果校验与兜底](#43-结果校验与兜底)
- [五、Day 6 知识速查](#五day-6-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、结构化抽取的核心概念

### 1.1 什么是信息抽取

信息抽取（Information Extraction）是从非结构化文本中识别并提取出预定义字段的过程。

```
┌─────────────────────────────────────────────────────────────────┐
│                      信息抽取的本质                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  输入：非结构化文本                                               │
│  ─────────────────────────────────────────────                  │
│  "求职者张伟，25 岁，曾在阿里巴巴担任 Python 开发工程师 3 年，      │
│   熟悉 Django、FastAPI，联系方式：zhangwei@example.com"           │
│                                                                  │
│       ↓  大模型 + 格式约束                                       │
│                                                                  │
│  输出：结构化 JSON                                               │
│  ─────────────────────────────────────────────                  │
│  {                                                               │
│    "name": "张伟",                                               │
│    "age": 25,                                                    │
│    "company": "阿里巴巴",                                        │
│    "skills": ["Python", "Django", "FastAPI"],                   │
│    "email": "zhangwei@example.com"                              │
│  }                                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

信息抽取的典型场景：

| 场景 | 输入文本 | 抽取字段 |
|------|---------|---------|
| 简历解析 | 求职者简历 | 姓名、邮箱、技能、工作年限 |
| 客服工单 | 用户留言 | 问题类型、情绪、订单号 |
| 商品描述 | 商品详情页文本 | 品牌、型号、价格、库存状态 |
| 合同信息 | 合同正文 | 甲乙方、金额、签订日期、有效期 |
| 新闻事件 | 新闻报道 | 时间、地点、人物、事件类型 |

### 1.2 为什么要求输出 JSON

从摘要到信息抽取，输出目标发生了本质变化：

```
┌──────────────────┬──────────────────────────┬──────────────────────────┐
│                  │  摘要任务                 │  抽取任务                 │
├──────────────────┼──────────────────────────┼──────────────────────────┤
│  输出类型        │  自然语言文本             │  结构化数据               │
│  下游消费        │  人直接阅读              │  程序解析 / 数据库入库      │
│  评估标准        │  语义准确性              │  字段完整、类型正确         │
│  格式约束重要性   │  中（格式影响体验）       │  高（格式决定能否用）        │
└──────────────────┴──────────────────────────┴──────────────────────────┘
```

JSON 是最适合的格式，因为：
- Python `json.loads()` 可直接解析，无需正则
- 字段名和类型可以预先定义
- 程序可以对结果做二次校验（类型检查、必填字段检查）
- 天然支持嵌套结构（如 `skills: ["Python", "Django"]`）

### 1.3 抽取 vs 摘要的核心差异

```
摘要：对原文内容的压缩和改写，允许模型做适当的语义整合

      原文（300字）→ 摘要（80字）：只要语义正确，怎么表达都行

抽取：从原文中识别并复制特定信息，字段值必须忠实来自原文

      原文 → {"姓名": "张伟"}：这个值必须原文里有，不能自行发挥
```

这就是为什么抽取任务的 Prompt 要特别强调**不允许推断**，以及**字段无法找到时返回 null** 而不是猜测一个值。

---

## 二、输出格式约束

### 2.1 字段定义的写法

清晰的字段定义是抽取稳定的基础，需要描述**字段名、类型、示例、缺失时的处理**：

```python
# 简单版：直接列字段名和类型
prompt = """
从以下简历中抽取信息，以 JSON 格式输出以下字段：
- name: 姓名（字符串）
- email: 邮箱（字符串）
- skills: 技能列表（字符串数组）
- years_exp: 工作年限（整数）

如果某字段在文本中找不到，返回 null。
只输出 JSON，不要任何说明文字。

简历内容：
{text}
"""

# 精确版：提供字段描述和类型约束
RESUME_FIELDS = {
    "name": "候选人全名（字符串，例如：张伟）",
    "age": "年龄（整数，例如：25，找不到则 null）",
    "email": "电子邮件（字符串，格式：xxx@xxx.com，找不到则 null）",
    "phone": "电话号码（字符串，保留原始格式，找不到则 null）",
    "current_company": "当前或最近的公司名称（字符串，找不到则 null）",
    "skills": "技能列表（字符串数组，即使只有一个也用数组，例如：[\"Python\"]）",
    "years_exp": "总工作年限（整数，例如：3，找不到则 null）",
    "education": "最高学历（字符串，例如 '本科' '硕士'，找不到则 null）",
}
```

### 2.2 让模型只输出 JSON

```
┌─────────────────────────────────────────────────────────────────┐
│              强制 JSON 输出的关键 Prompt 写法                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✓ 有效约束                                                      │
│  ─────────────────────────────────────────────                  │
│  "只输出 JSON，不要任何说明文字"                                   │
│  "直接输出 JSON 对象，从 { 开始，以 } 结尾"                       │
│  "不要 markdown 代码块，不要 ```json"                            │
│  "输出必须是合法的 JSON，可以直接被 json.loads() 解析"            │
│                                                                  │
│  ✗ 无效约束                                                      │
│  ─────────────────────────────────────────────                  │
│  "请输出结构化结果"  → 模型可能输出表格或列表                       │
│  "请用 JSON 格式"   → 模型可能输出 ```json ... ``` 代码块包裹     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

实际调用中还可以通过 API 参数强制 JSON 模式：

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    response_format={"type": "json_object"},  # 强制 JSON 输出
    temperature=0.0   # 抽取任务用最低温度，确定性最高
)
```

**注意**：使用 `response_format={"type": "json_object"}` 时，Prompt 中必须明确出现 "JSON" 字样，否则 API 会报错。

### 2.3 字段为空时的兜底策略

```
┌────────────────┬────────────────────────────────────────────────┐
│  策略          │  说明                                           │
├────────────────┼────────────────────────────────────────────────┤
│  返回 null     │  推荐。区分"字段存在但值不明"和"字段有值"           │
│                │  Prompt 写法："找不到则返回 null"                │
├────────────────┼────────────────────────────────────────────────┤
│  返回 ""       │  空字符串。适合字符串字段，但无法区分"原文是空"     │
│                │  和"没找到"两种情况                              │
├────────────────┼────────────────────────────────────────────────┤
│  不输出该字段   │  不推荐。程序端需要额外判断 key 是否存在，         │
│                │  否则 dict["field"] 直接 KeyError               │
└────────────────┴────────────────────────────────────────────────┘
```

---

## 三、信息抽取工具实现

### 3.1 简历信息抽取

```python
"""
简历信息抽取器
从非结构化简历文本中提取关键字段，输出 JSON
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

RESUME_PROMPT = """从以下简历文本中抽取信息，以 JSON 格式输出，字段说明如下：

- name: 候选人姓名（字符串）
- age: 年龄（整数，找不到则 null）
- email: 邮箱地址（字符串，找不到则 null）
- phone: 电话（字符串，保留原始格式，找不到则 null）
- current_company: 最近的公司名称（字符串，找不到则 null）
- skills: 技能列表（字符串数组，即使只有一个也用数组）
- years_exp: 总工作年限（整数，找不到则 null）
- education: 最高学历（字符串，例如 "本科" "硕士"，找不到则 null）

规则：
- 只提取文本中明确出现的信息，不要推断或补充
- 字段找不到时返回 null，不要猜测
- 只输出 JSON 对象，不要任何说明文字，不要 markdown 代码块

简历内容：
{resume}"""


def extract_resume(resume_text: str) -> dict:
    """从简历文本提取结构化信息"""
    prompt = RESUME_PROMPT.format(resume=resume_text.strip())

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()
    result = json.loads(raw)

    return {
        "data": result,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }


# ============== 测试示例 ==============

SAMPLE_RESUME = """
张伟，男，26 岁
邮箱：zhangwei@example.com  手机：138-0000-1234

工作经历：
2021.07 – 至今  阿里巴巴 · 后端工程师（约 3 年）
  - 负责订单系统核心模块开发
  - 主导 API 网关性能优化，QPS 提升 40%

2019.07 – 2021.06  字节跳动 · Python 开发实习生（2 年）

技能：Python、Django、FastAPI、MySQL、Redis、Docker

教育背景：
2015 – 2019  浙江大学  计算机科学  本科
"""


def main():
    print("=" * 60)
    print("简历信息抽取器")
    print("=" * 60)
    print("\n输入简历：")
    print(SAMPLE_RESUME)

    result = extract_resume(SAMPLE_RESUME)

    print("\n抽取结果：")
    print(json.dumps(result["data"], ensure_ascii=False, indent=2))
    print(f"\nToken：输入 {result['input_tokens']}，输出 {result['output_tokens']}")


if __name__ == "__main__":
    main()
```

**预期输出：**

```json
{
  "name": "张伟",
  "age": 26,
  "email": "zhangwei@example.com",
  "phone": "138-0000-1234",
  "current_company": "阿里巴巴",
  "skills": ["Python", "Django", "FastAPI", "MySQL", "Redis", "Docker"],
  "years_exp": 5,
  "education": "本科"
}
```

### 3.2 客服对话抽取

不同场景需要不同的字段定义。客服对话的目标是抽取**问题类型、情绪、关键信息**：

```python
"""
客服对话信息抽取器
从用户客服留言中提取问题分类、情绪和关键信息
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

SERVICE_PROMPT = """分析以下客服对话，提取关键信息，以 JSON 格式输出：

- issue_type: 问题类型，从以下选项中选一个："退款" "换货" "物流" "产品质量" "使用咨询" "投诉" "其他"
- sentiment: 用户情绪，"正面" "中性" 或 "负面"
- order_id: 订单号（字符串，找不到则 null）
- product_name: 涉及的商品名称（字符串，找不到则 null）
- urgency: 紧急程度，根据语气和问题性质判断，"高" "中" 或 "低"
- key_info: 用户反馈的核心问题，一句话概括（字符串，不超过 30 字）

只输出 JSON 对象，不要任何说明文字。

客服对话：
{conversation}"""


def extract_service_info(conversation: str) -> dict:
    """从客服对话中抽取结构化信息"""
    prompt = SERVICE_PROMPT.format(conversation=conversation.strip())

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ============== 测试示例 ==============

SAMPLE_CONVERSATIONS = [
    """
用户：我的订单 #202407001 的快递已经显示到了本市，但三天了还没有送到，
能帮我查一下吗？我明天就要用了。
    """,
    """
用户：这个耳机质量太差了！买了不到一个月就左耳没声音了，
要求退款，不然我就投诉你们！订单号 #202406088。
    """,
    """
用户：请问这款蓝牙耳机支持降噪功能吗？适合在嘈杂环境使用？
    """,
]


def main():
    print("=" * 60)
    print("客服对话信息抽取")
    print("=" * 60)

    for i, conv in enumerate(SAMPLE_CONVERSATIONS, 1):
        print(f"\n--- 对话 {i} ---")
        print(conv.strip())
        result = extract_service_info(conv)
        print("\n抽取结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

**预期输出（对话 2）：**

```json
{
  "issue_type": "产品质量",
  "sentiment": "负面",
  "order_id": "#202406088",
  "product_name": "耳机",
  "urgency": "高",
  "key_info": "耳机购买不足一月左耳无声音，要求退款"
}
```

### 3.3 通用抽取器

将字段定义参数化，一个抽取器支持多种场景：

```python
"""
通用信息抽取器
通过传入字段描述动态生成 Prompt，支持任意场景
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class InfoExtractor:
    """通用信息抽取器"""

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1"
        )

    def _build_prompt(self, text: str, fields: dict, extra_rules: str = "") -> str:
        field_lines = "\n".join(
            f"- {key}: {desc}" for key, desc in fields.items()
        )
        base_rules = (
            "- 只提取文本中明确出现的信息，不要推断或补充\n"
            "- 字段找不到时返回 null\n"
            "- 只输出 JSON 对象，不要任何说明文字，不要 markdown 代码块"
        )
        if extra_rules:
            base_rules += f"\n{extra_rules}"

        return (
            f"从以下文本中抽取信息，以 JSON 格式输出：\n\n"
            f"{field_lines}\n\n"
            f"规则：\n{base_rules}\n\n"
            f"文本内容：\n{text.strip()}"
        )

    def extract(self, text: str, fields: dict, extra_rules: str = "") -> dict:
        """
        提取信息

        Args:
            text: 待抽取的文本
            fields: 字段定义，例如 {"name": "姓名（字符串）", "age": "年龄（整数）"}
            extra_rules: 额外规则（追加到 Prompt 规则部分）

        Returns:
            {"data": {...}, "input_tokens": int, "output_tokens": int}
        """
        prompt = self._build_prompt(text, fields, extra_rules)

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)

        # 确保所有预期字段都存在
        for key in fields:
            if key not in data:
                data[key] = None

        return {
            "data": data,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }


# ============== 使用示例 ==============

def main():
    extractor = InfoExtractor()

    # 场景：商品描述抽取
    product_text = """
    苹果 iPhone 15 Pro，128GB，深空黑色。
    屏幕 6.1 英寸，搭载 A17 Pro 芯片。
    正品行货，全新未拆封，支持 7 天无理由退换。
    售价 ¥7999，包邮到家。
    """

    product_fields = {
        "brand": "品牌（字符串）",
        "model": "型号（字符串）",
        "storage": "存储容量（字符串，例如 128GB）",
        "color": "颜色（字符串）",
        "price": "价格（整数，单位：元，只写数字，不含货币符号）",
        "is_new": "是否全新（布尔值 true 或 false）",
    }

    print("=" * 60)
    print("场景：商品描述信息抽取")
    print("=" * 60)
    print(product_text)

    result = extractor.extract(product_text, product_fields)
    print("抽取结果：")
    print(json.dumps(result["data"], ensure_ascii=False, indent=2))
    print(f"Token：输入 {result['input_tokens']}，输出 {result['output_tokens']}")


if __name__ == "__main__":
    main()
```

---

## 四、抽取稳定性提升

### 4.1 常见失败模式

```
┌──────────────────┬──────────────────────────────────────────────┐
│  失败类型        │  示例                                         │
├──────────────────┼──────────────────────────────────────────────┤
│  格式污染        │  模型输出了 ```json ... ``` 代码块包裹          │
│                  │  或在 JSON 前加了"以下是抽取结果："             │
├──────────────────┼──────────────────────────────────────────────┤
│  字段推断        │  简历没写年龄，但模型根据毕业年份"推算"出来       │
├──────────────────┼──────────────────────────────────────────────┤
│  类型错误        │  price 应该是整数，模型返回了 "7999元"（字符串） │
├──────────────────┼──────────────────────────────────────────────┤
│  字段遗漏        │  某字段找不到时，模型不输出这个 key，            │
│                  │  程序直接 KeyError                            │
├──────────────────┼──────────────────────────────────────────────┤
│  列表/单值混淆   │  skills 期望是数组，模型返回了逗号分隔字符串      │
└──────────────────┴──────────────────────────────────────────────┘
```

**应对方法**：

- 格式污染 → 使用 `response_format={"type": "json_object"}` + Prompt 明确禁止 markdown
- 字段推断 → Prompt 强调"只提取原文明确出现的信息"
- 类型错误 → 字段描述里加上类型示例（"整数，例如：25"）
- 字段遗漏 → 提取后遍历 fields，缺失的 key 补 null
- 列表混淆 → 描述里强调"字符串数组，即使只有一个也用数组"

### 4.2 Few-shot 示例增强稳定性

对于复杂字段或格式容易出错的场景，在 Prompt 中加上示例：

```python
FEW_SHOT_PROMPT = """从以下简历中抽取信息，以 JSON 格式输出。

示例输入：
"李明，28岁，Python开发5年，现就职于腾讯，lifeisbeautiful@qq.com"

示例输出：
{{"name": "李明", "age": 28, "email": "lifeisbeautiful@qq.com", "current_company": "腾讯", "skills": ["Python"], "years_exp": 5, "education": null}}

注意：
- 找不到的字段输出 null（JSON 关键字，不是字符串 "null"）
- skills 始终是字符串数组，即使只有一个技能
- 只输出 JSON 对象，不要任何说明

现在请处理以下简历：
{resume}"""
```

Few-shot 的核心价值：**用具体的输入-输出对向模型展示期望格式**，比纯文字描述约束效果更稳定。

### 4.3 结果校验与兜底

```python
import json


def parse_json_safe(raw: str) -> dict:
    """解析 JSON，自动去除可能的 markdown 代码块包裹"""
    raw = raw.strip()

    # 去除 ```json ... ``` 或 ``` ... ``` 包裹
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]).strip()

    return json.loads(raw)


def safe_extract(client, prompt: str, fields: dict, max_retries: int = 2) -> dict:
    """带校验的抽取，JSON 解析失败时自动重试"""
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            data = parse_json_safe(raw)

            # 补全缺失字段
            for key in fields:
                if key not in data:
                    data[key] = None

            return data

        except (json.JSONDecodeError, Exception) as e:
            last_error = e
            continue

    raise RuntimeError(f"抽取失败，已重试 {max_retries} 次：{last_error}")
```

---

## 五、Day 6 知识速查

### 5.1 信息抽取 Prompt 模板

```python
EXTRACT_TEMPLATE = """从以下文本中抽取信息，以 JSON 格式输出：

{field_definitions}

规则：
- 只提取文本中明确出现的信息，不要推断
- 字段找不到时返回 null
- 直接输出 JSON 对象，不要说明文字，不要 markdown 代码块

文本：
{text}"""
```

### 5.2 关键参数对照

| 参数 | 推荐值 | 原因 |
|------|--------|------|
| `temperature` | `0.0` | 抽取要确定性，不需要创造性 |
| `response_format` | `{"type": "json_object"}` | 强制 JSON，减少格式污染 |
| `max_tokens` | 500–1000 | 根据字段数量调整，给 JSON 留足空间 |

### 5.3 JSON 解析标准写法

```python
import json

raw = response.choices[0].message.content.strip()

# 基础解析
data = json.loads(raw)

# 带兜底：补全所有预期字段
for key in expected_fields:
    if key not in data:
        data[key] = None
```

### 5.4 抽取 vs 摘要对比

```
┌──────────────┬──────────────────────────┬──────────────────────────┐
│              │  摘要任务                │  抽取任务                 │
├──────────────┼──────────────────────────┼──────────────────────────┤
│  输出格式    │  自然语言               │  JSON                    │
│  temperature │  0.1–0.3               │  0.0                     │
│  约束重点    │  长度 + 语气            │  字段名 + 类型 + 空值规则   │
│  解析方式    │  直接读                 │  json.loads()            │
│  失败处理    │  重新生成即可           │  需要校验 + 补全 + 重试    │
│  适用场景    │  内容消费（人读）        │  数据入库（程序用）         │
└──────────────┴──────────────────────────┴──────────────────────────┘
```

---

## 六、实践任务

### 任务清单

- [ ] 理解结构化抽取与摘要的核心差异（输出给人读 vs 给程序用）
- [ ] 实现简历信息抽取器，成功将结果解析为 Python 字典
- [ ] 实现客服对话抽取器（问题类型 + 情绪 + 紧急程度）
- [ ] 尝试用 `response_format={"type": "json_object"}` 强制 JSON 输出
- [ ] 给抽取结果加基础校验：确保所有预期字段都存在（缺失补 null）

### 产出标准

- 至少两个场景的抽取器可以稳定运行（简历 + 客服对话或商品描述）
- 对 3–5 个不同文本测试，字段输出稳定、JSON 解析无报错
- 遇到字段缺失时，程序不崩溃（返回 null 而非 KeyError）

---

## 七、下一步预告

Day 7 将进行**第 1 周复盘**：

- Token 为什么和成本有关？
- Temperature 为什么会影响输出？
- 为什么多轮对话必须传完整消息历史？
- 整理本周三个 Demo：命令行聊天、文章摘要、信息抽取

---

> 完成 Day 6 后，你已经能从非结构化文本中抽取出程序可直接使用的结构化数据！
>
> 下一步将在 Day 7 进行第 1 周复盘，回顾 API 调用、多轮对话、摘要和抽取这几大核心能力。
>
> ⬅️ 上一天：[Day 5 · 文章摘要器](day05_text_summarizer.md)　｜　➡️ 下一天：Day 7 · 第 1 周复盘（待更新）
