# MetaOS Alpha 任务索引

每个任务必须可独立测试、提交和回滚。阶段0之后才允许开始业务实现。

## A0-DOC-001：阶段0文档审计与架构冻结

- 价值：为 Alpha 后续实现提供共同边界，避免直接大规模重构。
- 依赖：现有仓库可读。
- 允许修改范围：根目录阶段0文档。
- 禁止修改范围：`metaos/`、`test/`、`library/`、`pyproject.toml`、迁移、根配置。
- 输入：当前仓库结构、运行数据、用户 Alpha 目标。
- 输出：阶段0九份文档。
- 接口：无代码接口。
- 验收标准：九份文档存在，且明确阶段0不代表业务已实现。
- 测试命令：`git status --short`，文档文件存在性检查。
- 回滚方式：删除本任务新增文档。
- 文档更新：本任务即文档更新。

## A1-SOV-001：用户主权 Schema

- 价值：让意图成为最高约束。
- 依赖：阶段0人工审查通过。
- 允许修改范围：`metaos/core` 或新增 `metaos/sovereignty`，`test/test_sovereignty_*`。
- 禁止修改范围：检索、RAG、Worker、Streamlit 业务逻辑。
- 输入：`DOMAIN_MODEL.md` 用户主权层设计。
- 输出：`CognitiveConstitution`、`Intent`、`CurrentRole`、`AttentionBudget`、`NotToDoItem` Pydantic Schema。
- 接口：Schema 仅本地导入，不暴露 API。
- 验收标准：字段、状态枚举、校验规则通过测试。
- 测试命令：`python -m pytest test/test_sovereignty_schema.py`。
- 回滚方式：回退新增模块和测试文件。
- 文档更新：同步更新 `DOMAIN_MODEL.md`。

## A1-SOV-002：用户主权持久化

- 价值：保存当前意图、角色、预算和不做清单。
- 依赖：A1-SOV-001。
- 允许修改范围：主权模块 repository，一个测试文件。
- 禁止修改范围：现有 `knowledge`、`retrieval`、`rag`。
- 输入：主权 Schema。
- 输出：SQLite repository 和初始化兼容逻辑。
- 接口：Repository 方法 `add/get/list/update_active`。
- 验收标准：可创建、读取、更新、停用主权对象。
- 测试命令：`python -m pytest test/test_sovereignty_repository.py`。
- 回滚方式：回退主权 repository 和测试；数据库新增表可保留为空或由迁移回滚。
- 文档更新：同步更新 `TECHNICAL_ARCHITECTURE.md` 存储表族。

## A1-SOV-003：用户主权 API

- 价值：为 UI 和后续研究任务提供意图入口。
- 依赖：A1-SOV-002。
- 允许修改范围：`metaos/app/api.py` 中主权 API、一个 API 测试文件。
- 禁止修改范围：RAG 与检索接口行为。
- 输入：主权 repository。
- 输出：`/alpha/constitution`、`/alpha/intents`、`/alpha/current-role`、`/alpha/attention-budgets`、`/alpha/not-to-do`。
- 接口：见 `API_CONTRACTS.md`。
- 验收标准：API 契约测试通过。
- 测试命令：`python -m pytest test/test_sovereignty_api.py`。
- 回滚方式：回退 API 路由和测试。
- 文档更新：同步更新 `API_CONTRACTS.md`。

## A2-LEDGER-001：每日账本 Schema

- 价值：为行动和复盘建立事实账。
- 依赖：A1-SOV-001。
- 允许修改范围：新增 `metaos/ledger` Schema，一个测试文件。
- 禁止修改范围：内容工坊、检索、研究执行。
- 输入：`DOMAIN_MODEL.md` 每日认知账本设计。
- 输出：DailyPlan、WorkEvent、Advice、Decision、Action、AttentionDrift、DailyReview、DailySummary Schema。
- 接口：Schema。
- 验收标准：状态枚举、日期、引用字段校验通过。
- 测试命令：`python -m pytest test/test_ledger_schema.py`。
- 回滚方式：回退新增模块和测试。
- 文档更新：同步更新 `DOMAIN_MODEL.md`。

## A2-LEDGER-002：Git 与 Markdown 采集

- 价值：自动记录真实工作痕迹。
- 依赖：A2-LEDGER-001。
- 允许修改范围：`metaos/ledger` 采集器，一个测试文件。
- 禁止修改范围：入库 pipeline、Chroma 索引。
- 输入：本地 repo path、日期范围、Markdown 目录。
- 输出：`WorkEvent` 列表。
- 接口：Collector 方法与后台任务 payload。
- 验收标准：固定 fixture repo 和 Markdown 变更能生成稳定事件。
- 测试命令：`python -m pytest test/test_ledger_collectors.py`。
- 回滚方式：回退采集器和测试。
- 文档更新：更新 `API_CONTRACTS.md` 采集接口说明。

