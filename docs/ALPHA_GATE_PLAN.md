# MetaOS Alpha 带闸门执行计划

本文档把 Alpha 计划固化为可执行的阶段闸门。书籍材料由用户入库，系统依赖软件由用户安装；Codex 负责在每个阶段开始前检查完成度，并给出缺口、原因和修复命令。

## 执行规则

- 每进入下一阶段前，先运行闸门检查。
- 如果上一阶段没有完成，必须报告：
  - 哪本书或哪类材料没有入库。
  - 哪个软件没有安装。
  - 哪个软件版本不符合要求。
  - 应执行的动作或命令。
- 书籍入库不以全文数量为指标，而以 `BookProfile`、结构化读书卡、机制卡为指标。
- 视频脚本中的事实性陈述优先引用当日日志、Git commit、文档和人工输入；书籍只作为解释框架。

## 检查命令

从仓库根目录运行：

```powershell
.\.venv311\Scripts\python.exe -m metaos.alpha.gate_check --stage 0
```

后续阶段把 `--stage` 改成 `1`、`2-3`、`4-5`、`6-7`、`8-9`、`10`、`11` 或 `12`。

需要机器可读输出时：

```powershell
.\.venv311\Scripts\python.exe -m metaos.alpha.gate_check --stage 4-5 --json
```

入库模板：

- 核心书 `BookProfile`：`docs/templates/BOOK_PROFILE_TEMPLATE.md`
- 个人材料：`docs/templates/PERSONAL_MATERIAL_TEMPLATE.md`

## 阶段闸门

### 第 0 周：环境准备

必须满足：

- Python 3.11 可用。
- Git 可用。
- Docker Desktop 可用。
- Redis 7 可从 `localhost:6379` 访问，推荐 Docker 容器。
- Ollama 可用，且已拉取 `bge-m3`。
- `.venv311` 能通过核心包检查。
- `.venv_ocr` 能通过 OCR 包检查。

如果 Redis 未运行但 Docker 可用，执行：

```powershell
docker run -d --name metaos-redis -p 6379:6379 redis:7
```

### 第 1 周：核心书库地图

必须完成 32 本核心书的 `BookProfile`。每本至少包含：

```text
这本书在回答什么问题
对 MetaOS 的作用
它应该转化成 MetaOS 的什么机制
```

不要求全文入库。

Profile 工作区：

```text
library/00_metaos/core_books/book_profiles/
```

执行方式：

1. 打开对应书籍的 `.md` 文件。
2. 删除 `TODO` 占位文字。
3. 用自己的判断补齐三个章节，且每个章节都要有实质内容：
   - `这本书在回答什么问题`
   - `对 MetaOS 的作用`
   - `它应该转化成 MetaOS 的什么机制`
4. 运行检查：

```powershell
.\.venv311\Scripts\python.exe -m metaos.alpha.gate_check --stage 1
```

检查结果含义：

- `BookProfile files` 失败：对应书籍的 Profile 文件还没创建。
- `Core BookProfiles` 失败：文件存在，但仍有 `TODO`、字段缺失或内容过短。
- `Book retrievability` 警告：Profile 已填写，但还没有通过 MetaOS 入库生成 chunks，因此 RAG 暂时检索不到。

让 RAG 可检索：

1. 启动 Redis、MetaOS app 和 worker。
2. 在 Streamlit 上传已填写的 BookProfile Markdown，或使用现有文档入库接口提交文件。
3. 等待入库任务生成知识条目和 chunks。
4. 对对应知识条目执行索引，或重建全部索引。
5. 重新运行 Stage 1 检查，直到 `Book retrievability` 不再列出已填写但未入库的书。

### 第 2-3 周：每日认知账本

必须优先入库个人材料，包括：

- 每日工作记录。
- MetaOS 开发日志。
- 重要决策及理由。
- 注意力漂移记录。
- 专家建议。
- 项目失败和复盘。
- 知道但未执行的事项。

早期知识库中，个人材料文件占比应达到 40%。

### 第 4-5 周：视频生成 Alpha

视频阶段前必须安装：

- Node 24 LTS，或至少 Node 22 LTS。
- pnpm。
- FFmpeg。
- Remotion。
- React。
- TypeScript。

优先入库公开视频闭环相关书：

- 《娱乐至死》
- 《浅薄》
- 《注意力商人》
- 《Stand Out of Our Light》
- 《系统之美》
- 《清单革命》

### 第 6-7 周：意图与注意力闭环

优先入库：

- 《论语》
- 《庄子》
- 《传习录》
- 《道德经》
- 《鬼谷子》
- 《黄帝内经》
- 《黄帝四经》
- 《阴符经》
- 《易经》
- 《资治通鉴》
- 《理想国》
- 《尼各马可伦理学》

这些材料应转化为机制卡：什么值得注意、哪些决定保留给用户、系统何时保持沉默、如何处理“知道但未执行”。

### 第 8-9 周：知识库与个人记忆

优先入库：

- 《心理学原理》注意/习惯章节
- 《Know Thyself》
- 《Rationality and the Reflective Mind》
- 《The Distracted Mind》
- 《人有人的用处》
- 《人工科学》
- 《国家的视角》

每本至少形成观点卡、证据卡、反证卡、行动规则、产品设计启示。

### 第 10 周：六部有限呈报

优先入库：

- 《好战略，坏战略》
- 《目标》
- 《高产出管理》

每条外部信息推荐必须有理由、目标关联、阅读时间、不读损失、建议行动和有效期限。

### 第 11 周：宰相 Alpha

优先入库：

- 《谈美》
- 《美学散步》
- 《人间词话》
- 《为什么读经典》

这些材料只用于精神恢复、表达训练和审美陪伴，不用于无限内容推荐。

### 第 12 周：封闭测试

必须满足：

- 32 本核心书都有 `BookProfile`。
- 至少 12 本有完整六段结构化读书卡。
- 至少 6 本已转化为 MetaOS 机制卡。
- 30 天真实数据可回放。
- 20 条以上视频生成记录可检查。

## 推荐修复命令

安装 pnpm：

```powershell
corepack enable
corepack prepare pnpm@latest --activate
pnpm --version
```

如果 `corepack` 不可用：

```powershell
npm install -g pnpm
pnpm --version
```

确认 FFmpeg：

```powershell
ffmpeg -version
```

确认 Node：

```powershell
node --version
npm --version
```

拉取 embedding 模型：

```powershell
ollama pull bge-m3
ollama list
```
