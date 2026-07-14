# Day 5：做一个文章摘要器

> 学习目标：掌握 Prompt 任务约束技巧，理解输出长度控制，完成一个可用的文章摘要工具
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 5
>
> 🧭 导航：[← Day 4 · 命令行聊天 Demo](day04_cli_chat_demo.md) → Day 6 · 信息抽取工具（待更新）

---

## 目录

- [一、Prompt 任务约束](#一prompt-任务约束)
  - [1.1 为什么需要任务约束](#11-为什么需要任务约束)
  - [1.2 约束的四个维度](#12-约束的四个维度)
  - [1.3 摘要任务的典型约束](#13-摘要任务的典型约束)
- [二、输出长度控制](#二输出长度控制)
  - [2.1 Prompt 层的长度控制](#21-prompt-层的长度控制)
  - [2.2 API 参数层的长度控制](#22-api-参数层的长度控制)
  - [2.3 两种方式的区别](#23-两种方式的区别)
- [三、文章摘要器实现](#三文章摘要器实现)
  - [3.1 两个版本的摘要 Prompt](#31-两个版本的摘要-prompt)
  - [3.2 基础摘要器](#32-基础摘要器)
  - [3.3 多风格摘要器](#33-多风格摘要器)
- [四、Prompt 版本对比实验](#四prompt-版本对比实验)
  - [4.1 对比框架](#41-对比框架)
  - [4.2 实验示例](#42-实验示例)
- [五、Day 5 知识速查](#五day-5-知识速查)
- [六、实践任务](#六实践任务)

---

## 一、Prompt 任务约束

### 1.1 为什么需要任务约束

不加约束时，模型输出会很随机：

```
┌─────────────────────────────────────────────────────────────────┐
│                    无约束 vs 有约束                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  无约束 Prompt:                                                  │
│  "请总结一下这篇文章"                                             │
│                                                                  │
│  可能的问题：                                                     │
│  - 输出 100 字，也可能输出 2000 字                                │
│  - 用列表，也可能用长段落                                          │
│  - 用文言文，也可能用白话                                          │
│  - 加了很多原文没有的内容                                          │
│                                                                  │
│  有约束 Prompt:                                                  │
│  "请用 3 句话总结文章核心观点，每句不超过 30 字，                  │
│   只提炼原文内容，不添加个人判断"                                  │
│                                                                  │
│  效果：可预测、可重复、可比较                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 约束的四个维度

```
┌─────────────────────────────────────────────────────────────────┐
│                    Prompt 约束的四个维度                          │
├──────────────┬──────────────────────────────────────────────────┤
│  维度        │  示例                                             │
├──────────────┼──────────────────────────────────────────────────┤
│  内容范围    │  "只提炼文章中明确出现的信息"                        │
│              │  "不要添加背景介绍或个人评价"                        │
├──────────────┼──────────────────────────────────────────────────┤
│  输出格式    │  "用编号列表输出"                                   │
│              │  "以一段连贯的段落呈现"                             │
│              │  "输出 JSON：{title, summary, keywords}"           │
├──────────────┼──────────────────────────────────────────────────┤
│  长度限制    │  "控制在 100 字以内"                               │
│              │  "3 到 5 个要点"                                   │
│              │  "不超过原文的 20%"                                │
├──────────────┼──────────────────────────────────────────────────┤
│  语气/风格   │  "用正式书面语"                                     │
│              │  "用简单口语，适合非专业读者"                        │
│              │  "保持原文语气"                                     │
└──────────────┴──────────────────────────────────────────────────┘
```

### 1.3 摘要任务的典型约束

```python
# 最简版（几乎无约束）
prompt_v0 = "请总结这篇文章"

# 加长度约束
prompt_v1 = "请用 3 句话总结这篇文章的核心内容"

# 加格式约束
prompt_v2 = """
请提炼以下文章的要点，以编号列表输出，每条不超过 20 字：

{article}
"""

# 加内容约束
prompt_v3 = """
请总结以下文章，要求：
1. 只提炼文章中明确陈述的内容
2. 不添加原文没有的信息
3. 用 2 至 3 个要点呈现

文章：
{article}
"""

# 全约束版
prompt_v4 = """
你是一位专业编辑，擅长提炼文章核心。

请对以下文章做摘要，严格遵守规则：
- 字数：100 字以内
- 格式：一段连贯的文字，无需分点
- 内容：只提炼文章的核心观点，不添加背景或评价
- 语气：简洁、客观

文章：
{article}

摘要：
"""
```

---

## 二、输出长度控制

### 2.1 Prompt 层的长度控制

通过提示词告诉模型输出多长：

```python
# 字数限制
"请用 50 字以内概括..."
"请写一段不超过 200 字的摘要..."

# 句数限制
"请用 1 句话总结核心结论..."
"请提炼 3 至 5 个关键要点..."

# 比例限制
"摘要长度控制在原文的 10% 左右..."

# 结构限制（间接控制长度）
"请输出：标题（10 字以内）+ 摘要（100 字以内）+ 关键词（3 个）"
```

**注意**：字数约束是软约束，模型不会精确计数。要求"100 字以内"，实际可能输出 80～130 字。
比起死抠字数，更有效的做法是约束结构（几句话、几个要点）。

### 2.2 API 参数层的长度控制

通过 API 参数从 Token 层面限制输出：

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    max_tokens=200,      # 最多输出 200 个 Token（约 100～150 个汉字）
    temperature=0.3      # 温度低一些，输出更稳定
)
```

**max_tokens 对照参考**

| max_tokens | 对应汉字（粗估） | 适合场景 |
|-----------|----------------|---------|
| 50        | 约 25 字       | 标题、关键词 |
| 100       | 约 50 字       | 一句话摘要 |
| 200       | 约 100 字      | 短摘要 |
| 500       | 约 250 字      | 段落摘要 |
| 1000      | 约 500 字      | 详细摘要 |

### 2.3 两种方式的区别

```
┌─────────────────────────────────────────────────────────────────┐
│             Prompt 约束 vs max_tokens 参数                       │
├──────────────────────┬──────────────────────────────────────────┤
│  Prompt 约束          │  max_tokens 参数                         │
├──────────────────────┼──────────────────────────────────────────┤
│  软约束              │  硬截断                                    │
│  模型会尝试遵守       │  Token 到上限后强制停止                    │
│  输出语义完整         │  可能截断在句子中间                        │
│  灵活，可描述意图     │  精确，适合严格限制场景                    │
└──────────────────────┴──────────────────────────────────────────┘

最佳实践：两者配合使用
- Prompt 给方向（"请写一段 100 字左右的摘要"）
- max_tokens 做保底（max_tokens=300，防止意外超长）
```

---

## 三、文章摘要器实现

### 3.1 两个版本的摘要 Prompt

产出标准要求：同一篇文章写出至少 2 个版本的 Prompt。

```python
"""
两个版本的摘要 Prompt，面向不同使用场景
"""

# ------- Prompt A：新闻摘要版 -------
# 适合：快速了解文章主旨，阅读效率优先
PROMPT_A = """你是一位资深新闻编辑，请对以下文章进行摘要。

要求：
- 输出 3 个要点，每个要点一行
- 每条不超过 25 字
- 只提炼文章明确表达的内容
- 使用简洁的陈述句

文章：
{article}

要点："""


# ------- Prompt B：深度分析版 -------
# 适合：需要理解文章结构和逻辑，研究场景
PROMPT_B = """你是一位专业的内容分析师，请对以下文章进行深度摘要。

摘要需要包含：
1. 核心主题（1 句话，不超过 20 字）
2. 主要观点（2 至 3 个，每条 20 字以内）
3. 关键结论（1 句话，不超过 30 字）

要求：
- 结构清晰，使用上述编号格式
- 只提炼文章内容，不添加外部信息
- 语言简洁、客观

文章：
{article}

分析结果："""
```

### 3.2 基础摘要器

```python
"""
文章摘要器 - 基础版
功能：对输入文章生成摘要，支持多种 Prompt 风格
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ============== Prompt 模板 ==============

PROMPTS = {
    "brief": {
        "name": "简洁版",
        "template": """请用 1 句话（不超过 50 字）概括以下文章的核心内容：

{article}

摘要：""",
        "max_tokens": 100
    },

    "bullets": {
        "name": "要点版",
        "template": """请提炼以下文章的核心要点，以编号列表输出，共 3 至 5 条，每条不超过 25 字：

{article}

要点：""",
        "max_tokens": 300
    },

    "structured": {
        "name": "结构化版",
        "template": """你是一位专业编辑，请对以下文章做结构化摘要。

输出格式：
核心主题：（1 句话）
主要观点：（2 至 3 条，每条一行）
关键结论：（1 句话）

只提炼文章内容，不添加主观判断。

文章：
{article}""",
        "max_tokens": 400
    },

    "audience": {
        "name": "面向读者版",
        "template": """你是一位科普作者，请用通俗易懂的语言为普通读者总结以下文章，
控制在 100 字以内，避免专业术语：

{article}

摘要：""",
        "max_tokens": 250
    }
}


# ============== 摘要器 ==============

class TextSummarizer:
    """文章摘要器"""

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1"
        )

    def summarize(
        self,
        article: str,
        style: str = "bullets",
        temperature: float = 0.3
    ) -> dict:
        """
        生成摘要

        Args:
            article: 待摘要的文章
            style: 摘要风格，可选 brief / bullets / structured / audience
            temperature: 温度（摘要任务建议 0.3 以下）

        Returns:
            包含摘要结果和元信息的字典
        """
        if style not in PROMPTS:
            raise ValueError(f"未知风格: {style}，可选：{list(PROMPTS.keys())}")

        prompt_config = PROMPTS[style]
        prompt = prompt_config["template"].format(article=article)

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=prompt_config["max_tokens"],
            temperature=temperature
        )

        summary = response.choices[0].message.content.strip()

        return {
            "style": style,
            "style_name": prompt_config["name"],
            "summary": summary,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }

    def summarize_all(self, article: str) -> list:
        """用所有风格生成摘要"""
        results = []
        for style in PROMPTS:
            result = self.summarize(article, style=style)
            results.append(result)
        return results


# ============== 使用示例 ==============

SAMPLE_ARTICLE = """
人工智能大模型正在深刻改变软件开发的方式。过去，开发者需要手动编写每一行代码，
调试往往占据了大量时间。如今，借助大模型的代码生成能力，开发者可以用自然语言描述需求，
模型自动生成初始代码，开发效率提升了数倍。

然而，这并不意味着开发者可以完全依赖模型。模型生成的代码存在错误率，
需要人工复核和调试。更重要的是，系统架构设计、需求拆解和业务判断，
目前仍然需要有经验的工程师来主导。

业内专家认为，大模型最大的价值在于降低重复性工作的成本，让开发者能够把精力
集中在真正需要创造力和判断力的任务上。未来的软件开发团队，可能不是"人 vs 模型"
的竞争关系，而是"人 + 模型"的协作关系。
"""


def main():
    summarizer = TextSummarizer()

    print("=" * 60)
    print("文章摘要器")
    print("=" * 60)
    print(f"\n原文（{len(SAMPLE_ARTICLE)} 字）：")
    print(SAMPLE_ARTICLE)

    # 演示两个核心风格
    for style in ["brief", "structured"]:
        result = summarizer.summarize(SAMPLE_ARTICLE, style=style)
        print(f"\n{'=' * 60}")
        print(f"风格：{result['style_name']}")
        print("-" * 40)
        print(result["summary"])
        print(f"\nToken 消耗：输入 {result['input_tokens']}，输出 {result['output_tokens']}")


if __name__ == "__main__":
    main()
```

### 3.3 多风格摘要器

```python
"""
文章摘要器 - 多风格交互版
支持从命令行或文件读取文章，选择风格，输出摘要
"""

import os
import sys
import argparse
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


PROMPTS = {
    "brief": {
        "name": "一句话摘要",
        "template": "请用 1 句话（不超过 50 字）概括以下文章的核心内容：\n\n{article}\n\n摘要：",
        "max_tokens": 100
    },
    "bullets": {
        "name": "要点列表",
        "template": "请提炼以下文章的核心要点，以编号列表输出，共 3 至 5 条，每条不超过 25 字：\n\n{article}\n\n要点：",
        "max_tokens": 300
    },
    "structured": {
        "name": "结构化摘要",
        "template": """你是一位专业编辑，请对以下文章做结构化摘要。

输出格式：
核心主题：（1 句话）
主要观点：（2 至 3 条，每条一行）
关键结论：（1 句话）

只提炼文章内容，不添加主观判断。

文章：
{article}""",
        "max_tokens": 400
    },
    "audience": {
        "name": "通俗摘要",
        "template": "请用通俗易懂的语言为普通读者总结以下文章，控制在 100 字以内，避免专业术语：\n\n{article}\n\n摘要：",
        "max_tokens": 250
    }
}


def summarize(article: str, style: str, temperature: float = 0.3) -> dict:
    """调用 API 生成摘要"""
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )

    config = PROMPTS[style]
    prompt = config["template"].format(article=article.strip())

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=config["max_tokens"],
        temperature=temperature
    )

    return {
        "style_name": config["name"],
        "summary": response.choices[0].message.content.strip(),
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }


def read_article(source: str) -> str:
    """从文件或标准输入读取文章"""
    if source == "-":
        return sys.stdin.read()

    path = Path(source)
    if not path.exists():
        print(f"错误：文件不存在：{source}")
        sys.exit(1)

    return path.read_text(encoding="utf-8")


def interactive_mode():
    """交互模式：粘贴文章，选择风格"""
    print("=" * 60)
    print("文章摘要器（交互模式）")
    print("=" * 60)

    # 输入文章
    print("\n请粘贴文章内容（输入完成后按 Enter 输入空行结束）：")
    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    article = "\n".join(lines).strip()

    if not article:
        print("文章内容为空，退出。")
        return

    # 选择风格
    print("\n可用摘要风格：")
    styles = list(PROMPTS.keys())
    for i, style in enumerate(styles, 1):
        print(f"  {i}. {PROMPTS[style]['name']} ({style})")

    choice = input("\n请选择风格（输入数字，直接回车默认 bullets）：").strip()
    if choice == "":
        selected_style = "bullets"
    elif choice.isdigit() and 1 <= int(choice) <= len(styles):
        selected_style = styles[int(choice) - 1]
    else:
        print(f"无效选择，使用默认风格 bullets")
        selected_style = "bullets"

    # 生成摘要
    print(f"\n正在生成摘要（风格：{PROMPTS[selected_style]['name']}）...")
    result = summarize(article, selected_style)

    print("\n" + "=" * 60)
    print(f"摘要（{result['style_name']}）：")
    print("-" * 40)
    print(result["summary"])
    print("-" * 40)
    print(f"Token 消耗：输入 {result['input_tokens']}，输出 {result['output_tokens']}")


def main():
    parser = argparse.ArgumentParser(description="文章摘要器")
    parser.add_argument("file", nargs="?", help="文章文件路径（- 表示从标准输入读取）")
    parser.add_argument("--style", choices=list(PROMPTS.keys()), default="bullets",
                        help="摘要风格（默认 bullets）")
    parser.add_argument("--all", action="store_true", help="用所有风格生成摘要并对比")
    parser.add_argument("--temp", type=float, default=0.3, help="温度（默认 0.3）")

    args = parser.parse_args()

    if args.file is None:
        interactive_mode()
        return

    article = read_article(args.file)
    print(f"已读取文章，字符数：{len(article)}")

    styles_to_run = list(PROMPTS.keys()) if args.all else [args.style]

    for style in styles_to_run:
        result = summarize(article, style, temperature=args.temp)
        print(f"\n{'=' * 60}")
        print(f"风格：{result['style_name']}")
        print("-" * 40)
        print(result["summary"])
        print(f"\nToken：输入 {result['input_tokens']}，输出 {result['output_tokens']}")


if __name__ == "__main__":
    main()
```

---

## 四、Prompt 版本对比实验

### 4.1 对比框架

在同一篇文章上跑多个 Prompt，记录结果，判断哪个版本效果更好：

```python
"""
Prompt 对比实验框架
同一篇文章，多个 Prompt 版本，记录对比结果
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)


def run_prompt(article: str, prompt_template: str, label: str, max_tokens: int = 300) -> dict:
    """运行单个 Prompt 并返回结果"""
    prompt = prompt_template.format(article=article)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3
    )

    output = response.choices[0].message.content.strip()

    return {
        "label": label,
        "output": output,
        "output_len": len(output),
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }


def compare_prompts(article: str, prompt_versions: list) -> list:
    """对比多个 Prompt 版本"""
    results = []
    for version in prompt_versions:
        result = run_prompt(
            article=article,
            prompt_template=version["template"],
            label=version["label"],
            max_tokens=version.get("max_tokens", 300)
        )
        results.append(result)
    return results


def print_comparison(results: list):
    """打印对比结果"""
    print("\n" + "=" * 60)
    print("Prompt 版本对比结果")
    print("=" * 60)

    for r in results:
        print(f"\n【{r['label']}】")
        print(f"输出字数：{r['output_len']} 字 | Token：输入 {r['input_tokens']}，输出 {r['output_tokens']}")
        print("-" * 40)
        print(r["output"])

    print("\n" + "=" * 60)
    print("对比摘要")
    print("-" * 40)
    print(f"{'版本':<20} {'输出字数':>8} {'输出Token':>10}")
    print("-" * 40)
    for r in results:
        print(f"{r['label']:<20} {r['output_len']:>8} {r['output_tokens']:>10}")


# ============== 实验配置 ==============

PROMPT_VERSIONS = [
    {
        "label": "V1 - 最简版",
        "template": "请总结以下文章：\n\n{article}",
        "max_tokens": 300
    },
    {
        "label": "V2 - 加长度约束",
        "template": "请用 3 句话总结以下文章的核心内容：\n\n{article}",
        "max_tokens": 200
    },
    {
        "label": "V3 - 加格式约束",
        "template": """请提炼以下文章的要点，以编号列表输出，共 3 条，每条不超过 25 字：

{article}

要点：""",
        "max_tokens": 200
    },
    {
        "label": "V4 - 全约束版",
        "template": """你是一位专业编辑，请对以下文章做摘要。

要求：
- 控制在 80 字以内
- 一段连贯的文字
- 只提炼文章核心观点
- 语言简洁客观

文章：
{article}

摘要：""",
        "max_tokens": 200
    }
]


SAMPLE_ARTICLE = """
人工智能大模型正在深刻改变软件开发的方式。过去，开发者需要手动编写每一行代码，
调试往往占据了大量时间。如今，借助大模型的代码生成能力，开发者可以用自然语言描述需求，
模型自动生成初始代码，开发效率提升了数倍。

然而，这并不意味着开发者可以完全依赖模型。模型生成的代码存在错误率，
需要人工复核和调试。更重要的是，系统架构设计、需求拆解和业务判断，
目前仍然需要有经验的工程师来主导。

业内专家认为，大模型最大的价值在于降低重复性工作的成本，让开发者能够把精力
集中在真正需要创造力和判断力的任务上。未来的软件开发团队，可能不是"人 vs 模型"
的竞争关系，而是"人 + 模型"的协作关系。
"""


if __name__ == "__main__":
    print(f"原文字数：{len(SAMPLE_ARTICLE.strip())} 字")
    results = compare_prompts(SAMPLE_ARTICLE, PROMPT_VERSIONS)
    print_comparison(results)
```

### 4.2 实验示例

以上实验运行后，典型结果对比如下（结果因模型版本和 temperature 有所不同）：

```
原文字数：约 300 字

【V1 - 最简版】
输出字数：约 200 字 | 可能包含展开说明和主观评价

【V2 - 加长度约束】
输出字数：约 60～80 字 | 3 句话，结构清晰

【V3 - 加格式约束】
输出字数：约 70～90 字 | 编号列表，条目感强

【V4 - 全约束版】
输出字数：约 60～80 字 | 一段流畅文字，最贴近目标
```

**实验结论**：
- 约束越少，输出越不可控，字数差异大
- 加了长度和格式约束后，输出稳定性明显提升
- 约束越具体，越容易得到符合预期的结果
- 没有"最好的 Prompt"，只有"最适合当前场景的 Prompt"

---

## 五、Day 5 知识速查

### 5.1 Prompt 约束要素

| 约束类型 | 作用 | 示例写法 |
|---------|------|---------|
| 角色设定 | 锁定输出风格和视角 | "你是一位专业编辑" |
| 长度约束 | 控制输出篇幅 | "用 3 句话" / "100 字以内" |
| 格式约束 | 控制结构 | "以编号列表输出" / "输出 JSON" |
| 内容约束 | 限定信息来源 | "只提炼文章中出现的内容" |
| 语气约束 | 控制表达风格 | "简洁客观" / "通俗易懂" |

### 5.2 temperature 对摘要任务的影响

```
temperature = 0.0 ～ 0.3  →  确定性高，输出最稳定，推荐用于摘要/抽取
temperature = 0.5 ～ 0.7  →  有一定变化，适合创意写作场景
temperature = 0.8 ～ 1.0  →  随机性强，同一输入会产生差异较大的输出
```

### 5.3 摘要任务代码模板

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

def summarize(article: str) -> str:
    prompt = f"""请提炼以下文章的核心要点，以编号列表输出，共 3 条，每条不超过 25 字：

{article}

要点："""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()
```

---

## 六、实践任务

### 任务清单

- [ ] 理解 Prompt 约束的四个维度（内容、格式、长度、语气）
- [ ] 实现基础摘要器（至少一个可运行的版本）
- [ ] 写出 2 个版本的摘要 Prompt 并对比效果
- [ ] 理解 Prompt 软约束与 `max_tokens` 硬截断的区别
- [ ] 在不同 temperature 下运行同一摘要任务，观察差异

### 产出标准

- 同一篇文章，至少 2 个风格的 Prompt 都能正常输出
- 对比记录：哪个版本输出更可控、更符合预期，以及原因
- 一个可重复运行的摘要脚本

### 推荐测试文章

可以用以下类型的文章测试：
- 新闻报道（适合验证客观摘要）
- 技术博客（适合验证要点提炼）
- 产品说明（适合验证结构化摘要）
- 故事或散文（适合验证语气/风格约束）

---

## 七、下一步预告

Day 6 将学习：
- 结构化信息抽取
- 从非结构化文本中提取指定字段
- 输出格式约束：要求模型只输出 JSON

---

> 完成 Day 5 后，你已经掌握了 Prompt 约束的核心技巧，能够写出可控、稳定的摘要工具！
>
> 下一步将进入信息抽取场景，学习如何让模型输出结构化数据。
>
> ⬅️ 上一天：[Day 4 · 命令行聊天 Demo](day04_cli_chat_demo.md)　｜　➡️ 下一天：Day 6 · 信息抽取工具（待更新）