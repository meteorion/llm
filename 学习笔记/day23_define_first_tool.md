# Day 23：定义第一个工具

> 学习目标：掌握工具参数设计原则和输入输出定义规范，实现三个可独立运行的真实场景工具，理解如何让工具对 LLM 调用"友好"
>
> 📚 所属阶段：**第三阶段 · 智能体与工程化**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 23
>
> 🧭 导航：[← Day 22 · 理解 Tool Calling](day22_tool_calling_basics.md) [→ Day 24 · 单工具调用 Demo](day24_single_tool_demo.md)

---

## 目录

- [一、工具参数设计原则](#一工具参数设计原则)
  - [1.1 参数设计的核心目标](#11-参数设计的核心目标)
  - [1.2 必填 vs 可选参数的决策](#12-必填-vs-可选参数的决策)
  - [1.3 参数类型约束与 enum 限制](#13-参数类型约束与-enum-限制)
  - [1.4 description 的写作标准](#14-description-的写作标准)
- [二、输入输出定义规范](#二输入输出定义规范)
  - [2.1 工具返回格式设计](#21-工具返回格式设计)
  - [2.2 错误处理：返回 dict 还是抛异常](#22-错误处理返回-dict-还是抛异常)
  - [2.3 让输出对模型"友好"](#23-让输出对模型友好)
- [三、三个真实场景工具实现](#三三个真实场景工具实现)
  - [3.1 查天气工具（调用真实 API）](#31-查天气工具调用真实-api)
  - [3.2 查汇率工具](#32-查汇率工具)
  - [3.3 查本地知识库工具](#33-查本地知识库工具)
- [四、工具独立测试](#四工具独立测试)
  - [4.1 工具函数测试策略](#41-工具函数测试策略)
  - [4.2 Schema 校验测试](#42-schema-校验测试)
- [五、Day 23 知识速查](#五day-23-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、工具参数设计原则

### 1.1 参数设计的核心目标

工具参数不是给"人"用的，是给 **LLM 填写**的。设计目标是：让模型在不需要额外解释的情况下，正确理解每个参数的含义并填写正确的值。

```
参数设计的两类失败：

  失败 A：参数太模糊
    参数名：data
    参数描述："数据"
    → 模型不知道该传什么：是城市名？是用户 ID？是 JSON？

  失败 B：参数过度复杂
    参数：一个嵌套三层的 JSON 对象，含 15 个字段
    → 模型填写出错概率极高，调试困难

  正确做法：
    参数名尽量自解释（city 比 c 好，user_id 比 uid 好）
    每个参数只传一类信息（城市 vs 国家用两个参数）
    参数数量控制在 5 个以内（超过的考虑拆分工具）
```

**一个直觉原则**：如果你看着参数名和描述，0.5 秒内能知道该传什么，模型也能。如果你需要想一下，模型大概率会填错。

### 1.2 必填 vs 可选参数的决策

```
┌──────────────────────────────────────────────────────────────────┐
│              必填 vs 可选参数决策流程                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  问：工具在没有这个参数时能正常运行吗？                              │
│       │                                                           │
│  不能  └→ required（必填）                                        │
│            例：get_weather 的 city，没有城市名无法查天气            │
│                                                                   │
│  能   └→  继续问：有默认值可以用吗？                               │
│              │                                                    │
│       有默认值 └→ optional + default                              │
│                  例：get_weather 的 unit，默认 celsius             │
│                                                                   │
│       没有默认值 └→ optional，文档说明缺省行为是什么               │
│                  例：search 的 page，缺省从第 1 页开始             │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**反模式**：把能有默认值的参数设为必填——增加了模型出错的概率，也让 Prompt 更冗长。

### 1.3 参数类型约束与 enum 限制

精确的类型约束能显著减少模型填写错误的概率：

```python
# 宽松约束（模型可能填 "celsius" 也可能填 "c" 或 "摄氏度"）
"unit": {"type": "string", "description": "温度单位"}

# 严格约束（enum 锁定取值，模型只能填这两个值）
"unit": {
    "type": "string",
    "enum": ["celsius", "fahrenheit"],
    "description": "温度单位：celsius（摄氏度）或 fahrenheit（华氏度）"
}
```

**类型约束的最佳实践**：

| 参数类型 | 建议约束 | 示例 |
|---------|---------|------|
| 选项型 | enum 锁定所有合法值 | `"order"` 用 `["asc", "desc"]` |
| 数值型 | type: integer/number，可加 minimum/maximum | 页码用 `minimum: 1` |
| 字符串型 | 加 description 举例说明格式 | `"日期，格式 YYYY-MM-DD，如 2024-01-15"` |
| 布尔型 | type: boolean，避免用 "yes"/"no" | `"include_details": {"type": "boolean"}` |

### 1.4 description 的写作标准

工具的 description 是模型做"是否调用"决策的核心依据，参数的 description 是模型做"如何填写"决策的核心依据。

**工具 description 四件套**：

```
① 这个工具能做什么（动词 + 对象）
   "获取指定货币对的实时汇率"

② 返回什么数据（格式 + 单位）
   "返回汇率数值（浮点数）和数据更新时间"

③ 适用边界（何时用）
   "用于需要精确汇率换算的场景"

④ 不适用边界（何时别用）—— 可选但很有用
   "不适用于历史汇率查询"
```

**参数 description 两件套**：

```
① 参数代表什么（语义）
   "源货币的 ISO 4217 三字母代码"

② 格式示例（至少一个）
   "例如：'CNY'、'USD'、'EUR'"
```

---

## 二、输入输出定义规范

### 2.1 工具返回格式设计

工具的返回值最终会被序列化成字符串传给模型，设计原则是**让模型容易理解和引用**。

```python
# 反模式 A：返回纯数字，没有上下文
def get_exchange_rate(from_currency, to_currency):
    return 7.28   # 7.28 是什么？人民币兑美元？还是倒过来？模型需要猜

# 反模式 B：返回嵌套复杂对象，大量无用字段
def get_exchange_rate(from_currency, to_currency):
    return {
        "request_id": "abc123",
        "timestamp": 1712345678,
        "meta": {"provider": "xxx", "version": "v2"},
        "data": {"rate": 7.28, "unit": "per_dollar", ...},  # 模型要找数据需要多层展开
    }

# 正确做法：简洁、自解释的平铺结构
def get_exchange_rate(from_currency, to_currency):
    return {
        "from": from_currency,     # CNY
        "to": to_currency,         # USD
        "rate": 7.28,              # 1 CNY = 7.28 USD
        "description": "1 CNY = 7.28 USD",  # 自然语言描述，模型可以直接引用
        "updated_at": "2024-01-15 14:30",
    }
```

**返回结构的三个原则**：
1. **平铺优于嵌套**：模型处理 `result["rate"]` 比 `result["data"]["exchange"]["rate"]` 更可靠
2. **包含语义上下文**：数值旁边附上单位和含义（`"rate": 7.28` 加上 `"description": "1 CNY = 7.28 USD"`）
3. **包含数据来源/时间**：让模型在回答时可以告知用户数据的新鲜度

### 2.2 错误处理：返回 dict 还是抛异常

工具函数的错误处理策略影响整个 Tool Calling 流程的健壮性：

```
两种错误处理方式的对比：

  方式 A：抛异常
    def get_weather(city):
        if not city:
            raise ValueError("城市名不能为空")
        ...
    
    问题：
    - 异常会中断整个对话流程
    - 需要在 dispatch_tool 里捕获，增加复杂度
    - 模型看不到错误信息，无法生成有用的回答
  
  方式 B：返回错误 dict（推荐）
    def get_weather(city):
        if not city:
            return {"error": "城市名不能为空", "city": city}
        ...
    
    优势：
    - 错误信息传给模型，模型可以生成友好的错误提示
    - 不中断对话流程
    - 模型可以基于错误信息决定是否重试或请用户澄清
```

**标准错误返回格式**：

```python
def tool_error(message: str, **context) -> dict:
    return {"error": True, "message": message, **context}

# 使用示例
def get_weather(city: str) -> dict:
    if not city or not city.strip():
        return tool_error("城市名不能为空")
    result = fetch_weather_api(city)
    if result is None:
        return tool_error(f"未找到城市 '{city}' 的天气数据，请检查城市名称是否正确")
    return result
```

### 2.3 让输出对模型"友好"

```
模型不友好的输出：
  {"t": 25, "c": "sun", "w": 3}
  → 缩写字段名，模型需要猜 t=温度？c=天气？w=风速？

模型友好的输出：
  {
    "city": "北京",
    "temperature_celsius": 25,
    "condition": "晴天",
    "wind_level": "3 级",
    "summary": "北京今天晴天，25°C，3 级风，适合户外活动"
  }
  → summary 字段是现成的自然语言，模型可以直接引用或改写
```

**summary 字段的价值**：为复杂数据提供预先整合好的自然语言描述，模型在生成回答时不需要自己组合多个字段，减少幻觉和格式错误的风险。

---

## 三、三个真实场景工具实现

### 3.1 查天气工具（调用真实 API）

```python
"""
tools/weather.py — 天气查询工具（使用 wttr.in 免费 API，无需 API Key）
"""

import json
import urllib.request
import urllib.parse

WEATHER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "获取指定城市的当前实时天气信息，包括温度、天气状况和体感描述。"
            "适用于需要告知用户当前天气的场景。不支持历史天气和未来预报。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，支持中文或英文，如'北京'、'Shanghai'、'Tokyo'",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位：celsius（摄氏度，默认）或 fahrenheit（华氏度）",
                },
            },
            "required": ["city"],
        },
    },
}


def get_weather(city: str, unit: str = "celsius") -> dict:
    try:
        encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded}?format=j1&lang=zh"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        current = data["current_condition"][0]
        temp_c = int(current["temp_C"])
        temp_f = int(current["temp_F"])
        condition = current["lang_zh"][0]["value"] if current.get("lang_zh") else current["weatherDesc"][0]["value"]
        wind_kmph = int(current["windspeedKmph"])

        temp = temp_c if unit == "celsius" else temp_f
        unit_str = "°C" if unit == "celsius" else "°F"

        return {
            "city": city,
            "temperature": temp,
            "unit": unit_str,
            "condition": condition,
            "wind_kmph": wind_kmph,
            "summary": f"{city}当前{condition}，气温 {temp}{unit_str}，风速 {wind_kmph} km/h",
        }
    except urllib.error.URLError:
        return {"error": True, "message": f"无法连接天气服务，请检查网络连接"}
    except (KeyError, IndexError, json.JSONDecodeError):
        return {"error": True, "message": f"未找到城市 '{city}' 的天气数据，请确认城市名称"}
    except Exception as e:
        return {"error": True, "message": f"天气查询失败：{e}"}


if __name__ == "__main__":
    print(json.dumps(get_weather("北京"), ensure_ascii=False, indent=2))
    print(json.dumps(get_weather("InvalidCityXYZ"), ensure_ascii=False, indent=2))
```

### 3.2 查汇率工具

```python
"""
tools/exchange_rate.py — 实时汇率查询工具（使用 exchangerate-api.com 免费端点）
"""

import json
import urllib.request

EXCHANGE_RATE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_exchange_rate",
        "description": (
            "获取两种货币之间的实时汇率，并计算指定金额的换算结果。"
            "适用于外汇换算、报价、旅行费用估算等场景。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "from_currency": {
                    "type": "string",
                    "description": "源货币 ISO 4217 代码，大写三字母，如 'CNY'、'USD'、'EUR'、'JPY'",
                },
                "to_currency": {
                    "type": "string",
                    "description": "目标货币 ISO 4217 代码，大写三字母，如 'USD'、'CNY'、'GBP'",
                },
                "amount": {
                    "type": "number",
                    "description": "需要换算的金额（可选），如不指定则只返回汇率",
                },
            },
            "required": ["from_currency", "to_currency"],
        },
    },
}

# 备用模拟数据（当 API 不可用时）
_MOCK_RATES = {
    ("CNY", "USD"): 0.138,
    ("USD", "CNY"): 7.245,
    ("EUR", "CNY"): 7.85,
    ("CNY", "EUR"): 0.127,
    ("USD", "EUR"): 0.923,
    ("EUR", "USD"): 1.083,
    ("USD", "JPY"): 151.2,
    ("JPY", "USD"): 0.0066,
}


def get_exchange_rate(from_currency: str, to_currency: str, amount: float = None) -> dict:
    from_currency = from_currency.upper().strip()
    to_currency = to_currency.upper().strip()

    if from_currency == to_currency:
        rate = 1.0
        source = "相同货币"
    else:
        rate = None
        try:
            url = f"https://open.er-api.com/v6/latest/{from_currency}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
            if data.get("result") == "success":
                rates = data.get("rates", {})
                rate = rates.get(to_currency)
                source = "实时数据"
        except Exception:
            pass

        if rate is None:
            rate = _MOCK_RATES.get((from_currency, to_currency))
            source = "参考数据（离线）"

        if rate is None:
            return {
                "error": True,
                "message": f"不支持 {from_currency} → {to_currency} 的汇率查询，请使用标准货币代码",
            }

    result = {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": round(rate, 6),
        "source": source,
        "description": f"1 {from_currency} = {rate:.4f} {to_currency}",
    }

    if amount is not None:
        converted = round(amount * rate, 2)
        result["amount"] = amount
        result["converted_amount"] = converted
        result["summary"] = f"{amount} {from_currency} ≈ {converted} {to_currency}（汇率 {rate:.4f}）"
    else:
        result["summary"] = f"当前汇率：1 {from_currency} = {rate:.4f} {to_currency}"

    return result


if __name__ == "__main__":
    print(json.dumps(get_exchange_rate("CNY", "USD", 1000), ensure_ascii=False, indent=2))
    print(json.dumps(get_exchange_rate("USD", "JPY"), ensure_ascii=False, indent=2))
    print(json.dumps(get_exchange_rate("ABC", "XYZ"), ensure_ascii=False, indent=2))
```

### 3.3 查本地知识库工具

将 Day 15–20 的 RAG 系统封装成一个工具，让 LLM 能按需查询本地文档：

```python
"""
tools/knowledge_base.py — 本地知识库查询工具（基于 Day 18 的向量检索）
"""

import json
import os
from dataclasses import dataclass, field

KNOWLEDGE_BASE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": (
            "在本地知识库中检索与问题相关的文档片段。"
            "适用于回答关于产品、政策、手册等私有文档的问题。"
            "当模型自身知识无法回答用户的具体业务问题时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询语句，用自然语言描述要查找的信息，如'退款政策是什么'",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回最相关的片段数量，默认 3，最大 5",
                },
            },
            "required": ["query"],
        },
    },
}


@dataclass
class SimpleKnowledgeBase:
    """简化版本地知识库（基于关键词匹配，不依赖 Embedding 模型）"""
    documents: list[dict] = field(default_factory=list)

    def add_document(self, text: str, source: str = "文档"):
        # 按段落切分
        chunks = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
        for chunk in chunks:
            self.documents.append({"text": chunk, "source": source})

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        query_words = set(query.lower().replace(" ", ""))
        scored = []
        for doc in self.documents:
            doc_words = set(doc["text"].lower().replace(" ", ""))
            shared = len(query_words & doc_words)
            if shared > 0:
                scored.append((shared, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]


# 全局知识库实例（真实场景用持久化向量库替换）
_kb = SimpleKnowledgeBase()

# 示例文档
_kb.add_document("""
退款政策

退款申请需在购买后 30 天内提交。超过 30 天将不予受理。

退款处理时间：提交后 3-5 个工作日退回原支付方式，节假日可能延长至 7 个工作日。

以下情况不支持退款：已激活的数字内容（电子书、激活码等）、已生产的定制商品、已拆封的食品类商品。

申请退款请联系：support@example.com
""", source="退款政策文档")

_kb.add_document("""
会员权益

普通会员：每月 10 元，享受 9 折优惠和优先客服。

高级会员：每月 30 元，享受 8 折优惠、优先发货（24 小时内）、专属客服通道。

会员积分：每消费 1 元获得 1 积分，100 积分兑换 1 元优惠券。积分有效期 1 年。
""", source="会员权益说明")


def search_knowledge_base(query: str, top_k: int = 3) -> dict:
    top_k = min(max(1, top_k), 5)  # 限制在 1-5 范围内
    results = _kb.search(query, top_k=top_k)

    if not results:
        return {
            "found": False,
            "message": f"知识库中未找到与 '{query}' 相关的内容",
            "results": [],
        }

    return {
        "found": True,
        "query": query,
        "count": len(results),
        "results": [
            {"index": i + 1, "source": r["source"], "content": r["text"]}
            for i, r in enumerate(results)
        ],
        "summary": f"找到 {len(results)} 条相关内容，来源：{', '.join(set(r['source'] for r in results))}",
    }


if __name__ == "__main__":
    print(json.dumps(search_knowledge_base("退款需要多久"), ensure_ascii=False, indent=2))
    print(json.dumps(search_knowledge_base("会员折扣"), ensure_ascii=False, indent=2))
    print(json.dumps(search_knowledge_base("什么是量子力学"), ensure_ascii=False, indent=2))
```

---

## 四、工具独立测试

### 4.1 工具函数测试策略

工具函数必须在接入 LLM 之前**单独测试**——发现的问题越早，修复越容易。

```python
"""
tests/test_tools.py — 工具函数独立测试
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.weather import get_weather
from tools.exchange_rate import get_exchange_rate
from tools.knowledge_base import search_knowledge_base


def assert_ok(result: dict, msg: str = ""):
    assert "error" not in result or result.get("error") != True, f"意外错误：{result} | {msg}"

def assert_error(result: dict, msg: str = ""):
    assert result.get("error") == True, f"期望错误但成功了：{result} | {msg}"

def assert_has_keys(result: dict, *keys):
    for k in keys:
        assert k in result, f"返回值缺少字段 '{k}'：{result}"


# ── 天气工具测试 ──────────────────────────────────────────────────────────────

def test_weather_valid_city():
    result = get_weather("北京")
    assert_ok(result, "北京应该能查到天气")
    assert_has_keys(result, "city", "temperature", "condition", "summary")
    assert isinstance(result["temperature"], (int, float)), "temperature 应该是数字"
    print(f"✓ test_weather_valid_city: {result['summary']}")

def test_weather_invalid_city():
    result = get_weather("XYZ_INVALID_CITY_12345")
    assert_error(result, "无效城市应该返回错误")
    assert "message" in result
    print(f"✓ test_weather_invalid_city: {result['message']}")

def test_weather_fahrenheit():
    result = get_weather("上海", unit="fahrenheit")
    assert_ok(result)
    assert result.get("unit") == "°F", f"单位应为 °F，实际：{result.get('unit')}"
    print(f"✓ test_weather_fahrenheit: {result['summary']}")


# ── 汇率工具测试 ──────────────────────────────────────────────────────────────

def test_exchange_rate_basic():
    result = get_exchange_rate("USD", "CNY")
    assert_ok(result)
    assert_has_keys(result, "rate", "summary", "description")
    assert result["rate"] > 1, f"USD→CNY 汇率应大于 1，实际：{result['rate']}"
    print(f"✓ test_exchange_rate_basic: {result['description']}")

def test_exchange_rate_with_amount():
    result = get_exchange_rate("CNY", "USD", amount=1000)
    assert_ok(result)
    assert "converted_amount" in result
    assert "summary" in result
    print(f"✓ test_exchange_rate_with_amount: {result['summary']}")

def test_exchange_rate_same_currency():
    result = get_exchange_rate("USD", "USD")
    assert_ok(result)
    assert result["rate"] == 1.0
    print(f"✓ test_exchange_rate_same_currency: rate={result['rate']}")

def test_exchange_rate_invalid():
    result = get_exchange_rate("ABC", "XYZ")
    assert_error(result)
    print(f"✓ test_exchange_rate_invalid: {result['message']}")


# ── 知识库工具测试 ────────────────────────────────────────────────────────────

def test_kb_found():
    result = search_knowledge_base("退款")
    assert result["found"] == True
    assert len(result["results"]) > 0
    print(f"✓ test_kb_found: {result['summary']}")

def test_kb_not_found():
    result = search_knowledge_base("量子力学原理推导")
    assert result["found"] == False
    print(f"✓ test_kb_not_found: {result['message']}")


# ── 运行所有测试 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_weather_valid_city,
        test_weather_invalid_city,
        test_weather_fahrenheit,
        test_exchange_rate_basic,
        test_exchange_rate_with_amount,
        test_exchange_rate_same_currency,
        test_exchange_rate_invalid,
        test_kb_found,
        test_kb_not_found,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} [异常]: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"通过: {passed}/{passed + failed}")
```

### 4.2 Schema 校验测试

```python
def validate_tool_schema(schema: dict) -> list[str]:
    """检查工具 Schema 是否符合规范，返回问题列表"""
    issues = []
    fn = schema.get("function", {})

    if not fn.get("name"):
        issues.append("缺少 name 字段")
    if not fn.get("description") or len(fn["description"]) < 20:
        issues.append(f"description 过短（当前：{len(fn.get('description', ''))} 字符），建议至少 20 字")

    params = fn.get("parameters", {})
    props = params.get("properties", {})
    required = params.get("required", [])

    for param_name, param_def in props.items():
        if not param_def.get("description"):
            issues.append(f"参数 '{param_name}' 缺少 description")
        if param_def.get("type") == "string" and not param_def.get("enum") \
                and len(param_def.get("description", "")) < 10:
            issues.append(f"参数 '{param_name}' 的 description 过短，建议加举例说明")

    return issues


# 验证三个工具的 Schema
from tools.weather import WEATHER_TOOL_SCHEMA
from tools.exchange_rate import EXCHANGE_RATE_TOOL_SCHEMA
from tools.knowledge_base import KNOWLEDGE_BASE_TOOL_SCHEMA

for schema in [WEATHER_TOOL_SCHEMA, EXCHANGE_RATE_TOOL_SCHEMA, KNOWLEDGE_BASE_TOOL_SCHEMA]:
    name = schema["function"]["name"]
    issues = validate_tool_schema(schema)
    if issues:
        print(f"⚠ {name}: {issues}")
    else:
        print(f"✓ {name}: Schema 校验通过")
```

---

## 五、Day 23 知识速查

### 工具定义完整模板

```python
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tool_name",                  # snake_case，动词开头（get_/search_/calculate_）
        "description": (
            "这个工具能做什么（动词+对象）。"   # ① 能做什么
            "返回xxx格式的数据。"               # ② 返回什么
            "适用于xxx场景。"                  # ③ 适用边界
            "不适用于xxx。"                    # ④ 不适用边界（可选）
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",          # string / integer / number / boolean
                    "description": "参数含义，格式举例如 'xxx'",
                    # "enum": ["a", "b"]       # 可选类型用 enum 锁定
                },
                "param2": {
                    "type": "integer",
                    "description": "参数含义，默认值为 N",
                    # "minimum": 1, "maximum": 10  # 可选数值范围
                },
            },
            "required": ["param1"],            # 必填参数列表
        },
    },
}
```

### 工具函数模板

```python
def tool_function(required_param: str, optional_param: int = 3) -> dict:
    # 输入校验
    if not required_param or not required_param.strip():
        return {"error": True, "message": "required_param 不能为空"}
    
    # 范围检查
    optional_param = min(max(1, optional_param), 10)
    
    try:
        # 核心逻辑
        raw_result = fetch_external_data(required_param)
        
        return {
            "input": required_param,           # 回显输入，便于模型理解
            "result": raw_result,
            "summary": f"...",                 # 可选：预先整合的自然语言描述
        }
    except Exception as e:
        return {"error": True, "message": f"操作失败：{e}"}
```

### 工具设计检查清单

```
□ 工具名使用动词 + 名词（get_weather, search_doc, calculate_tax）
□ description ≥ 20 字，含能做什么 + 返回什么 + 适用边界
□ 每个参数都有 description，字符串参数有格式举例
□ 可选参数有合理默认值，在函数内做范围约束
□ 返回值是平铺的 dict，字段名自解释
□ 错误时返回 {"error": True, "message": "..."} 而不是抛异常
□ 工具函数可以脱离 LLM 独立运行和测试
```

---

## 六、实践任务

- [ ] 在本机运行三个工具的独立测试：`python tools/weather.py` / `python tools/exchange_rate.py` / `python tools/knowledge_base.py`，确认每个都能输出正确结果
- [ ] 跑通 `python tests/test_tools.py`，确认 9 个测试用例全部通过
- [ ] 对 `get_weather` 用无效城市名测试，确认返回 `{"error": True, "message": "..."}` 而不是崩溃
- [ ] 用 `validate_tool_schema` 函数检查三个工具的 Schema，确认无问题
- [ ] 自己定义第四个工具（任选：查股价、查快递状态、翻译文本），完成 Schema + 函数实现 + 至少 3 个测试用例
- [ ] 思考并记录："如果工具返回的 summary 字段是错的，模型会怎么处理？"

**产出标准**：

- 三个工具文件（`tools/weather.py`、`tools/exchange_rate.py`、`tools/knowledge_base.py`）可独立运行
- 测试全部通过，至少验证了正常路径 + 错误路径

---

## 七、下一步预告

**Day 24：完成单工具调用 Demo**

Day 23 把工具本身做扎实（独立可运行、错误处理健壮、Schema 规范），Day 24 把工具**接入真实的 LLM 对话**，完成完整的单工具调用闭环：

- **工具注册与 tool_choice 控制**：`auto` vs `none` vs `{"type": "function", "function": {"name": "..."}}`（强制指定工具）
- **模型触发时机的调试**：什么样的问题会触发 `get_weather`？什么不会？如何调整 description 来改变触发边界？
- **多轮对话中的工具调用**：工具结果在历史消息里如何保留，模型在下一轮对话时能否引用上一次的工具结果？
- **工具调用失败的用户体验**：当工具返回 `error: True` 时，模型如何向用户解释，而不是直接说"工具出错了"？

Day 24 的产出：一个完整的单工具调用 Demo，用户能看到从"提问 → 工具调用日志 → 自然语言回答"的完整过程。
