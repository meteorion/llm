# Day 68：FastAPI 后端工程

> 学习目标：理解为什么要把 LLM/RAG/Agent 应用从"界面里直接调用"升级为"独立后端 API 服务"；掌握 FastAPI 的路径操作、Pydantic 请求/响应模型、依赖注入三个核心概念；给已有项目包一层带流式输出的 FastAPI 后端，用 Swagger UI 测试通过
>
> 📚 所属阶段：**深化阶段 · 补充篇（技能查缺补漏）**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) 第七节 · Day 68
>
> 🧭 导航：[← Day 67 · 第 11 周复盘 + 深化阶段总结](day67_week11_review_and_deepening_summary.md) → [Day 69 · Claude Code Skills 教程](day69_claude_code_skills.md)

---

## 目录

- [一、为什么需要独立后端服务](#一为什么需要独立后端服务)
  - [1.1 Day 26 Gradio 方案的耦合问题](#11-day-26-gradio-方案的耦合问题)
  - [1.2 FastAPI 解决的三个问题](#12-fastapi-解决的三个问题)
- [二、FastAPI 核心概念速览](#二fastapi-核心概念速览)
  - [2.1 路径操作](#21-路径操作)
  - [2.2 请求/响应模型：复用 Pydantic](#22-请求响应模型复用-pydantic)
  - [2.3 依赖注入](#23-依赖注入)
- [三、把 LLM 调用包装成 API 端点](#三把-llm-调用包装成-api-端点)
  - [3.1 基础同步端点](#31-基础同步端点)
  - [3.2 流式输出：StreamingResponse](#32-流式输出streamingresponse)
  - [3.3 健康检查端点](#33-健康检查端点)
- [四、给已有项目接入 FastAPI 后端](#四给已有项目接入-fastapi-后端)
- [五、用 Swagger UI 测试与验证](#五用-swagger-ui-测试与验证)
- [六、架构对比：Gradio 内嵌调用 vs 独立 FastAPI 后端](#六架构对比gradio-内嵌调用-vs-独立-fastapi-后端)
- [七、Day 68 知识速查](#七day-68-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步](#九下一步)

---

## 一、为什么需要独立后端服务

### 1.1 Day 26 Gradio 方案的耦合问题

Day 26 起用的 Gradio 方案，是在界面回调函数里直接调用 LLM/RAG/Agent 逻辑——界面代码和推理逻辑运行在同一个 Python 进程里：

```python
# Day 26 的写法：界面回调直接调用推理逻辑，两者耦合在一起
def chat_fn(message, history):
    reply = call_llm_with_tools(message, history)   # 推理逻辑直接嵌在界面回调里
    return reply

demo = gr.ChatInterface(chat_fn)
```

这在做演示 Demo 时足够好用，但有一个结构性限制：**只有 Gradio 这一个前端能调用这套逻辑**。如果想让手机 App、其他内部系统、或一个更定制化的网页前端也用上同一套 RAG/Agent 能力，就得把推理逻辑复制一份接进新的调用方——逻辑和界面没有解耦。

### 1.2 FastAPI 解决的三个问题

```
问题 1：多客户端复用
  独立后端 API 之后，Web 前端、移动端、其他内部服务都可以通过标准 HTTP 请求调用同一套推理逻辑
  不需要为每个新客户端重新接入一遍业务代码

问题 2：前后端职责分离
  前端只负责展示和交互，后端只负责推理和业务逻辑
  两者可以独立开发、独立部署、独立扩容（比如后端可以水平扩展多个实例，前端保持不变）

问题 3：自动生成接口文档
  FastAPI 基于类型注解自动生成 OpenAPI 文档（Swagger UI），
  不需要额外手写一份接口说明文档，其他团队成员能直接照着文档联调
```

---

## 二、FastAPI 核心概念速览

### 2.1 路径操作

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat")
def chat(request: ChatRequest):   # 见 2.2，参数类型注解会被 FastAPI 自动校验
    ...
```

`@app.get`/`@app.post` 装饰器把一个普通函数注册成一个 HTTP 端点——这是 FastAPI 最基础的用法，函数签名里的类型注解（`request: ChatRequest`）会被自动用来做请求体解析和校验。

### 2.2 请求/响应模型：复用 Pydantic

Day 8 已经用 Pydantic 做过结构化输出的字段约束，FastAPI 的请求/响应模型用的是同一套 Pydantic：

```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题，不能为空")
    session_id: str = Field(default="default")

class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    trace_id: str

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = rag_system.query(request.question, session_id=request.session_id)
    return ChatResponse(answer=result["answer"], sources=result["sources"], trace_id=result["trace_id"])
```

**校验自动生效**：如果客户端发来的请求体里 `question` 是空字符串，FastAPI 会在进入函数体之前就自动返回 422 错误，不需要手写 `if not question: raise ...` 这类校验代码——这是 Day 8/9 手写校验逻辑的框架化版本。

### 2.3 依赖注入

```python
from fastapi import Depends, Header, HTTPException

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    return x_api_key

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, api_key: str = Depends(verify_api_key)):
    ...
```

`Depends` 把"校验 API Key"这类横切逻辑从业务函数里抽出来，声明为一个独立的依赖项——多个端点都需要鉴权时，只需要在函数签名里加一个 `Depends(verify_api_key)`，不需要在每个端点内部重复写校验代码。

---

## 三、把 LLM 调用包装成 API 端点

### 3.1 基础同步端点

```python
# api.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="RAG Agent API", version="1.0")

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = rag_system.query(request.question, session_id=request.session_id)
    return ChatResponse(answer=result["answer"], sources=result.get("sources", []))
```

### 3.2 流式输出：StreamingResponse

Day 4/26 已经实现过流式输出（在 CLI 和 Gradio 界面里逐字打印），FastAPI 里的对应实现是 `StreamingResponse`：

```python
from fastapi.responses import StreamingResponse

def token_generator(question: str):
    for chunk in call_llm_stream(question):   # 复用 Day 3 已经写过的流式调用逻辑
        yield chunk

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    return StreamingResponse(token_generator(request.question), media_type="text/event-stream")
```

**关键点**：`StreamingResponse` 接收一个生成器（`yield` 而不是 `return`），HTTP 响应会随着生成器产出内容逐步发送给客户端，而不是等全部生成完毕才一次性返回——这是网页前端实现"逐字显示"效果的后端基础。

### 3.3 健康检查端点

```python
@app.get("/health")
def health_check():
    return {"status": "ok", "model_gateway": model_gateway.is_ready()}   # 复用 Day 48 的网关状态
```

健康检查端点是生产部署的标配（Day 56 的容器化部署、云平台的负载均衡都依赖它判断实例是否存活），不需要业务逻辑，只需要快速返回服务本身是否正常运行。

---

## 四、给已有项目接入 FastAPI 后端

```python
# api.py —— 把 Day 27/42/66 项目的推理逻辑接入 FastAPI，而不是重新实现一遍
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agentic_rag.graph import graph as agentic_rag_graph   # 复用 Day 66 的 Agentic RAG 图
from gateway.gateway import model_gateway                    # 复用 Day 48 的模型网关

app = FastAPI(title="RAG Agent API")

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    answer: str
    trace_id: str

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = agentic_rag_graph.invoke(
        {"question": request.question, "current_query": request.question,
         "retrieved_docs": [], "is_relevant": False, "retry_count": 0, "answer": ""},
        config={"configurable": {"thread_id": request.session_id}},   # 复用 Day 35 的会话隔离
    )
    return ChatResponse(answer=result["answer"], trace_id=request.session_id)

@app.get("/health")
def health_check():
    return {"status": "ok", "gateway_ready": model_gateway.is_ready()}
```

**关键设计**：`api.py` 只是一层薄薄的 HTTP 包装，真正的推理逻辑（Agentic RAG 图、模型网关）全部是之前 Day 48/66 已经独立实现好的模块——FastAPI 层不重新写业务逻辑，只负责把已有能力暴露成标准的 HTTP 接口，这和 Day 66 强调的"框架负责编排，具体能力模块保持独立复用"是同一个设计原则。

---

## 五、用 Swagger UI 测试与验证

```bash
uvicorn api:app --reload --port 8000
```

启动后访问 `http://localhost:8000/docs`，FastAPI 会根据代码里的类型注解和 Pydantic 模型自动生成一个可交互的 API 文档页面（Swagger UI）：

```
在 Swagger UI 里可以直接：
1. 展开 /chat 端点，点击"Try it out"
2. 填入 {"question": "退货运费谁承担？", "session_id": "test-1"}
3. 点击 Execute，查看返回的 JSON 响应
4. 故意传一个空字符串的 question，验证是否返回 422 校验错误
```

不需要额外写前端代码或用 Postman，Swagger UI 就是最快的联调验证方式——这也是 FastAPI 相比手写 Flask/纯 HTTP 服务的一个显著优势：文档和测试界面是自动生成的，不需要额外维护。

---

## 六、架构对比：Gradio 内嵌调用 vs 独立 FastAPI 后端

| 维度 | Gradio 内嵌调用（Day 26） | 独立 FastAPI 后端（Day 68） |
|-----|-------------------------|---------------------------|
| 客户端支持 | 只有 Gradio 网页界面 | 任意 HTTP 客户端（Web/移动端/其他服务） |
| 前后端耦合度 | 界面和推理逻辑同进程，强耦合 | 完全解耦，可独立开发部署 |
| 接口文档 | 无（Gradio 本身就是界面，不对外暴露 API 语义） | 自动生成 Swagger UI |
| 适用场景 | 个人 Demo、快速原型验证、内部演示 | 需要被多个客户端调用、需要正式对外提供服务的场景 |
| 引入成本 | 极低，几行代码就能跑起来 | 需要单独设计请求/响应模型、部署独立服务 |

**判断标准**：不是所有项目都需要拆成 FastAPI 独立后端——如果只是自己或团队内部演示，Gradio 内嵌调用完全够用，引入 FastAPI 反而增加了维护成本；只有当明确需要"多个不同客户端调用同一套推理能力"（比如同时给网页和 App 提供服务，或者需要被其他内部系统调用）时，独立后端架构的收益才真正体现——这和整个深化阶段反复强调的"按信号引入，而非无脑叠加"是同一个判断逻辑。

---

## 七、Day 68 知识速查

### FastAPI 三个核心概念

```
路径操作：@app.get / @app.post 把函数注册成 HTTP 端点
请求/响应模型：复用 Pydantic（Day 8），类型注解自动触发请求校验
依赖注入：Depends 把鉴权/配置注入这类横切逻辑抽成独立可复用的依赖项
```

### 流式输出实现对照

```
Day 4（CLI）    ：直接在终端里逐字 print
Day 26（Gradio）：yield 给 gr.ChatInterface 的流式回调
Day 68（FastAPI）：StreamingResponse 包装生成器，逐步发送 HTTP 响应
三者底层都是同一套"生成器逐步产出内容"的思路，只是外层的展示载体不同
```

### 架构选型判断

```
只需要自己/团队内部演示 → Gradio 内嵌调用，成本最低
需要多客户端调用同一套能力 → 独立 FastAPI 后端
```

---

## 八、实践任务

- [ ] 给一个已有的 RAG/Agent 项目写 `api.py`，实现 `/chat`（同步）和 `/health` 两个端点
- [ ] 用 Pydantic 定义 `ChatRequest`/`ChatResponse`，故意传一个空字符串的 `question`，验证 Swagger UI 里能看到 422 校验错误
- [ ] 实现 `/chat/stream` 流式端点，用 `curl -N` 或浏览器验证响应是逐步返回而不是一次性返回
- [ ] 用 `Depends` 实现一个简单的 API Key 校验依赖，验证不带 Key 的请求被拒绝
- [ ] 写一段架构对比笔记，说明自己的项目现在更适合"Gradio 内嵌"还是"独立 FastAPI 后端"，并给出判断理由

**产出标准**：一个可以通过 HTTP 请求调用的 FastAPI 服务，Swagger UI 里 `/chat` 和 `/health` 两个端点都能测试通过；一份架构对比笔记，说明两种架构各自的适用场景，而不是无差别地都拆成独立后端。

---

## 九、下一步

FastAPI 后端工程作为技能查缺补漏的补充篇到此结束——它不改变深化阶段"Day 31–67 全部完成"的既有结论，只是补齐了一项此前路线图没有覆盖到的通用工程技能。后续如果继续发现类似的技能缺口（比如求职时被问到但路线图没覆盖的内容），可以按同样的方式作为补充篇追加，不需要为每一项都重新设计一整条路线。
