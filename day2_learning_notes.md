# Day 2：补 Python 最小基础

> 学习目标：搭建 Python 开发环境，掌握大模型应用开发所需的 Python 最小知识集

---

## 一、为什么需要 Python

### 1.1 Python 在大模型应用开发中的地位

Python 是大模型应用开发的主流语言，原因如下：

| 优势 | 说明 |
|------|------|
| **生态丰富** | OpenAI、Anthropic、LangChain 等都优先支持 Python |
| **简洁易学** | 语法简单，上手快，适合快速原型开发 |
| **AI 生态** | NumPy、Pandas、PyTorch 等 AI 相关库完善 |
| **社区活跃** | 大量开源项目、教程、解决方案 |

### 1.2 Day 2 学习重点

```
┌─────────────────────────────────────────────────────────────┐
│                   Day 2 学习路线                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 环境搭建                                                 │
│     ├── 安装 Python 3.10+                                   │
│     ├── 创建虚拟环境                                         │
│     └── 包管理工具 pip                                        │
│                                                              │
│  2. Python 基础语法                                          │
│     ├── 函数定义与调用                                        │
│     ├── 列表（List）                                         │
│     ├── 字典（Dict）                                         │
│     └── 类（Class）                                          │
│                                                              │
│  3. 文件操作                                                 │
│     ├── 文件读取                                             │
│     ├── 文件写入                                             │
│     └── 上下文管理器（with）                                  │
│                                                              │
│  4. 异常处理                                                 │
│     ├── try-except 基础                                      │
│     ├── 常见异常类型                                         │
│     └── 最佳实践                                             │
│                                                              │
│  5. 实践任务                                                 │
│     └── 读取文本文件并统计行数                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、环境搭建

### 2.1 安装 Python

#### 2.1.1 版本选择

| 版本 | 状态 | 推荐 |
|------|------|------|
| Python 3.8 | 已停止支持 | 不推荐 |
| Python 3.9 | 维护中 | 可用 |
| **Python 3.10** | 稳定版 | **推荐** |
| **Python 3.11** | 性能提升明显 | **推荐** |
| Python 3.12 | 最新版 | 可用 |

> 建议使用 Python 3.10 或 3.11，兼顾稳定性和新特性

#### 2.1.2 安装方式

**Windows：**

```
方法一：官网下载安装包
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.10+ 安装包
3. 运行安装程序，勾选 "Add Python to PATH"
4. 验证安装：打开命令行，输入 python --version

方法二：使用 winget（Windows 11 自带）
winget install Python.Python.3.11

方法三：使用 Chocolatey
choco install python
```

**macOS：**

```bash
# 方法一：官网下载安装包
# 访问 https://www.python.org/downloads/

# 方法二：使用 Homebrew（推荐）
brew install python@3.11

# 验证安装
python3 --version
```

**Linux（Ubuntu/Debian）：**

```bash
# 安装 Python 3.11
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# 验证安装
python3 --version
```

#### 2.1.3 验证安装

```bash
# 检查 Python 版本
python --version
# 或
python3 --version

# 检查 pip 版本
pip --version
# 或
pip3 --version
```

### 2.2 虚拟环境

#### 2.2.1 为什么需要虚拟环境

```
问题场景：
┌─────────────────────────────────────────────────────────────┐
│                     没有虚拟环境的问题                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  项目 A 需要 requests 2.28.0                                 │
│  项目 B 需要 requests 2.31.0                                 │
│                                                              │
│  全局只能安装一个版本，导致冲突！                              │
│                                                              │
│  解决方案：虚拟环境                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   项目 A    │  │   项目 B    │  │   项目 C    │        │
│  │  venv_A     │  │  venv_B     │  │  venv_C     │        │
│  │ requests    │  │ requests    │  │ requests    │        │
│  │  2.28.0     │  │  2.31.0     │  │  2.29.0     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                              │
│  每个项目独立环境，互不影响                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### 2.2.2 创建虚拟环境

**方法一：使用 venv（Python 内置，推荐）**

