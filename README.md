# 大模型应用开发学习仓库

从零开始学习 AI 大模型应用开发的路线与配套笔记。核心理念：**用好预训练模型，边学边做**。

---

## 📂 文件目录

### 规划文档

| 文档 | 定位 | 何时看 |
| --- | --- | --- |
| [`plan.md`](规划文档/plan.md) | **战略地图**：四阶段全景、每阶段目标 / 项目 / 通关标准 | 把握方向、判断"学到哪、下一步学什么" |
| [`llm_app_30_day_roadmap.md`](规划文档/llm_app_30_day_roadmap.md) | **执行清单**：第一~三阶段的每日任务与产出标准（Day 1–30，已完成） | 落地到每天做什么 |
| [`day31_67_deepening_roadmap.md`](规划文档/day31_67_deepening_roadmap.md) | **深化阶段执行清单**：Day 31–67，先补 LangChain/LangGraph 框架基础，再按 A 深化 Agent → C 走向生产部署 → B 提升 RAG 质量 覆盖第三阶段剩余内容（含工程化架构、可观测性、成本性能含批处理、安全） | 30 天路线跑完后继续往深里做 |

### 学习笔记

| 文档 | 主题 | 关键内容 |
| --- | --- | --- |
| [`day01_llm_app_overview.md`](学习笔记/day01_llm_app_overview.md) | 大模型应用开发全景 | LLM 定义、Transformer 原理、Prompt / Token / RAG / Tool Calling |
| [`day02_python_basics.md`](学习笔记/day02_python_basics.md) | Python 最小基础 | 环境搭建、列表/字典/函数/类、文件操作、异常处理 |
| [`day03_first_api_call.md`](学习笔记/day03_first_api_call.md) | 第一次调用模型 API | HTTP 请求、API Key 管理、SDK 调用、LLM 客户端封装 |
| [`day04_cli_chat_demo.md`](学习笔记/day04_cli_chat_demo.md) | 命令行聊天 Demo | 消息角色、多轮对话、上下文管理、CLI 聊天程序 |
| [`day05_text_summarizer.md`](学习笔记/day05_text_summarizer.md) | 文章摘要器 | Prompt 任务约束、输出长度控制、多风格摘要器、Prompt 版本对比 |
| [`day06_info_extractor.md`](学习笔记/day06_info_extractor.md) | 信息抽取工具 | 结构化抽取原理、JSON 输出约束、简历/客服/商品多场景抽取、抽取稳定性提升 |
| [`day07_week1_review.md`](学习笔记/day07_week1_review.md) | 第 1 周复盘 | Token/成本关系、Temperature 数学原理、多轮对话无状态机制、三个 Demo 横向对比 |
| [`day08_structured_output.md`](学习笔记/day08_structured_output.md) | 结构化输出 | JSON Schema 字段约束、Pydantic 模型集成、类型校验与重试、批量抽取稳定性 |
| [`day09_error_handling.md`](学习笔记/day09_error_handling.md) | 输出校验与异常处理 | 异常分类与分层处理、指数退避重试、可重试与不可重试错误、字段分级兜底、结果三态设计 |
| [`day10_text_classifier.md`](学习笔记/day10_text_classifier.md) | 文本分类器 | 分类与抽取/摘要的区别、enum 标签约束、单/多标签分类、Self-Consistency 置信度评估、Prompt 对比实验 |
| [`day11_prompt_optimization.md`](学习笔记/day11_prompt_optimization.md) | Prompt 优化 | 角色设定/目标声明/Few-shot/输出限制四类手段、稳定性与准确率双维度评估、开发集与留出集验证、过拟合测试集辨别 |
| [`day12_cost_awareness.md`](学习笔记/day12_cost_awareness.md) | 建立成本意识 | 输入/输出 Token 计价差异、多轮对话成本平方级增长、成本记录表与实测、Prompt 优化的成本权衡、模型分级路由 |
| [`day13_config_and_logging.md`](学习笔记/day13_config_and_logging.md) | 配置管理和日志 | 环境变量与 .env、配置对象化 dataclass、logging 五级别、启动/请求/错误日志、可维护 LLM 客户端 |
| [`day14_week2_review.md`](学习笔记/day14_week2_review.md) | 第 2 周复盘 | Day 8–13 知识地图、稳定 Prompt 四件套、输出校验工程本质、可复用 Prompt 模板库、week2_toolkit 骨架 |
| [`day15_rag_from_scratch.md`](学习笔记/day15_rag_from_scratch.md) | RAG 基本原理 | 为何不能直塞知识库、离线构建与在线问答两阶段、Chunk Size/Overlap、向量检索、最小 RAG 实现 |
| [`day16_document_loader.md`](学习笔记/day16_document_loader.md) | 读取本地文档 | TXT/MD/PDF 三格式读取、编码自动检测、文本清洗规范化、统一 Document 加载器、对接 RAG 流程 |
| [`day17_text_chunking.md`](学习笔记/day17_text_chunking.md) | 文本切分 | 固定字符/Token 切分、段落/句子边界切分、RecursiveCharacterSplitter、四策略对比实验 |
| [`day18_embedding_and_retrieval.md`](学习笔记/day18_embedding_and_retrieval.md) | Embedding 与向量检索 | Embedding 原理与模型选择、API/本地 Embedding 调用、余弦相似度检索、FAISS/Chroma 向量库 |
| [`day19_rag_generation.md`](学习笔记/day19_rag_generation.md) | RAG 问答生成 | 上下文拼接策略、"只根据资料回答"约束、无资料拒答逻辑、端到端 RAG 问答生成器 |
| [`day20_answer_citation.md`](学习笔记/day20_answer_citation.md) | 给回答加引用 | 结构化引用 JSON 输出、引用溯源展示、虚构引用校验三道防线、带引用的完整 RAG 系统 |
| [`day21_week3_review.md`](学习笔记/day21_week3_review.md) | 第 3 周复盘 | Day 15–20 知识地图、RAG 准确率影响链、Chunk 切分传导路径、引用来源业务价值、完整 RAG Demo |
| [`day22_tool_calling_basics.md`](学习笔记/day22_tool_calling_basics.md) | 理解 Tool Calling | Tool Calling 完整交互流程、工具定义 JSON Schema、tool_calls 解析与结果传回、Tool Calling vs RAG vs 普通对话 |
| [`day23_define_first_tool.md`](学习笔记/day23_define_first_tool.md) | 定义第一个工具 | 参数设计原则、工具返回格式规范、天气/汇率/知识库三个真实工具实现、工具独立测试策略 |
| [`day24_single_tool_demo.md`](学习笔记/day24_single_tool_demo.md) | 单工具调用 Demo | tool_choice 三种模式、触发决策机制与调试、完整单工具调用 Demo（含日志）、多轮对话工具历史管理 |
| [`day25_multi_step_workflow.md`](学习笔记/day25_multi_step_workflow.md) | 多步工作流 | ReAct 循环模式、while 循环终止条件、max_iterations 安全上限、调用链可观测性与完整出行规划 Demo |
| [`day26_simple_ui.md`](学习笔记/day26_simple_ui.md) | 添加简单界面 | Gradio vs Streamlit 选型、ChatInterface 与流式输出、gr.State 跨轮状态、工具调用链可视化 Demo |
| [`day27_complete_project.md`](学习笔记/day27_complete_project.md) | 整合成完整作品 | 三选一项目方向、标准目录结构、core/tools/app.py 模块分工、README 工程化写法、5 分钟启动指南 |
| [`day28_engineering_details.md`](学习笔记/day28_engineering_details.md) | 补工程细节 | 异常处理分层设计、日志三类信息（启动/请求/错误）、fail-fast 配置验证、输出校验与脏数据防护 |
| [`day29_testing_and_optimization.md`](学习笔记/day29_testing_and_optimization.md) | 测试和优化 | 输出稳定性测试、工具调用精确率/召回率、Hit Rate 检索准确率、Token 成本分析、完整测试记录表 |
| [`day30_project_summary.md`](学习笔记/day30_project_summary.md) | 整理作品与总结 | README 5 分钟测试标准、项目介绍/运行步骤/示例写法、完整 README 模板、30 天认知总结与下一步路线 |
| [`day31_langchain_lcel_basics.md`](学习笔记/day31_langchain_lcel_basics.md) | LangChain 基础：LCEL 与核心抽象 | 为何引入框架、Runnable 接口与 LCEL 管道语法、ChatPromptTemplate 收益与代价、手写版 vs LangChain 版对比 |
| [`day32_langchain_structured_output_and_rag.md`](学习笔记/day32_langchain_structured_output_and_rag.md) | 用 LangChain 重新实现结构化输出与 RAG 链 | PydanticOutputParser 与 format_instructions、with_structured_output 对比、Retriever 接口与 Document 类型、RunnableParallel + RunnablePassthrough 拼 RAG 链 |
| [`day33_langgraph_basics_react_rewrite.md`](学习笔记/day33_langgraph_basics_react_rewrite.md) | LangGraph 基础：用状态图重写 ReAct | StateGraph / Node / Edge 三核心概念、TypedDict State 设计、add_messages Reducer、条件边路由、用 StateGraph 完整重写 Day 25 while 循环 ReAct |
| [`day34_conditional_edges_routing.md`](学习笔记/day34_conditional_edges_routing.md) | 条件边与分支路由 | add_conditional_edges 三参数、路由函数三条约束、条件边 vs 固定边判断标准、给 ReAct 图加"失败走重试/成功走汇总"分支、构造失败案例验证走重试分支不崩溃 |
| [`day35_checkpoint_and_loop_termination.md`](学习笔记/day35_checkpoint_and_loop_termination.md) | 循环终止与 Checkpoint 持久化 | recursion_limit 双层终止保护、MemorySaver 接入与 thread_id 会话隔离、interrupt_before 暂停与 invoke(None) 恢复、get_state / get_state_history 查询快照、SqliteSaver 跨进程持久化 |
| [`day36_human_in_the_loop.md`](学习笔记/day36_human_in_the_loop.md) | Human-in-the-loop 人工审核节点 | 批准/修改参数/拒绝三条审核路径、update_state 的 as_node 参数原理、AIMessage 同 id 替换修改工具参数、高风险操作判断标准、按工具名过滤精细化审核 |
| [`day37_week5_review.md`](学习笔记/day37_week5_review.md) | 第 5 周复盘：LangChain / LangGraph 解决了什么问题 | 原生 API vs LangChain vs LangGraph 适用边界对比表、引入各框架的 checklist、LangGraph 四项能力与手写 while 的结构性缺陷、本周知识地图 |
| [`day38_understanding_mcp.md`](学习笔记/day38_understanding_mcp.md) | 理解 MCP（Model Context Protocol） | MCP 三种核心能力（Tools / Resources / Prompts）、Server / Client 架构与交互流程图、MCP vs Function Calling 定位差异（互补非替代）、MCP vs A2A 各解决哪层连接问题 |
| [`day39_minimal_mcp_server.md`](学习笔记/day39_minimal_mcp_server.md) | 开发一个最小 MCP Server | FastMCP 与 @mcp.tool() 装饰器、类型提示自动生成 JSON Schema、把 Day 23 天气/汇率工具包装成 MCP Server、stdio transport 原理、.mcp.json 配置连接 Claude Code |
| [`day40_cross_session_memory.md`](学习笔记/day40_cross_session_memory.md) | 跨对话长期记忆 | 短期/长期记忆分层设计、JSON KV 存储用户偏好、记忆注入 System Prompt、向量存储记忆与语义检索、摘要压缩防止记忆膨胀、mem0 三核心接口与分层思路 |
| [`day41_multi_agent_collaboration.md`](学习笔记/day41_multi_agent_collaboration.md) | 多 Agent 协作模式 | Planner/Executor/Critic 三角色职责边界、Agent 间消息传递协议（SubTask/TaskResult/CriticVerdict）、协作 Demo 实现与可观察协作日志、A2A 协议设计动机（Task 状态机/流式 Push/Agent Card）、MCP+A2A 两层连接完整图景 |
| [`day42_week6_review_and_integration.md`](学习笔记/day42_week6_review_and_integration.md) | 阶段项目整合 + 第 6 周复盘 | Day 27 原项目四短板与升级架构图、四项能力各自解决的短板、Agent 行为评估三元组框架、15 条测试 case 示例报告（single_tool/multi_step/boundary 三类通过率）、本周知识地图 |
| [`day43_observability_langfuse.md`](学习笔记/day43_observability_langfuse.md) | 可观测性基础：接入 LangFuse/LangSmith | "能跑"vs"能被观测"本质区别、Trace/Span 核心概念与 LLM 映射关系、LangFuse 三种接入方式（OpenAI 拦截/@observe 装饰器/手动 SDK/LangChain 回调）、Dashboard 瀑布图解读、LangGraph Agent 可观测性实现、LangFuse vs LangSmith 选型指南 |
| [`day44_structured_logging_cost_dashboard.md`](学习笔记/day44_structured_logging_cost_dashboard.md) | 结构化日志与成本监控面板 | 纯文本 vs 结构化日志本质区别、四大核心字段（trace_id/tokens/cost/latency）设计详解、升级 Day 28 日志模块、成本聚合脚本（按天/按功能报表）、LangFuse 与本地 JSONL 日志分工 |