## A2-LEDGER-003：DailySummary 生成

- 价值：把每日事实、判断、反思和行动汇总为后续视频和周报输入。
- 依赖：A2-LEDGER-001、A2-LEDGER-002。
- 允许修改范围：`metaos/ledger` summary 服务，一个测试文件。
- 禁止修改范围：视频渲染。
- 输入：DailyReview、WorkEvent、Decision、Action。
- 输出：DailySummary。
- 接口：`generate_daily_summary(date)`。
- 验收标准：输出区分事实、判断、反思、行动，并通过 Schema 校验。
- 测试命令：`python -m pytest test/test_daily_summary.py`。
- 回滚方式：回退 summary 服务和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`。

## A3-WORKSHOP-001：EpisodeSpec Schema 与审核状态

- 价值：建立每日总结到视频的结构化入口。
- 依赖：A2-LEDGER-003。
- 允许修改范围：新增 `metaos/workshop` Schema，一个测试文件。
- 禁止修改范围：Remotion 模板和 FFmpeg 渲染。
- 输入：DailySummary。
- 输出：EpisodeSpec。
- 接口：Schema。
- 验收标准：未审核状态不能导出正式视频。
- 测试命令：`python -m pytest test/test_workshop_schema.py`。
- 回滚方式：回退 workshop Schema 和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`。

## A3-WORKSHOP-002：视频资产生成与渲染任务

- 价值：形成可审核 MP4 闭环。
- 依赖：A3-WORKSHOP-001。
- 允许修改范围：`metaos/workshop`、视频任务测试。
- 禁止修改范围：研究、检索、主权模块。
- 输入：EpisodeSpec。
- 输出：脚本、旁白、字幕、图卡、MP4。
- 接口：`/alpha/workshop/episodes/jobs`、`/alpha/workshop/episodes/{id}/render/jobs`。
- 验收标准：fixture EpisodeSpec 可生成审核态资产；渲染失败有 job error。
- 测试命令：`python -m pytest test/test_workshop_render.py`。
- 回滚方式：回退 workshop 服务和测试；删除生成的临时导出。
- 文档更新：更新 `API_CONTRACTS.md`。

## A4-KB-001：稳定文档版本与 Chunk ID

- 价值：保证新主题不重切块、不重建索引。
- 依赖：阶段0审查。
- 允许修改范围：知识底座标准化模块，一个测试文件。
- 禁止修改范围：现有 RAG 行为和 Chroma collection 删除。
- 输入：Source、Asset、ParsedDocument。
- 输出：DocumentVersion、稳定 Chunk ID、父子和前后关系。
- 接口：标准化服务。
- 验收标准：同一文档重复入库生成相同 stable ID；局部变更只影响相关块。
- 测试命令：`python -m pytest test/test_document_versioning.py`。
- 回滚方式：回退标准化模块和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`、`TECHNICAL_ARCHITECTURE.md`。

## A5-SEARCH-001：全文检索

- 价值：补足向量检索对精确词、名称、引用的不足。
- 依赖：A4-KB-001 或兼容现有 Chunk。
- 允许修改范围：新增 `metaos/search` 或扩展检索模块，一个测试文件。
- 禁止修改范围：议题编译和研究执行。
- 输入：Chunk 文本和元数据。
- 输出：全文检索结果。
- 接口：`full_text_search(query, filters, top_k)`。
- 验收标准：固定查询命中预期 chunk，返回 citation。
- 测试命令：`python -m pytest test/test_full_text_search.py`。
- 回滚方式：回退全文检索模块和测试；删除临时 FTS 表或索引。
- 文档更新：更新 `TECHNICAL_ARCHITECTURE.md`。

## A5-SEARCH-002：RRF 融合与元数据过滤

- 价值：把向量、全文和过滤统一成可解释检索。
- 依赖：A5-SEARCH-001。
- 允许修改范围：检索融合模块，一个测试文件。
- 禁止修改范围：Chroma 重建逻辑。
- 输入：向量结果、全文结果、过滤条件。
- 输出：融合后的 EvidenceCandidate。
- 接口：`/alpha/search`。
- 验收标准：RRF 排序稳定，过滤条件生效，citation 不丢失。
- 测试命令：`python -m pytest test/test_rrf_search.py`。
- 回滚方式：回退融合模块和测试。
- 文档更新：更新 `API_CONTRACTS.md`。

## A6-COMPILER-001：议题编译 Schema

- 价值：把问题转换为可执行研究契约。
- 依赖：A1-SOV-001。
- 允许修改范围：新增 `metaos/compiler` Schema，一个测试文件。
- 禁止修改范围：检索实现。
- 输入：自然语言问题、Intent、Role、AttentionBudget。
- 输出：ResearchTask、CognitiveOperator、ThemeSpec、EvidenceRequirement、ResearchScope、ResearchPlan。
- 接口：Schema。
- 验收标准：五个指定主题都可表达为 ThemeSpec。
- 测试命令：`python -m pytest test/test_compiler_schema.py`。
- 回滚方式：回退 compiler Schema 和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`。

