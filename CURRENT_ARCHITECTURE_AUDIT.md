# MetaOS Alpha 当前架构审计

审计日期：2026-06-15  
审计范围：仅审计现有仓库、运行目录、测试与阶段0设计缺口，不修改业务代码。  
结论：当前仓库已经具备 MetaOS Lite 的本地知识入库、Chunk、Chroma 向量检索、单轮 RAG、Redis/RQ Worker、FastAPI 和 Streamlit 基座，但尚未具备 MetaOS Alpha 的意图约束、议题编译、证据矩阵、反证审计、行动闭环、日报复盘和视频闭环。

## 当前仓库形态

仓库根目录当前包含：

- `metaos/`：Python 模块化单体。
- `test/`：现有自动化测试。
- `scripts/`：本地 Redis、App、Worker、OCR Worker 启停脚本。
- `docs/`：已有阶段门禁计划与模板。
- `library/`：运行态本地知识库、原始文件、Markdown、Chroma 索引、SQLite 数据库。
- `.venv311/`、`.venv_ocr/`、`.venv_ocr_gpu/`：本地运行环境。
- 若干根目录 PDF 与爬虫脚本，仍属于历史输入或实验资产。

当前 Git 状态：只有 `.vscode/` 为未跟踪项，本阶段不处理。

## 已有模块审计

### `metaos.core`

已实现：

- `Settings` 读取本地配置。
- `Source`、`Asset`、`Citation`、`KnowledgeItem`、`Chunk`、`Job` 等 Pydantic Schema。
- 基础错误类型与事件模型。

缺口：

- 没有 `CognitiveConstitution`、`Intent`、`CurrentRole`、`AttentionBudget`、`NotToDoItem`。
- 没有 `ResearchTask`、`ThemeSpec`、`EvidenceRequirement`、`ResearchPlan`。
- 没有结构化研究输出、判断分类、行动和复盘 Schema。
- 现有中文字符串在部分文件读取时显示为 mojibake，说明历史写入或终端编码链路需要单独处理。

### `metaos.workspace`

已实现：

- 本地目录约定与 `library/metaos.sqlite3` 初始化。
- SQLite 表：`jobs`、`sources`、`assets`、`knowledge_items`、`chunks`。
- Repository：Source、Asset、KnowledgeItem、Chunk、Job。

缺口：

- 没有 Alembic 迁移机制。
- 没有 PostgreSQL 适配。
- 没有 `DocumentVersion`、`Entity`、`Event`、`Claim`、`Relationship` 等 Alpha 知识底座表。
- 没有索引版本、Prompt 版本、引用审计记录表。

### `metaos.ingest` 与 `metaos.documents`

已实现：

- 文件上传与本地文件入库。
- TXT、Markdown 解析。
- PDF 文档路由、文本 PDF 提取、混合 PDF 页面计划。
- OCR Worker 可处理图片与扫描页。

缺口：

- 没有稳定文档版本模型。
- 入库后未显式保留“原文结构树”。
- 没有增量入库和内容版本对比契约。

### `metaos.knowledge`

已实现：

- 规则分类、摘要、标准 Markdown 生成。
- Chunker v1/v2，v2 支持 Markdown 块、页面标记、表格/代码块保护、重叠窗口。
- 删除知识条目时清理 chunks 与 Chroma 索引。

缺口：

- Chunk ID 使用随机 UUID，不满足 Alpha 对稳定 ID、父子块、前后块、索引版本的要求。
- 没有实体、事件、主张、关系、证据链接和多级摘要。
- 分类与摘要仍是规则或单轮简化逻辑，不是稳定知识底座。

### `metaos.retrieval`

已实现：

- ChromaDB 持久化向量索引。
- 默认 Ollama `bge-m3` embedding，测试可用 hash/fake embedding。
- 可恢复索引、跳过已索引 chunk、删除陈旧 chunk 索引。
- 检索结果返回 `chunk_id`、`knowledge_item_id`、`heading_path`、`score`、`file_path` 等。

缺口：

- 没有全文检索。
- 没有 RRF 融合。
- 没有元数据过滤 API。
- 没有可选重排器。
- 没有检索回归评测集。
- 结果只能回链到文件路径和 chunk，尚未形成可审计 citation contract。

### `metaos.rag`

已实现：

- 单轮 RAG 问答。
- 检索 top-k chunks 后调用 DeepSeek 兼容接口。
- 返回回答、引用列表、命中 chunks、token 用量与成本估算。

缺口：

- 没有议题编译。
- 没有研究计划、证据矩阵、缺失证据检测、补充检索、反证检索。
- 输出没有严格区分原文事实、模型推断、争议观点、个人反思。
- 模型输出没有 Pydantic Schema 校验。
- 回答不强制形成 Action、不行动或复盘。

### `metaos.tasks`

已实现：

- Redis/RQ 队列：`ingest`、`ocr`、`index`、`rag`。
- 入库、PDF 路由、OCR、索引、RAG 后台任务。
- 运行态监控与任务状态记录。