```bash
# 创建项目目录
mkdir my_llm_project
cd my_llm_project

# 创建虚拟环境
python -m venv venv
# 或指定 Python 版本
python3.11 -m venv venv

# 目录结构
# my_llm_project/
# └── venv/           # 虚拟环境目录
#     ├── bin/        # macOS/Linux 可执行文件
#     ├── Scripts/    # Windows 可执行文件
#     ├── lib/        # 安装的包
#     └── pyvenv.cfg  # 配置文件
```

**方法二：使用 conda（适合数据科学项目）**

```bash
# 创建环境
conda create -n my_llm_project python=3.11

# 激活环境
conda activate my_llm_project

# 退出环境
conda deactivate
```

#### 2.2.3 激活虚拟环境

```bash
# Windows (CMD)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

激活成功后，终端前面会显示虚拟环境名称：

```
(venv) C:\Users\username\my_llm_project>
(venv) username@MacBook my_llm_project %
```

#### 2.2.4 退出虚拟环境

```bash
# 所有平台通用
deactivate
```

#### 2.2.5 虚拟环境常用命令速查

| 操作 | 命令 |
|------|------|
| 创建虚拟环境 | `python -m venv venv` |
| 激活（Windows CMD） | `venv\Scripts\activate.bat` |
| 激活（Windows PowerShell） | `venv\Scripts\Activate.ps1` |
| 激活（macOS/Linux） | `source venv/bin/activate` |
| 退出虚拟环境 | `deactivate` |
| 删除虚拟环境 | 直接删除 `venv` 文件夹 |

### 2.3 包管理工具 pip

#### 2.3.1 pip 常用命令

```bash
# 安装包
pip install requests

# 安装指定版本
pip install requests==2.31.0

# 安装最低版本
pip install requests>=2.28.0

# 卸载包
pip uninstall requests

# 查看已安装的包
pip list

# 查看包详情
pip show requests

# 导出依赖列表
pip freeze > requirements.txt

# 从 requirements.txt 安装依赖
pip install -r requirements.txt

# 升级 pip
pip install --upgrade pip
```

#### 2.3.2 requirements.txt 文件

```
# requirements.txt 示例
# 格式：包名==版本号

requests==2.31.0
openai==1.12.0
python-dotenv==1.0.0
```

```bash
# 安装所有依赖
pip install -r requirements.txt
```

#### 2.3.3 国内镜像加速

```bash
# 临时使用国内镜像
pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple

# 永久配置镜像（Windows）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 永久配置镜像（macOS/Linux）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

**常用国内镜像：**

| 镜像源 | 地址 |
|--------|------|
| 清华 | https://pypi.tuna.tsinghua.edu.cn/simple |
| 阿里云 | https://mirrors.aliyun.com/pypi/simple |
| 中科大 | https://pypi.mirrors.ustc.edu.cn/simple |
| 豆瓣 | https://pypi.douban.com/simple |

---

## 三、Python 基础语法

### 3.1 变量与数据类型

#### 3.1.1 基本数据类型

```python
# 数字类型
age = 25              # int 整数
price = 99.99         # float 浮点数
complex_num = 3 + 4j  # complex 复数

# 字符串
name = "张三"
message = 'Hello, World!'
multi_line = """
这是一个
多行字符串
"""

# 布尔值
is_active = True
is_deleted = False

# 空值
result = None

# 类型检查
print(type(age))      # <class 'int'>
print(type(name))     # <class 'str'>
print(type(is_active)) # <class 'bool'>
```

#### 3.1.2 类型转换

```python
# 字符串转数字
num_str = "123"
num_int = int(num_str)      # 123 (int)
num_float = float(num_str)  # 123.0 (float)

# 数字转字符串
num = 456
num_str = str(num)          # "456"

# 布尔转换
print(bool(1))      # True
print(bool(0))      # False
print(bool(""))     # False（空字符串）
print(bool("abc"))  # True（非空字符串）
```

### 3.2 列表（List）

#### 3.2.1 列表基础

