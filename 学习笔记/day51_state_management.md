# Day 51：状态管理：会话/任务状态的持久化与恢复设计

> 学习目标：理解应用层状态管理和 Day 35 图内 Checkpoint 的边界差异；掌握把会话状态从进程内存迁移到外部存储（Redis/数据库）的设计方法；用显式状态机（pending/running/done/failed）建模长任务执行状态；验证服务重启后会话与任务状态能被正确恢复
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 51
>
> 🧭 导航：[← Day 50 · 上下文工程（Context Engineering）](day50_context_engineering.md) → [Day 52 · 第 7–8 周复盘：工程化架构小结](day52_engineering_architecture_review.md)

---

## 目录

- [一、状态管理要解决什么问题](#一状态管理要解决什么问题)
  - [1.1 和 Day 35 Checkpoint 的边界](#11-和-day-35-checkpoint-的边界)
  - [1.2 两类需要管理的状态](#12-两类需要管理的状态)
- [二、会话状态外部化存储](#二会话状态外部化存储)
  - [2.1 进程内存状态的局限](#21-进程内存状态的局限)
  - [2.2 用 Redis 存会话状态](#22-用-redis-存会话状态)
  - [2.3 序列化：消息历史与记忆对象怎么存](#23-序列化消息历史与记忆对象怎么存)
- [三、任务状态机建模](#三任务状态机建模)
  - [3.1 四态设计：pending/running/done/failed](#31-四态设计pendingrunningdonefailed)
  - [3.2 状态机实现：转移合法性校验](#32-状态机实现转移合法性校验)
  - [3.3 任务状态持久化到数据库](#33-任务状态持久化到数据库)
- [四、恢复验证：重启不丢状态](#四恢复验证重启不丢状态)
  - [4.1 完整实现：SessionStore + TaskStore](#41-完整实现sessionstore--taskstore)
  - [4.2 重启前后行为对比测试](#42-重启前后行为对比测试)
- [五、Day 51 知识速查](#五day-51-知识速查)
- [六、实践任务](#六实践任务)
- [七、下一步预告](#七下一步预告)

---

## 一、状态管理要解决什么问题

### 1.1 和 Day 35 Checkpoint 的边界

Day 35 讲的 Checkpoint 是 **LangGraph 图内部一次执行的快照**——`thread_id` 对应一次图的运行过程，`MemorySaver`/`SqliteSaver` 存的是"某个节点执行完之后 State 长什么样"。这解决的是"图能不能暂停恢复"的问题，作用范围局限在**一次图调用**内部。

今天讲的状态管理是**应用层更大范围的状态**：一个用户从打开页面到关闭页面的整个会话生命周期、一个可能跨越多次图调用的长任务的执行进度。两者的关系是**嵌套**而非替代——一个长任务内部可能调用了好几次带 Checkpoint 的图，但"这个任务现在进行到第几步、是否失败"这件事，Checkpoint 并不负责回答。

| 维度 | Day 35 Checkpoint | Day 51 应用层状态管理 |
|-----|------------------|---------------------|
| 管理范围 | 一次图执行内部的节点级快照 | 一个会话/任务的完整生命周期 |
| 存储对象 | State（`messages`、`iteration` 等图字段） | 会话上下文、任务进度、任务结果 |
| 典型问题 | "图能不能在某节点暂停再恢复" | "服务重启后用户会话还在不在" |
| 依赖框架 | 强依赖 LangGraph 的 Checkpointer 接口 | 与框架无关，自己设计存储和恢复逻辑 |

### 1.2 两类需要管理的状态

```
会话状态（Session State）
  → 一个用户的对话历史、长期记忆引用、当前偏好设置
  → 特点：轻量、频繁读写、生命周期跟随用户交互

任务状态（Task State）
  → 一个耗时操作（批量抽取、多步 Agent 任务）的执行进度
  → 特点：有明确的开始/结束、需要显式标记"进行到哪一步""是否失败"
```

两者共同的痛点是：**默认都存在进程内存里**（比如 Gradio 的 `gr.State`、一个全局字典），进程一旦重启（部署发布、崩溃重启、多实例负载均衡切到另一台机器），这些状态全部丢失。

---

## 二、会话状态外部化存储

### 2.1 进程内存状态的局限

Day 26 的简单界面里用 `gr.State` 存对话历史，这是最常见的"进程内存状态"写法：

```python
# Day 26 的写法：状态只活在这一个 Gradio 进程里
import gradio as gr

def chat_fn(message, history_state):
    history_state.append({"role": "user", "content": message})
    reply = call_llm(history_state)
    history_state.append({"role": "assistant", "content": reply})
    return reply, history_state

demo = gr.ChatInterface(chat_fn, additional_inputs=[gr.State([])])
```

问题在于：
- **单实例假设**：`gr.State` 绑定在一次浏览器会话和当前 Python 进程之间，进程重启或换一台机器接手，`history_state` 直接归零
- **无法做负载均衡**：如果部署了多个实例，用户的请求被路由到另一个实例，该实例的进程内存里根本没有这个用户的状态
- **无法审计和恢复**：出问题后想看"这个会话之前发生了什么"，进程内存没有留下任何痕迹

### 2.2 用 Redis 存会话状态

把会话状态从"进程内存里的一个变量"迁移成"通过 key 从外部存储读写"，接口形状可以基本不变：

```python
# session/session_store.py
import json
import time
import redis

class SessionStore:
    """把会话状态存到 Redis，key 按 session_id 隔离"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 3600):
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def load(self, session_id: str) -> dict:
        raw = self._client.get(self._key(session_id))
        if raw is None:
            return {"messages": [], "created_at": time.time()}
        return json.loads(raw)

    def save(self, session_id: str, state: dict) -> None:
        state["updated_at"] = time.time()
        self._client.set(self._key(session_id), json.dumps(state), ex=self._ttl)

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))
```

Gradio 层的调用方式只需要把"读写内存变量"换成"读写 SessionStore"，业务逻辑不变：

```python
# app.py
session_store = SessionStore()

def chat_fn(message, request: gr.Request):
    session_id = request.session_hash          # Gradio 提供的稳定会话标识
    state = session_store.load(session_id)

    state["messages"].append({"role": "user", "content": message})
    reply = call_llm(state["messages"])
    state["messages"].append({"role": "assistant", "content": reply})

    session_store.save(session_id, state)
    return reply
```

**关键改动只有两处**：不再用 `gr.State` 传递状态，而是每次请求开头 `load`、结尾 `save`；`session_id` 从"进程内一个变量"变成"外部存储的 key"。

### 2.3 序列化：消息历史与记忆对象怎么存

外部化存储要求状态可以被序列化成字符串（JSON 是最常见选择），这里有两个容易踩的坑：

| 坑 | 问题 | 处理方式 |
|----|------|---------|
| **消息对象不是原生可 JSON 化的类型** | LangChain 的 `HumanMessage`/`AIMessage` 直接 `json.dumps` 会报错 | 存储前转成 `{"role": ..., "content": ...}` 这种纯 dict，读取时再还原成消息对象 |
| **记忆对象（如向量、embedding）体积大** | 把完整 embedding 向量存进会话状态会让单条记录膨胀 | 会话状态只存"记忆的引用 ID"，实际向量留在专门的向量库里，按需检索 |

```python
def messages_to_dicts(messages: list) -> list[dict]:
    return [{"role": m.type, "content": m.content} for m in messages]

def dicts_to_messages(dicts: list[dict]) -> list:
    role_map = {"human": HumanMessage, "ai": AIMessage, "system": SystemMessage}
    return [role_map[d["role"]](content=d["content"]) for d in dicts]
```

---

## 三、任务状态机建模

### 3.1 四态设计：pending/running/done/failed

会话状态解决"聊天记录还在不在"，任务状态解决"一个长时间运行的操作现在到哪一步了"。用显式状态机代替"一个布尔值 `is_done`"：

```
pending  → 任务已创建，还未开始执行
   ↓
running  → 正在执行（可以附带进度百分比/当前步骤）
   ↓
done     → 成功完成，结果已就绪
   或
failed   → 执行失败，附带失败原因
```

只用一个 `is_done: bool` 无法区分"还没开始"和"执行失败"，也无法表达"正在执行、请稍候"——这是很多 Demo 级项目里进度提示做不对的根因。

### 3.2 状态机实现：转移合法性校验

```python
# task/task_state.py
from enum import Enum
from dataclasses import dataclass, field
import time

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

# 合法的状态转移表，防止"已完成的任务又被标记为运行中"这类逻辑错误
_VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING},
    TaskStatus.RUNNING: {TaskStatus.DONE, TaskStatus.FAILED},
    TaskStatus.DONE: set(),
    TaskStatus.FAILED: set(),
}

@dataclass
class TaskState:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: dict | None = None
    error: str | None = None
    updated_at: float = field(default_factory=time.time)

    def transition(self, new_status: TaskStatus, **kwargs):
        if new_status not in _VALID_TRANSITIONS[self.status]:
            raise ValueError(f"非法状态转移: {self.status} → {new_status}")
        self.status = new_status
        self.updated_at = time.time()
        for k, v in kwargs.items():
            setattr(self, k, v)
```

`_VALID_TRANSITIONS` 把"任务不能从 `done` 跳回 `running`"这种约束显式写死，而不是靠调用方自觉遵守——这是状态机相比自由字段赋值的核心价值。

### 3.3 任务状态持久化到数据库

```python
# task/task_store.py
import sqlite3
import json
from .task_state import TaskState, TaskStatus

class TaskStore:
    def __init__(self, db_path: str = "tasks.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0,
                result TEXT,
                error TEXT,
                updated_at REAL
            )
        """)
        self._conn.commit()

    def save(self, task: TaskState) -> None:
        self._conn.execute(
            """INSERT INTO tasks (task_id, status, progress, result, error, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(task_id) DO UPDATE SET
                 status=excluded.status, progress=excluded.progress,
                 result=excluded.result, error=excluded.error, updated_at=excluded.updated_at""",
            (task.task_id, task.status.value, task.progress,
             json.dumps(task.result) if task.result else None, task.error, task.updated_at),
        )
        self._conn.commit()

    def load(self, task_id: str) -> TaskState | None:
        row = self._conn.execute(
            "SELECT task_id, status, progress, result, error, updated_at FROM tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return TaskState(
            task_id=row[0], status=TaskStatus(row[1]), progress=row[2],
            result=json.loads(row[3]) if row[3] else None, error=row[4], updated_at=row[5],
        )

    def load_running_tasks(self) -> list[TaskState]:
        """服务启动时调用：找出重启前"卡在 running"的任务，交给上层决定重跑还是标记失败"""
        rows = self._conn.execute(
            "SELECT task_id FROM tasks WHERE status=?", (TaskStatus.RUNNING.value,)
        ).fetchall()
        return [self.load(r[0]) for r in rows]
```

`load_running_tasks` 是恢复设计里容易被忽略的一环：进程重启前如果有任务卡在 `running`，重启后既不能假装它已经 `done`，也不能让它永远卡住——正确做法是启动时扫描这些任务，明确标记为 `failed`（附带"服务重启中断"的错误信息）或重新入队执行。

---

## 四、恢复验证：重启不丢状态

### 4.1 完整实现：SessionStore + TaskStore

```python
# main.py
from session.session_store import SessionStore
from task.task_store import TaskStore
from task.task_state import TaskState, TaskStatus

session_store = SessionStore(redis_url="redis://localhost:6379/0")
task_store = TaskStore(db_path="tasks.db")

def on_startup():
    """服务启动时的恢复逻辑"""
    stuck_tasks = task_store.load_running_tasks()
    for task in stuck_tasks:
        task.transition(TaskStatus.FAILED, error="服务重启，任务中断")
        task_store.save(task)
    print(f"恢复检查完成：{len(stuck_tasks)} 个中断任务已标记为 failed")

def start_long_task(task_id: str, user_query: str):
    task = TaskState(task_id=task_id)
    task_store.save(task)                      # 落库为 pending

    task.transition(TaskStatus.RUNNING)
    task_store.save(task)                       # 落库为 running

    try:
        result = run_multi_step_agent(user_query)  # 耗时的多步 Agent 任务
        task.transition(TaskStatus.DONE, result=result, progress=1.0)
    except Exception as e:
        task.transition(TaskStatus.FAILED, error=str(e))
    task_store.save(task)                        # 落库为最终状态
```

### 4.2 重启前后行为对比测试

```python
def test_session_survives_restart():
    session_id = "test-session-001"

    # 模拟"进程 1"写入会话状态
    store_a = SessionStore()
    state = store_a.load(session_id)
    state["messages"].append({"role": "user", "content": "你好"})
    store_a.save(session_id, state)
    del store_a                                   # 模拟进程销毁

    # 模拟"进程 2"（重启后）重新读取
    store_b = SessionStore()
    recovered = store_b.load(session_id)
    assert recovered["messages"][0]["content"] == "你好"
    print("✅ 会话状态跨进程存活")

def test_task_marked_failed_after_restart():
    task_store = TaskStore(db_path=":memory:")   # 简化演示，实际用文件路径
    task = TaskState(task_id="task-001")
    task.transition(TaskStatus.RUNNING)
    task_store.save(task)                          # 模拟任务执行到一半时进程崩溃

    on_startup_check(task_store)                   # 模拟服务重启后的恢复扫描

    recovered = task_store.load("task-001")
    assert recovered.status == TaskStatus.FAILED
    assert "重启" in recovered.error
    print("✅ 中断任务被正确标记为 failed，而不是永久卡在 running")
```

预期输出：

```
✅ 会话状态跨进程存活
✅ 中断任务被正确标记为 failed，而不是永久卡在 running
```

---

## 五、Day 51 知识速查

### Checkpoint vs 应用层状态管理

```
Day 35 Checkpoint：图内部节点级快照，解决"图能不能暂停恢复"
Day 51 状态管理：  应用层会话/任务生命周期，解决"服务重启后状态还在不在"
两者可以嵌套：一个长任务内部调用了多次带 Checkpoint 的图
```

### 存储选型速查

| 状态类型 | 特点 | 推荐存储 |
|---------|------|---------|
| 会话状态 | 轻量、高频读写、有 TTL | Redis（自带过期机制） |
| 任务状态 | 需要历史可查询、结构化 | SQLite / PostgreSQL |
| 图内 Checkpoint | 框架托管，自动生成 | LangGraph 自带的 Checkpointer |

### 任务状态机模板

```python
class TaskStatus(str, Enum):
    PENDING = "pending"; RUNNING = "running"; DONE = "done"; FAILED = "failed"

_VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING},
    TaskStatus.RUNNING: {TaskStatus.DONE, TaskStatus.FAILED},
    TaskStatus.DONE: set(), TaskStatus.FAILED: set(),
}
```

### 重启恢复检查清单

```
□ 会话状态从外部存储读，而不是进程内变量
□ 服务启动时扫描"卡在 running"的任务，显式转为 failed 或重新入队
□ 消息对象存储前转成纯 dict，读取时再还原
□ 大体积记忆对象只存引用 ID，不整体塞进会话状态
```

---

## 六、实践任务

- [ ] 把项目里用 `gr.State`（或任何全局变量）存的会话历史改成 `SessionStore`，用 Redis（本地可用 `docker run -p 6379:6379 redis` 起一个）验证读写
- [ ] 实现 `TaskState` 状态机，故意触发一次非法转移（如 `done → running`），确认抛出异常而不是静默成功
- [ ] 实现 `TaskStore`，跑一次完整任务生命周期（pending → running → done），用 SQLite 客户端查看落库记录
- [ ] 手动模拟"任务执行到 running 时进程被杀掉"（`Ctrl+C` 中断），重启程序调用 `on_startup()`，验证该任务被正确标记为 `failed` 而不是永远卡在 `running`
- [ ] 跑一次 `test_session_survives_restart`：先用一个 Python 进程写入会话，销毁后用另一个新进程读取，确认历史消息还在

**产出标准**：重启服务后，用户会话状态（历史消息）能从外部存储正确恢复；重启前卡在 `running` 的任务，重启后被明确标记为 `failed` 并带有中断原因，而不是永久停留在 `running` 状态误导用户。

---

## 七、下一步预告

Day 52 进入**第 7–8 周复盘：工程化架构小结**：回顾模型网关（Day 48）、限流（Day 49）、上下文工程（Day 50）、状态管理（Day 51）这几项分别解决了系统的哪类"隐性成本"，以及在什么规模的项目里这些投入才划算——不是所有项目都需要把这几样都做全，复盘会给出一个判断边界。
