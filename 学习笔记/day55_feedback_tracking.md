# Day 55：反馈追踪：用户反馈信号采集与评估回流

> 学习目标：区分"系统怎么执行的"（可观测性）和"用户觉得结果好不好"（反馈信号）两条数据链路；掌握显式反馈（👍/👎）、人工标注、隐式信号（追问/重新提问）三种采集形式；给项目加一个反馈入口，把反馈和 `trace_id` 关联存储，产出一份可追溯的低分回答清单
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 55
>
> 🧭 导航：[← Day 54 · 输出护栏与内容过滤](day54_output_guardrails.md) → [Day 56 · Docker 容器化与部署](day56_docker_deployment.md)

---

## 目录

- [一、反馈追踪要解决什么问题](#一反馈追踪要解决什么问题)
  - [1.1 和 Day 43 可观测性的边界](#11-和-day-43-可观测性的边界)
  - [1.2 为什么"输出没被护栏拦截"不等于"用户满意"](#12-为什么输出没被护栏拦截不等于用户满意)
- [二、反馈信号的三种形式](#二反馈信号的三种形式)
  - [2.1 显式反馈：thumbs up/down](#21-显式反馈thumbs-updown)
  - [2.2 人工标注](#22-人工标注)
  - [2.3 隐式信号：用户是否追问/重新提问](#23-隐式信号用户是否追问重新提问)
- [三、反馈采集实现：关联 trace_id 存储](#三反馈采集实现关联-trace_id-存储)
  - [3.1 FeedbackStore 数据结构](#31-feedbackstore-数据结构)
  - [3.2 界面接入：Gradio 反馈入口](#32-界面接入gradio-反馈入口)
  - [3.3 隐式信号的自动检测](#33-隐式信号的自动检测)
- [四、反馈回流：从原始信号到低分回答清单](#四反馈回流从原始信号到低分回答清单)
  - [4.1 生成低分回答清单](#41-生成低分回答清单)
  - [4.2 反馈回流到离线评估集与 Prompt 迭代](#42-反馈回流到离线评估集与-prompt-迭代)
- [五、完整实现](#五完整实现)
- [六、Day 55 知识速查](#六day-55-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、反馈追踪要解决什么问题

### 1.1 和 Day 43 可观测性的边界

Day 43 接入 LangFuse 解决的是"系统怎么执行的"——一次请求调用了哪些工具、耗时多少、Token 消耗多少，这些都是**客观的执行事实**，不需要用户参与就能采集。今天要追踪的是完全不同的一类数据：**用户主观上觉得这次回答好不好**，这类信号只能来自用户本人（或事后的人工审核），系统内部再怎么记录调用链路也无法替代。

| 维度 | Day 43 可观测性 | Day 55 反馈追踪 |
|-----|----------------|----------------|
| 追踪对象 | 系统执行过程（调用链、耗时、Token） | 用户主观评价（好/坏、满意/不满意） |
| 数据来源 | 系统自动记录，不需要用户参与 | 依赖用户主动反馈或行为信号 |
| 解决的问题 | "这次调用哪里慢了、哪里出错了" | "这次回答质量到底行不行" |
| 关联点 | 两者共享同一个 `trace_id`，可以互相对照 | 通过 `trace_id` 回查对应的执行细节 |

两条链路不是替代关系，而是**同一个 `trace_id` 下的两类数据**：可观测性回答"发生了什么"，反馈追踪回答"发生的结果好不好"，把两者用 `trace_id` 关联起来，才能定位"哪种执行模式容易导致用户不满意"。

### 1.2 为什么"输出没被护栏拦截"不等于"用户满意"

Day 54 的护栏解决的是"有没有明确违规"（泄露、越权、格式错误），这是一条底线；但一个回答完全没有违规，依然可能是**跑题、啰嗦、没答到点子上**，这类"质量不够好"但"不违规"的情况，护栏层不负责判断，只能靠用户反馈信号才能被发现。反馈追踪补的正是护栏层之上、可观测性之外的这一块空白。

---

## 二、反馈信号的三种形式

### 2.1 显式反馈：thumbs up/down

用户主动点击的反馈，信号最直接，但**采集率通常很低**（大多数用户不会主动点赞/点踩）：

```
优点：信号明确，不需要额外推断
缺点：采集率低（行业经验通常个位数百分比），且愿意反馈的用户群体本身有偏差
       （更愿意点踩的往往是对结果强烈不满的用户，正向反馈样本天然偏少）
```

### 2.2 人工标注

事后由人工（客服/产品/开发者）抽样审阅对话记录，给出质量评分：

```
优点：质量高、可以设计标注维度（相关性/完整性/语气），不依赖用户主动行为
缺点：成本高，只能覆盖一小部分样本，无法做到全量覆盖
```

### 2.3 隐式信号：用户是否追问/重新提问

不需要用户主动做任何额外操作，从**对话行为模式**里推断满意度：

| 隐式信号 | 推断逻辑 |
|---------|---------|
| 用户紧接着用几乎相同的措辞重新提问 | 上一次回答大概率没有解决问题 |
| 用户在收到回答后立刻追加"不是这个意思""你没答对" | 明确的负向信号，且比 👎 更能定位具体哪里错了 |
| 用户话题突然中断，没有继续追问也没有表达满意 | 弱信号，可能满意也可能放弃，需要结合会话时长等其他特征综合判断 |
| 用户复制/采纳了回答里的内容（如有相关埋点） | 弱正向信号 |

隐式信号的价值在于**覆盖率远高于显式反馈**——不需要用户主动点击，只要有对话发生就能提取，但准确率不如显式反馈，需要结合规则或简单分类器过滤噪音。

---

## 三、反馈采集实现：关联 trace_id 存储

### 3.1 FeedbackStore 数据结构

```python
# feedback/feedback_store.py
from dataclasses import dataclass, field
from enum import Enum
import time
import json
import sqlite3

class FeedbackType(str, Enum):
    EXPLICIT_UP = "explicit_up"
    EXPLICIT_DOWN = "explicit_down"
    IMPLICIT_REASK = "implicit_reask"       # 用户重新提问，推断上次回答没解决问题
    IMPLICIT_COMPLAINT = "implicit_complaint"  # 用户明确表达"不对""没答到点子上"
    HUMAN_LABEL = "human_label"              # 人工标注

@dataclass
class FeedbackRecord:
    trace_id: str            # 关联 Day 43 可观测性里的同一个 trace_id
    feedback_type: FeedbackType
    score: int | None = None       # 人工标注场景可以打 1-5 分，显式反馈用 1/-1
    comment: str | None = None
    created_at: float = field(default_factory=time.time)

class FeedbackStore:
    def __init__(self, db_path: str = "feedback.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                trace_id TEXT, feedback_type TEXT, score INTEGER,
                comment TEXT, created_at REAL
            )
        """)
        self._conn.commit()

    def save(self, record: FeedbackRecord) -> None:
        self._conn.execute(
            "INSERT INTO feedback VALUES (?, ?, ?, ?, ?)",
            (record.trace_id, record.feedback_type.value, record.score,
             record.comment, record.created_at),
        )
        self._conn.commit()

    def load_by_trace(self, trace_id: str) -> list[FeedbackRecord]:
        rows = self._conn.execute(
            "SELECT trace_id, feedback_type, score, comment, created_at FROM feedback WHERE trace_id=?",
            (trace_id,),
        ).fetchall()
        return [FeedbackRecord(r[0], FeedbackType(r[1]), r[2], r[3], r[4]) for r in rows]
```

**关键设计**：`trace_id` 是反馈记录和可观测性记录之间唯一的关联键——采集反馈时必须能拿到当次请求的 `trace_id`（从 Day 43 的 LangFuse 调用里获取），否则反馈就成了"知道用户不满意，但查不到是哪次调用"的孤立数据。

### 3.2 界面接入：Gradio 反馈入口

```python
# app.py
import gradio as gr
from feedback.feedback_store import FeedbackStore, FeedbackRecord, FeedbackType

feedback_store = FeedbackStore()

def chat_fn(message, history):
    trace_id = generate_trace_id()   # 同一个 trace_id 也传给 Day 43 的 LangFuse 调用
    reply = call_llm_with_trace(message, trace_id=trace_id)
    return reply, trace_id   # 把 trace_id 一并带出去，供反馈回调使用

def on_feedback(trace_id: str, liked: bool):
    feedback_store.save(FeedbackRecord(
        trace_id=trace_id,
        feedback_type=FeedbackType.EXPLICIT_UP if liked else FeedbackType.EXPLICIT_DOWN,
        score=1 if liked else -1,
    ))

with gr.Blocks() as demo:
    chatbot = gr.Chatbot()
    trace_state = gr.State()
    msg = gr.Textbox()

    def respond(message, history):
        reply, trace_id = chat_fn(message, history)
        history = history + [(message, reply)]
        return history, trace_id, ""

    msg.submit(respond, [msg, chatbot], [chatbot, trace_state, msg])

    # Gradio Chatbot 内置的 like/dislike 回调，天然带有消息索引
    chatbot.like(
        lambda evt: on_feedback(trace_state.value, evt.liked),
    )
```

### 3.3 隐式信号的自动检测

```python
# feedback/implicit_signal.py
from difflib import SequenceMatcher

def is_likely_reask(prev_user_msg: str, curr_user_msg: str, threshold: float = 0.6) -> bool:
    """简单的重新提问检测：文本相似度高于阈值，视为对上一轮回答不满意"""
    similarity = SequenceMatcher(None, prev_user_msg, curr_user_msg).ratio()
    return similarity >= threshold

COMPLAINT_KEYWORDS = ["不对", "没答对", "不是这个意思", "重新说", "你理解错了"]

def is_explicit_complaint(user_msg: str) -> bool:
    return any(kw in user_msg for kw in COMPLAINT_KEYWORDS)

def detect_implicit_feedback(prev_trace_id: str, prev_user_msg: str, curr_user_msg: str) -> FeedbackRecord | None:
    if is_explicit_complaint(curr_user_msg):
        return FeedbackRecord(trace_id=prev_trace_id, feedback_type=FeedbackType.IMPLICIT_COMPLAINT)
    if is_likely_reask(prev_user_msg, curr_user_msg):
        return FeedbackRecord(trace_id=prev_trace_id, feedback_type=FeedbackType.IMPLICIT_REASK)
    return None
```

每一轮新的用户消息进来时，先跑一遍隐式信号检测，命中就针对**上一轮**的 `trace_id` 记一条反馈——隐式信号永远是"回头看上一次回答"，而不是评价当前这轮。

---

## 四、反馈回流：从原始信号到低分回答清单

### 4.1 生成低分回答清单

```python
# feedback/low_score_report.py
def generate_low_score_report(feedback_store: FeedbackStore, trace_store) -> list[dict]:
    """把负向反馈和对应的完整执行记录拼接成可分析的清单"""
    negative_types = {FeedbackType.EXPLICIT_DOWN, FeedbackType.IMPLICIT_REASK, FeedbackType.IMPLICIT_COMPLAINT}
    report = []
    for record in feedback_store.load_all():
        if record.feedback_type not in negative_types:
            continue
        trace_detail = trace_store.load(record.trace_id)   # 从 Day 43 的可观测性记录里回查
        report.append({
            "trace_id": record.trace_id,
            "feedback_type": record.feedback_type.value,
            "user_input": trace_detail.get("user_input"),
            "model_output": trace_detail.get("output"),
            "tools_called": trace_detail.get("tools_called"),
            "created_at": record.created_at,
        })
    return sorted(report, key=lambda r: r["created_at"], reverse=True)
```

**低分回答清单模板**：

| trace_id | 反馈类型 | 用户输入 | 模型输出摘要 | 调用的工具 |
|---------|---------|---------|------------|-----------|
| trace-00123 | explicit_down | "帮我查下周三北京的天气" | "抱歉，我只能查询当天天气" | get_weather |
| trace-00145 | implicit_reask | "退款多久到账" → "到账时间到底是多久" | "退款处理中，请耐心等待" | query_order |

每一行都能通过 `trace_id` 回查到 Day 43 记录的完整调用链——这是"反馈追踪"和"可观测性"两条链路真正被关联起来使用的地方。

### 4.2 反馈回流到离线评估集与 Prompt 迭代

```
低分回答清单产出后，两条回流路径：

路径 1：加入离线评估集
  → 把这些"曾经答错"的输入抽出来，做成 Day 63 RAGAS 评估里的负样本用例
  → 每次改动 Prompt/RAG 策略后，重跑这批用例，验证是否修复且没有引入新问题

路径 2：驱动下一轮 Prompt 迭代
  → 分析低分清单里的共性（比如"多轮追问类问题" answered 得普遍不好）
  → 针对性调整 System Prompt 或补充 Few-shot 示例（回到 Day 11 的 Prompt 优化方法论）
  → 迭代后，用同一批低分 case 复测，确认修复效果
```

反馈追踪的终点不是"采集到了多少条反馈"，而是这份低分清单能不能真正驱动下一轮迭代——采集了却没有回流利用，反馈机制就只是摆设。

---

## 五、完整实现

```python
# main.py
from feedback.feedback_store import FeedbackStore, FeedbackRecord, FeedbackType
from feedback.implicit_signal import detect_implicit_feedback
from feedback.low_score_report import generate_low_score_report

feedback_store = FeedbackStore()

def handle_turn(user_msg: str, prev_trace_id: str | None, prev_user_msg: str | None):
    if prev_trace_id and prev_user_msg:
        implicit = detect_implicit_feedback(prev_trace_id, prev_user_msg, user_msg)
        if implicit:
            feedback_store.save(implicit)

    trace_id = generate_trace_id()
    reply = call_llm_with_trace(user_msg, trace_id=trace_id)
    return reply, trace_id

# 定期跑报表（如每天一次）
if __name__ == "__main__":
    report = generate_low_score_report(feedback_store, trace_store)
    print(f"本周共 {len(report)} 条低分回答，按时间倒序：")
    for r in report[:10]:
        print(f"  [{r['feedback_type']}] {r['user_input']} → {r['model_output'][:50]}...")
```

---

## 六、Day 55 知识速查

### 三种反馈形式对比

| 形式 | 采集率 | 准确率 | 采集方式 |
|-----|-------|-------|---------|
| 显式反馈（👍/👎） | 低 | 高 | 用户主动点击 |
| 人工标注 | 覆盖率低（抽样） | 最高 | 事后人工审阅 |
| 隐式信号（追问/重新提问） | 高（无需用户主动操作） | 中（需规则/分类器过滤噪音） | 从对话行为模式自动推断 |

### 反馈追踪 vs 可观测性

```
Day 43 可观测性：追踪"系统怎么执行的"（调用链、耗时、Token），系统自动记录
Day 55 反馈追踪：追踪"用户觉得好不好"（满意度信号），依赖用户反馈或行为推断
共享的关联键：trace_id —— 两条数据链路通过它互相回查
```

### 反馈回流的两条路径

```
路径 1：低分 case → 加入离线评估集 → 每次改动后回归测试
路径 2：低分 case 共性分析 → 驱动 Prompt/RAG 策略迭代 → 用同批 case 复测验证
```

---

## 七、实践任务

- [ ] 给项目的对话界面加一个 👍/👎 反馈入口，点击后把 `FeedbackRecord` 和当次的 `trace_id` 一起存进 `FeedbackStore`
- [ ] 实现 `is_likely_reask()` 和 `is_explicit_complaint()`，构造一组"用户重新提问"的对话样本，验证隐式信号被正确检测
- [ ] 跑 `generate_low_score_report()`，产出一份至少包含 5 条记录的低分回答清单，确认每条都能通过 `trace_id` 回查到完整的用户输入/模型输出/调用工具
- [ ] 分析低分清单里的共性问题（比如某一类问题反复被追问），写一句话结论："这类问题回答得不好，因为 XX"
- [ ] （进阶）针对共性问题调整一版 System Prompt，用同批低分 case 复测，对比调整前后的隐式负反馈次数

**产出标准**：一份低分回答清单，每条记录都能通过 `trace_id` 追溯回具体的用户输入、模型输出、调用工具，可以直接用于下一步的 Prompt 迭代分析。

---

## 八、下一步预告

Day 56 进入**Docker 容器化与部署**：至此，项目已经具备可观测性（Day 43–44）、成本控制（Day 45–47）、架构与安全防线（Day 48–49、53–54）、上下文与状态管理（Day 50–51）、反馈闭环（Day 55）——下一步是把这些能力打包进一个可以真正对外提供服务的部署形态：写 Dockerfile、接入 GitHub Actions 做基础 CI、把开发阶段的本地向量库迁移到可远程访问的存储，让项目从"能在自己电脑上跑"变成"有一个别人能打开的 URL"。