```python
# 创建列表
fruits = ["apple", "banana", "cherry"]
numbers = [1, 2, 3, 4, 5]
mixed = [1, "hello", 3.14, True]  # 可以混合类型

# 访问元素
print(fruits[0])    # "apple"（正向索引）
print(fruits[-1])   # "cherry"（反向索引）
print(fruits[1:3])  # ["banana", "cherry"]（切片）

# 列表长度
print(len(fruits))  # 3

# 修改元素
fruits[0] = "orange"
print(fruits)       # ["orange", "banana", "cherry"]
```

#### 3.2.2 列表常用操作

```python
fruits = ["apple", "banana"]

# 添加元素
fruits.append("cherry")        # 末尾添加
fruits.insert(1, "orange")     # 指定位置插入
print(fruits)  # ["apple", "orange", "banana", "cherry"]

# 删除元素
fruits.remove("banana")        # 按值删除
deleted = fruits.pop()         # 删除并返回最后一个
deleted = fruits.pop(0)        # 删除并返回指定位置
del fruits[0]                  # 按索引删除

# 查找元素
fruits = ["apple", "banana", "cherry"]
print("banana" in fruits)      # True
print(fruits.index("banana"))  # 1（返回索引）
print(fruits.count("apple"))   # 1（统计出现次数）

# 排序
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
numbers.sort()                 # 原地排序
print(numbers)  # [1, 1, 2, 3, 4, 5, 6, 9]

numbers.sort(reverse=True)     # 降序
print(numbers)  # [9, 6, 5, 4, 3, 2, 1, 1]

# 反转
fruits.reverse()
print(fruits)  # ["cherry", "banana", "apple"]

# 合并列表
list1 = [1, 2, 3]
list2 = [4, 5, 6]
combined = list1 + list2       # [1, 2, 3, 4, 5, 6]
list1.extend(list2)            # list1 变成 [1, 2, 3, 4, 5, 6]
```

#### 3.2.3 列表推导式

```python
# 基本形式
numbers = [1, 2, 3, 4, 5]
squares = [x ** 2 for x in numbers]
print(squares)  # [1, 4, 9, 16, 25]

# 带条件过滤
evens = [x for x in numbers if x % 2 == 0]
print(evens)  # [2, 4]

# 带条件表达式
labels = ["偶数" if x % 2 == 0 else "奇数" for x in numbers]
print(labels)  # ["奇数", "偶数", "奇数", "偶数", "奇数"]

# 嵌套循环
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
flattened = [x for row in matrix for x in row]
print(flattened)  # [1, 2, 3, 4, 5, 6, 7, 8, 9]
```

### 3.3 字典（Dict）

#### 3.3.1 字典基础

```python
# 创建字典
person = {
    "name": "张三",
    "age": 25,
    "city": "北京"
}

# 空字典
empty_dict = {}
empty_dict = dict()

# 访问值
print(person["name"])           # "张三"
print(person.get("age"))        # 25
print(person.get("job", "无"))   # "无"（键不存在时返回默认值）

# 修改值
person["age"] = 26

# 添加键值对
person["job"] = "工程师"

# 删除键值对
del person["city"]
job = person.pop("job")         # 删除并返回值

# 检查键是否存在
print("name" in person)         # True
print("salary" in person)       # False
```

#### 3.3.2 字典常用操作

```python
person = {"name": "张三", "age": 25, "city": "北京"}

# 获取所有键、值、键值对
print(person.keys())    # dict_keys(['name', 'age', 'city'])
print(person.values())  # dict_values(['张三', 25, '北京'])
print(person.items())   # dict_items([('name', '张三'), ('age', 25), ('city', '北京')])

# 遍历字典
# 遍历键
for key in person:
    print(key)

# 遍历键和值
for key, value in person.items():
    print(f"{key}: {value}")

# 遍历值
for value in person.values():
    print(value)

# 合并字典（Python 3.9+）
defaults = {"theme": "dark", "language": "zh"}
settings = {"language": "en", "notifications": True}
merged = defaults | settings  # {"theme": "dark", "language": "en", "notifications": True}

# 更新字典
person.update({"age": 26, "job": "工程师"})
```

