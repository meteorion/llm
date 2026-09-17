# Day 65：PDF / 表格 / 扫描件解析进阶

> 学习目标：理解真实文档"很脏"的具体表现（排版混乱、表格转文本后错位、扫描件没有文字层）；了解表格转结构化数据和基础 OCR 的思路；用 Docling 重新解析 Day 16 处理过的 PDF，和 pdfplumber 对比表格抽取质量；记录 Docling 依然处理不了的边界情况
>
> 📚 所属阶段：**深化阶段 · 路线 B：提升 RAG 质量**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[深化阶段路线](../规划文档/day31_67_deepening_roadmap.md) · Day 65
>
> 🧭 导航：[← Day 64 · 构建评估集与持续评估](day64_eval_set_and_continuous_evaluation.md) → [Day 66 · 阶段项目整合（RAG 深化版）](day66_rag_deepening_integration.md)

---

## 目录

- [一、真实文档为什么"很脏"](#一真实文档为什么很脏)
  - [1.1 Day 16 pdfplumber 方案的局限](#11-day-16-pdfplumber-方案的局限)
  - [1.2 三类脏数据的具体表现](#12-三类脏数据的具体表现)
- [二、表格转结构化数据的思路](#二表格转结构化数据的思路)
  - [2.1 表格拍平成纯文本的问题](#21-表格拍平成纯文本的问题)
  - [2.2 保留行列结构的提取思路](#22-保留行列结构的提取思路)
- [三、基础 OCR 思路](#三基础-ocr-思路)
- [四、Docling 与 marker：新一代文档解析工具](#四docling-与-marker新一代文档解析工具)
  - [4.1 Docling：IBM 开源的结构化文档解析器](#41-doclingibm-开源的结构化文档解析器)
  - [4.2 marker：基于 Layout 检测的 PDF 转 Markdown](#42-marker基于-layout-检测的-pdf-转-markdown)
  - [4.3 为什么这些工具比纯文本提取更好](#43-为什么这些工具比纯文本提取更好)
- [五、对比实验：pdfplumber vs Docling](#五对比实验pdfplumber-vs-docling)
- [六、Docling 处理不了的边界情况](#六docling-处理不了的边界情况)
- [七、Day 65 知识速查](#七day-65-知识速查)
- [八、实践任务](#八实践任务)
- [九、下一步预告](#九下一步预告)

---

## 一、真实文档为什么"很脏"

### 1.1 Day 16 pdfplumber 方案的局限

Day 16 用 `pdfplumber` 实现的 PDF 解析已经能处理"逐页提取文本、跳过扫描件页"这类基础场景，但 `pdfplumber` 本质上是**按文本的物理坐标顺序提取字符**，它不理解文档的**逻辑结构**（这一段文字属于哪个标题、这几个数字属于哪张表格的哪一行哪一列）：

```
pdfplumber 的提取方式：
  按 PDF 内部记录的坐标顺序，把文字一个个"读"出来拼成字符串
  → 不理解"这是标题""这是表格""这是页眉"这些结构信息
```

### 1.2 三类脏数据的具体表现

| 类型 | 具体表现 |
|-----|---------|
| **排版混乱** | 多栏排版的 PDF（如学术论文双栏排版），按坐标顺序提取会把左栏和右栏的文字交替拼接，产生语义完全错乱的文本 |
| **表格转文本后错位** | 表格本来是"行列对齐"的结构，转成纯文本后失去了列对齐关系，比如"产品名 单价 数量"表头和后面几行数字对不上，模型很难理解哪个数字对应哪一列 |
| **扫描件没有文字层** | 扫描件本质是一张图片，PDF 里没有任何可提取的文字字符，`pdfplumber` 这类基于文本层提取的工具直接返回空字符串 |

**核心问题**：这一步是整个 RAG 流程的**最上游**——如果原始文档解析阶段就丢失或扭曲了信息，后续 Day 17-64 做的所有切分、检索、生成、评估优化都是建立在残缺或错误的数据基础上，投入再多优化也无法弥补数据源头的损失。

---

## 二、表格转结构化数据的思路

### 2.1 表格拍平成纯文本的问题

假设原始表格是：

```
| 产品名   | 单价  | 库存 |
| 蓝牙耳机 | 199元 | 50   |
| 保温杯   | 89元  | 120  |
```

用 pdfplumber 按坐标顺序提取，很可能变成：

```
产品名单价库存蓝牙耳机199元50保温杯89元120
```

丢失了空格和换行边界，模型完全无法从这段文字还原出"蓝牙耳机对应199元、库存50"这样的行列对应关系。

### 2.2 保留行列结构的提取思路

正确的表格解析应该**识别出表格的行列边界**，把每一行、每一个单元格作为独立的结构化数据保留，再转成对模型友好的格式（比如 Markdown 表格语法，而不是拍平的纯文本）：

```markdown
| 产品名 | 单价 | 库存 |
|-------|------|------|
| 蓝牙耳机 | 199元 | 50 |
| 保温杯 | 89元 | 120 |
```

Markdown 表格语法保留了行列对齐关系，模型在训练时见过大量 Markdown 表格数据，能够正确理解这种格式里"某一行某一列的值"的对应关系——这是新一代文档解析工具（Docling/marker）相比 pdfplumber 纯文本提取的核心优势之一：**输出结构化 Markdown，而不是拍平的纯文本**。

---

## 三、基础 OCR 思路

扫描件本质是图片而非文本，要提取其中的文字内容必须走**光学字符识别（OCR）**流程：

```
扫描件 PDF（本质是图片）
    │
    ▼
图像预处理（去噪、矫正倾斜、二值化）
    │
    ▼
OCR 引擎识别文字区域和内容（如 Tesseract、PaddleOCR，或云端 OCR API）
    │
    ▼
输出识别出的文字 + 每段文字的位置坐标
    │
    ▼
按坐标顺序 / 版面分析重新组织成可读文本
```

**关键认知**：OCR 只解决"能不能提取出文字"的问题，识别质量高度依赖扫描件本身的清晰度——模糊、倾斜、手写体、复杂背景的扫描件即使用最好的 OCR 引擎也可能出现识别错误，这类文档在真实业务里往往需要人工校对兜底，而不能假设 OCR 结果 100% 准确。

---

## 四、Docling 与 marker：新一代文档解析工具

### 4.1 Docling：IBM 开源的结构化文档解析器

Docling（IBM 开源，2024 年底发布）支持 PDF / Word / HTML / 表格 / 扫描件等多种格式，核心特点是**输出结构化 Markdown**，而不是拍平的纯文本：

```python
# pip install docling
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("产品说明书.pdf")

markdown_content = result.document.export_to_markdown()
print(markdown_content)
# 表格会被正确识别并输出为 Markdown 表格语法，标题层级也会被保留
```

Docling 内部集成了版面分析（Layout Analysis）能力，能识别出文档里的标题、段落、表格、图片等不同区域，分别按各自的语义结构输出，而不是简单按坐标顺序拼接字符。

### 4.2 marker：基于 Layout 检测的 PDF 转 Markdown

marker 是另一个基于深度学习版面检测的 PDF 转 Markdown 工具，效果同样明显优于 pdfplumber 的纯文本提取：

```python
# pip install marker-pdf
from marker.convert import convert_single_pdf
from marker.models import load_all_models

models = load_all_models()
markdown_text, images, metadata = convert_single_pdf("产品说明书.pdf", models)
```

### 4.3 为什么这些工具比纯文本提取更好

| 维度 | pdfplumber（Day 16） | Docling / marker（Day 65） |
|-----|---------------------|---------------------------|
| 提取方式 | 按坐标顺序拼接字符 | 版面分析，识别文档逻辑结构 |
| 表格处理 | 拍平成无结构纯文本，容易错位 | 输出 Markdown 表格语法，保留行列对齐 |
| 标题/层级 | 无法区分标题和正文 | 能识别标题层级，保留文档结构 |
| 扫描件 | 无文字层时直接返回空 | 内置或可配合 OCR 引擎处理扫描件 |
| 适用场景 | 简单排版、无表格的文本类 PDF | 复杂排版、含表格、含扫描页的真实业务文档 |

**2025 年后，Docling 已成为生产级文档解析的主流选择**——不是说 pdfplumber 过时了（简单场景依然够用、依赖更轻），而是遇到真实业务文档（合同、说明书、财报，通常都包含表格和复杂排版）时，Docling/marker 这类基于版面理解的工具明显更可靠。

---

## 五、对比实验：pdfplumber vs Docling

```python
# experiments/parser_comparison.py
import pdfplumber
from docling.document_converter import DocumentConverter

def parse_with_pdfplumber(pdf_path: str) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)

def parse_with_docling(pdf_path: str) -> str:
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    return result.document.export_to_markdown()

def compare(pdf_path: str):
    pdfplumber_text = parse_with_pdfplumber(pdf_path)
    docling_text = parse_with_docling(pdf_path)

    print("=== pdfplumber 提取结果（表格部分）===")
    print(pdfplumber_text[:500])
    print("\n=== Docling 提取结果（表格部分）===")
    print(docling_text[:500])
```

**典型对比记录（找一份带表格的产品说明书 PDF）**：

| 对比项 | pdfplumber | Docling |
|-------|-----------|---------|
| 表格行列对齐 | 丢失，数字和表头拼接在一起 | 正确输出 Markdown 表格，行列对应清晰 |
| 多栏排版处理 | 左右栏内容交替错乱 | 按版面区域正确分离左右栏内容 |
| 标题层级 | 无区分，标题和正文混在一起 | 保留 `#`/`##` 级别的 Markdown 标题结构 |
| 处理耗时 | 快 | 明显更慢（版面分析模型推理开销） |

**结论**：Docling 在表格和复杂排版场景下的抽取质量明显优于 pdfplumber，但代价是处理速度更慢、依赖更重（需要下载和运行版面分析模型）——对于简单的纯文本 PDF（无表格、单栏排版），pdfplumber 依然是更轻量的选择。

---

## 六、Docling 处理不了的边界情况

即使是 Docling 这类新一代工具，依然有解析失败或效果不佳的场景：

| 边界情况 | 失败根因 |
|---------|---------|
| **排版极度复杂**（多层嵌套表格、图文混排密集） | 版面分析模型对超出常见模式的复杂布局判断可能出错，表格边界识别错乱 |
| **纯图片 PDF（扫描件）** | Docling 本身的版面分析依赖文档结构信息，纯图片仍需要先过 OCR 引擎提取文字，再交给 Docling 做结构化整理，不能指望它单独解决扫描件问题 |
| **加密文档** | 无法直接打开和解析被密码保护的 PDF，需要先用其他工具解密 |
| **手写内容** | OCR 对手写体的识别准确率远低于印刷体，Docling 处理这类内容的表格/文字提取同样会继承 OCR 阶段的错误 |
| **低分辨率扫描件** | 图像本身模糊、噪点多，OCR 引擎识别错误率高，Docling 无法修复上游 OCR 阶段的错误 |

**记录失败根因的意义**：不是所有文档质量问题都能靠"换一个更好的解析工具"解决——有些是工具能力边界内的问题（复杂排版、加密文档，可以尝试预处理或换工具），有些是数据本身质量问题（模糊扫描件、手写内容），后者往往需要人工校对兜底，而不是无限投入在解析工具的选型上。

---

## 七、Day 65 知识速查

### 三类脏数据速查

```
排版混乱   → 多栏排版按坐标提取会交替错乱
表格错位   → 拍平成纯文本丢失行列对齐关系
扫描件无文字层 → 本质是图片，需要走 OCR 流程
```

### 工具选型速查

| 场景 | 推荐工具 |
|-----|---------|
| 简单单栏文本 PDF，无表格 | pdfplumber（轻量，Day 16 已用） |
| 含表格、复杂排版的真实业务文档 | Docling / marker（版面分析，输出结构化 Markdown） |
| 扫描件（无文字层） | OCR 引擎（Tesseract/PaddleOCR）+ Docling 做结构化整理 |

### Docling 的边界

```
能处理：表格行列对齐、多栏排版分离、标题层级保留
处理不了（工具能力边界）：极复杂排版、加密文档
需要配合其他工具：纯图片扫描件（先OCR）、手写内容（OCR准确率本身受限）
```

---

## 八、实践任务

- [ ] 找一份带表格的真实 PDF（如产品说明书、财报摘要），分别用 `pdfplumber`（Day 16 方案）和 `Docling` 解析
- [ ] 对比两者对表格部分的抽取结果，记录行列对齐是否正确
- [ ] 如果手头有多栏排版的 PDF（如学术论文），对比两个工具在处理栏目顺序上的差异
- [ ] 尝试解析一份扫描件 PDF，验证 pdfplumber 提取为空，Docling（或配合 OCR）是否能提取出文字
- [ ] 记录至少一个 Docling 也处理失败或效果不佳的场景，分析失败根因（复杂排版/纯图片/加密/手写）

**产出标准**：一份工具对比记录，说明 pdfplumber 和 Docling 在表格抽取上的准确率差异，以及 Docling 处理不了的边界情况和各自的失败根因。

---

## 九、下一步预告

Day 66 是**阶段项目整合（RAG 深化版）**：把 Day 58–65 这两周的全部 RAG 优化能力——混合检索、Reranker、HyDE、查询改写、RAGAS 评估体系、评估集持续回归、文档解析进阶——整合进 Day 20 的带引用 RAG 系统，并引入 **Agentic RAG** 模式：把检索嵌入 LangGraph 图，让 Agent 自主判断"是否需要检索、检索结果够不够好、要不要换个查询词重试"，而不是每次都固定触发一次检索。
