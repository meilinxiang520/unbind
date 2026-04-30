# unbind

**把任何文档变成自由的知识。** 一份文件进来，两条路出去：Markdown（喂给 AI 分析）或 EPUB（自己深读细品）。

PDF、Word、PPT、网页、CSV…扔进去，自动识别格式，高质量输出。

---

## 它能做什么

| 场景 | 命令 |
|------|------|
| 把 PDF 论文转成 EPUB，在电纸书上读 | `unbind bind paper.pdf` |
| 把 Word 合同转 EPUB，手机随时翻 | `unbind bind contract.docx` |
| 把 PPT 演讲稿转 Markdown，发给 AI 润色 | `unbind extract slides.pptx` |
| 把网页文章存成 EPUB 离线读 | `unbind bind https://example.com/essay` |
| 把 CSV 数据转 Markdown，粘贴给 AI 分析 | `unbind extract data.csv` |
| 从终端直接写内容，生成 EPUB | `echo "# 笔记" \| unbind bind -` |

---

## 安装指南

### 第一步：确认你有 Python

打开终端（Terminal），输入：

```bash
python3 --version
```

如果显示 `Python 3.10` 或更高版本，继续下一步。如果低于 3.10，先从 [python.org](https://www.python.org/downloads/) 安装最新版。

> **macOS 用户**：系统自带的 Python 版本较老，建议用 Homebrew 安装：
> ```bash
> brew install python@3.12
> ```

### 第二步：安装 unbind

```bash
pip install unbind
```

如果你没有 `pip`，试试：

```bash
pip3 install unbind
```

如果还不行（macOS 常见），用：

```bash
pip3 install --user unbind
```

安装完成后验证：

```bash
unbind --help
```

看到命令帮助就说明安装成功了。

### 第三步（可选）：安装 PDF 支持

要把 PDF 转成高质量 EPUB，需要额外安装 AI 引擎：

```bash
pip install unbind[pdf]
```

装完会自动下载 AI 模型（约 1.5GB），只下载一次。如果网速较慢，耐心等几分钟。

> 不装 `[pdf]` 的话，Word、PPT、网页、CSV 等其他格式都能正常用，只有 PDF 不支持。

---

## 使用指南

`unbind` 就两个命令：

- `unbind extract` — 提取内容，输出 Markdown（喂 AI）
- `unbind bind` — 打包成 EPUB（人读）

### 例子一：把 PDF 转成 EPUB

```bash
unbind bind 我的论文.pdf
```

运行完会生成 `我的论文.epub`，双击用 Apple Books 打开就能读。

指定书名和作者：

```bash
unbind bind 我的论文.pdf -o 论文.epub --title "我的博士论文" --author "张三"
```

### 例子二：把 Word 文档转成 Markdown

```bash
unbind extract 合同.docx -o ./output
```

会在 `./output/` 目录下生成 `合同.md`，可以直接复制粘贴给 ChatGPT 或 Claude。

### 例子三：把网页文章存成电子书

```bash
unbind bind https://zh.wikipedia.org/wiki/EPUB -o epub介绍.epub
```

### 例子四：管道输入

```bash
cat 笔记.txt | unbind bind - --title "我的读书笔记"
```

---

## 支持格式

| 格式 | 输入 → Markdown | 输入 → EPUB | 使用的引擎 |
|------|:---:|:---:|---|
| PDF | ✅ | ✅ | marker-pdf（AI 识别版面） |
| DOCX / DOC | ✅ | ✅ | markitdown |
| PPTX / PPT | ✅ | ✅ | markitdown |
| XLSX / XLS | ✅ | ✅ | markitdown |
| HTML | ✅ | ✅ | markitdown |
| EPUB | ✅ | ✅ | markitdown |
| CSV | ✅ | ✅ | markitdown |
| Markdown / TXT | ✅ | ✅ | 内置 |
| JSON | ✅ | ✅ | markitdown |
| RSS | ✅ | ✅ | markitdown |
| 图片（OCR 描述） | ✅ | ❌ | markitdown + LLM |
| 音频（转文字） | ✅ | ❌ | markitdown |
| ZIP（递归解压） | ✅ | ❌ | markitdown |
| Wikipedia URL | ✅ | ✅ | markitdown |
| YouTube URL | ✅ | ✅ | markitdown |

---

## 常见问题

### Q: 转换 PDF 时报错 "No module named marker"

没装 PDF 支持。运行：
```bash
pip install unbind[pdf]
```

### Q: 第一次转 PDF 等了很久

正常。首次运行要下载 AI 模型（1.5GB），之后就是秒级处理。

### Q: EPUB 在 Apple Books 里显示乱码

试试用 `--language` 指定语言：
```bash
unbind bind book.pdf --language zh
```

### Q: 报错 "unbind: command not found"

Python 的 bin 目录不在 PATH 里。试试：
```bash
python3 -m unbind bind book.pdf
```

或者重新安装，安装完成后看终端输出的提示，把提示的路径加到 `~/.zshrc` 里。

### Q: 能把 EPUB 转回 PDF 吗？

不能。unbind 的方向是「任何格式 → EPUB/Markdown」，反方向暂时不支持。

---

## 开发

```bash
git clone https://github.com/zhouxia/unbind.git
cd unbind
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,pdf]"
```

运行测试：
```bash
python3 -m pytest
```