---

## 📋 各文件内容目录

### [plan.md](规划文档/plan.md) — 四阶段战略路线图

- **零、如何使用本路线**
  - 与 30 天路线的关系
  - 入门前自测（Python / 概念 / API 调用）
  - 各阶段时间预估
- **第一阶段：夯实基础与提示词工程（入门）**
  - Python 编程速通（asyncio、IDE）
  - 大模型基础概念（Transformer、Token、Temperature、Embedding、幻觉）
  - 原生 API 调用（消息结构、流式输出）
  - 提示词工程（角色、CoT、Few-shot）
  - 结构化输出（JSON 约束、重试与兜底）
  - 阶段项目（CLI 聊天 / 摘要器 / 信息抽取）
- **第二阶段：核心应用架构 / RAG（进阶）**
  - RAG 全流程（文档加载 → 切分 → 向量化 → 检索 → 生成）
  - 文档解析进阶（PDF / 表格 / 扫描件）
  - RAG 优化（多路召回、Reranker、HyDE、查询改写）
  - 评估体系（RAGAS、引用来源）
  - 阶段项目（本地文档问答系统）
- **第三阶段：智能体与复杂工程化（高阶）**
  - Function Calling / 工具调用基础
  - Agent 开发（ReAct 循环、规划、记忆、多 Agent）
  - Agent 框架与协议（LangGraph、MCP）
  - 大模型工程化架构（模型网关、Context Engineering）
  - 可观测性与评估（LangFuse / LangSmith）
  - 成本与性能（缓存、批处理、模型分级路由）
  - 安全（Prompt 注入防护、输出护栏）
  - 阶段项目（文档助手 / 知识库客服 / 工具助理）
- **第四阶段：底层部署与模型定制（专家 · 按需）**
  - 私有化部署与量化（Ollama、vLLM、INT8/GGUF/GPTQ）
  - 模型微调（数据集构建、LoRA/QLoRA）
  - 多模态技术拓展（图文音频视频）
- **贯穿全程的横向能力**（评估驱动、成本意识、安全合规、版本管理）
- **学习建议与常见误区**（递进逻辑、5 条误区、每周复盘模板）
- **推荐技术栈**（Python / SDK / Streamlit / Chroma / LangChain / RAGAS）

---

### [llm_app_30_day_roadmap.md](规划文档/llm_app_30_day_roadmap.md) — 30 天每日执行清单

- **一、先明确你要学什么**（应用开发 vs. 模型训练）
- **二、30 天后的达标标准**（5 项能力指标）
- **三、整体学习顺序**（6 步递进路径）
- **四、30 天每日任务清单**
  - 第 1 周（Day 1–7）：打基础，把 API 跑通
    - Day 1：大模型应用开发全景
    - Day 2：Python 最小基础
    - Day 3：第一次调用模型 API
    - Day 4：命令行聊天 Demo
    - Day 5：文章摘要器
    - Day 6：信息抽取工具
    - Day 7：第 1 周复盘
  - 第 2 周（Day 8–14）：强化 Prompt 与工程基本功
    - Day 8：结构化输出
    - Day 9：输出校验与异常处理
    - Day 10：文本分类器
    - Day 11：Prompt 优化练习
    - Day 12：成本意识
    - Day 13：配置管理和日志
    - Day 14：第 2 周复盘
  - 第 3 周（Day 15–21）：RAG 文档问答
    - Day 15：RAG 基本原理
    - Day 16：读取本地文档
    - Day 17：文本切分
    - Day 18：Embedding 与向量检索
    - Day 19：检索结果喂给模型回答
    - Day 20：给回答加引用
    - Day 21：第 3 周复盘
  - 第 4 周（Day 22–30）：Tool Calling / Agent，做完整 Demo
    - Day 22：理解 Tool Calling
    - Day 23：定义第一个工具
    - Day 24：单工具调用 Demo
    - Day 25：多步工作流
    - Day 26：添加简单界面
    - Day 27：整合成完整作品
    - Day 28：补工程细节
    - Day 29：测试和优化
    - Day 30：整理作品与总结
- **五、建议做出的 3 个项目**（优先级清单）
- **六、推荐技术栈**（初学者路线）
- **七、学习中的常见误区**（5 条误区详解）
- **八、每周复盘模板**
- **九、入门判断标准**（3 件事检验法）
- **十、下一步建议**（30 天后延伸路线）

---

### [day01_llm_app_overview.md](学习笔记/day01_llm_app_overview.md) — Day 1：大模型应用开发全景

- **一、什么是大模型应用开发**
  - 定义（API 接入 + 业务场景）
  - 核心特点（不训练模型 / 以 Prompt 为核心 / 按量付费）
  - 与传统开发的关系
  - 典型应用场景（智能客服 / 文档问答 / 信息抽取 / 代码辅助）
- **二、大模型基础知识点**
  - 2.1 什么是 LLM（定义、"大"体现在哪里、核心能力）
  - 2.2 发展历程（2017 Transformer → 2025 推理模型时间线）
  - 2.3 工作原理（Transformer 架构、三阶段训练、推理过程、采样参数）
  - 2.4 主流大模型（闭源 / 开源 / 国内模型对比表）
  - 2.5 能力与局限（幻觉、知识截止、上下文限制等 7 类局限）
  - 2.6 如何选择合适的模型（决策树、场景推荐、成本对比）
  - 2.7 核心概念速查表
- **三、核心概念详解**
  - 3.1 Prompt（组成要素、示例对比、设计原则）
  - 3.2 Token（中英文换算、成本计算、上下文限制、优化策略）
  - 3.3 上下文窗口（结构图、溢出处理方式）
  - 3.4 Embedding（向量化原理、余弦相似度、应用场景、常见模型）
  - 3.5 RAG（为什么需要 / 完整流程图 / 关键环节 / 文档切分详解）
  - 3.6 Tool Calling（vs 普通对话 / 完整流程图 / 工具定义示例 / 与 Agent 的关系）
- **四、学习要点总结**（概念关系图、核心概念速查表）
- **五、Day 1 实践任务**（阅读总览 / 自定义概念 / 输出笔记）
- **六、延伸阅读**（推荐资源）
- **七、常见问题**（大模型开发 vs 传统开发 / 为什么先学原生 API / Token 贵吗）

---

### [day02_python_basics.md](学习笔记/day02_python_basics.md) — Day 2：Python 最小基础

- **一、为什么需要 Python**（生态优势、Day 2 学习路线图）
- **二、环境搭建**
  - 2.1 安装 Python（版本选择、Windows / macOS / Linux 安装方式）
  - 2.2 虚拟环境（为什么需要、venv / conda 创建与激活、常用命令速查）
  - 2.3 包管理工具 pip（常用命令、requirements.txt、国内镜像加速）
- **三、Python 基础语法**
  - 3.1 变量与数据类型（基本类型、类型转换）
  - 3.2 列表（基础操作、增删查改、推导式）
  - 3.3 字典（基础操作、遍历、推导式、嵌套字典）
  - 3.4 函数（定义与调用、参数类型、类型注解）
  - 3.5 类（定义、继承、实际应用示例：API 客户端类）
- **四、文件操作**
  - 4.1 文件读取（4 种方式、编码处理）
  - 4.2 文件写入（覆盖 / 追加 / JSON）
  - 4.3 文件模式速查表
  - 4.4 文件路径处理（os.path / pathlib 对比）
- **五、异常处理**
  - 5.1 基本语法（try-except 结构）
  - 5.2 完整结构（else / finally）
  - 5.3 常见异常类型表
  - 5.4 主动抛出异常
  - 5.5 自定义异常
  - 5.6 最佳实践（只捕获预期异常、不裸 except、异常链）
- **六、Day 2 实践任务**（安装 Python / 编写文件统计脚本 / 练习题）
- **七、常见问题**（Python 2 vs 3 / 编辑器选择 / 虚拟环境 / pip 慢）
- **八、知识速查表**（常用命令 + Python 语法速查）

---

### [day03_first_api_call.md](学习笔记/day03_first_api_call.md) — Day 3：第一次调用模型 API

- **一、API 调用基础概念**
  - 1.1 什么是 API（客户端-服务端示意图）
  - 1.2 HTTP 请求基础（请求组成、常用方法、常用状态码）
  - 1.3 JSON 数据格式（基础结构、Python 处理 JSON）
- **二、API Key 管理**
  - 2.1 什么是 API Key（作用、示例格式）
  - 2.2 获取 API Key（OpenAI、国内平台：DeepSeek / 阿里云 / 智谱 / Moonshot）
  - 2.3 安全存储（.env 文件推荐做法、系统环境变量、.gitignore 配置）
- **三、调用大模型 API**
  - 3.1 使用 requests 库调用（基础示例、完整响应结构解析）
  - 3.2 使用官方 SDK 调用（OpenAI SDK、DeepSeek SDK、阿里云 Qwen SDK）
- **四、封装可复用的 LLM 客户端**
  - 4.1 基础版本（多平台支持、枚举配置、流式输出、日志记录）
  - 4.2 带重试机制的客户端（指数退避装饰器）
