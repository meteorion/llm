# Day 3：第一次调用模型 API

> 学习目标：成功调用大模型 API，理解 HTTP 请求、API Key 管理和 JSON 数据格式
>
> 📚 所属阶段：**第一阶段 · 基础与提示词工程**（见 [`plan.md`](plan.md)）｜ 配套：[30 天路线](llm_app_30_day_roadmap.md) · Day 3
>
> 🧭 导航：[← Day 2 · Python 最小基础](day02_python_basics.md) → [Day 4 · 命令行聊天 Demo →](day04_cli_chat_demo.md)

---

## 一、API 调用基础概念

### 1.1 什么是 API

```
┌─────────────────────────────────────────────────────────────────┐
│                        API 调用原理                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   你的程序                        大模型服务                      │
│   ┌─────────┐                    ┌─────────┐                    │
│   │         │   HTTP 请求         │         │                    │
│   │  客户端  │ ──────────────────► │  服务端  │                    │
│   │         │   (问题 + API Key)   │         │                    │
│   │         │                     │  模型   │                    │
│   │         │   HTTP 响应         │  推理   │                    │
│   │         │ ◄────────────────── │         │                    │
│   │         │   (生成的回答)       │         │                    │
│   └─────────┘                    └─────────┘                    │
│                                                                  │
│   API = Application Programming Interface（应用程序编程接口）      │
│   本质：通过 HTTP 协议发送请求，接收响应                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 HTTP 请求基础

#### 1.2.1 HTTP 请求组成

```
POST /v1/chat/completions HTTP/1.1
Host: api.openai.com
Authorization: Bearer sk-xxxxxxxxxxxx
Content-Type: application/json

{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "user", "content": "你好"}
  ]
}
```

| 组成部分 | 说明 | 示例 |
|---------|------|------|
| **请求方法** | 操作类型 | POST、GET |
| **URL** | 请求地址 | `/v1/chat/completions` |
| **Headers** | 请求头 | `Authorization`、`Content-Type` |
| **Body** | 请求体 | JSON 格式的数据 |

#### 1.2.2 常用 HTTP 方法

| 方法 | 用途 | 大模型 API 中的使用 |
|------|------|-------------------|
| **POST** | 创建/提交资源 | 发送消息、创建对话 |
| **GET** | 获取资源 | 查询模型列表、账户信息 |
| **DELETE** | 删除资源 | 删除文件、取消任务 |

#### 1.2.3 常用 HTTP 状态码

| 状态码 | 含义 | 常见原因 |
|--------|------|---------|
| **200** | 成功 | 请求正常处理 |
| **400** | 请求错误 | 参数格式错误 |
| **401** | 未授权 | API Key 无效或过期 |
| **403** | 禁止访问 | 权限不足 |
| **404** | 未找到 | 资源不存在 |
| **429** | 请求过多 | 超出频率限制 |
| **500** | 服务器错误 | 服务端问题 |
| **503** | 服务不可用 | 服务器过载 |

### 1.3 JSON 数据格式

#### 1.3.1 JSON 基础

```json
{
  "name": "张三",
  "age": 25,
  "is_student": false,
  "hobbies": ["阅读", "编程", "旅行"],
  "address": {
    "city": "北京",
    "street": "朝阳区xxx街道"
  }
}
```

| JSON 类型 | Python 对应 | 示例 |
|-----------|-------------|------|
| object | dict | `{"key": "value"}` |
| array | list | `[1, 2, 3]` |
| string | str | `"hello"` |
| number | int/float | `123`, `3.14` |
| boolean | bool | `true`, `false` |
| null | None | `null` |

#### 1.3.2 Python 处理 JSON

```python
import json

# Python 对象转 JSON 字符串
data = {"name": "张三", "age": 25}
json_str = json.dumps(data, ensure_ascii=False, indent=2)
print(json_str)
# {
#   "name": "张三",
#   "age": 25
# }

# JSON 字符串转 Python 对象
parsed = json.loads(json_str)
print(parsed["name"])  # 张三

# 读取 JSON 文件
with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 写入 JSON 文件
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

---

## 二、API Key 管理

### 2.1 什么是 API Key