#### 3.3.3 字典推导式

```python
# 基本形式
numbers = [1, 2, 3, 4, 5]
squares = {x: x ** 2 for x in numbers}
print(squares)  # {1: 1, 2: 4, 3: 9, 4: 16, 5: 25}

# 从两个列表创建字典
keys = ["name", "age", "city"]
values = ["张三", 25, "北京"]
person = dict(zip(keys, values))
print(person)  # {'name': '张三', 'age': 25, 'city': '北京'}

# 过滤
scores = {"Alice": 85, "Bob": 60, "Charlie": 90, "David": 55}
passed = {name: score for name, score in scores.items() if score >= 60}
print(passed)  # {'Alice': 85, 'Bob': 60, 'Charlie': 90}
```

#### 3.3.4 嵌套字典

```python
# 嵌套字典结构（常见于 API 响应）
user_data = {
    "user": {
        "id": 123,
        "name": "张三",
        "profile": {
            "age": 25,
            "city": "北京",
            "interests": ["AI", "Python", "阅读"]
        }
    },
    "status": "active"
}

# 访问嵌套值
print(user_data["user"]["name"])                    # "张三"
print(user_data["user"]["profile"]["city"])         # "北京"
print(user_data["user"]["profile"]["interests"][0]) # "AI"

# 安全访问（避免 KeyError）
city = user_data.get("user", {}).get("profile", {}).get("city", "未知")
```

### 3.4 函数

#### 3.4.1 函数定义与调用

```python
# 基本函数
def greet():
    print("Hello, World!")

greet()  # 调用函数

# 带参数的函数
def greet(name):
    print(f"Hello, {name}!")

greet("张三")  # Hello, 张三!

# 带返回值的函数
def add(a, b):
    return a + b

result = add(3, 5)
print(result)  # 8

# 多返回值
def get_name_parts(full_name):
    parts = full_name.split()
    first_name = parts[0]
    last_name = parts[-1] if len(parts) > 1 else ""
    return first_name, last_name

first, last = get_name_parts("张 三")
print(first, last)  # 张 三
```

#### 3.4.2 参数类型

```python
# 位置参数
def power(base, exponent):
    return base ** exponent

print(power(2, 3))  # 8

# 关键字参数
print(power(base=2, exponent=3))  # 8
print(power(exponent=3, base=2))  # 8（顺序可以调换）

# 默认参数
def greet(name, greeting="你好"):
    print(f"{greeting}, {name}!")

greet("张三")              # 你好, 张三!
greet("张三", "早上好")    # 早上好, 张三!

# 可变位置参数 (*args)
def sum_all(*numbers):
    return sum(numbers)

print(sum_all(1, 2, 3, 4, 5))  # 15

# 可变关键字参数 (**kwargs)
def print_info(**kwargs):
    for key, value in kwargs.items():
        print(f"{key}: {value}")

print_info(name="张三", age=25, city="北京")

# 混合参数（顺序：位置参数 -> *args -> 默认参数 -> **kwargs）
def func(a, b, *args, default_val=10, **kwargs):
    print(f"a={a}, b={b}")
    print(f"args={args}")
    print(f"default_val={default_val}")
    print(f"kwargs={kwargs}")
```

#### 3.4.3 类型注解（Python 3.5+）

```python
# 基本类型注解
def greet(name: str) -> str:
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b

# 列表和字典类型注解
from typing import List, Dict, Optional, Union

def process_items(items: List[str]) -> int:
    return len(items)

def get_user(user_id: int) -> Dict[str, Union[str, int]]:
    return {"id": user_id, "name": "张三"}

# 可选类型（可以为 None）
def find_user(user_id: int) -> Optional[Dict]:
    if user_id > 0:
        return {"id": user_id, "name": "张三"}
    return None
```

### 3.5 类（Class）

#### 3.5.1 类的定义