- **五、实战练习**
  - 5.1 项目目录结构
  - 5.2 配置文件（requirements.txt / .env / .gitignore）
  - 5.3 完整示例程序（基础对话 / 多轮对话 / 流式输出 / 系统提示 / Token 统计 / 交互聊天）
- **六、常见问题排查**
  - 6.1 常见错误及解决方案（401 / 429 / 500 / 超时）
  - 6.2 调试技巧（日志级别、打印原始响应、httpbin 测试）
  - 6.3 代理设置（环境变量 / requests 代理 / OpenAI SDK 代理）
- **七、Day 3 知识速查**（调用流程 6 步、最简调用模板）
- **八、实践任务**（注册账号 / .env 配置 / 第一次调用 / 多轮对话 / 流式输出）

---

### [day04_cli_chat_demo.md](学习笔记/day04_cli_chat_demo.md) — Day 4：命令行聊天 Demo

- **一、消息结构详解**
  - 1.1 三种消息角色（system / user / assistant 示意图）
  - 1.2 消息结构（Python 列表格式）
  - 1.3 角色详解（system 5 种典型用法、user 多模态写法、assistant 历史保存）
  - 1.4 消息历史的重要性（无状态模型 + 必须传历史对比示意）
- **二、多轮对话实现**
  - 2.1 基础实现（全局 messages 列表管理）
  - 2.2 消息历史管理（MessageHistory 数据类：截断 / 导出 / 保存文件 / 统计）
  - 2.3 上下文窗口管理策略（tiktoken 计 Token、滑动窗口、摘要压缩）
- **三、完整命令行聊天程序**
  - 3.1 基础版 CLI（ChatBot 类、/clear / /history / /quit 命令）
  - 3.2 增强版 CLI（Config 数据类、流式输出、Token 统计、对话保存/加载、10 条命令）
- **四、消息历史优化技巧**
  - 4.1 常见问题（Token 超限 / 模型"遗忘" / 敏感信息）
  - 4.2 优化策略（摘要压缩、关键信息提取、敏感信息过滤）
- **五、Day 4 知识速查**（角色表、多轮对话要点、代码模板）
- **六、实践任务**（理解角色 / 基础多轮 / CLI 程序 / 流式输出 / /clear 命令）

---

### [day05_text_summarizer.md](学习笔记/day05_text_summarizer.md) — Day 5：文章摘要器

- **一、Prompt 任务约束**
  - 1.1 为什么需要任务约束（无约束 vs 有约束效果对比）
  - 1.2 约束的四个维度（内容范围 / 输出格式 / 长度限制 / 语气风格）
  - 1.3 摘要任务的典型约束（V0～V4 五个递进 Prompt 示例）
- **二、输出长度控制**
  - 2.1 Prompt 层的长度控制（字数 / 句数 / 比例 / 结构 四种写法）
  - 2.2 API 参数层的长度控制（max_tokens 对照表）
  - 2.3 两种方式的区别（软约束 vs 硬截断对比、最佳实践）
- **三、文章摘要器实现**
  - 3.1 两个版本的摘要 Prompt（新闻要点版 / 深度结构化版）
  - 3.2 基础摘要器（4 种风格：brief / bullets / structured / audience）
  - 3.3 多风格交互版（支持文件输入、命令行参数、`--all` 全风格对比）
- **四、Prompt 版本对比实验**
  - 4.1 对比框架（run_prompt / compare_prompts 工具函数）
  - 4.2 实验示例（V1～V4 四版 Prompt 横向对比，含结论）
- **五、Day 5 知识速查**（约束要素表、temperature 对照、代码模板）
- **六、实践任务**（理解约束 / 实现摘要器 / 写 2 个版本 Prompt / 对比 temperature）

---

### [day06_info_extractor.md](学习笔记/day06_info_extractor.md) — Day 6：信息抽取工具

- **一、结构化抽取的核心概念**
  - 1.1 什么是信息抽取（典型场景：简历 / 客服 / 商品 / 合同 / 新闻）
  - 1.2 为什么要求输出 JSON（摘要 vs 抽取的本质差异对比）
  - 1.3 抽取 vs 摘要的核心差异（忠实来自原文 vs 允许语义整合）
- **二、输出格式约束**
  - 2.1 字段定义的写法（简单版 vs 精确版含类型与示例）
  - 2.2 让模型只输出 JSON（有效 vs 无效约束对比 + response_format 参数）
  - 2.3 字段为空时的兜底策略（null / 空字符串 / 不输出 三种方式对比）
- **三、信息抽取工具实现**
  - 3.1 简历信息抽取（8 字段 + 完整可运行代码 + 预期输出）
  - 3.2 客服对话抽取（问题类型 / 情绪 / 紧急程度 + 三组测试样本）
  - 3.3 通用抽取器（InfoExtractor 类，字段定义参数化，支持任意场景）
- **四、抽取稳定性提升**
  - 4.1 常见失败模式（格式污染 / 字段推断 / 类型错误 / 字段遗漏 / 列表混淆）
  - 4.2 Few-shot 示例增强稳定性（示例输入-输出对写法）
  - 4.3 结果校验与兜底（JSON 解析 + 缺失字段补全 + 重试机制）
- **五、Day 6 知识速查**（Prompt 模板、关键参数表、抽取 vs 摘要对比表）
- **六、实践任务**（任务清单 + 产出标准）

---

### [day07_week1_review.md](学习笔记/day07_week1_review.md) — Day 7：第 1 周复盘

- **一、本周全景回顾**
  - 1.1 Day 1–6 知识地图（完整 ASCII 流程图）
  - 1.2 本周三个 Demo 概览（聊天 / 摘要 / 抽取对比表）
- **二、深度复盘三大问题**
  - 2.1 Token 为什么和成本有关（Tokenizer 原理、计费公式、Token 消耗四来源及优化）
  - 2.2 Temperature 为什么会影响输出（Softmax 数学原理、场景选择速查表）
  - 2.3 为什么多轮对话必须传历史消息（无状态本质、ConversationManager 实现）
- **三、三个 Demo 整理与横向对比**
  - 3.1 CLI 聊天 Demo（流式输出 + /clear 命令）
  - 3.2 文章摘要器（多风格 Prompt 字典管理）
  - 3.3 信息抽取工具（字段参数化 + 双重 JSON 约束）
  - 3.4 三个 Demo 设计差异对比表
- **四、第 1 周完整代码骨架**（week1_toolkit.py 汇总）
- **五、Day 7 知识速查**（核心公式、三参数速查、三 Demo 最小模板）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 8 结构化输出方向）

---

### [day08_structured_output.md](学习笔记/day08_structured_output.md) — Day 8：结构化输出

- **一、结构化输出的核心概念**
  - 1.1 为什么"大概像 JSON"不够用 / 1.2 三种约束强度：Prompt / API 参数 / Schema / 1.3 结构化输出的完整链路
- **二、JSON Schema 精确约束字段**
  - 2.1 JSON Schema 基本语法 / 2.2 类型、必填项与枚举约束 / 2.3 嵌套结构与数组约束
- **三、Pydantic 模型与 LLM 输出集成**
  - 3.1 为什么用 Pydantic / 3.2 定义抽取模型 / 3.3 自动生成 Prompt 约束
- **四、改造信息抽取脚本**
  - 4.1 Day 6 版本的局限 / 4.2 Schema + Pydantic 双重校验增强版 / 4.3 批量抽取与失败重试
- **五、大规模场景下的格式一致性**
  - 5.1 常见规模化痛点 / 5.2 稳定性工程手段
- **六、Day 8 知识速查**（三层约束表、Pydantic 写法速查、最小模板）
- **七、实践任务**（任务清单 + 产出标准）

---

### [day09_error_handling.md](学习笔记/day09_error_handling.md) — Day 9：输出校验与异常处理

- **一、异常处理的核心概念**
  - 1.1 为什么"能跑通"不等于"能上线" / 1.2 大模型调用链路中的异常分类 / 1.3 异常处理的分层设计
- **二、JSON 解析失败与校验失败的分层处理**
  - 2.1 json.JSONDecodeError / 2.2 pydantic.ValidationError / 2.3 统一异常处理包装函数
- **三、重试机制设计**
  - 3.1 立即重试 vs 指数退避 / 3.2 通用退避重试装饰器 / 3.3 可重试 vs 不可重试异常
- **四、空字段与部分缺失的业务兜底策略**
  - 4.1 三种兜底策略对比 / 4.2 按字段重要性分级处理 / 4.3 结果三态：success / needs_review / failed
- **五、完整实现：健壮的信息抽取器**（整合分类异常、指数退避、字段分级、结果三态）
- **六、Day 9 知识速查**（异常分类表、退避公式、结果三态表、最小模板）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 10 文本分类器方向）

---

### [day10_text_classifier.md](学习笔记/day10_text_classifier.md) — Day 10：文本分类器

- **一、分类任务的核心概念**
  - 1.1 分类 vs 抽取 vs 摘要的本质区别 / 1.2 分类任务的输入输出形态 / 1.3 标签集合的设计原则
- **二、标签集合约束的实现**
  - 2.1 用 enum 锁定标签范围 / 2.2 单标签 vs 多标签分类 / 2.3 "无法归类"的兜底标签设计
- **三、文本分类器实现**
  - 3.1 基础版单标签分类器 / 3.2 Pydantic + enum 强类型分类器 / 3.3 批量分类与结果统计
- **四、分类结果的置信度与验证**
  - 4.1 为什么模型给的标签不完全可信 / 4.2 Self-Consistency 多次采样估计置信度 / 4.3 小样本人工标注评估准确率
- **五、对比实验：Prompt 设计对分类准确率的影响**
- **六、Day 10 知识速查**（任务对比表、标签设计四原则、置信度评估速查、最小模板）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 11 Prompt 优化方向）

---

### [day11_prompt_optimization.md](学习笔记/day11_prompt_optimization.md) — Day 11：练 Prompt 优化

- **一、Prompt 优化的核心框架**
  - 1.1 四类优化手段总览 / 1.2 为什么"写清楚"比"写聪明"更重要 / 1.3 真优化 vs 假优化：辨别过拟合测试集
- **二、四类优化手段逐个拆解**
  - 2.1 角色设定 / 2.2 目标声明 / 2.3 Few-shot 示例 / 2.4 输出限制
- **三、写出并对比三版 Prompt**
  - 3.1 选定任务：客服工单紧急程度打分 / 3.2 V1/V2/V3 设计思路 / 3.3 对比实验框架实现
- **四、稳定性与准确率的关系与权衡**
  - 4.1 两个独立的评估维度 / 4.2 四象限：稳定性 × 准确率 / 4.3 留出集验证避免过拟合
- **五、完整对比实验与结果分析**
- **六、Day 11 知识速查**（四类手段速查、评估维度速查、最小模板）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 12 成本意识方向）

---

### [day12_cost_awareness.md](学习笔记/day12_cost_awareness.md) — Day 12：建立成本意识

- **一、Token 与成本的关系回顾与深化**
  - 1.1 计费公式回顾 / 1.2 输入与输出 Token 的价格差异 / 1.3 Token 消耗的常见来源
- **二、上下文长度对成本的放大效应**
  - 2.1 多轮对话的 Token 累积增长模型 / 2.2 长输入 vs 长输出成本结构对比 / 2.3 RAG 场景下的成本放大效应
