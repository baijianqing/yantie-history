# MetaOS Alpha 技术架构

## 架构原则

- 模块化单体。
- 独立 Worker。
- 本地优先。
- 公共 Schema 先行。
- API 契约先行。
- 运行态数据不被随意重建。
- 模型输出必须结构化并通过 Schema 校验。

## 当前技术基座

当前仓库已经使用：

- Python 3.11。
- FastAPI。
- Pydantic。
- SQLite。
- Redis。
- RQ。
- ChromaDB。
- Ollama `bge-m3`。
- DeepSeek 兼容 Chat API。
- Streamlit。
- PaddleOCR/PyMuPDF。
- pytest/unittest。

当前尚未使用但 Alpha 优先技术栈要求中出现：

- PostgreSQL。
- SQLAlchemy。
- Alembic。
- SQLite FTS5 或 PostgreSQL 全文检索。
- RRF。
- Prompt 版本。
- 索引版本。
- 引用审计。
- Node 24、TypeScript、React、Remotion、FFmpeg。
- Ruff、mypy。

## 目标模块边界

建议新增或扩展以下模块：

- `metaos.sovereignty`：用户主权层。
- `metaos.ledger`：每日认知账本。
- `metaos.workshop`：内容工坊。
- `metaos.foundation`：标准化知识底座。
- `metaos.search`：多路检索、RRF、过滤、重排。
- `metaos.compiler`：议题编译器和认知算子。
- `metaos.research`：研究执行器。
- `metaos.censorate`：御史台。
- `metaos.ministries`：三部有限推荐。
- `metaos.chancellor`：宰相。
- `metaos.evaluation`：检索、引用和研究质量评测。

现有模块保留：

- `metaos.ingest`
- `metaos.documents`
- `metaos.knowledge`
- `metaos.retrieval`
- `metaos.rag`
- `metaos.tasks`
- `metaos.app`
- `metaos.workspace`
- `metaos.llm_gateway`

## 存储架构

### Alpha 初期

为了降低迁移风险，Alpha 初期可以在现有 SQLite 基座上扩展表，同时预留 PostgreSQL 兼容字段与迁移路径。

必备能力：

- schema version。
- index version。
- prompt version。
- structured output version。
- stable ID。
- migration/audit log。

### 中期目标

当公共 Schema 稳定后，引入：

- SQLAlchemy ORM。
- Alembic 迁移。
- PostgreSQL 生产存储。
- SQLite 本地开发或离线存储。

### 表族规划

当前表族：

- `jobs`
- `sources`
- `assets`
- `knowledge_items`
- `chunks`

Alpha 新增表族：

- 用户主权：`cognitive_constitutions`、`intents`、`current_roles`、`attention_budgets`、`not_to_do_items`。
- 每日账本：`daily_plans`、`work_events`、`advices`、`decisions`、`actions`、`attention_drifts`、`daily_reviews`、`daily_summaries`。
- 知识底座：`document_versions`、`document_structures`、`entities`、`entity_aliases`、`events`、`claims`、`relationships`、`citations`、`evidence_links`、`summaries`。
- 检索：`index_versions`、`fts_entries`、`retrieval_runs`、`retrieval_results`、`eval_queries`、`eval_results`。
- 研究：`research_tasks`、`theme_specs`、`evidence_requirements`、`research_plans`、`evidence_matrix_rows`、`research_answers`。
- 审计：`audit_reports`、`citation_audit_items`、`counterevidence_items`、`bias_flags`。
- 推荐与宰相：`ministry_reports`、`recommendation_items`、`chancellor_briefings`.
- 内容工坊：`episode_specs`、`script_drafts`、`voiceover_jobs`、`subtitle_tracks`、`visual_cards`、`review_records`、`video_exports`。

A1-SOV-002 实现说明：

- 用户主权层持久化位于 `metaos/sovereignty/repository.py`。
- `initialize_sovereignty_database()` 会先执行现有 `workspace` SQLite 初始化，再补建主权层五张表。
- 当前阶段不引入 Alembic，不修改 `metaos/workspace/database.py`，以降低对现有 RAG、Streamlit、RQ 和知识库数据的影响。
- Repository 已提供 `add/get/list`，并为 `Intent`、`CurrentRole`、`NotToDoItem` 提供 `update_active`。

## 检索架构

目标检索流程：

1. 接收 `ResearchTask` 和 `ThemeSpec`。
2. 生成 query variants。
3. 执行向量检索。
4. 执行全文检索。
5. 应用元数据过滤。
6. 用 RRF 融合多路候选。
7. 可选重排。
8. 返回 `EvidenceCandidate` 列表。
9. 每个候选必须包含 `Citation` 回链。

RRF 基础规则：

- 每个检索通道返回 rank。
- 融合分数为 `sum(1 / (k + rank))`。
- `k` 初始值建议 60。
- RRF 参数必须进入 `retrieval_run` 记录。

## 研究执行架构

研究执行器应作为独立业务模块和 Worker 任务实现，不应塞进现有单轮 `rag.service`。

推荐流程：

1. `compiler` 生成研究契约。
2. `research` 创建研究任务。
3. `search` 返回候选证据。
4. `research` 构造证据矩阵。
5. `research` 检测缺失证据。
6. `search` 执行补充检索与反证检索。
7. `research` 生成结构化回答草案。
8. `censorate` 审计引用、范围、反证和成本。
9. `research` 生成最终回答。
10. `ledger` 生成 Action 或“不行动”记录。

## 模型 Provider 架构

保留 `metaos.llm_gateway` 作为边界，但需要扩展：

- Provider 名称。
- Model 名称。
- Prompt 版本。
- Structured output schema 名称。
- 请求/响应审计摘要。
- token 用量与成本。
- JSON Schema 或 Pydantic 校验错误。

模型输出必须：

- 先产出 JSON。
- 通过 Pydantic 校验。
- 校验失败时进入可重试路径。
- 最终失败时保存失败记录，不静默返回自由文本。

## Worker 架构

现有队列：

- `ingest`
- `ocr`
- `index`
- `rag`

Alpha 建议新增或扩展：

- `ledger`
- `research`
- `audit`
- `recommendation`
- `video`

幂等规则：

- Worker 输入必须包含 stable ID 或 job ID。
- 同一 job 重试不得创建重复业务记录。
- 失败要写入 `jobs.error` 和业务错误表。
- 长任务要写 progress。

## API 架构

FastAPI 继续作为本地 API 边界。Alpha API 分为：

- 主权 API。
- 每日账本 API。
- 知识底座 API。
- 检索 API。
- 议题编译 API。
- 研究 API。
- 审计 API。
- 推荐 API。
- 宰相 API。
- 内容工坊 API。

详见 `API_CONTRACTS.md`。

## 前端架构

Alpha 前端分两类：

- Streamlit：保留为本地操作台和调试界面。
- React/Remotion：用于内容工坊视频模板和可审核资产生成。

原则：

- 不做营销落地页。
- 首屏应是可操作工作台。
- 研究进度、证据矩阵、引用审计和行动状态必须可见。

## 技术后置规则

以下技术只有在评测证明必要时引入：

- PyTorch：本地重排、NER、指代消解或微调。
- LangGraph：研究流程稳定且普通任务编排无法维护后再评估。
- OpenSearch：检索数据规模和并发超过 SQLite/PostgreSQL 能力后再评估。
- Neo4j：关系查询复杂度超过关系库和递归 SQL 能力后再评估。
