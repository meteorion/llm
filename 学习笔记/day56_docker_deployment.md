# Day 56：Docker 容器化与部署

> 学习目标：写出一份具备多阶段构建、环境变量注入、依赖锁定的 Dockerfile 并本地跑通；搭建最小 GitHub Actions workflow 实现"push → 自动测试"的质量门控；把开发阶段的本地 Chroma 迁移到可远程访问的 Qdrant，摆脱单文件单点依赖；把项目部署到一个公开可访问的 URL
>
> 📚 所属阶段：**深化阶段 · 路线 C：走向生产部署**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 56
>
> 🧭 导航：[← Day 55 · 反馈追踪：用户反馈信号采集与评估回流](day55_feedback_tracking.md) → [Day 57 · 阶段项目整合 + 第 9 周复盘](day57_route_c_integration_review.md)

---

## 目录

- [一、Dockerfile 编写](#一dockerfile-编写)
  - [1.1 多阶段构建：为什么不是一个 FROM 到底](#11-多阶段构建为什么不是一个-from-到底)
  - [1.2 环境变量注入：不要把 API Key 写进镜像](#12-环境变量注入不要把-api-key-写进镜像)
  - [1.3 依赖锁定：requirements.txt 固定版本](#13-依赖锁定requirementstxt-固定版本)
- [二、部署选项对比](#二部署选项对比)
- [三、CI/CD 基础：GitHub Actions](#三cicd-基础github-actions)
  - [3.1 最小 workflow：push 触发自动测试](#31-最小-workflow push-触发自动测试)
  - [3.2 质量门控的意义](#32-质量门控的意义)
- [四、生产向量数据库迁移：Chroma → Qdrant](#四生产向量数据库迁移chroma--qdrant)
  - [4.1 为什么本地文件模式不适合生产](#41-为什么本地文件模式不适合生产)
  - [4.2 Qdrant Docker 部署与接入](#42-qdrant-docker-部署与接入)
  - [4.3 迁移验证：检索结果一致性对比](#43-迁移验证检索结果一致性对比)
- [五、完整实现：从本地到公开 URL](#五完整实现从本地到公开-url)
- [六、Day 56 知识速查](#六day-56-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、Dockerfile 编写

### 1.1 多阶段构建：为什么不是一个 FROM 到底

单阶段构建把"安装编译工具 → 装依赖 → 复制代码"全部塞进一个镜像，最终镜像会带着编译期才需要的工具链，体积臃肿。多阶段构建把"构建环境"和"运行环境"拆开：

```dockerfile
# Dockerfile
# ── 阶段 1：构建依赖 ──────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 阶段 2：运行环境（只拷贝构建产物，不带构建工具）─────────────
FROM python:3.11-slim AS runtime

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

# 不在 Dockerfile 里写死密钥，运行时通过环境变量注入
ENV PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["python", "app.py"]
```

`builder` 阶段产出的 `/install` 目录只包含已经装好的 Python 包，`runtime` 阶段用 `COPY --from=builder` 只拿这一份产物，不会带上 pip 安装过程中的缓存和中间文件——最终镜像体积明显小于单阶段写法。

### 1.2 环境变量注入：不要把 API Key 写进镜像

```dockerfile
# ❌ 错误写法：把密钥直接写进 Dockerfile 或 .env 并 COPY 进镜像
# ENV DEEPSEEK_API_KEY=sk-xxxxxxxx
# COPY .env .

# ✅ 正确写法：Dockerfile 里不出现任何密钥，运行时从外部注入
CMD ["python", "app.py"]
```

```bash
# 运行时通过 -e 参数或 --env-file 注入，密钥不会被打进镜像层
docker run -e DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY -p 7860:7860 my-app:latest

# 或者用 --env-file（.env 文件本身要在 .gitignore 里，不提交到仓库）
docker run --env-file .env -p 7860:7860 my-app:latest
```

**原因**：镜像一旦构建完成会被推送到镜像仓库（哪怕是私有仓库），任何能拉到这个镜像的人都能用 `docker history` 或直接解压镜像层看到 Dockerfile 里写死的内容——密钥必须在运行时通过环境变量、Secret 管理服务或部署平台的密钥面板注入，绝不写进镜像本身。

### 1.3 依赖锁定：requirements.txt 固定版本

```
# ❌ 不锁版本：本地能跑，构建镜像时可能装到新版本导致行为不一致
langchain
openai

# ✅ 锁定版本：本地开发环境和生产镜像用完全相同的依赖版本
langchain==0.3.7
openai==1.54.3
gradio==5.6.0
```

```bash
# 从当前开发环境导出锁定版本
pip freeze > requirements.txt

# 或用更精细的工具（pip-tools）区分直接依赖和传递依赖
pip-compile requirements.in -o requirements.txt
```

不锁版本是"能跑的 Demo"和"能稳定复现的部署"之间最容易被忽视的差距——同一份代码，今天构建和一个月后构建可能因为依赖自动升级到不兼容版本而行为不同。

---

## 二、部署选项对比

| 选项 | 优点 | 缺点 | 适合场景 |
|-----|------|------|---------|
| **Hugging Face Spaces** | 免费、Gradio/Streamlit 一键托管、零运维 | 免费额度资源有限，重负载场景不合适 | 演示、Portfolio 项目 |
| **Fly.io / Railway / Render** | 比传统云服务器易上手，按用量计费，支持 Docker 部署 | 比 Spaces 需要更多配置，免费额度有限 | 小型生产项目、需要自定义域名/更多资源 |
| **自己的 VPS** | 完全可控，无平台限制 | 需要自己维护操作系统、安全补丁、监控 | 对可控性要求高、有运维能力的场景 |

**选型建议**：个人项目/求职作品集优先 Hugging Face Spaces（配置成本最低）；需要长期稳定运行、有一定流量的项目考虑 Fly.io 这类 PaaS；只有明确需要完全掌控底层环境时才选 VPS。

---

## 三、CI/CD 基础：GitHub Actions

### 3.1 最小 workflow：push 触发自动测试

```yaml
# .github/workflows/test.yml
name: Run Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest tests/ -v
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
```

密钥通过 GitHub 仓库的 `Settings → Secrets and variables → Actions` 配置，workflow 文件里只引用 `${{ secrets.XXX }}`，不出现明文——和 Dockerfile 里"不要写死密钥"是同一个原则在 CI 层面的延伸。

### 3.2 质量门控的意义

```
没有 CI 的流程：
  写代码 → 本地随手跑一下 → git push → 合并到 main
  （测试是否通过完全靠开发者自觉，容易遗漏）

有 CI 的流程：
  写代码 → git push → GitHub Actions 自动跑测试 → 通过才允许合并（可配置分支保护规则）
  （测试变成强制关卡，不是"建议做"而是"必须过"）
```

即使项目规模很小，"push 后自动跑一遍已有测试"的成本极低（一个 workflow 文件），但能防住"改了一处逻辑却忘记跑测试，直接把回归问题带上 main"这类低级失误。

---

## 四、生产向量数据库迁移：Chroma → Qdrant

### 4.1 为什么本地文件模式不适合生产

Day 18 起用的 Chroma 默认是**本地文件模式**——向量数据存在容器/进程本地的一个目录里，这在生产环境会带来和 Day 51 状态管理同样性质的问题：

| 问题 | 具体表现 |
|-----|---------|
| 单点依赖 | 向量数据只在一个容器实例的文件系统里，容器重建（如重新部署）后数据丢失 |
| 无法多实例共享 | 部署多个应用实例做负载均衡时，每个实例的本地 Chroma 文件互相独立，检索结果不一致 |
| 缺乏远程访问能力 | 无法让另一个服务（如离线的批量索引任务）单独连接同一份向量数据 |

### 4.2 Qdrant Docker 部署与接入

```bash
# 一条命令启动 Qdrant（本地测试环境）
docker run -p 6333:6333 -v ./qdrant_storage:/qdrant/storage qdrant/qdrant
```

```python
# 从 Chroma 迁移到 Qdrant，只改向量库初始化和写入/查询的适配层
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(host="qdrant-host", port=6333)   # 生产环境指向远程 Qdrant 服务

client.recreate_collection(
    collection_name="docs",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)

def upsert_documents(chunks: list[str], embeddings: list[list[float]]):
    points = [
        PointStruct(id=i, vector=emb, payload={"text": chunk})
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    client.upsert(collection_name="docs", points=points)

def search(query_embedding: list[float], top_k: int = 3):
    results = client.search(collection_name="docs", query_vector=query_embedding, limit=top_k)
    return [{"text": r.payload["text"], "score": r.score} for r in results]
```

迁移只需要改动 Day 18/32 里"向量库初始化"和"写入/检索"这一层适配代码，上层的切分逻辑、Embedding 调用、RAG 生成链路完全不用动——这正是 Day 18 当初把检索封装成独立组件的收益：底层存储可以替换，接口形状不变。

### 4.3 迁移验证：检索结果一致性对比

```python
# tests/test_vectorstore_migration.py
def test_chroma_qdrant_consistency():
    query = "退款政策是什么？"
    chroma_results = chroma_search(query, top_k=3)
    qdrant_results = qdrant_search(query, top_k=3)

    chroma_texts = {r["text"] for r in chroma_results}
    qdrant_texts = {r["text"] for r in qdrant_results}

    overlap = chroma_texts & qdrant_texts
    print(f"Chroma 命中: {len(chroma_texts)}, Qdrant 命中: {len(qdrant_texts)}, 重合: {len(overlap)}")
    assert len(overlap) >= 2   # 允许排序细微差异，但核心命中文档应该一致
```

预期输出：

```
Chroma 命中: 3, Qdrant 命中: 3, 重合: 3
```

迁移验证的关键不是"两边分数完全一样"（不同向量库的距离计算实现细节可能有微小差异），而是**核心命中的文档集合基本一致**——如果迁移后检索到的文档发生了实质性变化，说明迁移过程中 Embedding 模型、索引参数或距离度量出现了不一致。

---

## 五、完整实现：从本地到公开 URL

```bash
# 1. 本地构建镜像
docker build -t my-llm-app:latest .

# 2. 本地运行验证
docker run -e DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY -p 7860:7860 my-llm-app:latest
# 打开 http://localhost:7860 验证功能正常

# 3. 推送到 Hugging Face Spaces（示例）
git remote add space https://huggingface.co/spaces/<username>/<space-name>
git push space main
# Space 在 Settings 里配置 DEEPSEEK_API_KEY 作为 Secret

# 4. 确认 GitHub Actions 跑通
git push origin main
# 在 GitHub 仓库的 Actions 标签页查看绿色 ✓
```

三个交付物到位后，项目就从"只能在自己电脑上跑的 Demo"变成"有公开 URL、有自动化测试门控、有可远程访问的向量存储"的可部署系统。

---

## 六、Day 56 知识速查

### Dockerfile 三原则

```
多阶段构建：把构建工具和运行环境分开，减小最终镜像体积
环境变量注入：密钥绝不写进镜像，运行时通过 -e / --env-file / 平台 Secret 面板注入
依赖锁定：requirements.txt 固定版本号，保证今天和一个月后构建行为一致
```

### 部署选项速查

| 场景 | 推荐 |
|-----|------|
| 个人作品集、演示 | Hugging Face Spaces |
| 小型生产、需要自定义配置 | Fly.io / Railway / Render |
| 完全可控、有运维能力 | 自己的 VPS |

### 向量库迁移检查清单

```
□ Qdrant/pgvector 已部署并可远程访问（不再是本地文件）
□ 写入/检索适配层已切换，上层 RAG 链路代码零改动
□ 迁移前后核心命中文档集合基本一致
□ 多实例部署时，所有实例指向同一个远程向量库
```

---

## 七、实践任务

- [ ] 写一份多阶段构建的 Dockerfile，本地 `docker build` 成功并 `docker run` 跑通项目
- [ ] 验证密钥不在镜像里：用 `docker history <image>` 或导出镜像层检查，确认没有明文密钥
- [ ] 写 `.github/workflows/test.yml`，push 后在 GitHub Actions 页面看到测试自动运行且通过
- [ ] 用 Docker 启动一个 Qdrant 实例，把项目的 Chroma 检索迁移过去，跑 `test_chroma_qdrant_consistency` 验证结果一致
- [ ] 把项目部署到 Hugging Face Spaces / Fly.io / 一台云服务器（任选其一），拿到一个可以分享给别人的公开 URL

**产出标准**：一个公开可访问的 URL；一个推送后能看到绿色 ✓ 的 GitHub Actions workflow；向量库已迁移到 Qdrant/pgvector，本地 Chroma 文件不再是唯一的数据来源。

---

## 八、下一步预告

Day 57 是**阶段项目整合 + 第 9 周复盘**：把 Day 43–56 的全部能力——可观测性、成本性能（缓存/批处理/路由）、模型网关、限流、上下文工程、状态管理、安全防护（注入攻防/输出护栏）、反馈追踪、容器化部署——整合进同一个项目，产出一版真正具备生产可维护性的完整系统，作为深化阶段路线 C 的收官交付。