- **三、成本记录与估算实践**
  - 3.1 设计一张成本记录表 / 3.2 用代码统计 Token 用量与成本 / 3.3 三个常见请求的实测记录
- **四、成本优化策略**
  - 4.1 精简 system prompt / 4.2 历史截断与摘要压缩 / 4.3 Prompt 优化的成本权衡：重新审视 Day 11 / 4.4 模型分级路由
- **五、Day 12 知识速查**（成本构成速查、优化手段速查、最小模板）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 13 配置管理和日志方向）

---

### [day13_config_and_logging.md](学习笔记/day13_config_and_logging.md) — Day 13：配置管理和日志

- **一、为什么需要配置管理**
  - 1.1 硬编码密钥的风险 / 1.2 配置与代码分离的原则 / 1.3 配置的三种来源及优先级
- **二、环境变量与 .env 文件**
  - 2.1 用 python-dotenv 管理 .env / 2.2 .gitignore 的正确配置 / 2.3 用 dataclass 封装配置对象
- **三、Python logging 基础**
  - 3.1 为什么不用 print / 3.2 logging 模块的五个级别 / 3.3 格式化与输出目标
- **四、给 LLM 项目加上实用日志**
  - 4.1 启动日志：记录关键配置 / 4.2 请求日志：耗时与 Token 消耗 / 4.3 错误日志：异常链与上下文
- **五、完整实现：可维护的 LLM 客户端**（整合配置 + 日志 + 重试的完整骨架）
- **六、Day 13 知识速查**（配置管理速查、logging 速查、最小模板）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 14 第 2 周复盘方向）

---

### [day14_week2_review.md](学习笔记/day14_week2_review.md) — Day 14：第 2 周复盘

- **一、第 2 周全景回顾**
  - 1.1 Day 8–13 知识地图 / 1.2 本周六个主题的逻辑链（能跑 → 可信赖 → 可迭代 → 可量化 → 可维护）
- **二、深度复盘三大问题**
  - 2.1 什么样的 Prompt 更稳定（四类根因 + 稳定性公式 + 四件套速查）
  - 2.2 为什么输出校验比"提示模型小心点"更可靠（三层防线 vs 依赖自律对比）
  - 2.3 为什么 Demo 要尽早引入日志和配置（技术债复利 + 最小成本引入时机）
- **三、可复用 Prompt 模板库**
  - 3.1 结构化抽取模板 / 3.2 文本分类模板 / 3.3 摘要生成模板 / 3.4 通用模板调用框架
- **四、第 2 周完整工程骨架**（`week2_toolkit.py`，整合配置/日志/成本记录/结构化调用）
- **五、Day 14 知识速查**（六主题一览表、稳定 Prompt 判断标准、工程保障三要素）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 15 RAG 基本原理方向）

---

### [day15_rag_from_scratch.md](学习笔记/day15_rag_from_scratch.md) — Day 15：理解 RAG 基本原理

- **一、为什么需要 RAG**
  - 1.1 大模型的三大知识局限（知识截止 / 私有知识 / 幻觉）
  - 1.2 为什么不能直接把整个知识库塞给模型（窗口限制 / "Lost in the Middle" / 成本 / 噪音干扰）
  - 1.3 RAG 的核心思想（先"找"再"答"，搜索引擎 + 大模型的结合）
- **二、RAG 完整流程**
  - 2.1 两个阶段：离线构建 + 在线问答（完整架构图）
  - 2.2 文档切分（Chunking）：为什么切、Chunk Size / Overlap 参数含义与影响
  - 2.3 Embedding 与向量化：一致性约束、常用方案对比
  - 2.4 向量检索：余弦相似度原理与代码实现
  - 2.5 上下文增强与生成：增强 Prompt 构建、"只根据资料回答"约束
- **三、最小 RAG 实现（纯 Python）**
  - 3.1 依赖安装 / 3.2 离线构建 / 3.3 在线问答 / 3.4 完整可运行代码（含拒答测试）
- **四、RAG 的关键参数与常见陷阱**
  - 4.1 Chunk Size 与 Overlap 的甜蜜区间 / 4.2 Top-K 影响对比表 / 4.3 成本视角重看 RAG
- **五、Day 15 知识速查**（流程速查、参数参考值、最小代码模板）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 16 读取本地文档方向）

---

### [day16_document_loader.md](学习笔记/day16_document_loader.md) — Day 16：读取本地文档

- **一、为什么文档读取不是"小问题"**
  - 1.1 RAG 流程中的位置（数据入口质量决定一切）/ 1.2 三种格式的难度层级（TXT < MD < PDF）
- **二、读取 TXT 和 MD 文件**
  - 2.1 基础读取与编码问题（UTF-8 / GBK / BOM 三坑）
  - 2.2 编码自动检测（chardet + 尝试列表兜底策略）
  - 2.3 MD 文件的特殊处理（保留标记 vs 去除标记的权衡）
- **三、读取 PDF 文件**
  - 3.1 为什么 PDF 比 TXT 难（绘图指令格式、无文本层）
  - 3.2 用 pdfplumber 提取文本（逐页提取、跳过扫描件页）
  - 3.3 常见 PDF 坑与处理方法（乱码 / 多栏乱序 / 页眉页脚 / 扫描件）
- **四、文本清洗与规范化**（统一换行符、压缩空行、去除多余空格）
- **五、统一文档加载器**
  - 5.1 接口设计原则（Document dataclass）/ 5.2 完整实现 / 5.3 与 Day 15 RAG 流程对接
- **六、Day 16 知识速查**（格式支持速查、编码处理速查、最小模板）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 17 文本切分方向）

---

### [day17_text_chunking.md](学习笔记/day17_text_chunking.md) — Day 17：文本切分

- **一、为什么切分策略很重要**
  - 1.1 切分质量对 RAG 效果的影响链（过细 / 过粗 / 在语义边界切断的三种问题）
  - 1.2 四种切分策略总览（固定字符 / 固定 Token / 语义边界 / 递归字符对比表）
- **二、固定大小切分**
  - 2.1 按字符数切分（代码实现 + 与词数切分的差异）
  - 2.2 按 Token 数切分（tiktoken 实现 + 何时选 Token 切分）
  - 2.3 固定大小切分的局限（截断示例图解）
- **三、按语义边界切分**
  - 3.1 按段落切分（双换行分隔 + 过滤短段落）
  - 3.2 按句子切分（中英文正则 + 句子 overlap）
  - 3.3 段落 + 大小限制的结合策略（合并短段 / 二次切分长段）
- **四、递归字符切分**
  - 4.1 递归切分的思路（分隔符优先级、何时降级的逻辑图）
  - 4.2 完整 RecursiveCharacterSplitter 实现
- **五、切分策略对比实验**
  - 5.1 实验框架（analyze_chunks / compare_strategies）
  - 5.2 不同策略的 Chunk 分布对比（块数 / 均值 / 标准差）
  - 5.3 对 RAG 检索质量的影响（相似度分数对比）
- **六、Day 17 知识速查**（策略选择指南、参数经验表、最小代码模板）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 18 Embedding 与向量检索方向）

---

### [day18_embedding_and_retrieval.md](学习笔记/day18_embedding_and_retrieval.md) — Day 18：Embedding 与向量检索

- **一、Embedding 的本质**
  - 1.1 从词向量到句向量的演进 / 1.2 为什么语义相近的文本向量距离更近 / 1.3 Embedding 模型的选择原则
- **二、Embedding API 调用与批量优化**
  - 2.1 OpenAI 兼容接口调用 Embedding / 2.2 本地模型：sentence-transformers / 2.3 批量向量化：降低 API 调用次数
- **三、相似度计算与纯 numpy 检索**
  - 3.1 三种距离度量对比（余弦 / 内积 / L2）/ 3.2 纯 numpy 实现向量检索 / 3.3 Top-K 与相似度阈值的影响
- **四、向量数据库：从 numpy 升级到 FAISS 和 Chroma**
  - 4.1 为什么需要向量数据库 / 4.2 FAISS：高性能向量检索 / 4.3 Chroma：带元数据的向量数据库
- **五、完整实现：RAG 检索组件**（整合文档加载 + 切分 + Embedding + 检索）
- **六、Day 18 知识速查**（方案选择速查、关键参数表、最小代码模板）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 19 把检索结果喂给模型方向）

---

### [day19_rag_generation.md](学习笔记/day19_rag_generation.md) — Day 19：RAG 问答生成

- **一、上下文拼接策略**
  - 1.1 上下文拼接的基本格式（资料编号 + 问题拼接结构）
  - 1.2 多个 Chunk 的排列策略（降序 / 三明治 / 原始顺序 + "Lost in the Middle" 效应）
  - 1.3 上下文长度控制与 Token 预算（Context 窗口分配比例）
- **二、"只根据资料回答"约束**
  - 2.1 为什么需要这个约束（幻觉的根源：模型宁愿猜也不拒答）
  - 2.2 约束 Prompt 的写法与强度（弱 / 中 / 强三版对比）
  - 2.3 约束强度与回答完整性的权衡
- **三、无相关文档时的拒答逻辑**
  - 3.1 为什么拒答比猜测更有价值 / 3.2 检索层拒绝（min_score）+ 模型层拒绝（双重保险）
- **四、完整实现：RAG 问答生成器**（端到端：加载 → 切分 → 检索 → 生成）
- **五、RAG Prompt 模板对比实验**
  - 5.1 三版 Prompt 设计（V1 简版 / V2 约束版 / V3 引用版）
  - 5.2 回答质量对比表
- **六、Day 19 知识速查**（流程速查、System Prompt 模板、关键参数表）
- **七、实践任务**（任务清单 + 产出标准）
- **八、下一步预告**（Day 20 给回答加引用方向）

---

### [day20_answer_citation.md](学习笔记/day20_answer_citation.md) — Day 20：给回答加引用

- **一、引用机制的核心概念**
  - 1.1 为什么 RAG 需要引用（可解释性：用户可追溯答案来源）/ 1.2 引用的三个层次（L1 标记 / L2 展示来源 / L3 可验证）/ 1.3 引用 vs 拒答（可解释性的两个侧面）
- **二、结构化引用输出设计**
  - 2.1 从自然语言引用到结构化引用（三个问题与 JSON 解法）/ 2.2 JSON Schema 设计：answer + sources（字段决策考量）/ 2.3 Prompt 设计：引导模型标注引用
- **三、引用溯源展示**
  - 3.1 展示设计：回答 + 引用区块 / 3.2 引用片段的截取与高亮（关键词定位截取）/ 3.3 多来源引用的排列策略
- **四、引用准确性验证**
  - 4.1 虚构引用问题（编号越界 / 内容不匹配 / 遗漏引用三种类型）/ 4.2 引用校验的三道防线（编号有效性 + 拒答一致性 + 内容匹配性）/ 4.3 引用覆盖率与忠实度（RAGAS 指标简化版）
- **五、完整实现：带引用的 RAG 问答系统**（端到端：检索 → 生成 JSON → 校验 → 格式化展示）
- **六、引用策略对比实验**
  - 6.1 三版方案设计（自然语言 / 结构化无校验 / 结构化+校验）/ 6.2 引用质量对比表