## A6-COMPILER-002：议题编译器服务

- 价值：运行时生成主题规格，杜绝主题硬编码。
- 依赖：A6-COMPILER-001、LLM Gateway 可用或 fake LLM。
- 允许修改范围：`metaos/compiler` 服务，一个测试文件。
- 禁止修改范围：每个主题新增 Python 分支。
- 输入：用户问题与当前意图。
- 输出：结构化 ResearchPlan。
- 接口：`/alpha/research/compile`。
- 验收标准：五个指定主题共用同一代码路径，输出通过 Schema 校验。
- 测试命令：`python -m pytest test/test_issue_compiler.py`。
- 回滚方式：回退 compiler 服务和测试。
- 文档更新：更新 `API_CONTRACTS.md`。

## A7-RESEARCH-001：证据矩阵与研究执行器

- 价值：从候选证据形成可审计判断。
- 依赖：A5-SEARCH-002、A6-COMPILER-002。
- 允许修改范围：新增 `metaos/research`，一个测试文件。
- 禁止修改范围：御史台实现、推荐、视频。
- 输入：ResearchTask、ResearchPlan、EvidenceCandidate。
- 输出：EvidenceMatrixRow、ResearchAnswer 草案。
- 接口：research service。
- 验收标准：能检测缺失证据和反证需求。
- 测试命令：`python -m pytest test/test_research_executor.py`。
- 回滚方式：回退 research 模块和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`。

## A7-RESEARCH-002：带引用回答与行动落账

- 价值：把研究结论转化为行动或“不行动”。
- 依赖：A7-RESEARCH-001、A2-LEDGER-001。
- 允许修改范围：`metaos/research` 与 ledger 接口适配测试。
- 禁止修改范围：御史台内部规则。
- 输入：EvidenceMatrix、AuditReport 可选。
- 输出：ResearchAnswer、Action 或 no_action。
- 接口：`/alpha/research/tasks/{task_id}/answer`。
- 验收标准：输出区分事实、推断、争议、反思；无来源结论被标记。
- 测试命令：`python -m pytest test/test_research_answer.py`。
- 回滚方式：回退回答服务和测试。
- 文档更新：更新 `API_CONTRACTS.md`。

## A8-KB-002：实体、事件、主张和证据链接

- 价值：让知识底座从 Chunk 检索升级为结构化证据网络。
- 依赖：A4-KB-001。
- 允许修改范围：知识底座结构化模块，一个测试文件。
- 禁止修改范围：检索排序策略。
- 输入：DocumentVersion、Chunk。
- 输出：Entity、Alias、Event、Claim、EvidenceLink、多级摘要。
- 接口：foundation extraction service。
- 验收标准：fixture 文档可抽取实体、事件、主张，并回链 citation。
- 测试命令：`python -m pytest test/test_knowledge_foundation.py`。
- 回滚方式：回退结构化模块和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`。

## A9-AUDIT-001：御史台引用与范围审计

