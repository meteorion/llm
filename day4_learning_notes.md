# Day 4：做一个命令行聊天 Demo

> 学习目标：理解消息角色，实现多轮对话，完成一个可交互的命令行聊天程序

---

## 一、消息结构详解

### 1.1 三种消息角色

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenAI 消息角色                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  system（系统消息）                                       │   │
│  │                                                          │   │
│  │  作用：设定模型的行为、角色、规则                          │   │
│  │  特点：在整个对话中持续生效                                │   │
│  │  示例："你是一个专业的 Python 编程助手"                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  user（用户消息）                                         │   │
│  │                                                          │   │
│  │  作用：用户的输入/问题                                    │   │
│  │  特点：每轮对话通常有一条                                  │   │
│  │  示例："如何学习 Python？"                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  assistant（助手消息）                                    │   │
│  │                                                          │   │
│  │  作用：模型的回复                                        │   │
│  │  特点：需要保存到历史，用于多轮对话                        │   │
│  │  示例："学习 Python 可以从以下几个方面入手..."            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 消息结构

```python
messages = [
    {"role": "system", "content": "你是一个有帮助的助手"},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么我可以帮助你的吗？"},
    {"role": "user", "content": "介绍一下 Python"},
    {"role": "assistant", "content": "Python 是一种简洁、易学的编程语言..."}
]
```

### 1.3 角色详解

#### 1.3.1 System 消息

```python
# 场景一：角色设定
system_prompt = "你是一位资深的 Python 开发工程师，擅长解决技术问题。"

# 场景二：行为约束
system_prompt = """
你是一个客服助手，请遵循以下规则：
1. 回答要简洁专业
2. 如果不知道答案，请承认并建议转人工
3. 不要讨论与客服无关的话题
"""

# 场景三：输出格式
system_prompt = """
你是一个数据提取助手，请以 JSON 格式输出结果。
输出格式：{"name": "", "age": "", "city": ""}
"""

# 场景四：领域专家
system_prompt = "你是一位医疗健康顾问，提供专业的健康建议。"

# 场景五：语言/风格
system_prompt = "请用简单易懂的语言回答，适合小学生理解。"
```

#### 1.3.2 User 消息

```python
# 简单问题
{"role": "user", "content": "什么是机器学习？"}

# 带上下文的问题
{"role": "user", "content": """
请帮我分析以下文本的情感：
"这家餐厅的服务太差了，等了一个小时才上菜！"
"""}

# 多模态（部分模型支持）
{
    "role": "user",
    "content": [
        {"type": "text", "text": "这张图片里有什么？"},
        {"type": "image_url", "image_url": {"url": "https://..."}}
    ]
}
```

#### 1.3.3 Assistant 消息

```python
# 模型回复会被添加到消息历史
# 用于保持多轮对话的上下文

messages = [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "我叫张三"},
    {"role": "assistant", "content": "你好，张三！有什么我可以帮助你的吗？"},
    {"role": "user", "content": "我叫什么名字？"},  # 模型能回答"张三"
]
```

### 1.4 消息历史的重要性

```
┌─────────────────────────────────────────────────────────────────┐
│                    为什么需要保存消息历史                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  模型本身是无状态的：                                            │
│  - 每次调用都是独立的                                            │
│  - 模型不"记得"之前的对话                                        │
│  - 必须通过消息历史传递上下文                                     │
│                                                                  │
│  不传历史的后果：                                                 │
│  ─────────────────                                              │
│  User: 我叫张三                                                  │
│  Assistant: 你好张三！                                           │
│                                                                  │
│  User: 我叫什么名字？                                            │
│  Assistant: 抱歉，我不知道您的名字...  ❌                         │
│                                                                  │
│  传历史的后果：                                                   │
│  ────────────                                                   │
│  [历史] User: 我叫张三                                           │
│  [历史] Assistant: 你好张三！                                     │
│  [当前] User: 我叫什么名字？                                      │
│  Assistant: 您叫张三。  ✓                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、多轮对话实现

### 2.1 基础实现

```python
"""
多轮对话基础实现
"""

from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

# 消息历史列表
messages = []

def add_message(role: str, content: str):
    """添加消息到历史"""
    messages.append({"role": role, "content": content})