缺口：

- 没有研究执行器任务。
- 没有御史台审计任务。
- 没有日报采集、视频渲染、推荐、宰相闭环任务。
- 失败重试策略主要依赖 RQ 默认能力，业务级重试与幂等契约未文档化。

### `metaos.app`

已实现：

- FastAPI：健康检查、workspace、jobs、document ingest、knowledge、chunks、index、search、RAG jobs。
- Streamlit：上传、队列监控、知识条目、chunk 健康、索引、搜索、RAG 问答、DeepSeek token/余额展示。

缺口：

- 没有 Alpha 意图、日报、研究、行动、复盘、推荐、视频审核界面。
- 没有 ResearchTask 进度展示。
- 现有 UI 文案有编码风险。

### `metaos.alpha`

已实现：

- `gate_plan.py` 定义 32 本核心书与阶段门禁数据。
- `gate_check.py` 检查本地环境、BookProfile、个人材料比例等。

缺口：

- 门禁计划不是 Alpha 业务实现。
- CoreBook 中文字符串同样存在编码显示风险。
- 现阶段门禁重点偏运行环境与资料准备，还未覆盖 Alpha Schema、API、研究流程。

## 当前运行数据审计

`library/metaos.sqlite3` 当前表计数：

- `sources`：6
- `assets`：9
- `knowledge_items`：3
- `chunks`：4882
- `jobs`：58

当前知识条目：

- `资治通鉴`，history，4622 chunks，chunker v2。
- `道德经`，philosophy，14 chunks，chunker v2。
- `lean_startup`，product，246 chunks，chunker v2。

当前 job 状态：

- `succeeded`：40
- `failed`：11
- `running`：6
- `pending`：1

当前 job 类型：

- `answer_question`：22
- `index_knowledge`：13
- `rebuild_index`：6
- `rebuild_chunks`：5
- `pdf_route`：5
- `ingest_document`：4
- `ocr_document`：3

运行态含义：

- Chroma 索引目录已经存在，且可能包含多次历史 collection 文件。
- SQLite 中只有 3 个知识条目，但 chunks 已经较多，主要来自大体量 PDF。
- 现有系统已可作为 Alpha 知识底座迁移起点，但不应在新主题研究时触发重切块或重建索引。

## 已有测试审计

当前 `test/` 中主要测试：

- `test_alpha_gate_check.py`：阶段门禁、BookProfile 检查、版本解析、Streamlit Windows event loop。
- `test_retrieval_resume.py`：索引续建、陈旧索引删除、强制重建。
- `test_knowledge_deletion.py`：删除知识条目时清理 chunks 和索引。

缺口：

- 缺少公共 Schema 校验测试。
- 缺少 API 契约测试。
- 缺少全文检索、RRF、元数据过滤、引用回链回归测试。
- 缺少议题编译器、认知算子、研究执行器、御史台、推荐、宰相、视频闭环测试。

## 关键风险

1. 中文编码风险  
   多个 Python/Markdown 输出在当前 PowerShell 读取中显示 mojibake。该问题会影响中文关键词匹配、提示词、错误信息、门禁文案和 UI 文案，必须在进入业务实现前单独立项确认文件编码、终端编码和历史文本修复策略。

2. 稳定 ID 风险  
   当前 `Source`、`Asset`、`KnowledgeItem`、`Chunk` 使用随机 ID。Alpha 要求新主题不重切块、不重建索引，因此需要基于内容、版本、结构位置生成稳定 ID，并保留索引版本。

3. 数据库演进风险  
   当前 SQLite schema 是内联初始化字符串，没有迁移系统。新增公共 Schema 和数据库模型前，必须先文档化，再以独立任务引入迁移或兼容升级方案。

4. 检索能力不足  
   当前只有向量检索，不满足 Alpha 的“稠密向量检索+全文检索+元数据过滤+RRF融合+可选重排”。

5. 引用审计不足  
   当前 citation 只到 chunk 和文件路径，无法审计回答中每个结论是否被引用支持，也无法区分事实、推断、争议、反思。

6. RAG 与 Alpha 研究混同  
   当前 RAG 是单轮问答。Alpha 需要议题编译、证据要求、研究计划、证据矩阵、反证、审计和行动闭环，应新增模块而不是把所有逻辑塞进 `rag.service`。

7. 运行态数据混杂  
   `library/` 同时包含原文、Markdown、数据库、索引和阶段资料。后续任务要避免误删或重建运行态数据。

## 阶段0结论

当前系统适合作为 Alpha 的本地知识与任务执行基座。下一步不应直接重构业务代码，而应按以下顺序推进：

1. 先冻结公共 Schema、数据库模型、API 契约和任务边界。
2. 再逐阶段实现用户主权层、每日账本、内容工坊、知识底座标准化、检索增强、议题编译、研究执行、审计、推荐和宰相闭环。
3. 每个任务只改一个业务模块和一个测试目录，保持 RAG、Streamlit、RQ、视频能力不回归。