```
┌─────────────────────────────────────────────────────────────────┐
│                       API Key 的作用                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   API Key = 访问凭证（类似密码）                                  │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    身份验证                              │  │
│   │   证明你是谁 → 统计用量 → 计费 → 权限控制                │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│   示例：sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx          │
│         ├─ 前缀：标识类型                                       │
│         └─ 密钥部分：随机生成的字符串                           │
│                                                                  │
│   ⚠️ 重要：API Key 类似银行卡密码，必须妥善保管！                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 获取 API Key

#### 2.2.1 OpenAI API Key

```
1. 访问 https://platform.openai.com/
2. 注册/登录账号
3. 点击右上角头像 → View API keys
4. 点击 "Create new secret key"
5. 复制并保存 Key（只显示一次！）
```

#### 2.2.2 国内平台 API Key

| 平台 | 注册地址 | 特点 |
|------|---------|------|
| **DeepSeek** | https://platform.deepseek.com/ | 性价比高，推理能力强 |
| **阿里云百炼** | https://bailian.console.aliyun.com/ | Qwen 系列，中文效果好 |
| **智谱 AI** | https://open.bigmodel.cn/ | GLM 系列，长上下文 |
| **Moonshot** | https://platform.moonshot.cn/ | Kimi，超长上下文 |

### 2.3 安全存储 API Key

#### 2.3.1 错误做法（不要这样！）

```python
# ❌ 错误：硬编码在代码中
api_key = "sk-proj-xxxxxxxxxxxx"

# ❌ 错误：提交到 Git 仓库
# 代码泄露后 API Key 会被盗用
```

#### 2.3.2 正确做法：使用环境变量

**方法一：.env 文件（推荐）**

```bash
# 创建 .env 文件
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
```

```python
# 使用 python-dotenv 读取
from dotenv import load_dotenv
import os

load_dotenv()  # 加载 .env 文件
api_key = os.getenv("OPENAI_API_KEY")
```

**方法二：系统环境变量**

```bash
# macOS/Linux（临时）
export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxx"

# macOS/Linux（永久，添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxx"' >> ~/.zshrc
source ~/.zshrc

# Windows（临时，CMD）
set OPENAI_API_KEY=sk-proj-xxxxxxxxxxxx

# Windows（临时，PowerShell）
$env:OPENAI_API_KEY="sk-proj-xxxxxxxxxxxx"

# Windows（永久）
# 设置 → 系统 → 关于 → 高级系统设置 → 环境变量
```

```python
# Python 中读取
import os
api_key = os.getenv("OPENAI_API_KEY")
```

#### 2.3.3 .gitignore 配置

```gitignore
# .gitignore 文件中添加
.env
*.env
.env.local
secrets.json
credentials.json
```

---

## 三、调用大模型 API

### 3.1 使用 requests 库调用

#### 3.1.1 安装依赖

```bash
pip install requests python-dotenv
```

#### 3.1.2 基础调用示例

```python
"""
第一次调用大模型 API
功能：发送一句话，打印模型回复
"""

import os
import json
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "https://api.openai.com/v1"
MODEL = "gpt-4o-mini"

def call_llm(prompt: str) -> str:
    """
    调用大模型 API

    Args:
        prompt: 用户输入的提示词

    Returns:
        模型生成的回复
    """
    # 构建请求
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    # 发送请求
    response = requests.post(url, headers=headers, json=data)

    # 检查状态码
    if response.status_code != 200:
        raise Exception(f"API 调用失败: {response.status_code} - {response.text}")

    # 解析响应
    result = response.json()
    return result["choices"][0]["message"]["content"]


def main():
    # 测试调用
    prompt = "你好，请用一句话介绍 Python 语言"
    print(f"用户: {prompt}")

    try:
        reply = call_llm(prompt)
        print(f"助手: {reply}")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()
```

#### 3.1.3 完整响应结构

```json
{
  "id": "chatcmpl-xxxxxxxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Python 是一种简洁、易学、功能强大的编程语言..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 25,
    "total_tokens": 40
  }
}
```

| 字段 | 说明 |
|------|------|
| `choices[0].message.content` | 生成的回复内容 |
| `choices[0].finish_reason` | 结束原因（stop/length/content_filter） |
| `usage.prompt_tokens` | 输入 Token 数 |
| `usage.completion_tokens` | 输出 Token 数 |
| `usage.total_tokens` | 总 Token 数 |

### 3.2 使用官方 SDK 调用

#### 3.2.1 OpenAI SDK

```bash
pip install openai
```

```python
"""
使用 OpenAI SDK 调用
"""

from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# 创建客户端
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    # 使用代理或国内镜像时需要设置
    # base_url="https://your-proxy.com/v1"
)

# 发送请求
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    temperature=0.7
)

# 获取回复
print(response.choices[0].message.content)