def chat(user_input: str, system_prompt: str = None) -> str:
    """
    发送对话请求

    Args:
        user_input: 用户输入
        system_prompt: 系统提示词（可选，首次对话设置）

    Returns:
        模型回复
    """
    # 首次对话时添加系统提示
    if system_prompt and len(messages) == 0:
        messages.append({"role": "system", "content": system_prompt})

    # 添加用户消息
    add_message("user", user_input)

    # 调用 API
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages
    )

    # 获取回复
    reply = response.choices[0].message.content

    # 添加助手消息到历史
    add_message("assistant", reply)

    return reply


# 使用示例
if __name__ == "__main__":
    # 第一轮
    print("用户: 我叫张三")
    reply = chat("我叫张三", system_prompt="你是一个友好的助手")
    print(f"助手: {reply}")

    # 第二轮
    print("\n用户: 我喜欢编程")
    reply = chat("我喜欢编程")
    print(f"助手: {reply}")

    # 第三轮（模型会记住前面的信息）
    print("\n用户: 我叫什么名字？我喜欢什么？")
    reply = chat("我叫什么名字？我喜欢什么？")
    print(f"助手: {reply}")
```

### 2.2 消息历史管理

```python
"""
消息历史管理器
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
import json


@dataclass
class MessageHistory:
    """消息历史管理类"""

    messages: List[Dict] = field(default_factory=list)
    max_tokens: int = 4000  # 最大 Token 限制
    system_prompt: Optional[str] = None

    def add_system(self, content: str):
        """添加系统消息"""
        # 确保系统消息只在开头
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = content
        else:
            self.messages.insert(0, {"role": "system", "content": content})
        self.system_prompt = content

    def add_user(self, content: str):
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        """添加助手消息"""
        self.messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> List[Dict]:
        """获取当前消息列表"""
        return self.messages.copy()

    def get_last_n_turns(self, n: int) -> List[Dict]:
        """获取最近 N 轮对话"""
        # 过滤掉 system 消息
        non_system = [m for m in self.messages if m["role"] != "system"]

        # 取最近 N 轮（每轮包含 user + assistant）
        turns = []
        count = 0
        for msg in reversed(non_system):
            turns.insert(0, msg)
            if msg["role"] == "user":
                count += 1
            if count >= n:
                break

        # 重新添加 system 消息
        if self.system_prompt:
            turns.insert(0, {"role": "system", "content": self.system_prompt})

        return turns

    def truncate(self, max_messages: int = 20):
        """截断历史，保留最近的消息"""
        if len(self.messages) <= max_messages:
            return

        # 保留 system 消息
        system_msg = None
        if self.messages and self.messages[0]["role"] == "system":
            system_msg = self.messages[0]
            self.messages = self.messages[1:]

        # 保留最近的消息
        self.messages = self.messages[-(max_messages - 1):]

        # 恢复 system 消息
        if system_msg:
            self.messages.insert(0, system_msg)

    def clear(self):
        """清空历史（保留 system 消息）"""
        if self.system_prompt:
            self.messages = [{"role": "system", "content": self.system_prompt}]
        else:
            self.messages = []

    def full_clear(self):
        """完全清空历史"""
        self.messages = []
        self.system_prompt = None

    def to_json(self) -> str:
        """导出为 JSON"""
        return json.dumps(self.messages, ensure_ascii=False, indent=2)

    def from_json(self, json_str: str):
        """从 JSON 导入"""
        self.messages = json.loads(json_str)
        if self.messages and self.messages[0]["role"] == "system":
            self.system_prompt = self.messages[0]["content"]

    def save_to_file(self, filepath: str):
        """保存到文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def load_from_file(self, filepath: str):
        """从文件加载"""
        with open(filepath, "r", encoding="utf-8") as f:
            self.from_json(f.read())

    def get_stats(self) -> Dict:
        """获取统计信息"""
        roles = {}
        for msg in self.messages:
            roles[msg["role"]] = roles.get(msg["role"], 0) + 1

        total_chars = sum(len(m["content"]) for m in self.messages)

        return {
            "total_messages": len(self.messages),
            "by_role": roles,
            "total_chars": total_chars,
            "estimated_tokens": total_chars // 2  # 粗略估计
        }


# 使用示例
if __name__ == "__main__":
    history = MessageHistory()

    # 设置系统提示
    history.add_system("你是一个有帮助的助手")

    # 模拟对话
    history.add_user("你好")
    history.add_assistant("你好！有什么我可以帮助你的吗？")
    history.add_user("介绍一下 Python")
    history.add_assistant("Python 是一种简洁、易学的编程语言...")

    # 查看统计
    print("统计信息:", history.get_stats())

    # 获取最近 1 轮
    print("最近对话:", history.get_last_n_turns(1))

    # 保存历史
    history.save_to_file("chat_history.json")
