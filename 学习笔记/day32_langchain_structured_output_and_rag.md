# Day 32：用 LangChain 重新实现结构化输出与 RAG 链

> 学习目标：用 `PydanticOutputParser` 重做 Day 8 的结构化抽取，再用 LangChain `Retriever` + LCEL 拼出 Day 19 的最小 RAG 问答链，感受框架在这两类场景下的真实收益
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 32
>
> 🧭 导航：[← Day 31 · LangChain 基础：LCEL 与核心抽象](day31_langchain_lcel_basics.md) → [Day 33 · LangGraph 基础：用状态图重写 ReAct](day33_langgraph_basics_react_rewrite.md)

---

## 目录

- [一、OutputParser 体系：从手写解析到框架标准化](#一outputparser-体系从手写解析到框架标准化)
  - [1.1 Day 8 手写解析的三个步骤和它们的问题](#11-day-8-手写解析的三个步骤和它们的问题)
  - [1.2 LangChain 三种 OutputParser 对比](#12-langchain-三种-outputparser-对比)
  - [1.3 `with_structured_output()`：比 Parser 更简洁的新写法](#13-with_structured_output比-parser-更简洁的新写法)
- [二、实战：用 PydanticOutputParser 重做 Day 8 结构化抽取](#二实战用-pydanticoutputparser-重做-day-8-结构化抽取)
  - [2.1 手写版回顾（Day 8 核心代码）](#21-手写版回顾day-8-核心代码)
  - [2.2 LangChain 版：format_instructions 自动生成约束](#22-langchain-版format_instructions-自动生成约束)
  - [2.3 两版本对比：框架省掉了什么，隐藏了什么](#23-两版本对比框架省掉了什么隐藏了什么)
- [三、Retriever 接口：把向量检索包装进 LangChain](#三retriever-接口把向量检索包装进-langchain)
  - [3.1 Retriever 是什么，它封装了哪些细节](#31-retriever-是什么它封装了哪些细节)
  - [3.2 用 Chroma 创建 Retriever](#32-用-chroma-创建-retriever)
  - [3.3 手写检索 vs Retriever 的核心区别](#33-手写检索-vs-retriever-的核心区别)
- [四、实战：用 LCEL 拼出最小 RAG 链](#四实战用-lcel-拼出最小-rag-链)
  - [4.1 RAG 链的 LCEL 组装：RunnableParallel 与 RunnablePassthrough](#41-rag-链的-lcel-组装runnableparallel-与-runnablepassthrough)
  - [4.2 完整 RAG 链代码](#42-完整-rag-链代码)
  - [4.3 手写 RAG vs LangChain RAG 对比](#43-手写-rag-vs-langchain-rag-对比)
- [五、Day 32 知识速查](#五day-32-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、OutputParser 体系：从手写解析到框架标准化

### 1.1 Day 8 手写解析的三个步骤和它们的问题

Day 8 的结构化抽取分三步手写，每一步都有可能出错：

```python
# Day 8 手写流程（每步都要自己写）
response = client.chat.completions.create(...)
text = response.choices[0].message.content   # 步骤 1：取文本

data = json.loads(text)                       # 步骤 2：JSON 解析（会抛 JSONDecodeError）
resume = Resume(**data)                       # 步骤 3：Pydantic 校验（会抛 ValidationError）
```

| 步骤 | 问题 | Day 8 的处理方式 |
|-----|------|----------------|
| 取文本 | 要记住固定写法 `.choices[0].message.content` | 每次手写 |
| JSON 解析 | 模型偶尔输出 markdown 代码块，导致 `json.loads` 失败 | 手写 try/except + 清理 ` ```json ` |
| Pydantic 校验 | 字段类型不对、缺必填字段 | 手写异常捕获 + 重试逻辑 |

这三步在每个有结构化输出需求的模块里都要重写。LangChain 的 `OutputParser` 把这个模式标准化了。

### 1.2 LangChain 三种 OutputParser 对比

| Parser | 输出类型 | 适用场景 |
|--------|---------|---------|
| `StrOutputParser` | `str`（纯文本） | 普通对话、摘要，不需要解析结构 |
| `JsonOutputParser` | `dict` | 输出是 JSON 但不需要严格类型校验 |
| `PydanticOutputParser` | Pydantic 对象 | 需要类型安全、字段校验、IDE 自动补全 |

三者都是 `Runnable`，可以直接用 `|` 接在 `llm` 之后。

### 1.3 `with_structured_output()`：比 Parser 更简洁的新写法

LangChain 0.2 引入了 `with_structured_output()`，是更简洁的替代方案：

```python
from pydantic import BaseModel, Field

class Resume(BaseModel):
    name: str = Field(description="候选人姓名")
    years_of_experience: int = Field(description="工作年限")
    skills: list[str] = Field(description="技能列表")

# 直接绑定到 llm，不需要单独写 parser
structured_llm = llm.with_structured_output(Resume)
result = structured_llm.invoke("请从以下简历抽取：张三，5年经验，Python/Go...")
# result 是一个 Resume 对象，直接访问 result.name
```

| 对比维度 | `PydanticOutputParser` | `with_structured_output()` |
|---------|----------------------|--------------------------|
| **格式约束方式** | 在 Prompt 里插入 `format_instructions` 文本 | 通过 `tool_calling` 或 `json_mode` 在 API 层约束 |
| **Prompt 控制** | 完全透明，你写什么进 Prompt | 框架控制约束部分，透明度低 |
| **可组合性** | 可以参与任意 LCEL 链 | 返回的是"绑定了结构化输出的 llm"，用法略有差异 |
| **可靠性** | 依赖模型遵从 Prompt 文本 | API 层强制，更可靠（支持的模型上） |
| **适用场景** | 需要精确控制 Prompt 内容 | 快速原型，直接用最新推荐写法 |

Day 32 重点讲 `PydanticOutputParser`，因为它让你看清楚框架内部做了什么；`with_structured_output()` 是值得知道的更简洁写法。

---

## 二、实战：用 PydanticOutputParser 重做 Day 8 结构化抽取

### 2.1 手写版回顾（Day 8 核心代码）

```python
import json
from pydantic import BaseModel, Field
from openai import OpenAI

class Resume(BaseModel):
    name: str = Field(description="候选人姓名")
    years_of_experience: int = Field(description="工作年限，整数")
    skills: list[str] = Field(description="技能列表")

client = OpenAI(api_key=..., base_url="https://api.deepseek.com/v1")

def extract_resume(text: str) -> Resume:
    prompt = f"""请从以下简历中抽取信息，只输出 JSON，格式：
{{"name": "...", "years_of_experience": 整数, "skills": ["...", ...]}}

简历：
{text}"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):  # 处理 markdown 代码块
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return Resume(**json.loads(raw))
```

手写版需要自己：① 在 Prompt 里手工描述 JSON 格式；② 处理 markdown 代码块；③ 捕获 `json.JSONDecodeError` 和 `ValidationError`。

### 2.2 LangChain 版：format_instructions 自动生成约束

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

class Resume(BaseModel):
    name: str = Field(description="候选人姓名")
    years_of_experience: int = Field(description="工作年限，整数")
    skills: list[str] = Field(description="技能列表")

# 初始化模型和 parser
llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    temperature=0,
)
parser = PydanticOutputParser(pydantic_object=Resume)

# parser.get_format_instructions() 自动生成 JSON Schema 约束文本
# 效果类似 Day 8 手写的格式说明，但更严格、更标准
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个简历信息抽取助手。\n\n{format_instructions}"),
    ("human", "请从以下简历中抽取信息：\n\n{resume_text}"),
]).partial(format_instructions=parser.get_format_instructions())

# 组装链
chain = prompt | llm | parser

# 调用
resume_text = "张三，软件工程师，有 5 年工作经验，熟练使用 Python 和 Go。"
result = chain.invoke({"resume_text": resume_text})
print(result.name)                  # 张三
print(result.years_of_experience)   # 5
print(result.skills)                # ['Python', 'Go']
```

`.partial(format_instructions=...)` 把 `format_instructions` 预先填进模板，调用时只需传 `resume_text`。

**查看 `format_instructions` 的实际内容**（调试必备）：

```python
print(parser.get_format_instructions())
# 输出类似：
# The output should be formatted as a JSON instance that conforms to the JSON schema below...
# {"properties": {"name": {"description": "候选人姓名", "title": "Name", "type": "string"}, ...}}
```

这段文字会被插进 `system` 消息，替代 Day 8 里手写的格式说明。

### 2.3 两版本对比：框架省掉了什么，隐藏了什么

| 维度 | 手写版（Day 8） | LangChain 版 |
|-----|--------------|-------------|
| **格式约束文本** | 手写 JSON 示例（容易漏字段） | `parser.get_format_instructions()` 自动生成 JSON Schema |
| **取响应文本** | `response.choices[0].message.content` | `StrOutputParser` / `PydanticOutputParser` 自动提取 |
| **markdown 清理** | 手写 strip + split | Parser 内置处理 |
| **Pydantic 校验** | 手写 `Resume(**json.loads(raw))` | Parser 内部完成，抛 `OutputParserException` |
| **重试逻辑** | 手写 try/except + 重试循环 | 可套 `OutputFixingParser` 让模型自动修复输出 |
| **Prompt 透明度** | 完全看得到 | `format_instructions` 冗长，塞进 system 后 Prompt 变长 |

**OutputFixingParser**（进阶：解析失败自动修复）：

```python
from langchain.output_parsers import OutputFixingParser

# 解析失败时，会再调一次模型，让它修复不合规的输出
robust_parser = OutputFixingParser.from_llm(parser=parser, llm=llm)
chain = prompt | llm | robust_parser
```

这相当于自动化了 Day 9 里手写的"解析失败→重试"逻辑。代价是失败时额外多一次模型调用。

---

## 三、Retriever 接口：把向量检索包装进 LangChain

### 3.1 Retriever 是什么，它封装了哪些细节

LangChain 的 `Retriever` 是一个只做一件事的 `Runnable`：**接受字符串查询，返回 `List[Document]`**。

```python
# Retriever 接口签名（概念性表达）
retriever.invoke("查询字符串") -> List[Document]

# Document 对象结构
Document(
    page_content="文档片段的文本内容",
    metadata={"source": "document.pdf", "chunk_id": 3}
)
```

它封装了 Day 18 手写的三个步骤：
1. 把查询字符串向量化（调 embedding 模型）
2. 在向量库里做余弦相似度检索，取 Top-K
3. 把检索结果包装成 `Document` 列表

封装之后，RAG 链里不需要关心"用的是 FAISS 还是 Chroma"、"embedding 怎么调用"——这些都藏在 `retriever` 内部。

### 3.2 用 Chroma 创建 Retriever

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
import os

# 初始化 embedding 模型（OpenAI 兼容接口）
embeddings = OpenAIEmbeddings(
    model="text-embedding-v3",          # 或其他兼容 embedding 模型
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 方式一：从文档列表创建（小批量，适合 Demo）
docs = [
    Document(page_content="退款政策：购买后 7 天内可申请无理由退款。", metadata={"source": "policy.txt"}),
    Document(page_content="配送范围：支持全国配送，偏远地区需要 7-15 个工作日。", metadata={"source": "policy.txt"}),
]
vectorstore = Chroma.from_documents(docs, embedding=embeddings)

# 方式二：加载已有的持久化向量库（对应 Day 18 的做法）
# vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# 从向量库创建 Retriever
retriever = vectorstore.as_retriever(
    search_type="similarity",    # 相似度检索（默认）
    search_kwargs={"k": 3},      # 返回最相似的 3 条
)

# 直接调用
results = retriever.invoke("退款需要多久？")
for doc in results:
    print(doc.page_content)
    print(doc.metadata)
```

### 3.3 手写检索 vs Retriever 的核心区别

```python
# Day 18 手写版（直接操作 Chroma）
def retrieve(query: str, k: int = 3) -> list[str]:
    query_embedding = embedding_model.embed_query(query)
    results = chroma_collection.query(
        query_embeddings=[query_embedding], n_results=k
    )
    return results["documents"][0]   # list[str]，只有文本

# LangChain Retriever 版
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
docs = retriever.invoke(query)       # List[Document]，含文本 + 元数据
```

| 维度 | 手写检索 | LangChain Retriever |
|-----|---------|-------------------|
| **返回类型** | `list[str]`（只有文本） | `List[Document]`（文本 + metadata） |
| **是 Runnable** | 否，不能直接用 `\|` 组合 | 是，可以参与任意 LCEL 链 |
| **切换向量库** | 手改检索代码 | 换 `vectorstore`，`retriever` 接口不变 |
| **透明度** | 看得到每一步操作 | embedding 调用被隐藏 |

`Document` 保留 `metadata` 是关键收益：它让 RAG 链能把"这段文字来自哪个文件第几页"传递到答案里，即 Day 20 的引用溯源功能，不需要额外传参。

---

## 四、实战：用 LCEL 拼出最小 RAG 链

### 4.1 RAG 链的 LCEL 组装：RunnableParallel 与 RunnablePassthrough

Day 19 的 RAG 链逻辑：

```
用户问题 → 检索相关片段 → 拼进 Prompt（问题 + 上下文）→ 模型回答
```

LCEL 表达这个逻辑的难点：Prompt 需要两个输入（`question` 和 `context`），但链的输入只有一个（`question`）。解决方案是 `RunnableParallel`：

```python
from langchain_core.runnables import RunnablePassthrough

# 用 dict 字面量表达 RunnableParallel（LCEL 语法糖）
rag_chain = (
    {
        "context": retriever | format_docs,   # 走检索分支，处理成文字
        "question": RunnablePassthrough(),    # 原样透传用户问题
    }
    | prompt    # 接收 {"context": "...", "question": "..."} dict
    | llm
    | StrOutputParser()
)
```

`{"context": ..., "question": ...}` 这个 dict 字面量是 `RunnableParallel` 的语法糖：两个分支并行执行，结果合并成一个 dict 传给下一步。`RunnablePassthrough()` 把输入原样传出，不做任何处理——这里用来把用户问题传进 Prompt 的 `{question}` 变量。

### 4.2 完整 RAG 链代码

```python
import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document

# 初始化模型
llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0,
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-v3",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 构建向量库（Demo 用内存版，生产用持久化）
docs = [
    Document(page_content="退款政策：购买后 7 天内可申请无理由退款，超过 7 天不予退款。"),
    Document(page_content="配送说明：标准配送 3-5 个工作日，偏远地区 7-15 个工作日。"),
    Document(page_content="会员权益：黄金会员享受 9 折优惠，铂金会员享受免运费特权。"),
]
vectorstore = Chroma.from_documents(docs, embedding=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# 辅助函数：把 List[Document] 格式化成字符串
def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(doc.page_content for doc in docs)

# RAG Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", """只根据以下资料回答问题。如果资料中没有相关信息，请回答"资料中没有相关信息"，不要编造答案。

资料：
{context}"""),
    ("human", "{question}"),
])

# 组装 RAG 链
rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)

# 调用
answer = rag_chain.invoke("退款要几天？")
print(answer)
# 输出："购买后 7 天内可申请无理由退款，超过 7 天不予退款。"

# 问资料范围外的问题
answer2 = rag_chain.invoke("怎么联系客服？")
print(answer2)
# 输出："资料中没有相关信息。"
```

### 4.3 手写 RAG vs LangChain RAG 对比

| 维度 | 手写版（Day 19） | LangChain 版 |
|-----|---------------|-------------|
| **检索** | 手写 embedding + 向量库查询 | `retriever.invoke()` 一行 |
| **结果格式化** | 手写 `"\n\n".join(...)` | 相同，LangChain 版也需要 `format_docs` |
| **Prompt 组装** | 手写 f-string 拼 context + question | `ChatPromptTemplate` 声明式，变量注入 |
| **多输入处理** | 显式传 `{"context": ..., "question": ...}` | `RunnableParallel` + `RunnablePassthrough` 处理 |
| **切换向量库** | 改检索函数实现 | 换 `vectorstore`，链代码不动 |
| **流式输出** | 手写 stream 循环 | `rag_chain.stream(question)` 直接支持 |
| **调试透明度** | 每步结果直接可 `print` | 需要单独 `invoke` 中间节点查看 |

- ❌ `format_docs` 函数仍然需要手写——LangChain 没有"把 Document 列表转字符串"的内置组件，这不算缺点，只是这步业务逻辑确实因场景而异
- ✅ 流式输出、批量调用、Provider 切换，LangChain 版本都是零额外代码
- ✅ `metadata` 自动跟着 `Document` 走，为 Day 20 的引用功能做好准备

---

## 五、Day 32 知识速查

### OutputParser 选型速查

| 需求 | 推荐 Parser | 备注 |
|-----|------------|------|
| 普通文字输出 | `StrOutputParser` | 90% 的场景 |
| 输出是 JSON dict | `JsonOutputParser` | 不需要类型校验 |
| 输出需要类型安全 | `PydanticOutputParser` | 配合 Pydantic BaseModel |
| 快速原型，不关注 Prompt | `with_structured_output()` | API 层约束，更简洁 |
| 解析失败自动修复 | `OutputFixingParser` | 包装上面任意一个 |

### LCEL RAG 链组件速查

| 组件 | 模块 | 作用 |
|-----|------|------|
| `Chroma.from_documents()` | `langchain_community.vectorstores` | 从 Document 列表创建向量库 |
| `.as_retriever()` | vectorstore 方法 | 创建 Retriever，统一检索接口 |
| `RunnablePassthrough()` | `langchain_core.runnables` | 把输入原样传出，不做处理 |
| `RunnableParallel(...)` | `langchain_core.runnables` | 并行执行多个分支，结果合并为 dict |
| dict 字面量 `{"a": ..., "b": ...}` | LCEL 语法糖 | 等价于 `RunnableParallel` |
| `PydanticOutputParser` | `langchain_core.output_parsers` | 解析 JSON 并校验为 Pydantic 对象 |
| `.get_format_instructions()` | `PydanticOutputParser` 方法 | 自动生成 JSON Schema 约束文本 |

### 何时用框架组件 vs 手写

| 判断标准 | 用框架组件 | 手写更好 |
|---------|----------|---------|
| 需要流式 / 批量 / 异步 | ✅ 天然支持 | 需额外实现 |
| 需要切换 Provider 或向量库 | ✅ 只改初始化 | 改动扩散 |
| 需要精确控制 Prompt 内容 | `PydanticOutputParser` | `with_structured_output()` 不透明 |
| 调试排错优先 | 部分手写更直接 | ✅ 更透明 |
| 一次性脚本 | 过度设计 | ✅ 简单直接 |

---

## 六、实践任务

- [ ] 用 `PydanticOutputParser` 重写 Day 8 的简历信息抽取，打印 `parser.get_format_instructions()` 查看自动生成的 JSON Schema 约束，对比和 Day 8 手写格式说明的差异
- [ ] 尝试给模型返回一个故意写错格式的响应（直接 mock），观察 `PydanticOutputParser` 抛的是什么异常，再套上 `OutputFixingParser` 观察它怎么自动修复
- [ ] 用 `Chroma.from_documents()` 创建包含 5-10 条文档的向量库，验证 `retriever.invoke("...")` 返回的 `Document` 对象结构
- [ ] 用本节的完整 RAG 链代码跑两个问题：一个在资料范围内、一个不在，验证拒答逻辑生效
- [ ] 把 RAG 链改成 `rag_chain.stream(question)` 流式输出，观察 token 逐字出现的效果，对比 Day 19 手写流式输出的代码量差异

**产出标准**：两条 LangChain 链（结构化抽取 / RAG 问答）跑出和手写版一致的结果；能说清楚 `RunnablePassthrough` 和 `RunnableParallel` 各自的作用，以及 `format_instructions` 实际往 Prompt 里插了什么内容。

---

## 七、下一步预告

Day 33 进入 LangGraph：把 Day 25 手写的 `while` 循环 ReAct 工作流用 `StateGraph` 重写。Day 31–32 学的 LCEL 管道（`prompt | model | parser`）是基础——LangGraph 的 `Node` 本质上也是一个 `Runnable`，和今天的 Parser、Retriever 是同一套接口；区别是 LangGraph 在 LCEL 之上加了"循环 + 显式状态"两样东西，让 Agent 的多步推理能被图结构管理，而不是藏在 Python 的 `while` 循环里。
