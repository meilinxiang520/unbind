# unbind 项目复盘

## 一句话总结

用 markitdown 的架构 + marker-pdf 的品质 + EPUB 3.0 的打包，三天从零到 PyPI 发布一个万能文档转换工具。

---

## 阶段一：灵感 — 发现需求缝隙

### 触发点

手里有两个工具：
- **pdf2epub**：PDF → EPUB，质量很高（marker-pdf AI 引擎），但只支持 PDF
- **markitdown**：什么格式都能转 Markdown，但质量一般（PDF 用的 pdfminer），而且只能出 MD

### 关键洞察

markitdown 的**架构**是黄金标准（Converter Registry + Stream I/O），pdf2epub 的**EPUB 打包**是钻石品质。markitdown 没有 EPUB 输出，pdf2epub 没有多格式输入。

**合在一起 = 一个工具，任何格式入，两条路出（Markdown 喂 AI，EPUB 人读）**

### 可复用方法论

> 看到两个互补工具时，不要想"用哪个"，要问"它们的接口能对接吗？"
> 核心洞察往往在二者**数据结构的交点**上。

---

## 阶段二：架构设计 — 站在巨人肩膀上

### 不做的事（同样重要）

| 不做 | 原因 |
|------|------|
| 自己写 DOCX/PPTX/HTML 转换 | markitdown 已经做好了，代理即可 |
| 自己写 PDF 解析 | marker-pdf 的 AI 引擎无人能敌 |
| 自己写 EPUB 规范 | pdf2epub 已验证的方案直接迁移 |
| PDF 的 pdfminer 降级路径 | 质量优先，不提供次选方案 |

### 核心架构

```
CLI (extract / bind)
    └── Engine (Converter Registry)
        ├── PdfConverter (marker-pdf, priority 0.0)
        ├── DelegatingConverter (markitdown, priority 1.0)
        └── PlainTextConverter (内置, priority 10.0)
                │
                ▼
        ConverterResult(markdown + images + title)
                │
                ▼
        EPUB Packager (Markdown → EPUB 3.0, MathML, 图片优化)
```

### 可复用方法论

> 三个问题决定架构：
> 1. 哪些是已有工具做得比我好的？→ 直接代理
> 2. 哪些是已有工具做不到的？→ 自己写
> 3. 哪些是用户不关心的？→ 不提供选项

---

## 阶段三：实现 — 数据流优先

### 开发顺序

1. 骨架：pyproject.toml + 空模块
2. 抽象层：ConverterResult, Converter, StreamInfo
3. 引擎：registry + 路由 + 双输出 API
4. 转换器：PDF（最复杂）→ Delegating（最宽）→ Text（兜底）
5. 打包器：EPUB 3.0
6. CLI：extract / bind 两个命令
7. 测试：真实文档端到端

### 关键踩坑

| 问题 | 根因 | 解法 |
|------|------|------|
| PlainTextConverter 不接收 stdin | StreamInfo 无 ext 无 mime 时谁都不接受 | 最后兜底：ext 和 mime 都为空 → 当文本处理 |
| marker-pdf 要文件路径 | 内部全用 BinaryIO | 临时文件过渡（`tempfile.NamedTemporaryFile`） |
| uv 创建的 venv 没有 pip | uv 最小化设计 | 用 `uv pip install` 代替 `pip install` |
| 系统 Python 3.9 太老 | macOS 自带 | `brew install python@3.12` + uv 管理 venv |

### 可复用方法论

> 数据流先于界面。内部统一用 stream（BinaryIO），CLI 层做 path/url/stdin 适配。
> 开发顺序：数据模型 → 引擎 → 转换器 → 打包 → CLI。不要先写 CLI 再补逻辑。

---

## 阶段四：GitHub 发布 — 让别人找到你

### 清单（按顺序）

```
☑ .gitignore          # 排除 venv, __pycache__, .DS_Store
☑ README.md           # 小白能照着操作的指南
☑ LICENSE             # MIT（开源信任门槛最低）
☑ git init + commit
☑ gh repo create --public
☑ 填写 repo description（一句话说清做什么）
☑ 添加 topics（搜索关键词：python, epub, markdown, pdf-converter...）
☑ git tag v0.1.0
☑ gh release create  # 带 Release Notes
```

### GitHub About 区域必填三项

| 字段 | 效果 |
|------|------|
| Description | 搜索结果里直接展示，60 字以内 |
| Website | 指向 README 或文档站 |
| Topics | 决定搜索排名，上限 20 个 |

### 可复用方法论

> GitHub 页面就是你的产品首页。description 是广告语，topics 是 SEO，README 是说明书。
> 三者缺一不可。缺了 = 别人搜不到，搜到了也不知道是干什么的。

---

## 阶段五：PyPI 发布 — 让用户一键安装

### 流程

```bash
python3 -m build          # 构建 whl + tar.gz
twine upload dist/*       # 上传到 PyPI
```

### 前提条件

- pyproject.toml 配好：name, version, description, dependencies, scripts
- PyPI 账号 + API token（在 pypi.org/manage/account/token/ 创建）
- twine 用 `__token__` 作为用户名，token 作为密码

### 可复用方法论

> `pip install` 是 Python 工具的终极分发方式。
> README 里的安装指令应该在发布前就能用——所以先发 PyPI，再推广。
> API token 比密码安全，可以随时吊销。

---

## 阶段六：复盘 — 下次做工具的流程模板

### 通用流程（不限于 Python）

```
Week 1: Research → 找出已有方案的交集和缝隙
Day 1-2: Architecture → 数据模型 + 接口设计
Day 3-5: Implementation → 核心功能 + CLI
Day 6: Package → 构建 + 依赖管理
Day 7: Publish → GitHub + 包管理器 + 推广
```

### 从命令行工具到赚钱的 App

unbind 是 CLI 工具。要走 App Store / Google Play，需要加一层：

| 层 | CLI 工具 | App |
|----|---------|------|
| 用户界面 | 终端命令 | GUI（按钮、拖拽、预览） |
| 打包 | pip/wheel | .app (macOS) / .apk (Android) |
| 分发 | PyPI | App Store / Google Play |
| 付费 | 不易 | IAP / 订阅 / 买断 |
| 信任门槛 | GitHub stars | App Store 审核徽章 |

**unbind → App 的路径**：
- macOS：Electron 壳 + unbind Python 后端 → .app → Developer Program($99/年) → Mac App Store
- iOS/Android：unbind 做云端转换服务（FastAPI），App 做上传/预览/下载客户端
- 付费模型：免费转 3 次，订阅无限转，或按次付费

### 下次可以复用的东西

1. **架构模式**：Converter Registry + Stream I/O，几乎任何格式转换工具都能用
2. **EPUB 打包器**：`packagers/_epub.py` 已经独立，任何 Markdown 都能喂进去
3. **PyPI 发布流程**：build + twine + token，20 分钟搞定
4. **GitHub 发布清单**：上面的 checklist 直接搬
5. **README 模板**：安装三步走（检查环境 → 安装 → 验证），示例驱动，FAQ 收尾

---

## 最终状态

| 渠道 | 地址 |
|------|------|
| GitHub | https://github.com/meilinxiang520/unbind |
| PyPI | https://pypi.org/project/unbind/0.1.0/ |
| 安装 | `pip install unbind` |
| 协议 | MIT |

---

*2026-05-28*