```

### 2.3 上下文窗口管理策略

```python
"""
上下文窗口管理策略
"""

from typing import List, Dict
import tiktoken  # pip install tiktoken


class ContextManager:
    """上下文窗口管理器"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4000,
        reserved_tokens: int = 1000  # 预留给输出的 Token
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.reserved_tokens = reserved_tokens
        self.available_tokens = max_tokens - reserved_tokens

        # 尝试加载 tokenizer
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except:
            # 回退到通用编码器
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, messages: List[Dict]) -> int:
        """计算消息列表的 Token 数"""
        total = 0
        for msg in messages:
            # 每条消息有固定的开销
            total += 4  # role + content 结构
            total += len(self.encoding.encode(msg["content"]))
        total += 2  # 对话的固定开销
        return total

    def truncate_messages(
        self,
        messages: List[Dict],
        strategy: str = "sliding_window"
    ) -> List[Dict]:
        """
        截断消息列表以适应上下文窗口

        Args:
            messages: 原始消息列表
            strategy: 截断策略

        Returns:
            截断后的消息列表
        """
        if self.count_tokens(messages) <= self.available_tokens:
            return messages

        # 分离 system 消息和其他消息
        system_msg = None
        other_msgs = messages

        if messages and messages[0]["role"] == "system":
            system_msg = messages[0]
            other_msgs = messages[1:]

        if strategy == "sliding_window":
            # 滑动窗口：保留最近的消息
            truncated = self._sliding_window(other_msgs)
        elif strategy == "summarize":
            # 摘要压缩（需要额外实现）
            truncated = self._summarize_strategy(other_msgs)
        else:
            truncated = self._sliding_window(other_msgs)

        # 重新添加 system 消息
        if system_msg:
            truncated.insert(0, system_msg)

        return truncated

    def _sliding_window(self, messages: List[Dict]) -> List[Dict]:
        """滑动窗口策略"""
        result = []
        current_tokens = 0

        # 从最新消息开始添加
        for msg in reversed(messages):
            msg_tokens = len(self.encoding.encode(msg["content"])) + 4
            if current_tokens + msg_tokens > self.available_tokens:
                break
            result.insert(0, msg)
            current_tokens += msg_tokens

        return result

    def _summarize_strategy(self, messages: List[Dict]) -> List[Dict]:
        """摘要压缩策略（简化版）"""
        # 这里只做简单实现，实际应用中可以调用 LLM 生成摘要
        # 将早期消息压缩为摘要
        if len(messages) <= 4:
            return messages

        # 保留最近 2 轮对话
        recent = messages[-4:]  # 最近 2 轮（user + assistant）

        # 早期消息压缩为摘要提示
        summary = "[早期对话内容已省略...]"
        summary_msg = {"role": "system", "content": summary}

        return [summary_msg] + recent


# 使用示例
if __name__ == "__main__":
    manager = ContextManager(model="gpt-4o-mini", max_tokens=1000)

    messages = [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "消息1 " * 100},
        {"role": "assistant", "content": "回复1 " * 100},
        {"role": "user", "content": "消息2 " * 100},
        {"role": "assistant", "content": "回复2 " * 100},
    ]

    print(f"原始 Token 数: {manager.count_tokens(messages)}")
    truncated = manager.truncate_messages(messages)
    print(f"截断后 Token 数: {manager.count_tokens(truncated)}")
```

---

## 三、完整命令行聊天程序

### 3.1 基础版 CLI 聊天

```python
"""
命令行聊天程序 - 基础版
功能：
- 多轮对话
- 上下文记忆
- 简单命令
"""

import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ChatBot:
    """聊天机器人"""

    def __init__(self, system_prompt: str = None):
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1"
        )
        self.messages = []

        if system_prompt:
            self.messages.append({
                "role": "system",
                "content": system_prompt
            })

    def chat(self, user_input: str) -> str:
        """发送消息并获取回复"""
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input
        })

        # 调用 API
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=self.messages,
            temperature=0.7
        )

        # 获取回复
        reply = response.choices[0].message.content

        # 添加助手消息
        self.messages.append({
            "role": "assistant",
            "content": reply
        })

        return reply

    def clear_history(self):
        """清空历史（保留 system 消息）"""
        if self.messages and self.messages[0]["role"] == "system":
            self.messages = [self.messages[0]]
        else:
            self.messages = []

    def show_history(self):
        """显示历史记录"""
        for i, msg in enumerate(self.messages):
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                print(f"[系统] {content[:50]}...")
            elif role == "user":
                print(f"[用户] {content}")
            elif role == "assistant":
                print(f"[助手] {content[:100]}...")


def main():
    """主函数"""
    print("=" * 50)
    print("命令行聊天程序")
    print("命令: /clear - 清空历史, /history - 显示历史, /quit - 退出")
    print("=" * 50)
    print()

    # 创建聊天机器人
    bot = ChatBot(
        system_prompt="你是一个友好、专业的助手。回答要简洁明了。"
    )

    while True:
        try:
            # 获取用户输入
            user_input = input("你: ").strip()

            # 检查命令
            if user_input == "/quit":
                print("再见！")
                break
            elif user_input == "/clear":
                bot.clear_history()
                print("[历史已清空]")
                continue
            elif user_input == "/history":
                bot.show_history()
                continue

            # 空输入跳过
            if not user_input:
                continue

            # 发送消息
            print("助手: ", end="", flush=True)
            reply = bot.chat(user_input)
            print(reply)

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    main()
```

### 3.2 增强版 CLI 聊天

```python
"""
命令行聊天程序 - 增强版
功能：
- 流式输出
- 多种模式切换
- 历史管理
- Token 统计
- 配置持久化
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Generator
from dataclasses import dataclass, field, asdict
from enum import Enum

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ============== 配置 ==============