- **七、Day 20 知识速查**（流程速查、校验三防线表、Schema 模板、最小模板、关键参数表）
- **八、实践任务**（任务清单 + 产出标准）
- **九、下一步预告**（Day 21 第 3 周复盘方向）

---

### [day30_project_summary.md](学习笔记/day30_project_summary.md) — Day 30：整理作品与总结

- **一、为什么 README 是项目的"脸"**
  - 1.1 5 分钟测试：陌生人能跑起来吗？（黄金标准与测试流程）
  - 1.2 README 必须包含的四个部分（介绍 / 功能 / 快速开始 / 示例）
  - 1.3 常见疏漏：让人跑不起来的五种情况（Python 版本缺失 / 无 .env.example 等）
- **二、写好项目介绍**
  - 2.1 一句话介绍：用"做什么 + 怎么做到"结构（好坏对比示例）
  - 2.2 功能列表：具体而非抽象（❌抽象 vs ✅具体 对比）
  - 2.3 技术栈说明：让读者快速定位自己的熟悉度（表格格式）
- **三、写好运行步骤**
  - 3.1 三步启动原则（git clone + pip install / 配置 / python app.py）
  - 3.2 每步都必须可验证（✅ 预期输出写法）
  - 3.3 .env 配置的正确写法（.env.example 每变量加注释 + .gitignore）
- **四、写好示例输入输出**
  - 4.1 为什么示例比功能描述更有力（功能描述 vs 真实对话示例对比）
  - 4.2 选择哪些示例：三类必选场景（核心功能 / 差异化亮点 / 边界处理）
  - 4.3 示例的呈现格式（代码块 + 角色前缀）
- **五、完整 README 模板**（可直接复用的个人助理 Demo README）
- **六、30 天学习总结**
  - 6.1 三个阶段的核心产出（Day 1–14 / Day 15–21 / Day 22–30 产出清单）
  - 6.2 最重要的五个认知转变（API调用→工程系统 / Prompt→规格 / RAG / 工具 / 可维护性）
  - 6.3 下一步去哪里（路线A: Agent深化 / 路线B: RAG提升 / 路线C: 生产部署）
- **七、Day 30 知识速查**（README 必备章节速查表、三步启动模板）
- **八、实践任务**（任务清单 + 产出标准：5 分钟测试）
- **九、30 天学习结束语**

---

### [day31_langchain_lcel_basics.md](学习笔记/day31_langchain_lcel_basics.md) — Day 31：LangChain 基础：LCEL 与核心抽象

- **一、为什么要在原生 API 之上套一层框架**
  - Provider 绑定、链路重复、输出解析散落三个痛点（对应 Day 3–29 的实际经历）
  - 框架解决了什么：统一 Provider 接口 + LCEL 标准化链路
  - 框架的代价：调试难度增加 / 版本迭代快 / 隐藏 API 细节 / 依赖重
- **二、核心抽象：Runnable 接口**
  - Runnable 是什么（invoke / stream / batch 三个统一方法）
  - LCEL 管道语法：`prompt | model | parser` 创建 `RunnableSequence`
  - 管道的执行过程与类型转换（dict → ChatPromptValue → AIMessage → str）
- **三、PromptTemplate 与 ChatPromptTemplate**
  - 相比手拼字符串多做了什么（变量校验、角色验证、MessagesPlaceholder）
  - 隐藏了什么：实际 messages 内容、token 计数位置、内部重试逻辑
  - 两种模板类型的使用场景（ChatPromptTemplate 是当前主流）
- **四、实战：重写 Day 4 命令行聊天 Demo**
  - 手写版本回顾（显式 messages 列表，直接取 response.choices[0].message.content）
  - LangChain 版本（MessagesPlaceholder + chain.invoke）
  - 两版本对比表：框架省掉了什么、隐藏了什么、调试透明度差异
- **五、Day 31 知识速查**（LCEL 核心组件表、Runnable 方法表、手写 vs LangChain 决策表）
- **六、实践任务**（安装 / 重写 Demo / 打印中间状态调试 / 流式输出实验）
- **七、下一步预告**（Day 32：PydanticOutputParser + Retriever + RAG 链）

---

### [day32_langchain_structured_output_and_rag.md](学习笔记/day32_langchain_structured_output_and_rag.md) — Day 32：用 LangChain 重新实现结构化输出与 RAG 链

- **一、OutputParser 体系：从手写解析到框架标准化**
  - Day 8 手写解析的三个步骤与各自的问题（取文本 / JSON 解析 / Pydantic 校验）
  - 三种 OutputParser 对比（StrOutputParser / JsonOutputParser / PydanticOutputParser）
  - `with_structured_output()`：API 层约束 vs Prompt 层约束的区别
- **二、实战：用 PydanticOutputParser 重做 Day 8 结构化抽取**
  - 手写版回顾（json.loads + Pydantic 校验 + markdown 清理）
  - LangChain 版（`format_instructions` 自动生成约束，`.partial()` 预填模板）
  - 两版本对比表 + OutputFixingParser 自动修复解析失败
- **三、Retriever 接口：把向量检索包装进 LangChain**
  - Retriever 封装了什么（embedding + 检索 + 结果包装为 Document）
  - 用 Chroma 创建 Retriever（`as_retriever` + `search_kwargs`）
  - 手写 `list[str]` vs `List[Document]` 的本质区别（metadata 随检索结果传递）
- **四、实战：用 LCEL 拼出最小 RAG 链**
  - `RunnableParallel` 与 `RunnablePassthrough` 解决"单输入喂给多变量 Prompt"问题
  - 完整 RAG 链代码（retriever | format_docs + RunnablePassthrough | prompt | llm | parser）
  - 手写 RAG vs LangChain RAG 对比（流式 / 批量 / 切换向量库 / 调试透明度）
- **五、Day 32 知识速查**（OutputParser 选型表、LCEL RAG 链组件表、框架 vs 手写判断标准）
- **六、实践任务**（重写 Day 8 抽取 / 故意出错验证 OutputFixingParser / 完整 RAG 链运行）
- **七、下一步预告**（Day 33：LangGraph StateGraph + Node 重写 ReAct 循环）

---

### [day33_langgraph_basics_react_rewrite.md](学习笔记/day33_langgraph_basics_react_rewrite.md) — Day 33：LangGraph 基础：用状态图重写 ReAct

- **一、为什么需要 LangGraph：while 循环的三个隐性问题**
  - Day 25 手写 ReAct 的状态在哪里（隐式 messages 列表）
  - 隐式状态带来的三个问题（不可中断 / 不可观测 / 不可持久化）
  - LangGraph 的核心主张：把状态显式化
- **二、三个核心概念：StateGraph / Node / Edge**
  - State：显式的 Agent 状态快照
  - Node：处理状态的 Runnable（接收 State，返回更新字典）
  - Edge：固定边 / 条件边 / 入口边 / 结束边
- **三、State 的设计：TypedDict 与 Reducer**
  - 用 TypedDict 定义 State
  - Reducer：直接覆盖 vs add_messages 追加
  - ReAct 场景下 State 需要哪些字段
- **四、实战：用 StateGraph 重写 Day 25 的 ReAct 工作流**
  - Day 25 手写版核心逻辑回顾（while 循环结构）
  - Node 拆分：call_model / call_tools / should_continue 路由函数
  - 完整 LangGraph ReAct Demo（含工具定义、图构建、运行）
  - 两版本对比：手写 while vs StateGraph（6 个维度）
- **五、Day 33 知识速查**（核心 API 速查、Node 签名规范、使用场景判断表）
- **六、实践任务**（跑通 Demo / 打印每步状态 / 可视化图结构）
- **七、下一步预告**（Day 34：条件边与分支路由，工具失败走重试的三路路由）

---

### [day34_conditional_edges_routing.md](学习笔记/day34_conditional_edges_routing.md) — Day 34：条件边与分支路由

- **一、从二路到多路：条件边解决什么问题**
  - Day 33 的 should_continue 只是最简单的二路条件边
  - 手写 while 里的 if/elif/else 散落且没有名字、无法可视化
  - 条件边把每个分支变成有名字、可画出来的边（一等公民）
- **二、add_conditional_edges 的完整用法**
  - 三个参数：源节点 / 路由函数 / 映射表（key → 目标节点）
  - 路由函数的三条约束（只读 State、返回字符串 key、不是 Node）
  - 映射表写法 vs 直接返回节点名（前者把业务语义与节点名解耦）
- **三、条件边 vs 固定边：什么时候用哪个**
  - 判断标准：下一步去向是否由 State 运行时内容决定
  - 常见误区：路由函数只返回一个值时该用固定边（假分支的误导性）
- **四、实战：给 ReAct 图加错误处理分支**
  - 需求与图结构（失败走 retry_node、成功走 summarize）
  - State 新增 tool_ok / retry_count，retry_count 为何不复用 iteration
  - 新增节点与路由函数（call_tools 记录 tool_ok、retry_node 记账、summarize 降级汇总）
  - 完整代码 + 构造失败案例（查询不支持城市观察走 retry 分支）
- **五、Day 34 知识速查**（条件边 API 速查、条件边 vs 固定边判断表、路由函数三约束）
- **六、实践任务**（成功/失败两路验证 / stream 逐节点观察 / 改 MAX_RETRIES 验证降级）
- **七、下一步预告**（Day 35：循环终止与 Checkpoint 持久化，MemorySaver 中断恢复）

---

### [day35_checkpoint_and_loop_termination.md](学习笔记/day35_checkpoint_and_loop_termination.md) — Day 35：循环终止与 Checkpoint 持久化

- **一、循环终止：LangGraph 里的终止条件设计**
  - 回顾 Day 33/34 的终止方式（路由函数里的常量比较）
  - LangGraph 内置 recursion_limit：最后一道防线（Node 执行次数之和，超限抛 GraphRecursionError）
  - 终止条件双保险设计原则（业务层管语义终止、框架层管系统兜底）
- **二、Checkpoint 是什么：持久化执行快照**
  - 为什么需要 Checkpoint（进程崩溃/长任务/Human-in-the-loop 三场景）
  - Checkpoint vs State：每个 Node 后的历史快照 vs 当前运行时状态
  - thread_id：区分不同会话，相同 thread_id 共享快照序列
- **三、MemorySaver：内存级 Checkpoint 接入**
  - 接入方式：compile 时传 checkpointer（节点/边代码零改动）
  - invoke 时必须传 config（含 thread_id），原因与 Checkpointer 读写机制
  - get_state / get_state_history 查询快照（next 字段判断是否暂停）
- **四、实战：中断 → 查看暂停状态 → 从原状态恢复**
  - interrupt_before 指定暂停节点（compile 时配置）
  - 查看暂停位置与工具调用参数（为 Day 36 Human-in-the-loop 做铺垫）
  - invoke(None) 恢复执行原理 + update_state 恢复前修改 State
  - 完整演示代码（含历史快照序列打印）
- **五、SqliteSaver：Checkpoint 跨进程重启存活**
  - MemorySaver vs SqliteSaver 对比（存储位置、进程重启、适用场景）
  - SqliteSaver 接入方式（只改初始化，其余零改动）