```python
class Person:
    """表示一个人的类"""

    # 类属性（所有实例共享）
    species = "人类"

    # 构造方法
    def __init__(self, name: str, age: int):
        # 实例属性
        self.name = name
        self.age = age

    # 实例方法
    def introduce(self):
        return f"我叫{self.name}，今年{self.age}岁"

    def celebrate_birthday(self):
        self.age += 1
        print(f"生日快乐！{self.name}现在{self.age}岁了")

    # 魔术方法：字符串表示
    def __str__(self):
        return f"Person(name={self.name}, age={self.age})"

    def __repr__(self):
        return f"Person('{self.name}', {self.age})"


# 创建实例
person = Person("张三", 25)
print(person.introduce())      # 我叫张三，今年25岁
print(person)                  # Person(name=张三, age=25)
person.celebrate_birthday()    # 生日快乐！张三现在26岁了
```

#### 3.5.2 继承

```python
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        raise NotImplementedError("子类必须实现此方法")


class Dog(Animal):
    def speak(self):
        return f"{self.name}说：汪汪汪！"


class Cat(Animal):
    def __init__(self, name, color):
        super().__init__(name)  # 调用父类构造方法
        self.color = color

    def speak(self):
        return f"{self.name}说：喵喵喵！"


dog = Dog("旺财")
print(dog.speak())  # 旺财说：汪汪汪！

cat = Cat("咪咪", "白色")
print(cat.speak())  # 咪咪说：喵喵喵！
print(cat.color)    # 白色
```

#### 3.5.3 实际应用示例：API 客户端类

```python
import json
from typing import Dict, Optional, List


class LLMClient:
    """大模型 API 客户端类"""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.messages: List[Dict] = []

    def add_message(self, role: str, content: str):
        """添加消息到历史记录"""
        self.messages.append({"role": role, "content": content})

    def clear_history(self):
        """清空历史记录"""
        self.messages = []

    def build_request_body(self, prompt: str, model: str = "gpt-4o-mini") -> Dict:
        """构建请求体"""
        self.add_message("user", prompt)
        return {
            "model": model,
            "messages": self.messages,
            "temperature": 0.7
        }

    def get_last_response(self) -> Optional[str]:
        """获取最后一条助手消息"""
        for msg in reversed(self.messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return None


# 使用示例
client = LLMClient(api_key="your-api-key")
client.add_message("system", "你是一个有帮助的助手")
client.add_message("user", "你好！")
client.add_message("assistant", "你好！有什么我可以帮助你的吗？")

request_body = client.build_request_body("请介绍一下 Python")
print(json.dumps(request_body, ensure_ascii=False, indent=2))
```

---

## 四、文件操作

### 4.1 文件读取

#### 4.1.1 基本读取方式

```python
# 方式一：一次性读取全部内容
with open("example.txt", "r", encoding="utf-8") as f:
    content = f.read()
    print(content)

# 方式二：逐行读取（内存友好）
with open("example.txt", "r", encoding="utf-8") as f:
    for line in f:
        print(line.strip())  # strip() 去除首尾空白

# 方式三：读取所有行为列表
with open("example.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()
    print(lines)  # ['第一行\n', '第二行\n', ...]

# 方式四：读取指定字符数
with open("example.txt", "r", encoding="utf-8") as f:
    first_100_chars = f.read(100)
    print(first_100_chars)
```

#### 4.1.2 不同编码的处理

```python
# UTF-8 编码（推荐）
with open("example.txt", "r", encoding="utf-8") as f:
    content = f.read()

# GBK 编码（部分 Windows 文件）
with open("example.txt", "r", encoding="gbk") as f:
    content = f.read()

# 自动检测编码
import chardet

with open("example.txt", "rb") as f:
    raw_data = f.read()
    result = chardet.detect(raw_data)
    encoding = result["encoding"]

content = raw_data.decode(encoding)
```

### 4.2 文件写入

