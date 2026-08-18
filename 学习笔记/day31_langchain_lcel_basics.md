# Day 31：LangChain 基础：LCEL 与核心抽象

> 学习目标：理解 LangChain 在原生 API 之上做了哪些抽象、LCEL 管道语法的核心机制，并通过重写 Day 4 命令行 Demo 感受框架的收益与代价
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 31
>
> 🧭 导航：[← Day 30 · 整理作品与总结](day30_project_summary.md) → [Day 32 · 用 LangChain 重新实现结构化输出与 RAG 链](day32_langchain_structured_output_and_rag.md)

---

## 目录

- [一、为什么要在原生 API 之上套一层框架](#一为什么要在原生-api-之上套一层框架)
  - [1.1 原生 API 的三个痛点](#11-原生-api-的三个痛点)
  - [1.2 框架解决了什么：统一接口与标准化链路](#12-框架解决了什么统一接口与标准化链路)
  - [1.3 框架的代价：什么时候不该用 LangChain](#13-框架的代价什么时候不该用-langchain)
- [二、核心抽象：Runnable 接口](#二核心抽象runnable-接口)
  - [2.1 Runnable 是什么](#21-runnable-是什么)
  - [2.2 LCEL 管道语法：prompt | model | parser](#22-lcel-管道语法prompt--model--parser)
  - [2.3 管道的执行过程与类型转换](#23-管道的执行过程与类型转换)
- [三、PromptTemplate 与 ChatPromptTemplate](#三prompttemplate-与-chatprompttemplate)
  - [3.1 相比手拼字符串多做了什么](#31-相比手拼字符串多做了什么)
  - [3.2 隐藏了什么：不透明的部分](#32-隐藏了什么不透明的部分)
  - [3.3 两种模板类型的使用场景](#33-两种模板类型的使用场景)
- [四、实战：重写 Day 4 命令行聊天 Demo](#四实战重写-day-4-命令行聊天-demo)
  - [4.1 手写版本回顾（Day 4 核心代码）](#41-手写版本回顾day-4-核心代码)
  - [4.2 LangChain 版本：用 LCEL 重写](#42-langchain-版本用-lcel-重写)
  - [4.3 两版本对比：框架省掉了什么，隐藏了什么](#43-两版本对比框架省掉了什么隐藏了什么)
- [五、Day 31 知识速查](#五day-31-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、为什么要在原生 API 之上套一层框架

### 1.1 原生 API 的三个痛点

Day 1–30 全程只用原生 API——这是刻意选择，目的是先理解底层（路线图的"常见误区 2"：不理解底层就重度依赖框架，后面只会拼组件不会排错）。现在切换到 LangChain，先弄清楚它解决的是什么问题。

| 痛点 | 具体表现 | 曾出现在哪几天 |
|-----|---------|--------------|
| **Provider 绑定** | 切换 DeepSeek → Qwen 要改客户端初始化、API 参数名、响应字段名 | Day 3、Day 4 |
| **链路代码重复** | 每个 Demo 都写"拼 messages → 调 API → 取 content → 解析输出"这条链 | Day 5–29 几乎每天 |
| **输出解析散落** | JSON 解析、Pydantic 校验、重试逻辑各自散落在业务代码里 | Day 8、Day 9 |

### 1.2 框架解决了什么：统一接口与标准化链路

LangChain 做了两件核心的事：

**1. 统一 Provider 接口**

```python
# 用 LangChain，切换模型只改初始化这一行
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com/v1")

# 换成 Qwen 只需改初始化，后面的链路代码不动
from langchain_community.chat_models import ChatTongyi
llm = ChatTongyi(model="qwen-turbo")
```

**2. 标准化"组装 Prompt → 调用模型 → 解析输出"链路**

```python
# 原生 API：每次手写消息拼装、调用、取字段
messages = [{"role": "user", "content": prompt}]
response = client.chat.completions.create(model=model, messages=messages)
text = response.choices[0].message.content

# LangChain LCEL：组装成管道，invoke 一次搞定
chain = prompt_template | llm | output_parser
result = chain.invoke({"question": "..."})
```

### 1.3 框架的代价：什么时候不该用 LangChain

学完好处，必须正视代价——这是路线图把 LangChain 放在 Day 31 而不是 Day 1 的原因。

| 代价 | 具体表现 |
|-----|---------|
| **抽象层增加调试难度** | 报错堆栈里有 LangChain 内部代码，难以定位是 Prompt 问题还是 API 问题 |
| **版本迭代频繁** | LangChain 0.1 → 0.2 → 0.3 破坏性变更多，生产项目要锁定版本 |
| **隐藏了 API 细节** | 不知道实际发出的 messages 长什么样，流式输出的处理方式被封装 |
| **依赖重** | `pip install langchain` 拉进来大量依赖，简单 Demo 用不上 |

**结论**：原型阶段和复杂多步流程用 LangChain 收益大；一次性脚本或需要精确控制 API 参数的场景，手写反而更清晰。

---

## 二、核心抽象：Runnable 接口

### 2.1 Runnable 是什么

LangChain 0.1 之后的核心设计：**所有组件都实现同一个 `Runnable` 接口**。

```python
# Runnable 接口的三个核心方法（所有组件都有）
component.invoke(input)              # 同步调用，返回单个结果
component.stream(input)              # 流式调用，返回 generator
component.batch([input1, input2])    # 批量调用，并行执行，返回列表
```

`PromptTemplate`、`ChatOpenAI`、`OutputParser`——它们都是 `Runnable`，因此可以用 `|` 串起来。这是 LCEL 的设计基础。

### 2.2 LCEL 管道语法：prompt | model | parser

LCEL（LangChain Expression Language）的核心是 `|` 运算符——把多个 `Runnable` 串成一条链（本质是 `RunnableSequence`）：

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有帮助的助手。"),
    ("human", "{question}"),
])
llm = ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com/v1")
parser = StrOutputParser()

chain = prompt | llm | parser  # 创建 RunnableSequence

answer = chain.invoke({"question": "Python 和 Go 哪个更适合写 CLI 工具？"})
```

`chain.stream({"question": "..."})` 直接支持流式输出，`chain.batch([...])` 支持并行批量——这些都不需要额外代码，因为 `RunnableSequence` 把每一步的流式/批量自动传播。

### 2.3 管道的执行过程与类型转换

```
chain.invoke({"question": "..."})
      ↓
prompt.invoke({"question": "..."})
  → 输出：ChatPromptValue（含 system + human 两条消息）
      ↓
llm.invoke(ChatPromptValue)
  → 输出：AIMessage（原始响应对象，含 content、response_metadata 等字段）
      ↓
parser.invoke(AIMessage)
  → 输出：str（纯文本，即 AIMessage.content）
```

每一步的类型转换是**隐式**的——这是 LCEL 的便利之处，也是出问题时难调试的原因。想看中间状态：

```python
# 调试时单独 invoke 某一步
print(prompt.invoke({"question": "..."}))  # 看实际发出的消息结构
```

---

## 三、PromptTemplate 与 ChatPromptTemplate

### 3.1 相比手拼字符串多做了什么

```python
# 手拼字符串（Day 4 风格）
messages = [
    {"role": "system", "content": "你是一个助手。"},
    {"role": "user", "content": f"请回答：{question}"},
]

# ChatPromptTemplate（LangChain 风格）
from langchain_core.prompts import ChatPromptTemplate
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个助手。"),
    ("human", "请回答：{question}"),
])
```

框架多做的事情：

| 功能 | 手写方式 | 框架提供 |
|-----|---------|---------|
| **变量占位符校验** | f-string，忘了加变量不报错 | `{question}` 缺少时抛 `KeyError` |
| **消息角色验证** | 拼错 `"sistem"` 不报错 | `("system", ...)` 创建时就验证 |
| **多轮历史插入** | 手动 `messages.extend(history)` | `MessagesPlaceholder("history")` 声明式插入 |
| **序列化** | 不支持 | `.save()` / `.load()` 保存模板 |

### 3.2 隐藏了什么：不透明的部分

```python
# 你看到的
chain.invoke({"question": "..."})

# 实际发出的 API 请求（被框架隐藏）
{
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "你是一个助手。"},
        {"role": "user", "content": "请回答：..."}
    ]
}
```

框架隐藏了：
- 实际发出的 `messages` 内容（调试时需要单独打印 `prompt.invoke(input)`）
- token 计数（`usage` 字段藏在 `AIMessage.response_metadata["token_usage"]` 里）
- 内部重试逻辑（和手写的 `try/except` 配置方式不同）

### 3.3 两种模板类型的使用场景

| 模板类型 | 适用场景 | 示例 |
|---------|---------|------|
| `PromptTemplate` | 单次文本补全（legacy completion API） | 旧版模型、非对话任务 |
| `ChatPromptTemplate` | 聊天模型（当前主流） | GPT-4、DeepSeek Chat、Qwen |

现在几乎只用 `ChatPromptTemplate`——聊天模型是主流，`PromptTemplate` 是历史遗留。

---

## 四、实战：重写 Day 4 命令行聊天 Demo

### 4.1 手写版本回顾（Day 4 核心代码）

Day 4 命令行聊天 Demo 的核心逻辑（手写版）：

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

def chat(history: list[dict], user_input: str) -> str:
    history.append({"role": "user", "content": user_input})
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=history,
        temperature=0,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    return reply

def main():
    history = [{"role": "system", "content": "你是一个有帮助的助手。"}]
    print("命令行聊天 Demo（输入 exit 退出）")
    while True:
        user_input = input("你：").strip()
        if user_input.lower() == "exit":
            break
        reply = chat(history, user_input)
        print(f"助手：{reply}\n")

if __name__ == "__main__":
    main()
```

手写版的特点：messages 列表透明可见，历史记录由代码显式维护，API 参数直接暴露。

### 4.2 LangChain 版本：用 LCEL 重写

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
import os

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有帮助的助手。"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | llm | StrOutputParser()

def main():
    history = []
    print("命令行聊天 Demo - LangChain 版（输入 exit 退出）")
    while True:
        user_input = input("你：").strip()
        if user_input.lower() == "exit":
            break
        reply = chain.invoke({"input": user_input, "history": history})
        history.append(HumanMessage(content=user_input))
        history.append(AIMessage(content=reply))
        print(f"助手：{reply}\n")

if __name__ == "__main__":
    main()
```

注意历史记录类型从 `list[dict]` 变成了 `list[HumanMessage | AIMessage]`——LangChain 用对象而不是字典表示消息。

### 4.3 两版本对比：框架省掉了什么，隐藏了什么

| 维度 | 手写版（Day 4） | LangChain 版 |
|-----|--------------|-------------|
| **代码行数** | ~25 行 | ~22 行（差距不大） |
| **messages 拼装** | 显式 `append({"role": ..., "content": ...})` | `MessagesPlaceholder` 声明式 |
| **响应取值** | `response.choices[0].message.content` | `StrOutputParser()` 自动提取 |
| **历史记录类型** | `list[dict]` | `list[HumanMessage \| AIMessage]` |
| **Provider 切换** | 需改客户端、参数名、响应字段名 | 只改 `ChatOpenAI(...)` 初始化 |
| **调试透明度** | 直接打印 messages 列表 | 需单独 `prompt.invoke(...)` 才能看实际消息 |
| **错误定位** | 堆栈直接指向业务代码 | 堆栈含 LangChain 内部层，定位慢 |

- ❌ 这个规模的 Demo，LangChain 的收益并不显著——代码量没有明显减少，调试反而更麻烦
- ✅ 框架真正的价值在 Day 33 开始的 LangGraph 多步编排场景——链路越复杂，统一接口和可组合性越值钱

---

## 五、Day 31 知识速查

### LCEL 核心组件速查

| 组件 | 模块 | 作用 |
|-----|------|------|
| `ChatPromptTemplate` | `langchain_core.prompts` | 结构化消息模板，支持变量占位符 |
| `MessagesPlaceholder` | `langchain_core.prompts` | 在模板里声明式插入历史消息列表 |
| `ChatOpenAI` | `langchain_openai` | OpenAI 兼容的聊天模型（支持 DeepSeek） |
| `StrOutputParser` | `langchain_core.output_parsers` | 从 AIMessage 提取纯文本 |
| `HumanMessage` / `AIMessage` | `langchain_core.messages` | LangChain 的消息对象（替代 dict） |

### Runnable 方法速查

| 方法 | 用途 | 返回类型 |
|-----|------|---------|
| `.invoke(input)` | 同步单次调用 | 单个结果 |
| `.stream(input)` | 流式调用 | `Iterator[chunk]` |
| `.batch([i1, i2])` | 并行批量调用 | `list` |
| `.ainvoke(input)` | 异步单次调用 | `Coroutine` |

### 手写 vs LangChain 决策表

| 场景 | 推荐 | 原因 |
|-----|------|------|
| 简单单步调用 | 手写 | 依赖少、调试直接、无框架版本风险 |
| 多步链路（RAG、Agent） | LangChain | 统一接口 + 流式/批量天然支持 |
| 精确控制 API 参数 | 手写 | 框架封装会屏蔽部分参数 |
| 跨 Provider 可移植性 | LangChain | 只改初始化，链路代码不动 |

---

## 六、实践任务

- [ ] 安装 LangChain：`pip install langchain langchain-openai langchain-core`
- [ ] 把 Day 4 的命令行聊天 Demo 用 `ChatPromptTemplate` + LCEL 管道重写一遍，确认多轮对话功能一致
- [ ] 打印 `prompt.invoke({"input": "你好", "history": []})` 查看实际生成的消息结构，和手写 messages 做对比
- [ ] 故意拼错一个模板变量名（如把 `{input}` 改成 `{user_input}`），观察报错信息和手写版本的差异
- [ ] 将 LangChain 版本改用 `chain.stream(...)` 输出，观察流式 token 逐字出现的效果

**产出标准**：两个版本（手写 / LangChain）功能一致的命令行聊天 Demo，能用对比表说清楚"框架省掉了什么、隐藏了什么"；知道如何通过单独调用 `prompt.invoke(...)` 查看实际发出的消息内容来调试。

---

## 七、下一步预告

Day 32 继续用 LangChain 重写已有功能：用 `PydanticOutputParser` 重做 Day 8 的结构化抽取，再用 `Retriever` + LCEL 拼出 Day 19 的最小 RAG 问答链。今天搞懂的 `prompt | model | parser` 管道是 Day 32 所有链路的基础——知道怎么拼，明天学的是把哪些组件换成结构化解析器或检索器。