@dataclass
class Config:
    """配置类"""
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = "你是一个友好、专业的助手。"
    max_history: int = 20
    stream: bool = True

    @classmethod
    def load(cls, filepath: str = "config.json") -> "Config":
        """从文件加载配置"""
        path = Path(filepath)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    def save(self, filepath: str = "config.json"):
        """保存配置到文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)


# ============== 消息管理 ==============

@dataclass
class Message:
    """消息类"""
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tokens: int = 0


class MessageHistory:
    """消息历史管理"""

    def __init__(self, max_messages: int = 20):
        self.messages: List[Message] = []
        self.max_messages = max_messages

    def add(self, role: str, content: str, tokens: int = 0):
        """添加消息"""
        msg = Message(role=role, content=content, tokens=tokens)
        self.messages.append(msg)

        # 超出限制时截断
        if len(self.messages) > self.max_messages:
            self._truncate()

    def _truncate(self):
        """截断历史"""
        # 保留第一条 system 消息
        system_msg = None
        if self.messages and self.messages[0].role == "system":
            system_msg = self.messages[0]
            self.messages = self.messages[1:]

        # 保留最近的消息
        self.messages = self.messages[-(self.max_messages - 1):]

        # 恢复 system 消息
        if system_msg:
            self.messages.insert(0, system_msg)

    def to_api_format(self) -> List[Dict]:
        """转换为 API 格式"""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def clear(self, keep_system: bool = True):
        """清空历史"""
        if keep_system and self.messages and self.messages[0].role == "system":
            self.messages = [self.messages[0]]
        else:
            self.messages = []

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_tokens = sum(m.tokens for m in self.messages)
        by_role = {}
        for m in self.messages:
            by_role[m.role] = by_role.get(m.role, 0) + 1

        return {
            "total_messages": len(self.messages),
            "total_tokens": total_tokens,
            "by_role": by_role
        }


# ============== 聊天客户端 ==============

class ChatClient:
    """聊天客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url=config.base_url
        )
        self.history = MessageHistory(max_messages=config.max_history)

        # 添加系统提示
        if config.system_prompt:
            self.history.add("system", config.system_prompt)

        # 统计
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.request_count = 0

    def chat(self, user_input: str) -> str:
        """发送消息并获取回复（非流式）"""
        self.history.add("user", user_input)

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=self.history.to_api_format(),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )

        reply = response.choices[0].message.content
        self.history.add("assistant", reply)

        # 更新统计
        if response.usage:
            self.total_input_tokens += response.usage.prompt_tokens
            self.total_output_tokens += response.usage.completion_tokens

        self.request_count += 1

        return reply

    def chat_stream(self, user_input: str) -> Generator[str, None, None]:
        """发送消息并流式获取回复"""
        self.history.add("user", user_input)

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=self.history.to_api_format(),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True
        )

        full_reply = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_reply += content
                yield content

        self.history.add("assistant", full_reply)
        self.request_count += 1

    def set_system_prompt(self, prompt: str):
        """设置系统提示"""
        self.history.clear(keep_system=False)
        self.history.add("system", prompt)

    def clear_history(self):
        """清空历史"""
        self.history.clear(keep_system=True)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.history.get_stats(),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "request_count": self.request_count
        }