```python
# 覆盖写入
with open("output.txt", "w", encoding="utf-8") as f:
    f.write("这是第一行\n")
    f.write("这是第二行\n")

# 追加写入
with open("output.txt", "a", encoding="utf-8") as f:
    f.write("这是追加的一行\n")

# 写入多行
lines = ["第一行", "第二行", "第三行"]
with open("output.txt", "w", encoding="utf-8") as f:
    f.writelines([line + "\n" for line in lines])

# 写入 JSON 文件
import json

data = {"name": "张三", "age": 25, "city": "北京"}
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

### 4.3 文件模式速查

| 模式 | 说明 |
|------|------|
| `"r"` | 只读（默认） |
| `"w"` | 覆盖写入（文件不存在则创建） |
| `"a"` | 追加写入（文件不存在则创建） |
| `"x"` | 独占创建（文件已存在则报错） |
| `"rb"` | 二进制读 |
| `"wb"` | 二进制写 |
| `"r+"` | 读写（文件必须存在） |
| `"w+"` | 读写（覆盖写入） |

### 4.4 文件路径处理

```python
import os
from pathlib import Path

# 传统方式
current_dir = os.getcwd()
file_path = os.path.join("data", "example.txt")
file_name = os.path.basename(file_path)
file_dir = os.path.dirname(file_path)
file_exists = os.path.exists(file_path)

# Pathlib 方式（推荐，Python 3.4+）
path = Path("data") / "example.txt"

print(path.name)       # example.txt
print(path.stem)       # example
print(path.suffix)     # .txt
print(path.parent)     # data
print(path.exists())   # True/False
print(path.is_file())  # True/False
print(path.is_dir())   # True/False

# 创建目录
Path("data/output").mkdir(parents=True, exist_ok=True)

# 读取文件（Pathlib 方式）
content = path.read_text(encoding="utf-8")
path.write_text("Hello, World!", encoding="utf-8")
```

---

## 五、异常处理

### 5.1 基本语法

```python
# 基本结构
try:
    # 可能出错的代码
    result = 10 / 0
except ZeroDivisionError:
    # 处理特定异常
    print("除数不能为零")

# 捕获多种异常
try:
    with open("nonexistent.txt", "r") as f:
        content = f.read()
except FileNotFoundError:
    print("文件不存在")
except PermissionError:
    print("没有权限访问文件")
except Exception as e:
    print(f"发生未知错误：{e}")

# 获取异常信息
try:
    result = int("abc")
except ValueError as e:
    print(f"转换失败：{e}")
```

### 5.2 完整结构

```python
try:
    # 可能出错的代码
    result = risky_operation()
except ValueError as e:
    # 处理特定异常
    print(f"值错误：{e}")
except (TypeError, KeyError) as e:
    # 处理多种异常
    print(f"类型或键错误：{e}")
except Exception as e:
    # 处理所有其他异常
    print(f"未知错误：{e}")
else:
    # 没有异常时执行
    print(f"操作成功：{result}")
finally:
    # 无论是否异常都执行
    print("清理工作")
```

### 5.3 常见异常类型

| 异常 | 说明 | 示例 |
|------|------|------|
| `ValueError` | 值错误 | `int("abc")` |
| `TypeError` | 类型错误 | `"1" + 1` |
| `KeyError` | 键不存在 | `d["missing_key"]` |
| `IndexError` | 索引越界 | `lst[100]` |
| `FileNotFoundError` | 文件不存在 | `open("nofile.txt")` |
| `PermissionError` | 权限错误 | 写入只读文件 |
| `ZeroDivisionError` | 除零错误 | `1 / 0` |
| `AttributeError` | 属性不存在 | `"str".nonexistent() |
| `ImportError` | 导入失败 | `import nonexistent` |

### 5.4 主动抛出异常

```python
def set_age(age: int):
    if age < 0:
        raise ValueError("年龄不能为负数")
    if age > 150:
        raise ValueError("年龄不合理")
    return age

# 使用
try:
    set_age(-5)
except ValueError as e:
    print(e)  # 年龄不能为负数
```

### 5.5 自定义异常