- **六、Day 35 知识速查**（Checkpoint 核心 API 表、StateSnapshot 字段、终止条件双保险表）
- **七、实践任务**（验证中断恢复 / 历史快照 / update_state / SqliteSaver）
- **八、下一步预告**（Day 36：Human-in-the-loop，interrupt + update_state 实现审核/拒绝/修改三路径）

---

### [day36_human_in_the_loop.md](学习笔记/day36_human_in_the_loop.md) — Day 36：Human-in-the-loop 人工审核节点

- **一、从"暂停"到"审核"：Day 35 还差什么**
  - Day 35 只有暂停和直接继续，缺少人工决策逻辑
  - 高风险操作的判断标准（不可逆/外部副作用/资金/隐私/高影响范围）
  - 三条审核路径的设计目标（批准/修改参数/拒绝）
- **二、三条审核路径的实现原理**
  - 路径 1 批准：invoke(None) 直接继续
  - 路径 2 修改参数：update_state 替换 AIMessage（同 id 覆盖），再 invoke(None)
  - 路径 3 拒绝：update_state 注入假 ToolMessage + as_node="call_tools" 跳过工具执行
- **三、实战：给"发送邮件"工具加人工审核**
  - 场景（不可逆+外部副作用，典型高风险操作）与图结构（interrupt_before call_tools）
  - 完整代码（审核辅助函数：show_pending / approve / modify_and_approve / reject）
  - 演示三条路径（拒绝时 📧 模拟发送不打印，验证工具未执行）
- **四、高风险操作的判断标准与设计原则**
  - 必须审核 vs 无需审核对比表
  - 精细化粒度：按工具名过滤，低风险工具自动执行
  - update_state 的 as_node 行为对比表（不传/call_tools/call_model）
- **五、Day 36 知识速查**（三路径速查代码、as_node 行为表、同 id 替换原理、高风险判断标准）
- **六、实践任务**（三条路径验证 / get_state_history 看快照 / 去掉 as_node 观察异常）
- **七、下一步预告**（Day 37：第 5 周复盘，LangChain vs LangGraph 适用边界横向对比）

---

### [day37_week5_review.md](学习笔记/day37_week5_review.md) — Day 37：第 5 周复盘：LangChain / LangGraph 解决了什么问题

- **一、第 5 周产出回顾**（Day 31–36 升级路径：链路标准化 → 状态显式 → 可中断审核）
- **二、复盘问题 1：LangChain LCEL 解决了什么问题**
  - 原生 API 的三个重复劳动（Provider 绑定 / 链路组装 / 输出解析）
  - LCEL 标准化了什么、隐藏了什么（透明度权衡）
  - 什么场景不值得引入 LangChain
- **三、复盘问题 2：LangGraph 解决了什么问题**
  - 手写 while 循环的三个结构性缺陷（状态隐式 / 不可中断 / 不可持久化）
  - LangGraph 的四项能力（状态显式 / 可视化 / 持久化 / 可中断恢复）
  - LangChain 和 LangGraph 是互补关系：LCEL 管单步链路，LangGraph 管多步编排
- **四、复盘问题 3：什么场景手写仍然够用**
  - 三个框架各自引入的成本对比
  - 引入 LangChain / LangGraph / 手写 while 的判断 checklist
- **五、适用边界对比表**（原生 API vs LangChain vs LangGraph，10 个维度横向对比）
- **六、本周知识地图**（Day 31–36 各天核心产出与解决问题一览表）

---

### [day38_understanding_mcp.md](学习笔记/day38_understanding_mcp.md) — Day 38：理解 MCP（Model Context Protocol）

- **一、为什么需要 MCP：工具集成的碎片化问题**
  - 现有工具集成模式（同进程函数注册）的三个局限
  - MCP 的核心主张：标准化工具服务器，USB-C 类比
- **二、MCP 的三种核心能力**
  - Tools（可执行操作，模型触发）、Resources（数据拉取，Client 主动）、Prompts（提示词模板）
  - 三者副作用对比：Tools 可能有副作用，Resources 通常只读，Prompts 纯只读
- **三、Server / Client 架构与交互流程**
  - MCP Client ↔ Server 交互流程图（list_tools → 注册给模型 → call_tool 转发 → 结果返回）
  - 独立进程架构的三个收益（语言无关 / 可复用 / 进程隔离）
- **四、MCP vs Function Calling：不同层的协议**
  - Function Calling 是"模型层"约定（模型如何表达工具调用意图）
  - MCP 是"连接层"协议（工具服务如何被标准化、跨应用复用）
  - 两者关系：MCP Server 通过 Function Calling 把工具暴露给模型
- **五、MCP vs A2A：两个协议解决不同层的问题**
  - MCP 管"模型与工具/数据的连接"、A2A 管"Agent 与 Agent 的任务委派"
  - 两层协议对比图（多 Agent 系统里共存）
- **六、为什么 MCP 成为 2026 年的事实标准**（开放协议 / 生态积累 / 真实痛点 / 主流采纳）
- **七、知识速查表**（三种能力对比、MCP vs Function Calling vs A2A 三协议对比）
- **八、实践任务**（读 MCP 官方文档 / 浏览 filesystem Server 源码 / 用自己话解释 MCP 定位）

---

### [day39_minimal_mcp_server.md](学习笔记/day39_minimal_mcp_server.md) — Day 39：开发一个最小 MCP Server

- **一、从理论到代码：今天要做什么**（Day 23 同进程工具 → Day 39 独立进程 MCP Server）
- **二、MCP Python SDK 安装与 API 选型**
  - `pip install mcp`；FastMCP（高级装饰器）vs 低级 Server API
- **三、最小 MCP Server 实现**
  - `FastMCP("server-name")` 创建实例
  - `@mcp.tool()` 装饰器：自动从类型提示生成 Schema、从 docstring 读描述
  - Python 类型提示 → JSON Schema 映射表
  - `mcp.run()` 启动（默认 stdio transport）
- **四、把 Day 23 工具包装进来**
  - 天气查询工具（`get_weather`）、汇率查询工具（`get_exchange_rate`）
  - 完整 Server 文件（~40 行有效代码）
- **五、stdio Transport：Server 怎么运行**
  - stdio vs HTTP transport 的适用场景对比
  - Client spawn Server 子进程的通信机制
- **六、连接 Claude Code：配置 .mcp.json**
  - 项目级 `.mcp.json` 格式（command / args / env）
  - 验证 Server 已连接的方法
- **七、手动验证：list_tools 与 call_tool 的原始报文**（MCP Client SDK 测试脚本）
- **八、知识速查**（FastMCP 核心 API、配置格式、Day 23 vs Day 39 对比表）
- **九、实践任务**（安装验证 / 测试脚本 / 接入 Claude Code / 扩展新工具）

---

### [day40_cross_session_memory.md](学习笔记/day40_cross_session_memory.md) — Day 40：跨对话长期记忆

- **一、为什么需要长期记忆：短期上下文的局限**（session messages 重启即消失的用户体验问题）
- **二、记忆分层设计**
  - 三层记忆结构（工作记忆 / 情节记忆 / 语义记忆）
  - 长期记忆的三类内容（用户偏好 / 事实 / 历史摘要）
- **三、最简实现：JSON 文件存储用户偏好**
  - `memory.py` 读写模块（load / save / set_preference / get_preference）
  - `remember_preference` 工具 + System Prompt 引导模型主动写入
  - `build_system_prompt()` 把记忆注入 System Prompt
  - 跨会话验证流程（会话 1 记忆 → 重启 → 会话 2 直接使用）
- **四、进阶：向量存储记忆**
  - KV 存储不够的场景（自由文本、需要语义检索）
  - 向量化记忆的写入与检索伪代码
- **五、记忆增长控制：防止无限膨胀**
  - 去重与更新（KV 天然覆盖）、摘要压缩、LRU 淘汰
- **六、mem0 参考实现**
  - add / search / update 三个核心接口
  - 分层设计思路（LLM 提取 → 向量化 → 按需检索）
  - 手写 vs mem0 的引入决策标准
- **七、扩展：作为 MCP 工具暴露记忆能力**（给 Day 39 MCP Server 加记忆工具）
- **八、知识速查**（三层记忆速查、注入模式、两种写入方式对比）
- **九、实践任务**（跨会话验证 / 注入对比实验 / MCP 记忆工具扩展）

---

### [day41_multi_agent_collaboration.md](学习笔记/day41_multi_agent_collaboration.md) — Day 41：多 Agent 协作模式

- **一、为什么需要多 Agent 协作**（单 Agent 的规划弱、容错差、不可替换三个局限）
- **二、Planner / Executor / Critic 三角色设计**
  - 各角色职责边界与 System Prompt 设计原则
  - 能做什么、不做什么的边界约束
- **三、Agent 间的消息传递协议**
  - SubTask（task_id / description / tool_name / tool_args / depends_on）
  - TaskResult（task_id / status / result / error）
  - CriticVerdict（passed / missing[] / reason / retry_hint）
- **四、协作 Demo 实现**
  - Planner 实现（structured output 拆子任务）
  - Executor 实现（依赖检查 + 工具注册表 + 错误处理）
  - Critic 实现（对照原始问题判断完整性）
  - 主流程与可观察协作日志（Planner/Executor/Critic 三节打印）
- **五、思考题：A2A 协议解决了哪些工程问题**
  - Demo 的三个短板（状态无持久化 / 同步阻塞 / 工具表硬编码）
  - Task 状态机 / 流式 Push / Agent Card 各自解决的短板
- **六、MCP + A2A：两层连接的完整图景**（三层协议对比表）
- **七、知识速查**（三角色边界、数据结构、A2A 三项设计速查）
- **八、实践任务**（Demo 跑通 / 故意失败验证 / 复杂问题拆解 / 重试机制思考）

---

### [day42_week6_review_and_integration.md](学习笔记/day42_week6_review_and_integration.md) — Day 42：阶段项目整合 + 第 6 周复盘

- **一、第 6 周产出回顾**（Day 38–41 升级路径：工具标准化 → 用户体验 → 任务复杂度）
- **二、Day 27 原项目的短板与升级方案**
  - 原项目四个短板（工具耦合 / 无跨会话记忆 / 规划瓶颈 / 不可观测）
  - 升级版 Agent 架构图（LangGraph + MCP + 记忆 + 多 Agent 分层）
  - 四项能力各自解决了哪个短板
- **三、复盘问题 1：MCP 的收益边界**（何时值得引入 MCP，何时手写更合适）
- **四、复盘问题 2：长期记忆与工具调用的职责划分**（用户明确指定时以当前输入为准）
- **五、复盘问题 3：多 Agent 何时值得引入**（判断标准：可分解性 + 容错需求）
- **六、Agent 行为评估框架**
  - 测试 Case 三元组结构（输入 / 预期工具调用序列 / 预期回答要点）
  - 三类任务（single_tool / multi_step / boundary）评估维度对比
  - 15 条 Case 示例评估报告（含通过率表格和根因分析）
  - 通过率低时的根因定位流程
- **七、本周知识地图**（Day 38–41 横向对比：主题 / 产出 / 解决的问题 / 核心 API）
- **八、实践任务**（升级版项目整合 / 跑 15 条评估 case / 修 Planner Prompt 回归测试）