- 价值：防止无来源结论和越界回答。
- 依赖：A7-RESEARCH-002。
- 允许修改范围：新增 `metaos/censorate`，一个测试文件。
- 禁止修改范围：研究执行器生成逻辑。
- 输入：ResearchAnswer、EvidenceMatrix、ResearchScope。
- 输出：AuditReport。
- 接口：audit service。
- 验收标准：缺引用、错引用、越界结论可被标记。
- 测试命令：`python -m pytest test/test_censorate_audit.py`。
- 回滚方式：回退 censorate 模块和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`。

## A9-AUDIT-002：反证、完整性、偏误和成本审计

- 价值：把研究质量从“有答案”提升到“经得起反查”。
- 依赖：A9-AUDIT-001。
- 允许修改范围：`metaos/censorate`，一个测试文件。
- 禁止修改范围：检索底层实现。
- 输入：ResearchTask、EvidenceMatrix、retrieval runs、AttentionBudget。
- 输出：AuditReport 增强项。
- 接口：audit service。
- 验收标准：缺反证、证据不足、确认偏误、超预算可被标记。
- 测试命令：`python -m pytest test/test_censorate_quality.py`。
- 回滚方式：回退审计增强和测试。
- 文档更新：更新 `TECHNICAL_ARCHITECTURE.md`。

## A10-MIN-001：三部有限推荐

- 价值：让推荐服从意图和预算，而不是制造信息流。
- 依赖：A1-SOV-002、A5-SEARCH-002。
- 允许修改范围：新增 `metaos/ministries`，一个测试文件。
- 禁止修改范围：宰相、视频。
- 输入：Intent、AttentionBudget、候选信息。
- 输出：MinistryReport、RecommendationItem。
- 接口：`/alpha/ministries/daily/jobs`。
- 验收标准：每部最多 3 条，整体最多 5 条，可返回无事上奏。
- 测试命令：`python -m pytest test/test_ministries.py`。
- 回滚方式：回退 ministries 模块和测试。
- 文档更新：更新 `API_CONTRACTS.md`。

## A11-CHAN-001：宰相今日简报

- 价值：把意图、预算、研究和复盘合成为今日重点。
- 依赖：A1-SOV-002、A2-LEDGER-003、A7-RESEARCH-002、A10-MIN-001。
- 允许修改范围：新增 `metaos/chancellor`，一个测试文件。
- 禁止修改范围：检索、视频渲染。
- 输入：Intent、Role、AttentionBudget、DailyReview、ResearchAnswer、MinistryReport。
- 输出：ChancellorBriefing。
- 接口：`/alpha/chancellor/daily/jobs`。
- 验收标准：输出今日重点、暂缓、忽略和认知陷阱提醒。
- 测试命令：`python -m pytest test/test_chancellor.py`。
- 回滚方式：回退 chancellor 模块和测试。
- 文档更新：更新 `DOMAIN_MODEL.md`、`API_CONTRACTS.md`。

## A11-CLOSE-001：完整闭环验收

- 价值：确认 Alpha 从季度意图到周报闭环可运行。
- 依赖：阶段1到阶段11核心任务。
- 允许修改范围：端到端测试目录和必要 glue code。
- 禁止修改范围：大规模重构任何单模块。
- 输入：fixture 意图、知识库、每日事件、研究问题。
- 输出：端到端运行记录、DailySummary、EpisodeSpec、ResearchAnswer、Action、ChancellorBriefing。
- 接口：端到端测试。
- 验收标准：Alpha 九条验收全部有自动化或人工可审证据。
- 测试命令：`python -m pytest test/test_alpha_end_to_end.py`。
- 回滚方式：回退端到端 glue code 和测试 fixture。
- 文档更新：更新 `ROADMAP.md` 完成状态。

## A5-SEARCH-003: Vector retrieval adapter

- Value: make the Alpha search channel use the existing Chroma/Ollama retrieval service as a first-class dense vector source instead of relying on test-only mock candidates.
- Dependencies: A5-SEARCH-001, A5-SEARCH-002, existing `metaos.retrieval.service.RetrievalService.search`.
- Allowed changes: `metaos/search` adapter code, one focused search test file, and task/roadmap documentation.
- Forbidden changes: Chroma rebuild behavior, embedding provider configuration, RQ workers, RAG answer behavior, root configuration, migrations, and `pyproject.toml`.
- Input: natural language query, a retrieval service implementing `search(query, top_k)`, optional metadata filters, and `top_k`.
- Output: `SearchCandidate` objects with vector score, citation back-links, metadata, and RRF-compatible fields.
- Interface: `vector_search(query, retrieval, filters=None, top_k=5)` and `search_result_to_candidate(result)`.
- Acceptance: vector results preserve source/asset/file citations, obey metadata filters, skip empty queries, and feed `rrf_fuse` without losing citations.
- Test command: `python -m pytest test/test_vector_search.py`.
- Rollback: remove `metaos/search/vector.py`, its exports, and `test/test_vector_search.py`.
- Documentation update: this task entry plus `ROADMAP.md` status note.

## A5-SEARCH-004: Hybrid evidence search entrypoint

- Value: give research execution one stable Alpha entrypoint for full-text, dense vector, metadata-filtered, RRF-fused evidence retrieval.
- Dependencies: A5-SEARCH-001, A5-SEARCH-002, A5-SEARCH-003.
- Allowed changes: `metaos/search` orchestration code, one focused search test file, and task/roadmap documentation.
- Forbidden changes: embedding generation, Chroma index mutation, RQ workers, RAG prompting, public database schemas, root configuration, and `pyproject.toml`.
- Input: natural language query, optional `Chunk` sequence, optional vector retrieval service, optional metadata filters, and `top_k`.
- Output: fused `EvidenceCandidate` objects with channel ranks, channel scores, citation back-links, and deterministic RRF ordering.
- Interface: `hybrid_search(query, chunks=(), vector_retrieval=None, filters=None, top_k=5, full_text_top_k=None, vector_top_k=None)`.
- Acceptance: hybrid search fuses full-text and vector hits, supports full-text-only mode, preserves citations, applies filters, and skips empty queries without side effects.
- Test command: `python -m pytest test/test_hybrid_search.py`.
- Rollback: remove `metaos/search/hybrid.py`, its exports, and `test/test_hybrid_search.py`.
- Documentation update: this task entry plus `ROADMAP.md` status note.