```python
class APIError(Exception):
    """API 调用错误"""

    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class RateLimitError(APIError):
    """请求频率限制错误"""

    def __init__(self, retry_after: int = 60):
        super().__init__("请求频率超限", status_code=429)
        self.retry_after = retry_after


# 使用
def call_api():
    raise RateLimitError(retry_after=30)


try:
    call_api()
except RateLimitError as e:
    print(f"请求被限制，请{e.retry_after}秒后重试")
except APIError as e:
    print(f"API 错误：{e.message}，状态码：{e.status_code}")
```

### 5.6 最佳实践

```python
# 1. 只捕获预期的异常
def read_config(path: str) -> dict:
    """读取配置文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # 文件不存在，返回默认配置
        return {"default": True}
    except json.JSONDecodeError as e:
        # JSON 格式错误
        raise ValueError(f"配置文件格式错误：{e}")

# 2. 不要裸露的 except
# 错误示例
try:
    do_something()
except:  # 不要这样做！会捕获所有异常，包括系统退出
    pass

# 正确示例
try:
    do_something()
except Exception as e:  # 至少指定 Exception
    logger.error(f"操作失败：{e}")

# 3. 异常链
def load_user(user_id: int):
    try:
        with open(f"users/{user_id}.json") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ValueError(f"用户 {user_id} 不存在") from e

# 4. 上下文管理器处理资源
class DatabaseConnection:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None

    def __enter__(self):
        self.connection = connect(self.connection_string)
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
        # 返回 False 让异常继续传播
        return False


# 使用
with DatabaseConnection("postgresql://...") as conn:
    conn.execute("SELECT * FROM users")
```

---

## 六、Day 2 实践任务

### 任务 1：安装 Python 并配置虚拟环境

**步骤：**

```bash
# 1. 检查 Python 版本
python --version

# 2. 创建项目目录
mkdir llm_learning
cd llm_learning

# 3. 创建虚拟环境
python -m venv venv

# 4. 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 5. 升级 pip
pip install --upgrade pip

# 6. 验证
which python  # macOS/Linux
where python  # Windows
# 应该显示 venv 目录下的 Python
```

### 任务 2：编写文件统计脚本

**创建测试文件 `sample.txt`：**

```
这是第一行
这是第二行
这是第三行
这是第四行
这是第五行
```

**创建脚本 `file_stats.py`：**

```python
"""
文件统计工具
功能：读取文本文件并统计行数、字数、字符数
"""

import sys
from pathlib import Path


def count_file_stats(file_path: str) -> dict:
    """
    统计文件的各种指标

    Args:
        file_path: 文件路径

    Returns:
        包含统计结果的字典
    """
    path = Path(file_path)

    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    if not path.is_file():
        raise ValueError(f"路径不是文件：{file_path}")

    # 读取文件内容
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # 尝试其他编码
        content = path.read_text(encoding="gbk")

    # 统计
    lines = content.splitlines()
    words = content.split()

    stats = {
        "文件名": path.name,
        "行数": len(lines),
        "词数": len(words),
        "字符数": len(content),
        "非空行数": len([line for line in lines if line.strip()]),
        "平均每行字符数": round(len(content) / len(lines), 2) if lines else 0
    }

    return stats


def print_stats(stats: dict):
    """格式化打印统计结果"""
    print("\n" + "=" * 40)
    print("文件统计结果")
    print("=" * 40)
    for key, value in stats.items():
        print(f"{key:15}: {value}")
    print("=" * 40 + "\n")


def main():
    """主函数"""
    # 获取文件路径
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = input("请输入文件路径: ").strip()

    # 统计并打印
    try:
        stats = count_file_stats(file_path)
        print_stats(stats)
    except FileNotFoundError as e:
        print(f"错误：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"发生错误：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**运行脚本：**

```bash
# 方式一：命令行参数
python file_stats.py sample.txt

# 方式二：交互式
python file_stats.py
# 然后输入文件路径
```

**预期输出：**

```
========================================
文件统计结果
========================================
文件名          : sample.txt
行数            : 5
词数            : 10
字符数          : 50
非空行数        : 5
平均每行字符数  : 10.0
========================================
```

### 任务 3：练习题

**练习 1：列表操作**

```python
# 给定一个字符串列表，完成以下操作
words = ["apple", "banana", "cherry", "date", "elderberry"]