# 获取 Token 使用量
print(f"Token 使用: {response.usage.total_tokens}")
```

#### 3.2.2 DeepSeek SDK

```python
"""
使用 OpenAI SDK 调用 DeepSeek（兼容 OpenAI 接口）
"""

from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

response = client.chat.completions.create(
    model="deepseek-chat",  # 或 "deepseek-reasoner"（推理模型）
    messages=[
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ]
)

print(response.choices[0].message.content)
```

#### 3.2.3 阿里云 Qwen SDK

```bash
pip install dashscope
```

```python
"""
使用阿里云 DashScope SDK
"""

import dashscope
from dashscope import Generation
from dotenv import load_dotenv
import os

load_dotenv()

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

response = Generation.call(
    model="qwen-turbo",
    messages=[
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ]
)

print(response.output.choices[0].message.content)
```

---

## 四、封装可复用的 LLM 客户端

### 4.1 基础版本

```python
"""
LLM 客户端封装
支持多个平台、错误处理、日志记录
"""

import os
import json
import time
import logging
from typing import Optional, List, Dict, Generator
from dataclasses import dataclass
from enum import Enum

import requests
from dotenv import load_dotenv

load_dotenv()


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """支持的 LLM 平台"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048


# 平台配置
PROVIDER_CONFIGS = {
    LLMProvider.OPENAI: LLMConfig(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini"
    ),
    LLMProvider.DEEPSEEK: LLMConfig(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat"
    ),
}


class LLMClient:
    """大模型客户端"""

    def __init__(self, provider: LLMProvider = LLMProvider.OPENAI):
        self.provider = provider
        config = PROVIDER_CONFIGS.get(provider)
        if not config or not config.api_key:
            raise ValueError(f"未配置 {provider.value} 的 API Key")

        self.config = config
        self.messages: List[Dict] = []

    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        self.messages.append({"role": role, "content": content})
        logger.debug(f"添加消息: [{role}] {content[:50]}...")

    def clear_history(self):
        """清空历史消息"""
        self.messages = []
        logger.info("历史消息已清空")

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False
    ) -> str:
        """
        发送对话请求

        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            stream: 是否流式输出

        Returns:
            模型回复
        """
        # 构建消息列表
        messages = []

        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加历史消息
        messages.extend(self.messages)

        # 添加当前用户输入
        messages.append({"role": "user", "content": prompt})

        if stream:
            return self._stream_chat(messages)

        # 发送请求
        return self._send_request(messages)

    def _send_request(self, messages: List[Dict]) -> str:
        """发送请求"""
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

        logger.info(f"发送请求到 {self.provider.value}")
        start_time = time.time()

        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)

            if response.status_code != 200:
                error_msg = f"API 错误: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

            result = response.json()
            reply = result["choices"][0]["message"]["content"]

            # 更新历史
            self.add_message("user", messages[-1]["content"])
            self.add_message("assistant", reply)

            # 记录 Token 使用
            usage = result.get("usage", {})
            elapsed = time.time() - start_time
            logger.info(
                f"请求完成 - "
                f"Token: {usage.get('total_tokens', 'N/A')} - "
                f"耗时: {elapsed:.2f}s"
            )

            return reply

        except requests.exceptions.Timeout:
            logger.error("请求超时")
            raise Exception("请求超时，请稍后重试")
        except requests.exceptions.RequestException as e:
            logger.error(f"网络错误: {e}")
            raise Exception(f"网络错误: {e}")

    def _stream_chat(self, messages: List[Dict]) -> Generator[str, None, None]:
        """流式输出"""
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True
        }

        logger.info(f"发送流式请求到 {self.provider.value}")

        try:
            with requests.post(url, headers=headers, json=data, stream=True) as response:
                if response.status_code != 200:
                    raise Exception(f"API 错误: {response.status_code}")

                full_reply = ""
                for line in response.iter_lines():
                    if not line:
                        continue

                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                full_reply += content
                                yield content
                        except json.JSONDecodeError:
                            continue

                # 更新历史
                self.add_message("user", messages[-1]["content"])
                self.add_message("assistant", full_reply)

        except Exception as e:
            logger.error(f"流式请求错误: {e}")
            raise


def main():
    """主函数"""
    # 创建客户端
    client = LLMClient(provider=LLMProvider.DEEPSEEK)

    # 单次对话
    print("=== 单次对话 ===")
    reply = client.chat("你好，请用一句话介绍 Python")
    print(f"助手: {reply}")

    # 多轮对话
    print("\n=== 多轮对话 ===")
    client.clear_history()

    reply1 = client.chat("我想学习 Python，有什么建议吗？")
    print(f"助手: {reply1}")

    reply2 = client.chat("应该从哪里开始？")  # 模型会记住上下文
    print(f"助手: {reply2}")

    # 流式输出
    print("\n=== 流式输出 ===")
    client.clear_history()
    print("助手: ", end="", flush=True)
    for chunk in client.chat("讲一个简短的笑话", stream=True):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
```

### 4.2 添加重试和错误处理

```python
"""
带重试机制的 LLM 客户端
"""

import time
import random
from functools import wraps
from typing import Callable, Type, Tuple


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        exponential_base: 指数基数
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        raise

                    # 计算延迟时间（指数退避 + 抖动）
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"请求失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    logger.info(f"等待 {delay:.2f} 秒后重试...")
                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


class RobustLLMClient(LLMClient):
    """带重试机制的 LLM 客户端"""

    @retry(max_retries=3, exceptions=(Exception,))
    def chat(self, prompt: str, **kwargs) -> str:
        """带重试的对话"""
        return super().chat(prompt, **kwargs)


# 使用示例
if __name__ == "__main__":
    client = RobustLLMClient(provider=LLMProvider.DEEPSEEK)
    reply = client.chat("你好")
    print(reply)
```

---

## 五、实战练习

### 5.1 创建项目结构

```
llm_basics/
├── .env                    # API Key 配置（不要提交到 Git）
├── .gitignore              # Git 忽略配置
├── requirements.txt        # 依赖列表
├── config.py               # 配置管理
├── llm_client.py           # LLM 客户端
└── main.py                 # 主程序
```

### 5.2 配置文件

**requirements.txt:**
```
requests>=2.31.0
python-dotenv>=1.0.0
openai>=1.0.0
```

**.env:**
```
# OpenAI
OPENAI_API_KEY=sk-proj-your-key-here

# DeepSeek
DEEPSEEK_API_KEY=sk-your-key-here

# 其他配置
LLM_PROVIDER=deepseek
```

**.gitignore:**
```
.env
__pycache__/
*.pyc
.venv/
venv/
.idea/
.vscode/
```

### 5.3 完整示例程序

```python
"""
main.py - 大模型 API 调用示例
"""

from llm_client import LLMClient, LLMProvider
from dotenv import load_dotenv
import os

load_dotenv()


def demo_basic_chat():
    """基础对话示例"""
    print("=" * 50)
    print("示例 1：基础对话")
    print("=" * 50)

    client = LLMClient(provider=LLMProvider.DEEPSEEK)

    # 单轮对话
    reply = client.chat("请用一句话解释什么是机器学习")
    print(f"回复: {reply}\n")


def demo_multi_turn():
    """多轮对话示例"""
    print("=" * 50)
    print("示例 2：多轮对话")
    print("=" * 50)

    client = LLMClient(provider=LLMProvider.DEEPSEEK)

    # 第一轮
    reply1 = client.chat("我想学习 Python 编程")
    print(f"助手: {reply1}\n")

    # 第二轮（模型会记住上下文）
    reply2 = client.chat("应该从哪些方面入手？")
    print(f"助手: {reply2}\n")

    # 第三轮
    reply3 = client.chat("推荐几本书？")
    print(f"助手: {reply3}\n")


def demo_streaming():
    """流式输出示例"""
    print("=" * 50)
    print("示例 3：流式输出")
    print("=" * 50)

    client = LLMClient(provider=LLMProvider.DEEPSEEK)

    print("助手: ", end="", flush=True)
    for chunk in client.chat("讲一个简短的程序员笑话", stream=True):
        print(chunk, end="", flush=True)
    print("\n")


def demo_system_prompt():
    """系统提示词示例"""
    print("=" * 50)
    print("示例 4：系统提示词（角色设定）")
    print("=" * 50)

    client = LLMClient(provider=LLMProvider.DEEPSEEK)

    system_prompt = """你是一位资深 Python 开发工程师，擅长解释技术概念。
