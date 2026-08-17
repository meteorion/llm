# Day 16：读取本地文档

> 学习目标：掌握从本地文件读取文本内容的完整方案——支持 `txt`、`md`、`pdf` 三种格式，处理编码问题，并封装成一个统一的文档加载器接口，直接对接 Day 15 的切分 + 向量化流程
>
> 📚 所属阶段：**第二阶段 · RAG 核心应用架构**（见 [`plan.md`](../规划文档/plan.md)）｜ 配套：[30 天路线](../规划文档/llm_app_30_day_roadmap.md) · Day 16
>
> 🧭 导航：[← Day 15 · RAG 基本原理](day15_rag_from_scratch.md) [→ Day 17 · 文本切分](day17_text_chunking.md)

---

## 目录

- [一、为什么文档读取不是"小问题"](#一为什么文档读取不是小问题)
  - [1.1 RAG 流程中的位置](#11-rag-流程中的位置)
  - [1.2 三种格式的难度层级](#12-三种格式的难度层级)
- [二、读取 TXT 和 MD 文件](#二读取-txt-和-md-文件)
  - [2.1 基础读取与编码问题](#21-基础读取与编码问题)
  - [2.2 编码自动检测](#22-编码自动检测)
  - [2.3 MD 文件的特殊处理](#23-md-文件的特殊处理)
- [三、读取 PDF 文件](#三读取-pdf-文件)
  - [3.1 为什么 PDF 比 TXT 难](#31-为什么-pdf-比-txt-难)
  - [3.2 用 pdfplumber 提取文本](#32-用-pdfplumber-提取文本)
  - [3.3 常见 PDF 坑与处理方法](#33-常见-pdf-坑与处理方法)
- [四、文本清洗与规范化](#四文本清洗与规范化)
  - [4.1 为什么原始文本需要清洗](#41-为什么原始文本需要清洗)
  - [4.2 常见清洗操作](#42-常见清洗操作)
- [五、统一文档加载器](#五统一文档加载器)
  - [5.1 接口设计原则](#51-接口设计原则)
  - [5.2 完整实现](#52-完整实现)
  - [5.3 与 Day 15 RAG 流程对接](#53-与-day-15-rag-流程对接)
- [六、Day 16 知识速查](#六day-16-知识速查)
- [七、实践任务](#七实践任务)
- [八、下一步预告](#八下一步预告)

---

## 一、为什么文档读取不是"小问题"

### 1.1 RAG 流程中的位置

文档读取是整个 RAG 系统的入口，决定了后续所有环节的数据质量：

```
原始文件（PDF/TXT/MD）
        ↓  ← Day 16：文档读取（质量决定一切）
原始文本字符串
        ↓  ← Day 17：文本切分
Chunk 列表
        ↓  ← Day 18：Embedding 向量化
向量 + 文本存入数据库
        ↓  ← Day 19/20：检索 + 生成回答
```

"垃圾进，垃圾出"——如果读取阶段引入了乱码、多余空白、页眉页脚噪音，后续的切分和向量化都会受到污染，最终的回答质量也会降低。文档读取看起来简单，但处理好细节需要专注。

### 1.2 三种格式的难度层级

```
难度：TXT ──────────── MD ──────────────── PDF
     │                │                    │
     最简单            中等                  最难
     纯文本，          Markdown 标记         二进制格式，
     Python 内置       需要决定是否保留标记   需要第三方库，
     open() 即可       通常直接读原始文本     有多种坑
```

**推荐学习顺序**：先搞定 TXT/MD（今天就能完整跑通），再处理 PDF（积累坑点经验），不要一开始就死磕扫描件 OCR（那是 Day 16 之后的进阶内容）。

---

## 二、读取 TXT 和 MD 文件

### 2.1 基础读取与编码问题

Python 的 `open()` 内置函数读 TXT 已经够用，但**编码**是最常见的坑：

```python
# 错误做法：不指定编码，依赖系统默认
with open("doc.txt") as f:
    text = f.read()
# Windows 默认 GBK，macOS/Linux 默认 UTF-8
# 同一份文件在不同系统上可能产生乱码

# 正确做法：明确指定 UTF-8
with open("doc.txt", encoding="utf-8") as f:
    text = f.read()

# 如果文件是 GBK 编码（常见于 Windows 下创建的中文文件）
with open("doc.txt", encoding="gbk") as f:
    text = f.read()
```

**编码错误时的处理策略**：

```python
# 策略 1：忽略无法解码的字节（可能丢失部分字符）
with open("doc.txt", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# 策略 2：用替换字符代替无法解码的字节（保留结构，有乱码标记）
with open("doc.txt", encoding="utf-8", errors="replace") as f:
    text = f.read()

# 策略 3：先尝试 UTF-8，失败再尝试 GBK（适合中文文件）
def read_text_safe(path: str) -> str:
    for encoding in ("utf-8", "gbk", "utf-8-sig"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法解码文件：{path}，请手动指定编码")
```

**`utf-8-sig` 是什么**：Windows 上的记事本保存 UTF-8 文件时会在文件开头加一个 BOM（字节顺序标记，`﻿`），`utf-8-sig` 会自动去掉这个 BOM。如果读出来的文本开头有奇怪字符，通常就是这个原因。

### 2.2 编码自动检测

当不知道文件编码时，`chardet` 库可以自动检测：

```bash
pip install chardet
```

```python
import chardet

def detect_encoding(path: str) -> str:
    with open(path, "rb") as f:          # 以二进制模式读取
        raw = f.read(10_000)             # 只读前 10KB，通常足够判断编码
    result = chardet.detect(raw)
    return result["encoding"] or "utf-8"


def read_with_detection(path: str) -> str:
    encoding = detect_encoding(path)
    with open(path, encoding=encoding, errors="replace") as f:
        return f.read()
```

**何时用自动检测**：自动检测有一定误判率，优先顺序建议是：
1. 文件来源明确知道编码 → 直接指定
2. 中文文件 → 先试 UTF-8，失败再试 GBK
3. 来源不明的混杂文件 → 用 `chardet` 检测

### 2.3 MD 文件的特殊处理

Markdown 文件本质是纯文本，用 `open()` 直接读取即可——但要决定是否保留 Markdown 语法标记：

```
保留标记（不做处理）：

  # 第一章：产品介绍
  产品 **特点** 包括：
  - 功能 A
  - 功能 B

去除标记（清洗后）：

  第一章：产品介绍
  产品 特点 包括：
  功能 A
  功能 B
```

**RAG 场景的建议**：直接保留 Markdown 标记，不必额外去除。原因：
- 大模型理解 Markdown 语法，`# 标题` 和 `**加粗**` 不影响语义理解
- 去除标记的正则表达式容易误伤正文内容（如代码块里的 `*` 号）
- 如果确实需要去除，用专门的库（如 `markdownify` 或 `markdown-it-py`）比手写正则更可靠

```python
def read_md(path: str) -> str:
    return read_text_safe(path)   # 直接复用 TXT 读取，不做额外处理
```

---

## 三、读取 PDF 文件

### 3.1 为什么 PDF 比 TXT 难

```
┌──────────────────────────────────────────────────────────────────────┐
│                   PDF 的本质：不是文本格式                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  TXT 文件：字节直接对应字符，`open()` 就能读出纯文本                    │
│                                                                       │
│  PDF 文件：存储的是"在哪个坐标画什么字形"的绘图指令                      │
│  → 字符顺序不等于阅读顺序（排版软件按视觉位置存储）                      │
│  → 文字可能是图片（扫描件），没有可提取的文本层                          │
│  → 表格、多栏布局、页眉页脚都混在一起，需要特殊处理                      │
│                                                                       │
│  所以 PDF 文本提取本质上是"逆向工程"，而不是简单的解码                   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

**常用 PDF 处理库对比**：

| 库 | 优点 | 缺点 | 适合场景 |
|----|------|------|---------|
| `PyPDF2` | 轻量，纯 Python | 复杂排版提取质量差 | 简单双栏以内的文档 |
| `pdfplumber` | 表格提取好，可获取位置信息 | 速度稍慢 | **推荐，适合大多数场景** |
| `pymupdf`（fitz） | 速度快，提取质量高 | 有商业许可证限制 | 需要高性能的场景 |
| `unstructured` | 支持多种格式，处理能力强 | 依赖多，安装复杂 | 生产级 RAG 系统 |

Day 16 推荐使用 `pdfplumber`——安装简单，中文支持好，提取质量在免费库里较好。

### 3.2 用 pdfplumber 提取文本

```bash
pip install pdfplumber
```

```python
import pdfplumber

def read_pdf(path: str) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:                         # 扫描件的页面 extract_text() 返回 None
                pages.append(text)
    return "\n\n".join(pages)               # 每页之间用双换行分隔，保留页面边界信息
```

**逐页提取而非一次提取整个文档**，原因：
1. 可以记录每段文字来自哪一页（后续 Day 20 加引用时需要）
2. 某些页面可能是图片（无文本），逐页处理可以跳过，而不是让整个提取失败

### 3.3 常见 PDF 坑与处理方法

**坑 1：提取出来的文本有乱码或方块字**

```
原因：PDF 内嵌字体的 Unicode 映射表不完整（常见于国内 PDF 生成工具）
处理：换用 pymupdf（fitz），它有更强的字体处理能力；或者接受部分字符丢失
```

**坑 2：多栏布局文字顺序错乱**

```
原因：PDF 按视觉坐标存储，pdfplumber 默认按从上到下顺序读取，
      两栏排版会变成"左栏第 1 行 + 右栏第 1 行 + 左栏第 2 行..."

处理：pdfplumber 支持 crop() 方法按区域提取，
      可以分别提取左右两栏再拼接（比较复杂，通用方案建议换 pymupdf）
```

**坑 3：页眉页脚混入正文**

```
原因：页眉页脚和正文没有语义分隔符，提取时全部混在一起

处理：最简单的方案是 crop 裁剪，去除顶部和底部固定高度的区域
```

```python
def read_pdf_with_crop(path: str, margin_top: float = 50, margin_bottom: float = 50) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            bbox = (0, margin_top, page.width, page.height - margin_bottom)
            cropped = page.crop(bbox)
            text = cropped.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)
```

**坑 4：扫描件（图片 PDF）**

```
原因：整个 PDF 是图片扫描，没有文本层，extract_text() 返回空字符串或 None

处理：需要 OCR（光学字符识别），常用工具：
  - pytesseract（开源，需安装 Tesseract 引擎）
  - 商业 OCR API（百度 OCR、腾讯 OCR 等）
  
Day 16 不处理扫描件，先跳过（函数里检测到 None 则跳过该页）
```

---

## 四、文本清洗与规范化

### 4.1 为什么原始文本需要清洗

不同来源的文档读取后，文本质量参差不齐：

```
原始 PDF 提取文本的典型噪音：

  "第  1  章   产品介绍"    ← 多余空格（PDF 坐标还原时的间距问题）
  "\n\n\n\n"               ← 连续多个空行
  "©2024 Company Inc."     ← 页脚版权信息
  "- 1 -"                  ← 页码
  "continued from page 3"  ← 接续标注
  "图 3-1：产品架构图\n"    ← 图注（没有图片内容，图注单独出现）
```

### 4.2 常见清洗操作

```python
import re


def clean_text(text: str) -> str:
    # 1. 统一换行符（Windows \r\n → \n）
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. 去除连续多个空行（保留最多一个空行）
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 3. 去除行内多余空格（多个连续空格 → 一个）
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 4. 去除每行首尾空白
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # 5. 去掉全空白行后的连续空行（再次压缩）
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
```

**清洗的边界**：只去除明确的"噪音"（多余空白、控制字符），不要做语义层面的修改（不要去停用词、不要做词干化）——那是 NLP 任务的预处理，不是 RAG 的文档加载阶段应该做的。清洗过度反而会破坏 Embedding 模型依赖的上下文信息。

---

## 五、统一文档加载器

### 5.1 接口设计原则

```
设计目标：调用方不需要关心文件格式，只传入文件路径，
          得到统一格式的文档对象

理想接口：
  loader.load("report.pdf")   → Document(text="...", source="report.pdf", pages=12)
  loader.load("notes.txt")    → Document(text="...", source="notes.txt", pages=1)
  loader.load("readme.md")    → Document(text="...", source="readme.md", pages=1)
  loader.load_directory("./docs/")  → [Document, Document, ...]
```

**为什么用 `dataclass` 而不是直接返回字符串**：
- 后续 Day 20 加引用时需要 `source`（哪个文件）
- 后续可扩展 `metadata`（文件大小、修改时间、页数）
- 统一格式让切分模块的接口保持稳定

### 5.2 完整实现

```python
"""
day16_document_loader.py — 统一文档加载器

支持：TXT、MD、PDF
依赖：pip install pdfplumber chardet
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import chardet
import pdfplumber


@dataclass
class Document:
    text: str
    source: str
    file_type: str
    page_count: int = 1
    metadata: dict = field(default_factory=dict)


def _detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read(10_000)
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def _read_text_safe(path: str) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    encoding = _detect_encoding(path)
    with open(path, encoding=encoding, errors="replace") as f:
        return f.read()


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _load_txt(path: str) -> Document:
    raw = _read_text_safe(path)
    return Document(text=_clean_text(raw), source=path, file_type="txt")


def _load_md(path: str) -> Document:
    raw = _read_text_safe(path)
    return Document(text=_clean_text(raw), source=path, file_type="md")


def _load_pdf(path: str) -> Document:
    pages_text = []
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    if not pages_text:
        raise ValueError(f"PDF 无法提取文本（可能是扫描件）：{path}")

    combined = "\n\n".join(pages_text)
    return Document(
        text=_clean_text(combined),
        source=path,
        file_type="pdf",
        page_count=page_count,
    )


LOADERS = {
    ".txt": _load_txt,
    ".md": _load_md,
    ".markdown": _load_md,
    ".pdf": _load_pdf,
}


def load_document(path: str) -> Document:
    ext = Path(path).suffix.lower()
    loader = LOADERS.get(ext)
    if loader is None:
        raise ValueError(f"不支持的文件格式：{ext}（支持：{list(LOADERS)}）")
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在：{path}")
    return loader(path)


def load_directory(
    dir_path: str,
    extensions: list[str] | None = None,
    recursive: bool = False,
) -> list[Document]:
    exts = extensions or list(LOADERS.keys())
    pattern = "**/*" if recursive else "*"
    docs, errors = [], []

    for ext in exts:
        for file_path in Path(dir_path).glob(f"{pattern}{ext}"):
            try:
                docs.append(load_document(str(file_path)))
            except Exception as e:
                errors.append((str(file_path), str(e)))

    if errors:
        for path, err in errors:
            print(f"[跳过] {path}：{err}")

    return docs
```

### 5.3 与 Day 15 RAG 流程对接

把 Day 15 的向量索引入口从"硬编码字符串列表"改为"文档加载器输出"：

```python
from day15_rag_from_scratch import build_index, answer_with_rag
from day16_document_loader import load_directory

if __name__ == "__main__":
    # Day 15：知识库是硬编码字符串
    # documents = ["退款政策：...", "配送说明：..."]

    # Day 16：从真实文件读取
    docs = load_directory("./知识库/", extensions=[".txt", ".md", ".pdf"])
    documents = [doc.text for doc in docs]
    print(f"加载了 {len(documents)} 份文档")

    print("正在构建向量索引...")
    index = build_index(documents)
    print(f"索引完成：{len(index['chunks'])} 个 Chunk")

    result = answer_with_rag("退款需要多少天？", index)
    print(result["answer"])
```

---

## 六、Day 16 知识速查

### 格式支持速查

| 格式 | 读取方式 | 主要坑 | 推荐处理 |
|------|---------|--------|---------|
| TXT | `open()` 内置 | 编码（UTF-8 vs GBK vs BOM） | 尝试列表 + chardet 兜底 |
| MD | 同 TXT | 通常无坑 | 直接读，不用去除 Markdown 标记 |
| PDF | `pdfplumber` | 乱码 / 多栏乱序 / 扫描件 / 页眉页脚 | `extract_text()` + crop 去边距 |

### 编码处理速查

```python
# 优先尝试顺序（中文文档）
for enc in ("utf-8", "utf-8-sig", "gbk"):
    try: return open(path, encoding=enc).read()
    except UnicodeDecodeError: continue
# 最后用 chardet 检测
```

### 最小代码模板

```python
from pathlib import Path
import pdfplumber

def load_document(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in (".txt", ".md"):
        for enc in ("utf-8", "utf-8-sig", "gbk"):
            try:
                return open(path, encoding=enc).read()
            except UnicodeDecodeError:
                continue
    elif ext == ".pdf":
        pages = []
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    pages.append(t)
        return "\n\n".join(pages)
    raise ValueError(f"不支持的格式：{ext}")
```

---

## 七、实践任务

- [ ] 创建一个 `知识库/` 目录，放入至少 2 个 `.txt` 或 `.md` 文件（内容随意，比如前几天笔记的摘录）
- [ ] 运行 `day16_document_loader.py`，用 `load_directory()` 读取这些文件，打印每份文档的文本长度
- [ ] 找一份 PDF 文件（任何中文 PDF），用 `load_document()` 读取，检查提取的文本质量
- [ ] 在读取后对文本应用 `_clean_text()`，对比清洗前后的差异（重点看多余空行和空格是否被处理）
- [ ] 把加载器接入 Day 15 的 RAG demo，替换掉硬编码的知识库字符串，用真实文件问答

**产出标准**：

- `load_document()` 能成功读取 TXT / MD / PDF 三种格式，输出 `Document` 对象
- 至少完成一次"读取本地文件 → RAG 问答"的完整链路

---

## 八、下一步预告

**Day 17：文本切分**

Day 16 的文档加载器输出的是一整段原始文本，Day 17 要把它切分成适合向量化的 Chunk：

- Day 15 实现的 `chunk_text()` 只是按词数切分，没有考虑语义边界
- Day 17 会实现更智能的切分策略：按段落/章节切分、按句子边界切分、递归切分
- 核心问题：如何在"切分足够小（检索精准）"和"保留足够上下文（模型能完整回答）"之间找平衡
- 配套的实验：不同切分策略对同一问题的检索质量对比
