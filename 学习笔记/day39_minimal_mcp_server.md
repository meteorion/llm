# Day 39：开发一个最小 MCP Server

> 学习目标：用 MCP 官方 Python SDK 把 Day 23 定义的天气 / 汇率工具包装成一个真实的 MCP Server，让 Claude Code（或任意 MCP Client）能列出并调用这个 Server 暴露的工具；理解 `@mcp.tool()` 装饰器、stdio transport、以及 MCP Client 连接配置的完整流程
>
> 📚 所属阶段：**深化阶段 · 路线 A：LangChain / LangGraph / MCP 与多 Agent**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 39
>
> 🧭 导航：[← Day 38 · 理解 MCP（Model Context Protocol）](day38_understanding_mcp.md) → [Day 40 · 跨对话长期记忆](day40_cross_session_memory.md)

---

## 目录

- [一、从理论到代码：今天要做什么](#一从理论到代码今天要做什么)
- [二、MCP Python SDK 安装与 API 选型](#二mcp-python-sdk-安装与-api-选型)
  - [2.1 安装](#21-安装)
  - [2.2 FastMCP vs 低级 Server API](#22-fastmcp-vs-低级-server-api)
- [三、最小 MCP Server 实现](#三最小-mcp-server-实现)
  - [3.1 创建 Server 实例](#31-创建-server-实例)
  - [3.2 用 @mcp.tool() 注册工具](#32-用-mcptool-注册工具)
  - [3.3 类型提示如何变成 JSON Schema](#33-类型提示如何变成-json-schema)
  - [3.4 运行入口](#34-运行入口)
- [四、把 Day 23 工具包装进来](#四把-day-23-工具包装进来)
  - [4.1 天气查询工具](#41-天气查询工具)
  - [4.2 汇率查询工具](#42-汇率查询工具)
  - [4.3 完整 Server 文件](#43-完整-server-文件)
- [五、stdio Transport：Server 怎么运行](#五stdio-transportserver-怎么运行)
  - [5.1 什么是 stdio transport](#51-什么是-stdio-transport)
  - [5.2 为什么 MCP 默认用 stdio 而不是 HTTP](#52-为什么-mcp-默认用-stdio-而不是-http)
- [六、连接 Claude Code：配置 .mcp.json](#六连接-claude-code配置-mcpjson)
  - [6.1 配置文件位置与格式](#61-配置文件位置与格式)
  - [6.2 验证 Server 已连接](#62-验证-server-已连接)
- [七、手动验证：list_tools 与 call_tool 的原始报文](#七手动验证list_tools-与-call_tool-的原始报文)
- [八、Day 39 知识速查](#八day-39-知识速查)
- [九、实践任务](#九实践任务)
- [十、下一步预告](#十下一步预告)

---

## 一、从理论到代码：今天要做什么

Day 38 建立了理论框架：MCP Server 暴露 `list_tools` 和 `call_tool` 两个接口，Client 发现工具、把工具注册给模型、转发模型的工具调用请求。

今天把这个流程落地成代码，目标是：

1. 用 MCP Python SDK 写一个 Server，暴露 Day 23 定义的天气 / 汇率工具
2. 配置 Claude Code 连接这个 Server
3. 验证 Claude Code 能列出工具并成功调用

从"工具和应用同进程"（Day 23-25 的 `@tool` 函数）升级到"工具作为独立进程服务"（今天的 MCP Server）。代码变化量不大，但架构上的意义是：这个 Server 从此可以被任何 MCP Client 共享使用，不再和某个 AI 应用绑定。

---

## 二、MCP Python SDK 安装与 API 选型

### 2.1 安装

```bash
pip install mcp
```

验证安装：

```python
import mcp
print(mcp.__version__)
```

### 2.2 FastMCP vs 低级 Server API

MCP Python SDK 提供两层 API：

| API | 入口 | 特点 | 适用场景 |
|-----|------|------|---------|
| **FastMCP**（高级） | `from mcp.server.fastmcp import FastMCP` | 装饰器风格，自动从类型提示生成 JSON Schema，代码极简 | 日常开发、快速验证 |
| **低级 Server**（底层） | `from mcp.server import Server` | 手动实现 `list_tools` / `call_tool` handler，完全控制 | 需要动态生成工具列表、工具元数据高度定制 |

**今天用 FastMCP**。它的 `@mcp.tool()` 装饰器做的事情和 LangChain 的 `@tool` 类似：读取函数签名（参数名 + 类型提示）和 docstring，自动生成 MCP 工具描述。写法对已经熟悉 Day 23-25 的人几乎没有学习成本。

---

## 三、最小 MCP Server 实现

### 3.1 创建 Server 实例

```python
from mcp.server.fastmcp import FastMCP

# 参数是 Server 的名字，显示在 Client 的工具列表里
mcp = FastMCP("weather-tools")
```

`FastMCP` 实例管理着这个 Server 的所有工具、Resources 和 Prompts。这里的名字 `"weather-tools"` 会在 Client 端作为工具来源的标识。

### 3.2 用 @mcp.tool() 注册工具

```python
@mcp.tool()
def get_weather(city: str) -> str:
    """查询指定城市的当前天气。返回天气状况、气温和湿度。"""
    # 工具逻辑（见第四节）
    ...
```

`@mcp.tool()` 自动完成三件事：
1. 从 `city: str` 读取参数名和类型，生成 JSON Schema
2. 从 docstring 读取工具描述（这是模型决定何时调用的依据）
3. 把这个函数注册到 `mcp` 实例，在 Client 调用 `list_tools` 时返回

### 3.3 类型提示如何变成 JSON Schema

FastMCP 把 Python 类型提示翻译成 JSON Schema：

| Python 类型提示 | JSON Schema 类型 |
|----------------|----------------|
| `str` | `"type": "string"` |
| `int` | `"type": "integer"` |
| `float` | `"type": "number"` |
| `bool` | `"type": "boolean"` |
| `list[str]` | `"type": "array", "items": {"type": "string"}` |
| `Optional[str]` | `"type": "string"` + 从 required 移除 |

对比 Day 23 手写 JSON Schema 定义工具的方式：

```python
# Day 23：手写 JSON Schema（7 行）
{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的当前天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"]
        }
    }
}

# Day 39：FastMCP 装饰器（1 行注解 + 函数签名）
@mcp.tool()
def get_weather(city: str) -> str:
    """查询指定城市的当前天气。返回天气状况、气温和湿度。"""
    ...
```

**关键区别**：FastMCP 通过类型提示自动生成 Schema，参数的 description 从 docstring 里读——这意味着 docstring 要写清楚（它是模型唯一知道这个工具用途的信息来源）。

### 3.4 运行入口

```python
if __name__ == "__main__":
    mcp.run()
```

`mcp.run()` 默认使用 **stdio transport** 运行 Server（见第五节）。Server 启动后在 stdin 等待 Client 发来的 JSON-RPC 消息，响应写到 stdout。

---

## 四、把 Day 23 工具包装进来

### 4.1 天气查询工具

Day 23 的天气工具通过 Mock 数据模拟（真实项目替换成 API 调用）。MCP 版本几乎不改函数体，只换成 `@mcp.tool()` 装饰器：

```python
@mcp.tool()
def get_weather(city: str) -> str:
    """
    查询指定城市的当前天气状况。
    
    返回包含天气描述、温度（摄氏度）和湿度的字符串。
    如果城市名无法识别，返回提示信息。
    """
    weather_data = {
        "北京": {"condition": "晴", "temp": 22, "humidity": 45},
        "上海": {"condition": "多云", "temp": 26, "humidity": 72},
        "广州": {"condition": "小雨", "temp": 29, "humidity": 85},
        "深圳": {"condition": "阴", "temp": 28, "humidity": 78},
    }
    
    if city not in weather_data:
        return f"暂无 {city} 的天气数据，支持的城市：{', '.join(weather_data.keys())}"
    
    d = weather_data[city]
    return f"{city}：{d['condition']}，{d['temp']}°C，湿度 {d['humidity']}%"
```

**工具返回值为纯字符串**：MCP 工具的返回值会被 Client 转成 `ToolMessage` 传回给模型。返回纯文本（而不是 dict 或 JSON）是最稳妥的做法——模型读自然语言比读结构化数据更可靠，且避免 Client 在序列化上的歧义。

### 4.2 汇率查询工具

```python
@mcp.tool()
def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    """
    查询两种货币之间的即时汇率。
    
    参数：
    - from_currency: 源货币代码，如 USD、CNY、EUR、JPY
    - to_currency: 目标货币代码，如 USD、CNY、EUR、JPY
    
    返回汇率换算结果字符串，如 "1 USD = 7.25 CNY"。
    """
    # Mock 汇率数据（真实项目调用汇率 API）
    rates = {
        ("USD", "CNY"): 7.25,
        ("CNY", "USD"): 0.138,
        ("EUR", "CNY"): 7.89,
        ("CNY", "EUR"): 0.127,
        ("USD", "EUR"): 0.92,
        ("EUR", "USD"): 1.09,
        ("USD", "JPY"): 149.5,
        ("JPY", "USD"): 0.0067,
    }
    
    key = (from_currency.upper(), to_currency.upper())
    if key not in rates:
        return f"暂不支持 {from_currency} 到 {to_currency} 的汇率查询"
    
    rate = rates[key]
    return f"1 {from_currency.upper()} = {rate} {to_currency.upper()}"
```

### 4.3 完整 Server 文件

```python
# tools/weather_mcp_server.py

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-tools")


@mcp.tool()
def get_weather(city: str) -> str:
    """
    查询指定城市的当前天气状况。
    返回包含天气描述、温度（摄氏度）和湿度的字符串。
    如果城市名无法识别，返回提示信息。
    """
    weather_data = {
        "北京": {"condition": "晴", "temp": 22, "humidity": 45},
        "上海": {"condition": "多云", "temp": 26, "humidity": 72},
        "广州": {"condition": "小雨", "temp": 29, "humidity": 85},
        "深圳": {"condition": "阴", "temp": 28, "humidity": 78},
    }
    if city not in weather_data:
        return f"暂无 {city} 的天气数据，支持的城市：{', '.join(weather_data.keys())}"
    d = weather_data[city]
    return f"{city}：{d['condition']}，{d['temp']}°C，湿度 {d['humidity']}%"


@mcp.tool()
def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    """
    查询两种货币之间的即时汇率。
    参数：from_currency 源货币代码（USD/CNY/EUR/JPY），to_currency 目标货币代码。
    返回汇率换算结果字符串。
    """
    rates = {
        ("USD", "CNY"): 7.25,
        ("CNY", "USD"): 0.138,
        ("EUR", "CNY"): 7.89,
        ("CNY", "EUR"): 0.127,
        ("USD", "EUR"): 0.92,
        ("EUR", "USD"): 1.09,
        ("USD", "JPY"): 149.5,
        ("JPY", "USD"): 0.0067,
    }
    key = (from_currency.upper(), to_currency.upper())
    if key not in rates:
        return f"暂不支持 {from_currency} 到 {to_currency} 的汇率查询"
    rate = rates[key]
    return f"1 {from_currency.upper()} = {rate} {to_currency.upper()}"


if __name__ == "__main__":
    mcp.run()
```

这是一个完整的、可直接运行的 MCP Server，共约 40 行有效代码（不含注释）。

---

## 五、stdio Transport：Server 怎么运行

### 5.1 什么是 stdio transport

`mcp.run()` 默认使用 **stdio transport**：Server 通过 **标准输入（stdin）** 读取 Client 发来的请求，通过 **标准输出（stdout）** 写回响应，通信格式是 JSON-RPC 2.0。

```
MCP Client（Claude Code）
    │ 启动子进程：python weather_mcp_server.py
    │
    ├─── stdin ──► Server 进程（读取请求）
    └─── stdout ◄── Server 进程（写回响应）
```

Client 把 Server 作为子进程启动，通过 stdin/stdout 管道通信。Server 的进程生命周期由 Client 管理：Client 启动时 spawn Server，Client 退出时 kill Server。

### 5.2 为什么 MCP 默认用 stdio 而不是 HTTP

| | stdio transport | HTTP transport |
|--|--|--|
| **部署复杂度** | 零配置（只需要 `python server.py` 命令） | 需要端口、绑定地址、可能需要 TLS |
| **安全性** | 进程隔离，无需开放端口，无网络攻击面 | 需要处理认证、防火墙规则 |
| **适用场景** | 本地工具（文件系统、数据库、本地 API） | 远程工具服务（需要被多台机器访问） |
| **多 Client 支持** | 每个 Client spawn 一个独立 Server 进程 | 单个 HTTP Server 可服务多个 Client |

对于"本地开发工具"（如今天的天气/汇率工具），stdio 是最优选——零运维成本、天然进程隔离、无安全风险。需要把工具部署为团队共享服务时，才切换到 HTTP transport。

---

## 六、连接 Claude Code：配置 .mcp.json

### 6.1 配置文件位置与格式

Claude Code 支持两种 MCP Server 配置位置：

**项目级配置**（只在当前项目生效）：在项目根目录创建 `.mcp.json`

```json
{
  "mcpServers": {
    "weather-tools": {
      "command": "python",
      "args": ["tools/weather_mcp_server.py"]
    }
  }
}
```

**用户级配置**（全局生效）：`~/.claude/claude_desktop_config.json`（Claude Desktop）或通过 Claude Code 的 `/mcp` 命令添加

```json
{
  "mcpServers": {
    "weather-tools": {
      "command": "python",
      "args": ["/绝对路径/weather_mcp_server.py"]
    }
  }
}
```

配置字段说明：
- `command`：启动 Server 的可执行文件（`python` / `node` / `./server`）
- `args`：命令行参数列表，通常是脚本路径
- `env`（可选）：Server 进程的额外环境变量（如 API Key）

需要传 API Key 给 Server 时：

```json
{
  "mcpServers": {
    "weather-tools": {
      "command": "python",
      "args": ["tools/weather_mcp_server.py"],
      "env": {
        "WEATHER_API_KEY": "your-key-here"
      }
    }
  }
}
```

### 6.2 验证 Server 已连接

Claude Code 重启后，在对话里问：

```
你现在可以查天气吗？北京现在天气怎么样？
```

如果 Server 连接成功，Claude Code 会调用 `get_weather(city="北京")` 并返回结果。

也可以用 Claude Code 的 `/mcp` 命令查看已注册的 MCP Server 列表和工具清单，确认 `weather-tools` Server 显示在其中。

---

## 七、手动验证：list_tools 与 call_tool 的原始报文

不依赖 Claude Code，也可以用 MCP SDK 提供的测试工具直接验证 Server 的两个核心接口：

```python
# test_server.py — 用 MCP Client SDK 直接测试 Server
import asyncio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def test():
    server_params = StdioServerParameters(
        command="python",
        args=["tools/weather_mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. 初始化握手
            await session.initialize()

            # 2. 列出工具（list_tools）
            tools = await session.list_tools()
            print("=== 工具列表 ===")
            for tool in tools.tools:
                print(f"  {tool.name}: {tool.description}")
                print(f"  参数 Schema: {tool.inputSchema}")

            # 3. 调用工具（call_tool）
            result = await session.call_tool("get_weather", {"city": "上海"})
            print("\n=== 调用结果 ===")
            print(result.content[0].text)

            result2 = await session.call_tool(
                "get_exchange_rate",
                {"from_currency": "USD", "to_currency": "CNY"}
            )
            print(result2.content[0].text)


asyncio.run(test())
```

预期输出：

```
=== 工具列表 ===
  get_weather: 查询指定城市的当前天气状况。...
  参数 Schema: {'type': 'object', 'properties': {'city': {'type': 'string'}}, 'required': ['city']}
  get_exchange_rate: 查询两种货币之间的即时汇率。...
  参数 Schema: {'type': 'object', 'properties': {'from_currency': {...}, 'to_currency': {...}}, ...}

=== 调用结果 ===
上海：多云，26°C，湿度 72%
1 USD = 7.25 CNY
```

这段测试代码演示的是 Day 38 流程图里"Client 调用 Server"的完整过程：`initialize()` 握手 → `list_tools()` 拿工具列表 → `call_tool()` 执行工具。

---

## 八、Day 39 知识速查

### FastMCP 核心 API

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server-name")   # 创建 Server 实例

@mcp.tool()                     # 注册工具（自动从类型提示和 docstring 生成 Schema）
def my_tool(param: str) -> str:
    """工具描述（模型会读这里来判断何时调用）"""
    return "结果"

@mcp.resource("resource://path")  # 注册 Resource（数据源）
def my_resource() -> str:
    return "资源内容"

mcp.run()                       # 启动 Server（默认 stdio transport）
mcp.run(transport="sse")        # HTTP SSE transport（用于远程服务）
```

### MCP Server 配置格式

```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {"API_KEY": "..."}
    }
  }
}
```

### 从 Day 23 工具到 MCP 工具的对比

| | Day 23 手写工具（Function Calling） | Day 39 MCP 工具 |
|--|--|--|
| **定义方式** | 手写 JSON Schema dict + 独立函数 | `@mcp.tool()` + 类型提示 + docstring |
| **注册到** | 调用 API 时的 `tools=[]` 参数 | MCP Server 进程，通过 `list_tools` 暴露 |
| **运行位置** | 和 AI 应用同一进程 | 独立进程，Client 通过 stdio / HTTP 连接 |
| **可复用性** | 只属于当前应用 | 任何 MCP Client 都能连接使用 |
| **Schema 生成** | 全手写 | 从 Python 类型提示自动生成 |

---

## 九、实践任务

- [ ] 安装 `mcp` 包，运行 `python -c "from mcp.server.fastmcp import FastMCP; print('OK')"` 确认安装成功
- [ ] 把 `weather_mcp_server.py` 写到项目里（见第四节完整代码），用 `test_server.py` 直接测试 `list_tools` 和 `call_tool` 两个接口返回正确
- [ ] 在项目根目录创建 `.mcp.json`（见第六节），重启 Claude Code，验证能通过对话让 Claude 查天气和查汇率
- [ ] 扩展练习：给 Server 再加一个工具——比如 `list_supported_cities() -> str`（返回支持查询的城市列表），不改 Claude Code 配置，重启后验证新工具自动出现在工具列表里

**产出标准**：Claude Code 对话里输入"上海天气怎么样，再告诉我 1 美元换多少人民币"，Claude 依次调用两个工具并返回正确结果；用 `/mcp` 命令能看到 `weather-tools` Server 和它的工具列表。

---

## 十、下一步预告

Day 40 转向**跨对话长期记忆**：今天的 MCP Server 每次对话都是无状态的——用户上次说"常用货币是美元"，下次重启后模型不记得。Day 40 引入记忆层，让模型跨会话"记住"用户偏好（如常用城市、常用货币对），验证重启程序后同一个问题的回答能体现记忆生效。今天实现的 MCP Server 是个好的扩展点——可以给 Server 加一个 `remember_preference(key, value)` 工具，让模型主动把用户偏好写入持久存储。