---

### [day43_observability_langfuse.md](学习笔记/day43_observability_langfuse.md) — Day 43：可观测性基础：接入 LangFuse/LangSmith

- **一、为什么"能跑"不等于"能被观测"**（logging 的局限 / LLM 应用的三项额外可观测性需求）
- **二、Trace 和 Span：调用链的两个核心概念**（Trace = 一次请求完整故事 / Span = 故事里每一章 / LLM 操作对应关系）
- **三、LangFuse vs LangSmith：选哪个**（开源性 / SDK 覆盖 / 国内访问 / 选型标准）
- **四、接入 LangFuse：三种方式**
  - 方式一：OpenAI SDK 拦截（最少改动）
  - 方式二：手动 SDK 埋点（最灵活）
  - 方式三：LangChain 回调（已有 LCEL 链）
- **五、在 Dashboard 里能看到什么**（Trace 列表 / 瀑布图详情 / 用 Dashboard 定位 multi_step 失败）
- **六、给 LangGraph Agent 加可观测性**（`@observe` 装饰每个 Node，整图执行成为 Trace）
- **七、Day 43 知识速查**（Trace/Span 概念 / 三种接入方式速查 / LangFuse vs logging 对比）
- **八、实践任务**（注册 LangFuse / 跑 3 类请求验证 / 瀑布图解读 / 加业务语义）

---

### [day44_structured_logging_cost_dashboard.md](学习笔记/day44_structured_logging_cost_dashboard.md) — Day 44：结构化日志与成本监控面板

- **一、为什么日志必须结构化**（纯文本日志的四大致命缺陷 / 结构化 JSONL 的核心优势）
- **二、字段设计详解**
  - trace_id：关联同一次请求的所有记录
  - tokens 和 cost：成本的原子单位（input/output 分开、定价公式）
  - latency：三个维度（total / llm / tool）
  - function_name：成本归因的关键
- **三、给 Day 28 日志系统加结构化字段**（`structured_logger.py` 实现 / Agent 调用点埋点）
- **四、成本聚合脚本**（JSONL 格式约定 / `cost_report.py` 实现 / 按天/按功能报表输出示例）
- **五、LangFuse 与本地日志的分工**（实时调试 vs 批量分析，两者互补）
- **六、Day 44 知识速查**（必备字段清单 / 纯文本 vs 结构化对比 / 成本计算公式）
- **七、实践任务**（建 logger / 埋点 / 跑报表 / 定位高成本功能）

---

### [day29_testing_and_optimization.md](学习笔记/day29_testing_and_optimization.md) — Day 29：测试和优化

- **一、为什么 LLM 项目需要系统测试**
  - 1.1 LLM 测试 vs 普通软件测试（确定性 vs 概率性、assertEqual vs 语义匹配）
  - 1.2 四个测试维度（输出稳定性 / 工具触发准确率 / 检索准确率 / 成本合理性）
  - 1.3 10 组测试用例的设计原则（覆盖边界，不只测正常情况）
- **二、输出稳定性测试**
  - 2.1 稳定性的定义（核心行为一致，措辞可不同）
  - 2.2 temperature=0 时的真实稳定性（贪心解码仍有不稳定来源）
  - 2.3 稳定性测试实现（多次运行 + 工具触发行为对比）
- **三、工具调用准确率测试**
  - 3.1 触发准确率：精确率 / 召回率 / F1 定义与计算
  - 3.2 误触发与漏触发案例分析（description 过宽、别名未处理、多工具歧义）
  - 3.3 工具调用准确率测试实现（ToolTestCase + evaluate_tool_accuracy）
  - 3.4 优化触发准确率的三个手段（精化 description / System Prompt 护栏 / 参数规范化）
- **四、检索准确率测试（RAG 场景）**
  - 4.1 检索准确率的核心问题
  - 4.2 Hit Rate 与 MRR 两个指标（定义 + 公式 + 目标值）
  - 4.3 检索准确率测试实现（test_retrieval 函数）
- **五、成本分析**
  - 5.1 每轮对话的 Token 消耗结构（System Prompt + 历史 + 工具 Schema + 消息）
  - 5.2 两大成本陷阱（历史未截断 / 工作流失控）
  - 5.3 成本分析实现（CostRecord + print_cost_report）
  - 5.4 四类成本优化手段（历史截断 / 按需工具 / Prompt 压缩 / 模型路由）
- **六、完整测试记录表设计**
  - 6.1 测试记录表结构（10 行表格 + 汇总 + 优先级分析）
  - 6.2 完整测试脚本（run_test_suite，覆盖四维度）
  - 6.3 结果分析与改进优先级（P0/P1/P2/P3 矩阵 + 快速修复对照表）
- **七、Day 29 知识速查**（测试维度指标表、触发准确率优化优先手段）
- **八、实践任务**（任务清单 + 产出标准）
- **九、下一步预告**（Day 30 整理作品与总结）

---

### [day28_engineering_details.md](学习笔记/day28_engineering_details.md) — Day 28：补工程细节

- **一、工程细节的价值**
  - 1.1 "能跑"和"稳定跑"的差距（四个测试场景对比）
  - 1.2 四件套：异常处理 / 日志 / 配置验证 / 输出校验职责分工图
- **二、异常处理：分层设计**
  - 2.1 LLM 项目的异常分类（网络/认证/工具/格式/上下文 五类）
  - 2.2 工具层异常处理（返回 dict，不抛异常）
  - 2.3 工作流层异常处理（重试策略：RateLimitError / APITimeoutError）
  - 2.4 UI 层兜底（try/except Exception + 用户友好文案）
- **三、日志：三类关键信息**
  - 3.1 启动日志（API Key 脱敏打印、配置摘要）
  - 3.2 请求日志（耗时 + Token 消耗，用于性能分析和成本监控）
  - 3.3 错误日志（logger.exception 自动附 traceback + 上下文）
  - 3.4 日志配置：basicConfig 在主入口调用一次，子模块用 getLogger(__name__)
- **四、配置验证：Fail-Fast 原则**
  - 4.1 fail-fast vs fail-slow 对比（配置错误时的体验差距）
  - 4.2 启动时配置验证实现（errors 列表 + sys.exit(1)）
  - 4.3 不同类型配置项的验证策略（字符串/整数/枚举/文件路径/URL）
- **五、输出校验：防止脏数据传播**
  - 5.1 工具返回值校验（必要字段检查、error dict 透传）
  - 5.2 LLM 输出格式校验（Pydantic + response_format json_object + 降级）
  - 5.3 工作流整体输出校验（空回答兜底）
- **六、完整工程化改造示例**（core/config.py + core/workflow.py 改造后完整代码）
- **七、Day 28 知识速查**（四件套速查表、异常处理分层原则）
- **八、实践任务**（任务清单 + 产出标准）
- **九、下一步预告**（Day 29 测试和优化）

---

### [day27_complete_project.md](学习笔记/day27_complete_project.md) — Day 27：整合成完整作品

- **一、整合日的核心任务**
  - 1.1 三选一项目方向（文档问答 / 客服助手 / 工具个人助理对比表）
  - 1.2 整合 vs 重写：正确的姿势（四步整合流程）
  - 1.3 功能边界：砍掉做不完的部分（核心/增强/坚决不做三级）
- **二、标准项目目录结构**
  - 2.1 推荐目录布局（完整目录树 + 文件说明）
  - 2.2 各目录的职责说明（tools / core / app.py 分工表）
  - 2.3 必须有的四个文件（.env.example / .gitignore / requirements.txt / README.md）
- **三、可调用工具的个人助理（完整实现）**
  - 3.1 功能设计（天气 + 汇率 + 知识问答 + 调用链展示）
  - 3.2 核心模块实现（config.py / client.py / tools/__init__.py / workflow.py）
  - 3.3 完整入口与 Gradio 界面（app.py 约 60 行 + 运行方式）
- **四、README 工程化写法**
  - 4.1 README 的必要章节（项目描述 / 功能 / 快速开始 / 技术栈 / 截图）
  - 4.2 快速启动指南（安装 → 配置 → 运行三步，含示例命令）
  - 4.3 让别人 5 分钟跑起来的关键（5 个常见疏漏）
- **五、Day 27 知识速查**（整合检查清单、模块调用关系图）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 28 补工程细节）

---

### [day26_simple_ui.md](学习笔记/day26_simple_ui.md) — Day 26：添加简单界面

- **一、为什么要加界面**
  - 1.1 命令行 Demo 的三个瓶颈（不可分享、无视觉呈现、单次交互）
  - 1.2 Streamlit vs Gradio：选哪个（定位对比、学习曲线、聊天界面支持）
- **二、Gradio 快速入门**
  - 2.1 安装与最小示例（15 行完整可运行聊天 Demo）
  - 2.2 gr.Interface vs gr.ChatInterface（布局示意图 + 选型指南）
  - 2.3 常用组件速查（文本/交互/对话/状态类组件）
- **三、接入 LLM 的关键技巧**
  - 3.1 流式输出（yield 生成器实现打字机效果）
  - 3.2 在聊天界面展示工具调用链（追加消息 vs gr.Blocks 独立面板两种方式）
  - 3.3 状态管理：跨轮保持对话历史（gr.State 用法）
- **四、完整 Demo：带工具调用链的出行规划助手**
  - 4.1 界面设计（左侧聊天 + 右侧调用链 ASCII 布局图）
  - 4.2 完整实现（Gradio Blocks 自定义布局 + 工具调用链格式化展示）
- **五、Day 26 知识速查**（关键参数速查表、最小流式聊天模板、常见报错排查）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 27 整合成完整作品）

---

### [day25_multi_step_workflow.md](学习笔记/day25_multi_step_workflow.md) — Day 25：多步工作流

- **一、多步工作流的核心概念**
  - 1.1 单步 vs 多步：本质区别（固定 2 次 vs 运行时确定 N+1 次 API 调用）
  - 1.2 ReAct 模式：推理 + 行动的循环（决策 → 执行 → 再决策流程图）
  - 1.3 调用链的终止条件（model_done / max_iterations / 连续错误三种退出）
- **二、实现循环调用结构**
  - 2.1 基础 while 循环框架（每轮 API 调用 + 退出判断）
  - 2.2 安全限制：最大迭代次数（不同场景的推荐值 + Token 增长分析）
  - 2.3 工具调用历史的完整记录（每轮追加规则 + 不能删 tool_calls 的原因）
- **三、可观测性：让推理过程透明**
  - 3.1 为什么多步工作流必须可观测（失败点分析）
  - 3.2 调用链日志的设计（WorkflowLogger 实现）
  - 3.3 结构化的调用链记录（WorkflowResult dataclass）
- **四、完整多步工作流 Demo**
  - 4.1 场景设计：出行规划助手（天气 + 汇率双工具链）
  - 4.2 完整实现（带日志、WorkflowResult 记录、强制终止兜底）
  - 4.3 典型调用链示例（0/1/2 步工具调用 + 并行工具调用）
- **五、Day 25 知识速查**（单步 vs 多步对比表、最小模板、常见问题速查）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 26 添加简单界面）

---