# ============== 命令行界面 ==============

class ChatCLI:
    """命令行界面"""

    COMMANDS = {
        "/help": "显示帮助",
        "/quit": "退出程序",
        "/clear": "清空对话历史",
        "/history": "显示对话历史",
        "/stats": "显示统计信息",
        "/system <prompt>": "设置系统提示",
        "/model <name>": "切换模型",
        "/temp <value>": "设置温度",
        "/save": "保存对话",
        "/load": "加载对话",
    }

    def __init__(self, config: Config):
        self.config = config
        self.client = ChatClient(config)
        self.running = True

    def run(self):
        """运行 CLI"""
        self._print_welcome()

        while self.running:
            try:
                user_input = input("\n你: ").strip()

                if not user_input:
                    continue

                # 处理命令
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                # 发送消息
                self._send_message(user_input)

            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                print(f"\n[错误] {e}")

    def _print_welcome(self):
        """打印欢迎信息"""
        print("=" * 60)
        print("           命令行聊天程序 v1.0")
        print("=" * 60)
        print(f"模型: {self.config.model}")
        print(f"温度: {self.config.temperature}")
        print()
        print("输入 /help 查看可用命令")
        print("=" * 60)

    def _handle_command(self, cmd: str):
        """处理命令"""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            self._show_help()
        elif command == "/quit" or command == "/exit":
            self._show_stats()
            print("再见！")
            self.running = False
        elif command == "/clear":
            self.client.clear_history()
            print("[对话历史已清空]")
        elif command == "/history":
            self._show_history()
        elif command == "/stats":
            self._show_stats()
        elif command == "/system":
            if args:
                self.client.set_system_prompt(args)
                print(f"[系统提示已设置]")
            else:
                print("用法: /system <提示内容>")
        elif command == "/model":
            if args:
                self.config.model = args
                print(f"[模型已切换为: {args}]")
            else:
                print(f"当前模型: {self.config.model}")
        elif command == "/temp":
            if args:
                try:
                    self.config.temperature = float(args)
                    print(f"[温度已设置为: {self.config.temperature}]")
                except ValueError:
                    print("请输入有效的数字")
            else:
                print(f"当前温度: {self.config.temperature}")
        elif command == "/save":
            self._save_conversation()
        elif command == "/load":
            self._load_conversation()
        else:
            print(f"未知命令: {command}")
            print("输入 /help 查看可用命令")

    def _send_message(self, user_input: str):
        """发送消息"""
        print("助手: ", end="", flush=True)

        start_time = time.time()

        if self.config.stream:
            # 流式输出
            for chunk in self.client.chat_stream(user_input):
                print(chunk, end="", flush=True)
        else:
            # 非流式输出
            reply = self.client.chat(user_input)
            print(reply)

        elapsed = time.time() - start_time
        print(f"\n[耗时: {elapsed:.2f}s]", end="")

    def _show_help(self):
        """显示帮助"""
        print("\n可用命令:")
        for cmd, desc in self.COMMANDS.items():
            print(f"  {cmd:20} {desc}")

    def _show_history(self):
        """显示历史"""
        print("\n对话历史:")
        print("-" * 40)
        for msg in self.client.history.messages:
            role = msg.role
            content = msg.content
            if len(content) > 100:
                content = content[:100] + "..."

            role_map = {
                "system": "[系统]",
                "user": "[用户]",
                "assistant": "[助手]"
            }
            print(f"{role_map.get(role, role)} {content}")
        print("-" * 40)

    def _show_stats(self):
        """显示统计"""
        stats = self.client.get_stats()
        print("\n统计信息:")
        print("-" * 40)
        print(f"  总消息数: {stats['total_messages']}")
        print(f"  请求次数: {stats['request_count']}")
        print(f"  输入 Token: {stats['total_input_tokens']}")
        print(f"  输出 Token: {stats['total_output_tokens']}")
        print("-" * 40)

    def _save_conversation(self):
        """保存对话"""
        filename = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {
            "config": asdict(self.config),
            "messages": [
                {"role": m.role, "content": m.content}
                for m in self.client.history.messages
            ]
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[对话已保存到: {filename}]")

    def _load_conversation(self):
        """加载对话"""
        # 查找最近的对话文件
        files = list(Path(".").glob("chat_*.json"))
        if not files:
            print("[没有找到对话文件]")
            return

        latest = max(files, key=lambda p: p.stat().st_mtime)
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.client.history.messages = [
            Message(role=m["role"], content=m["content"])
            for m in data["messages"]
        ]
        print(f"[已加载对话: {latest}]")


# ============== 主函数 ==============

def main():
    """主函数"""
    # 检查 API Key
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("错误: 未设置 DEEPSEEK_API_KEY 环境变量")
        print("请在 .env 文件中配置")
        sys.exit(1)

    # 加载配置
    config = Config.load()
    config.api_key = os.getenv("DEEPSEEK_API_KEY")

    # 启动 CLI
    cli = ChatCLI(config)
    cli.run()


if __name__ == "__main__":
    main()
```

---

## 四、消息历史优化技巧

### 4.1 常见问题

```
问题 1：历史太长导致 Token 超限
解决：滑动窗口 + 摘要压缩

问题 2：模型"忘记"早期信息
解决：关键信息提取 + 注入到当前提示

问题 3：历史中包含敏感信息
解决：消息过滤 + 脱敏处理
```

### 4.2 优化策略

```python
"""
消息历史优化策略
"""

class HistoryOptimizer:
    """历史优化器"""

    @staticmethod
    def summarize_old_messages(messages: List[Dict], llm_client) -> List[Dict]:
        """将早期消息压缩为摘要"""
        if len(messages) <= 6:
            return messages

        # 保留最近 3 轮
        recent = messages[-6:]
        old = messages[:-6]

        # 生成摘要
        old_text = "\n".join([
            f"{m['role']}: {m['content']}"
            for m in old
        ])

        summary_prompt = f"""请将以下对话历史压缩为一段简短的摘要，保留关键信息：

{old_text}

摘要："""

        summary = llm_client.chat(summary_prompt)

        # 返回压缩后的消息
        return [
            {"role": "system", "content": f"[历史摘要] {summary}"}
        ] + recent

    @staticmethod
    def extract_key_info(messages: List[Dict], llm_client) -> Dict:
        """提取关键信息"""
        text = "\n".join([m["content"] for m in messages])

        prompt = f"""从以下对话中提取关键信息（姓名、偏好、目标等）：

{text}

以 JSON 格式输出关键信息："""

        result = llm_client.chat(prompt)
        # 解析 JSON...

    @staticmethod
    def filter_sensitive(messages: List[Dict]) -> List[Dict]:
        """过滤敏感信息"""
        import re

        sensitive_patterns = [
            (r'\b\d{11}\b', '[电话号码]'),  # 手机号
            (r'\b[\w.-]+@[\w.-]+\.\w+\b', '[邮箱]'),  # 邮箱
            (r'\b\d{17,19}\b', '[身份证]'),  # 身份证
        ]

        filtered = []
        for msg in messages:
            content = msg["content"]
            for pattern, replacement in sensitive_patterns:
                content = re.sub(pattern, replacement, content)
            filtered.append({**msg, "content": content})

        return filtered
```

---

## 五、Day 4 知识速查

### 5.1 消息角色

| 角色 | 作用 | 示例 |
|------|------|------|
| `system` | 设定行为、角色 | "你是一个 Python 专家" |
| `user` | 用户输入 | "如何学习 Python？" |
| `assistant` | 模型回复 | "学习 Python 可以从..." |

### 5.2 多轮对话要点

```
1. 维护消息历史列表
2. 每次请求携带完整历史
3. 收到回复后添加到历史
4. 注意 Token 限制
5. 必要时截断或压缩历史
```

### 5.3 代码模板

```python
messages = [
    {"role": "system", "content": "你是一个助手"}
]

# 用户输入
messages.append({"role": "user", "content": "你好"})

# API 调用
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
)

# 保存回复
reply = response.choices[0].message.content
messages.append({"role": "assistant", "content": reply})
```

---

## 六、实践任务

### 任务清单

- [ ] 理解三种消息角色的区别
- [ ] 实现基础多轮对话
- [ ] 完成命令行聊天程序
- [ ] 测试流式输出
- [ ] 实现历史清空功能

### 产出标准

- 一个可交互的命令行聊天程序
- 支持多轮对话，模型能记住上下文
- 至少实现 /clear、/quit 命令

---

## 七、下一步预告

Day 5 将学习：
- Prompt 任务约束技巧
- 输出长度控制
- 实现一个文章摘要器

---

> 完成 Day 4 后，你已经实现了完整的命令行聊天程序！
>
> 明天我们将学习如何用 Prompt 约束模型输出，实现摘要功能。