# 1. 找出长度大于 5 的单词
# 2. 将所有单词转为大写
# 3. 按字母顺序排序
# 4. 统计每个单词出现的首字母
```

**练习 2：字典操作**

```python
# 给定学生成绩字典，完成以下操作
scores = {
    "张三": {"数学": 85, "语文": 90, "英语": 78},
    "李四": {"数学": 92, "语文": 88, "英语": 95},
    "王五": {"数学": 78, "语文": 85, "英语": 82}
}

# 1. 计算每个学生的平均分
# 2. 找出数学最高分的学生
# 3. 计算每门课的平均分
```

**练习 3：文件处理**

```python
# 创建一个脚本，实现以下功能：
# 1. 读取一个 CSV 文件（每行格式：姓名,年龄,城市）
# 2. 统计每个城市的人数
# 3. 计算平均年龄
# 4. 将结果写入新的文件
```

---

## 七、常见问题

### Q1：Python 2 和 Python 3 有什么区别？

| 区别 | Python 2 | Python 3 |
|------|----------|----------|
| print | `print "hello"` | `print("hello")` |
| 整数除法 | `5/2 = 2` | `5/2 = 2.5` |
| 字符串 | 默认 ASCII | 默认 Unicode |
| range | 返回列表 | 返回迭代器 |

> Python 2 已于 2020 年停止维护，请使用 Python 3

### Q2：如何选择代码编辑器？

| 编辑器 | 特点 | 推荐场景 |
|--------|------|---------|
| VS Code | 免费、插件丰富、轻量 | 通用开发 |
| PyCharm | 专业 Python IDE | 大型项目 |
| Jupyter Notebook | 交互式编程 | 数据分析、学习 |
| Cursor | AI 辅助编程 | 快速开发 |

### Q3：虚拟环境和全局环境怎么选择？

- **虚拟环境**：项目开发，隔离依赖
- **全局环境**：通用工具，如 `black`、`pylint`

### Q4：pip 安装包很慢怎么办？

使用国内镜像源：

```bash
pip install package_name -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 八、Day 2 知识速查表

### 8.1 常用命令

| 操作 | 命令 |
|------|------|
| 检查 Python 版本 | `python --version` |
| 创建虚拟环境 | `python -m venv venv` |
| 激活虚拟环境（Windows） | `venv\Scripts\activate` |
| 激活虚拟环境（macOS/Linux） | `source venv/bin/activate` |
| 退出虚拟环境 | `deactivate` |
| 安装包 | `pip install package_name` |
| 导出依赖 | `pip freeze > requirements.txt` |
| 安装依赖 | `pip install -r requirements.txt` |

### 8.2 Python 语法速查

```python
# 列表
lst = [1, 2, 3]
lst.append(4)          # 添加
lst.pop()              # 删除末尾
lst[0]                 # 访问
[x*2 for x in lst]     # 推导式

# 字典
d = {"name": "张三", "age": 25}
d["name"]              # 访问
d.get("job", "无")     # 安全访问
d["city"] = "北京"     # 添加
for k, v in d.items()  # 遍历

# 函数
def func(a: int, b: int = 10) -> int:
    return a + b

# 类
class MyClass:
    def __init__(self, name):
        self.name = name

    def method(self):
        return self.name

# 文件
with open("file.txt", "r", encoding="utf-8") as f:
    content = f.read()

# 异常
try:
    risky_operation()
except ValueError as e:
    handle_error(e)
finally:
    cleanup()
```

---

## 九、下一步预告

Day 3 将学习：
- HTTP 请求基础
- API Key 管理
- 第一次调用大模型 API

---

> 完成 Day 2 的学习后，你已经具备了 Python 开发的基础能力。
>
> 明天我们将正式开始调用大模型 API，实现第一个 LLM 应用！