### [day24_single_tool_demo.md](学习笔记/day24_single_tool_demo.md) — Day 24：单工具调用 Demo

- **一、tool_choice 参数深度解析**
  - 1.1 三种模式的行为差异（auto / none / required）
  - 1.2 强制指定工具（指定名称模式）
  - 1.3 什么时候用哪种模式（场景对照表）
- **二、模型如何决定触发工具**
  - 2.1 触发决策的影响因素（意图匹配、description 清晰度、自信度）
  - 2.2 调整触发边界的实用方法（修改 description + System Prompt 兜底）
  - 2.3 模型不调工具时该怎么办（诊断步骤）
- **三、完整单工具调用 Demo**
  - 3.1 核心调用逻辑（最简洁版）
  - 3.2 带日志的完整实现（天气 + 汇率双工具、日志记录、耗时统计）
- **四、多轮对话中的工具调用**
  - 4.1 工具调用历史的保存规则（为什么 tool_calls 消息不能删）
  - 4.2 跨轮引用工具结果（4 轮对话示例）
- **五、Day 24 知识速查**（tool_choice 速查、最简代码框架、常见问题排查表）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 25 多步工作流）

---

### [day23_define_first_tool.md](学习笔记/day23_define_first_tool.md) — Day 23：定义第一个工具

- **一、工具参数设计原则**
  - 1.1 参数设计的核心目标（为 LLM 填写而设计，非为人类）
  - 1.2 必填 vs 可选参数的决策（决策流程图 + 反模式）
  - 1.3 参数类型约束与 enum 限制（宽松 vs 严格约束对比）
  - 1.4 description 的写作标准（工具四件套 + 参数两件套）
- **二、输入输出定义规范**
  - 2.1 工具返回格式设计（平铺优于嵌套 + summary 字段价值）
  - 2.2 错误处理：返回 dict 还是抛异常（两种方式对比 + 标准错误格式）
  - 2.3 让输出对模型"友好"（缩写 vs 自解释字段名对比）
- **三、三个真实场景工具实现**
  - 3.1 查天气工具（wttr.in 免费 API + 完整错误处理）
  - 3.2 查汇率工具（exchangerate-api + 备用离线数据）
  - 3.3 查本地知识库工具（简化版向量检索，接入 RAG 体系）
- **四、工具独立测试**
  - 4.1 工具函数测试策略（正常路径 + 错误路径 + assert 工具函数）
  - 4.2 Schema 校验测试（validate_tool_schema 自动检查规范性）
- **五、Day 23 知识速查**（完整工具定义模板、函数模板、设计检查清单）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 24 单工具调用 Demo）

---

### [day22_tool_calling_basics.md](学习笔记/day22_tool_calling_basics.md) — Day 22：理解 Tool Calling

- **一、Tool Calling 的核心概念**
  - 1.1 什么是 Tool Calling（模型决策 vs 代码执行）
  - 1.2 "回答问题"和"调用工具做事"的本质区别（数据来源 / 副作用 / 回答依据三维对比）
  - 1.3 模型何时决定调用工具（意图识别 + description 清晰度）
- **二、Tool Calling 完整交互流程**
  - 2.1 完整流程图（5 步：注册工具 → 模型决策 → 代码执行 → 结果传回 → 最终回答）
  - 2.2 工具定义的结构（Function Schema：name / description / parameters）
  - 2.3 模型返回的 tool_calls 结构（id / name / arguments 字段解析）
  - 2.4 工具结果的传入方式（role: tool + tool_call_id 匹配）
- **三、最小 Tool Calling 实现**
  - 3.1 工具定义与注册（天气查询 + 计算器两个工具示例）
  - 3.2 工具分发器与执行（dispatch_tool + 安全计算）
  - 3.3 完整可运行代码（双次 API 调用 + 多工具处理）
- **四、Tool Calling vs RAG vs 普通对话**
  - 4.1 三种交互模式对比（数据新鲜度 / 私有数据 / 副作用 / 延迟 / 场景）
  - 4.2 Tool Calling 与 Agent 的关系（单步 vs 多步循环推理）
- **五、Day 22 知识速查**（5 步流程、关键参数表、最小代码模板）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 23 工具设计原则）

---

### [day21_week3_review.md](学习笔记/day21_week3_review.md) — Day 21：第 3 周复盘

- **一、第 3 周全景回顾**
  - 1.1 Day 15–20 知识地图（完整 ASCII 流程图）
  - 1.2 本周六个主题的逻辑链（文档读取 → 切分 → Embedding → 检索 → 生成 → 引用）
- **二、深度复盘三大问题**
  - 2.1 RAG 准确率主要受哪些环节影响（五环节影响链 + 诊断优先级 + 调试代码）
  - 2.2 Chunk 切分为什么会直接影响答案质量（三条影响路径 + 参数选择指南）
  - 2.3 为什么引用来源对业务场景很重要（信任度可预测性 + 三类场景必要性）
- **三、完整最小 RAG Demo**（整合 Day 16–20：加载/切分/向量化/检索/生成/校验）
- **四、第 3 周完整工程骨架**（模块职责表 + 接口契约）
- **五、Day 21 知识速查**（六主题一览、RAG 问题诊断速查、关键参数经验值）
- **六、实践任务**（任务清单 + 产出标准）
- **七、下一步预告**（Day 22 Tool Calling 方向）

---

## 🗺️ 学习路线（四阶段）

| 阶段 | 主题 | 预估周期 | 对应 30 天路线 |
| --- | --- | --- | --- |
| 一 | 基础与提示词工程 | 3–4 周 | Day 1–14 |
| 二 | RAG 核心应用架构 | 3–4 周 | Day 15–21 |
| 三 | 智能体与工程化 | 4–6 周 | Day 22–30 + 延伸 |
| 四 | 底层部署与模型定制（按需） | 4–8 周 | 30 天之后 |

详见 [`plan.md`](规划文档/plan.md)。

## 📒 学习笔记进度

- [x] [Day 1 · 理解大模型应用开发的全景](学习笔记/day01_llm_app_overview.md)
- [x] [Day 2 · 补 Python 最小基础](学习笔记/day02_python_basics.md)
- [x] [Day 3 · 第一次调用模型 API](学习笔记/day03_first_api_call.md)
- [x] [Day 4 · 做一个命令行聊天 Demo](学习笔记/day04_cli_chat_demo.md)
- [x] [Day 5 · 做一个文章摘要器](学习笔记/day05_text_summarizer.md)
- [x] [Day 6 · 做一个信息抽取工具](学习笔记/day06_info_extractor.md)
- [x] [Day 7 · 第 1 周复盘](学习笔记/day07_week1_review.md)
- [x] [Day 8 · 学习结构化输出](学习笔记/day08_structured_output.md)
- [x] [Day 9 · 增加输出校验与异常处理](学习笔记/day09_error_handling.md)
- [x] [Day 10 · 做一个文本分类器](学习笔记/day10_text_classifier.md)
- [x] [Day 11 · 练 Prompt 优化](学习笔记/day11_prompt_optimization.md)
- [x] [Day 12 · 建立成本意识](学习笔记/day12_cost_awareness.md)
- [x] [Day 13 · 补配置管理和日志](学习笔记/day13_config_and_logging.md)
- [x] [Day 14 · 第 2 周复盘](学习笔记/day14_week2_review.md)
- [x] [Day 15 · 理解 RAG 基本原理](学习笔记/day15_rag_from_scratch.md)
- [x] [Day 16 · 读取本地文档](学习笔记/day16_document_loader.md)
- [x] [Day 17 · 做文本切分](学习笔记/day17_text_chunking.md)
- [x] [Day 18 · 接入 Embedding 和向量检索](学习笔记/day18_embedding_and_retrieval.md)
- [x] [Day 19 · 把检索结果喂给模型回答](学习笔记/day19_rag_generation.md)
- [x] [Day 20 · 给回答加引用](学习笔记/day20_answer_citation.md)
- [x] [Day 21 · 第 3 周复盘](学习笔记/day21_week3_review.md)
- [x] [Day 22 · 理解 Tool Calling](学习笔记/day22_tool_calling_basics.md)
- [x] [Day 23 · 定义第一个工具](学习笔记/day23_define_first_tool.md)
- [x] [Day 24 · 完成单工具调用 Demo](学习笔记/day24_single_tool_demo.md)
- [x] [Day 25 · 做多步工作流](学习笔记/day25_multi_step_workflow.md)
- [x] [Day 26 · 给项目加一个简单界面](学习笔记/day26_simple_ui.md)
- [x] [Day 27 · 整合成一个完整作品](学习笔记/day27_complete_project.md)
- [x] [Day 28 · 补工程细节](学习笔记/day28_engineering_details.md)
- [x] [Day 29 · 测试和优化](学习笔记/day29_testing_and_optimization.md)
- [x] [Day 30 · 整理作品与总结](学习笔记/day30_project_summary.md)
- 🎉 **30 天学习完成！**
- [x] [Day 31 · LangChain 基础：LCEL 与核心抽象](学习笔记/day31_langchain_lcel_basics.md)
- [x] [Day 32 · 用 LangChain 重新实现结构化输出与 RAG 链](学习笔记/day32_langchain_structured_output_and_rag.md)
- [x] [Day 33 · LangGraph 基础：用状态图重写 ReAct](学习笔记/day33_langgraph_basics_react_rewrite.md)
- [x] [Day 34 · 条件边与分支路由](学习笔记/day34_conditional_edges_routing.md)
- [x] [Day 35 · 循环终止与 Checkpoint 持久化](学习笔记/day35_checkpoint_and_loop_termination.md)
- [x] [Day 36 · Human-in-the-loop 人工审核节点](学习笔记/day36_human_in_the_loop.md)
- [x] [Day 37 · 第 5 周复盘：LangChain/LangGraph 解决了什么问题](学习笔记/day37_week5_review.md)
- [x] [Day 38 · 理解 MCP（Model Context Protocol）](学习笔记/day38_understanding_mcp.md)
- [x] [Day 39 · 开发一个最小 MCP Server](学习笔记/day39_minimal_mcp_server.md)
- [x] [Day 40 · 跨对话长期记忆](学习笔记/day40_cross_session_memory.md)
- [x] [Day 41 · 多 Agent 协作模式（Planner/Executor/Critic）](学习笔记/day41_multi_agent_collaboration.md)
- [x] [Day 42 · 阶段项目整合 + 第 6 周复盘](学习笔记/day42_week6_review_and_integration.md)
- [x] [Day 43 · 可观测性基础：接入 LangFuse/LangSmith](学习笔记/day43_observability_langfuse.md)
- [x] [Day 44 · 结构化日志与成本监控面板](学习笔记/day44_structured_logging_cost_dashboard.md)

新增笔记请沿用 `dayNN_<主题>.md` 命名（两位数字便于排序），例如 `day06_info_extractor.md`。

## 🚀 如何开始

1. 先读 [`plan.md`](规划文档/plan.md) 建立整体认知，做一次[入门自测](规划文档/plan.md#零如何使用本路线)。
2. 打开 [`llm_app_30_day_roadmap.md`](规划文档/llm_app_30_day_roadmap.md)，按每日任务推进。
3. 每天学完在对应 `dayNN_*.md` 中记录笔记、完成实践任务。