请用简洁、易懂的语言回答问题，必要时给出代码示例。"""

    reply = client.chat(
        "什么是装饰器？",
        system_prompt=system_prompt
    )
    print(f"助手: {reply}\n")


def demo_token_counting():
    """Token 计数示例"""
    print("=" * 50)
    print("示例 5：Token 使用统计")
    print("=" * 50)

    client = LLMClient(provider=LLMProvider.DEEPSEEK)

    # 发送请求并查看使用量
    prompts = [
        "你好",
        "请介绍一下 Python",
        "写一个快速排序算法"
    ]

    for prompt in prompts:
        client.clear_history()
        reply = client.chat(prompt)
        print(f"提示: {prompt}")
        print(f"回复长度: {len(reply)} 字符\n")


def interactive_chat():
    """交互式聊天"""
    print("=" * 50)
    print("交互式聊天（输入 'quit' 退出）")
    print("=" * 50)

    client = LLMClient(provider=LLMProvider.DEEPSEEK)
    client.chat("你好！",
                system_prompt="你是一个友好的助手，回答简洁明了。")
    client.clear_history()  # 清空，但系统提示下次还会用

    while True:
        user_input = input("\n你: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("再见！")
            break

        if not user_input:
            continue

        print("助手: ", end="", flush=True)
        for chunk in client.chat(user_input, stream=True):
            print(chunk, end="", flush=True)
        print()


def main():
    """主函数"""
    # 检查 API Key
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("错误：未设置 DEEPSEEK_API_KEY 环境变量")
        print("请在 .env 文件中配置：DEEPSEEK_API_KEY=your-key")
        return

    # 运行示例
    demo_basic_chat()
    demo_multi_turn()
    demo_streaming()
    demo_system_prompt()
    demo_token_counting()

    # 交互式聊天
    interactive_chat()


if __name__ == "__main__":
    main()
```

---

## 六、常见问题排查

### 6.1 常见错误及解决

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `401 Unauthorized` | API Key 无效 | 检查 Key 是否正确、是否过期 |
| `429 Too Many Requests` | 请求频率超限 | 降低请求频率、等待后重试 |
| `500 Internal Server Error` | 服务器错误 | 稍后重试 |
| `Connection Error` | 网络问题 | 检查网络、使用代理 |
| `Timeout` | 请求超时 | 增加 timeout 参数 |

### 6.2 调试技巧

```python
# 1. 打印请求详情
import logging
logging.basicConfig(level=logging.DEBUG)

# 2. 查看原始响应
response = requests.post(url, headers=headers, json=data)
print(f"状态码: {response.status_code}")
print(f"响应头: {response.headers}")
print(f"响应体: {response.text}")

# 3. 使用 httpbin 测试
import requests
response = requests.post("https://httpbin.org/post", json={"test": "data"})
print(response.json())
```

### 6.3 代理设置

```python
# 方法一：环境变量
# export HTTP_PROXY=http://127.0.0.1:7890
# export HTTPS_PROXY=http://127.0.0.1:7890

# 方法二：requests 代理
proxies = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
}
response = requests.post(url, headers=headers, json=data, proxies=proxies)

# 方法三：OpenAI SDK
from openai import OpenAI
client = OpenAI(
    api_key="your-key",
    http_client=httpx.Client(proxies="http://127.0.0.1:7890")
)
```

---

## 七、Day 3 知识速查

### 7.1 API 调用流程

```
1. 获取 API Key → 平台注册获取
2. 安全存储     → .env 文件 + 环境变量
3. 构建请求     → URL + Headers + Body
4. 发送请求     → requests.post() 或 SDK
5. 解析响应     → JSON 解析提取内容
6. 错误处理     → try-except + 重试机制
```

### 7.2 代码模板

```python
# 最简调用模板
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url="https://api.deepseek.com/v1"  # 可选
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好"}]
)

print(response.choices[0].message.content)
```

---

## 八、实践任务

### 任务清单

- [ ] 注册至少一个平台账号并获取 API Key
- [ ] 创建 .env 文件配置 API Key
- [ ] 完成第一次 API 调用，成功看到模型回复
- [ ] 实现一个简单的多轮对话程序
- [ ] 尝试流式输出

### 产出标准

- 一个能正常运行的 Python 脚本
- 能够发送消息并打印模型回复
- 代码中不包含硬编码的 API Key

---

## 九、下一步预告

Day 4 将学习：
- 消息角色：system / user / assistant
- 多轮对话的消息历史管理
- 实现一个命令行聊天 Demo

---

> 完成 Day 3 后，你已经成功调用了大模型 API！
>
> 明天我们将深入学习消息结构，实现完整的聊天程序。
>
> ⬅️ 上一天：[Day 2 · 补 Python 最小基础](day02_python_basics.md)　｜　➡️ 下一天：[Day 4 · 做一个命令行聊天 Demo](day04_cli_chat_demo.md)
