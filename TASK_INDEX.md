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

## A1-SOV-001：用户主权数据模式

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

## A1-SOV-003：用户主权接口

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

## A2-LEDGER-001：每日账本数据模式

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

## A2-LEDGER-003：每日总结生成

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

## A3-WORKSHOP-001：视频规格数据模式与审核状态

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

## A4-KB-001：稳定文档版本与知识块标识符

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

## A5-SEARCH-003：向量检索适配器

- 价值：让 Alpha 搜索通道把现有 Chroma/Ollama 检索服务作为正式的稠密向量来源，而不是依赖测试专用的模拟候选证据。
- 依赖：A5-SEARCH-001、A5-SEARCH-002、现有 `metaos.retrieval.service.RetrievalService.search`。
- 允许修改范围：`metaos/search` 适配器代码、一个聚焦的搜索测试文件、任务和路线图文档。
- 禁止修改范围：Chroma 重建行为、embedding provider 配置、RQ worker、RAG 回答行为、根配置、迁移和 `pyproject.toml`。
- 输入：自然语言查询、实现 `search(query, top_k)` 的检索服务、可选元数据过滤条件和 `top_k`。
- 输出：带向量分数、引用回链、元数据和 RRF 兼容字段的 `SearchCandidate` 对象。
- 接口：`vector_search(query, retrieval, filters=None, top_k=5)` 和 `search_result_to_candidate(result)`。
- 验收标准：向量结果保留 source/asset/file 引用，遵守元数据过滤，跳过空查询，并且进入 `rrf_fuse` 时不丢失引用。
- 测试命令：`python -m pytest test/test_vector_search.py`。
- 回滚方式：删除 `metaos/search/vector.py`、相关导出和 `test/test_vector_search.py`。
- 文档更新：本任务条目和 `ROADMAP.md` 状态说明。

## A5-SEARCH-004：混合证据检索入口

- 价值：为研究执行提供一个稳定的 Alpha 检索入口，统一全文、稠密向量、元数据过滤和 RRF 融合后的证据结果。
- 依赖：A5-SEARCH-001、A5-SEARCH-002、A5-SEARCH-003。
- 允许修改范围：`metaos/search` 编排代码、一个聚焦的搜索测试文件、任务和路线图文档。
- 禁止修改范围：embedding 生成、Chroma 索引写入、RQ worker、RAG prompt、公开数据库 schema、根配置和 `pyproject.toml`。
- 输入：自然语言查询、可选 `Chunk` 序列、可选向量检索服务、可选元数据过滤条件和 `top_k`。
- 输出：融合后的 `EvidenceCandidate` 对象，包含通道排名、通道分数、引用回链和确定性的 RRF 排序。
- 接口：`hybrid_search(query, chunks=(), vector_retrieval=None, filters=None, top_k=5, full_text_top_k=None, vector_top_k=None)`。
- 验收标准：混合检索融合全文和向量命中，支持仅全文模式，保留引用，应用过滤条件，并且空查询无副作用。
- 测试命令：`python -m pytest test/test_hybrid_search.py`。
- 回滚方式：删除 `metaos/search/hybrid.py`、相关导出和 `test/test_hybrid_search.py`。
- 文档更新：本任务条目和 `ROADMAP.md` 状态说明。

## A5-SEARCH-005：Alpha 搜索接口

- 价值：通过已记录的 HTTP API 暴露 Alpha 混合证据检索路径。
- 依赖：A5-SEARCH-004 和现有 FastAPI app 接线。
- 允许修改范围：`metaos/app/api.py`、一个聚焦的 API 测试文件、任务/API/路线图文档。
- 禁止修改范围：搜索排序内部逻辑、Chroma 索引写入、RQ worker、数据库迁移、Streamlit UI、根配置和 `pyproject.toml`。
- 输入：包含 `query`、`top_k`、可选 `filters`、可选通道 top-k 值和 `include_vector` 的 JSON body。
- 输出：JSON 格式的 `EvidenceCandidate` 列表，包含引用回链、通道排名、通道分数和融合分数。
- 接口：`POST /alpha/search`。
- 验收标准：接口拒绝空查询，返回带引用的全文/向量融合证据候选，支持元数据过滤，并且可以在不构造向量检索的情况下只走全文检索。
- 测试命令：`python -m pytest test/test_alpha_search_api.py`。
- 回滚方式：删除 `/alpha/search` 路由、请求 schema 和 `test/test_alpha_search_api.py`。
- 文档更新：本任务条目、`ROADMAP.md` 和 `API_CONTRACTS.md`。

## A6-COMPILER-001：议题编译数据模式

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

## A6-COMPILER-003：Alpha 研究编译接口

- 价值：通过已记录的 HTTP API 暴露运行时 `ThemeSpec` 和 `ResearchPlan` 编译能力。
- 依赖：A6-COMPILER-002 和现有 FastAPI app 接线。
- 允许修改范围：`metaos/app/api.py`、一个聚焦的编译器 API 测试文件、任务/API/路线图文档。
- 禁止修改范围：编译器 schema 变更、provider prompt 策略、搜索/研究执行内部逻辑、RQ worker、数据库迁移、根配置和 `pyproject.toml`。
- 输入：匹配 `CompileResearchRequest` 的 JSON body。
- 输出：schema 合法的 `ResearchCompilation` JSON，包含 task、operator、ThemeSpec、证据需求、范围和计划。
- 接口：`POST /alpha/research/compile`。
- 验收标准：接口对不同主题复用同一运行时编译路径，返回结构化编译结果，并把无效 provider 输出映射为 HTTP 400。
- 测试命令：`python -m pytest test/test_alpha_research_compile_api.py`。
- 回滚方式：删除 `/alpha/research/compile` 路由/helper 和 `test/test_alpha_research_compile_api.py`。
- 文档更新：本任务条目、`ROADMAP.md` 和 `API_CONTRACTS.md`。

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

## A7-RESEARCH-003：研究候选证据召回服务

- 价值：把研究执行从手工提供候选证据推进为按计划召回，并在构建证据矩阵前按证据需求标注候选证据。
- 依赖：A6-COMPILER-002、A5-SEARCH-004、A7-RESEARCH-001。
- 允许修改范围：`metaos/research` 服务代码、一个聚焦的研究测试文件、任务和路线图文档。
- 禁止修改范围：搜索内部逻辑、御史台规则、答案起草策略、推荐/宰相行为、根配置、迁移和 `pyproject.toml`。
- 输入：`ResearchCompilation`、证据搜索 callable 和 `top_k_per_query`。
- 输出：召回的 `EvidenceCandidate` 对象，以及包含证据矩阵的 `ResearchExecutionDraft`。
- 接口：`retrieve_research_candidates(compilation, search, top_k_per_query=5)` 和 `execute_research_plan(compilation, search, top_k_per_query=5)`。
- 验收标准：候选证据按证据需求召回，标注需求 ID、类型、查询和立场，完成去重，保留引用，并生成支持/反驳矩阵行。
- 测试命令：`python -m pytest test/test_research_service.py`。
- 回滚方式：删除 `metaos/research/service.py`、相关导出和 `test/test_research_service.py`。
- 文档更新：本任务条目和 `ROADMAP.md` 状态说明。

## A7-RESEARCH-004：研究执行轨迹

- 价值：通过记录进度事件、检索运行、采纳候选 ID 和执行版本，让研究执行可审计、可展示。
- 依赖：A7-RESEARCH-003。
- 允许修改范围：`metaos/research` 轨迹 schema/服务代码、一个聚焦的研究测试文件、任务和路线图文档。
- 禁止修改范围：搜索排序、御史台规则、答案起草、RQ 队列行为、API 路由、根配置、迁移和 `pyproject.toml`。
- 输入：`ResearchCompilation`、证据搜索 callable 和 `top_k_per_query`。
- 输出：包含 `ResearchProgressEvent`、`ResearchRetrievalRun`、召回候选和 `ResearchExecutionDraft` 的 `ResearchExecutionReport`。
- 接口：`execute_research_plan_with_trace(compilation, search, top_k_per_query=5)` 和 `retrieve_research_candidates_with_trace(...)`。
- 验收标准：报告记录执行版本、确定性进度阶段、每个查询的召回数量、采纳候选 ID，并与旧执行入口生成相同证据矩阵。
- 测试命令：`python -m pytest test/test_research_service.py`。
- 回滚方式：删除轨迹 schema/导出，并把 `execute_research_plan` 恢复为直接构建证据矩阵。
- 文档更新：本任务条目和 `ROADMAP.md` 状态说明。

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

## A11-OPS-001：任务重试元数据

- 价值：在接入重试按钮或自动重新入队前，为 Alpha worker 提供已测试的重试状态转换和审计轨迹。
- 依赖：现有 `JobRepository` 和 `Job` schema。
- 允许修改范围：`metaos/workspace/jobs.py`、一个聚焦的 job repository 测试文件、任务和路线图文档。
- 禁止修改范围：数据库 schema 迁移、RQ 队列分发行为、任务 worker 实现、Streamlit UI、API 路由、根配置和 `pyproject.toml`。
- 输入：失败 job id 和可选重试消息。
- 输出：同一个 job 被重置为 `pending`，progress 为 `0`，error 被清空，并在 `result.retry_history` 中记录失败/重试时间和之前的 error/message。
- 接口：`JobRepository.retry_failed(job_id, message="Retry queued")`。
- 验收标准：只有失败任务可以重试，重试历史只追加，保留上一次失败信息，并保留原 job payload/result 数据。
- 测试命令：`python -m pytest test/test_job_repository_retry.py`。
- 回滚方式：删除 `retry_failed`、`RETRY_HISTORY_KEY` 和 `test/test_job_repository_retry.py`。
- 文档更新：本任务条目和 `ROADMAP.md` 状态说明。

## A11-OPS-002：RQ 重试入队

- 价值：把失败任务的重试元数据转化为真实的 RQ 重新入队路径，并复用原 job id 和任务类型。
- 依赖：A11-OPS-001 和现有 RQ 队列 helper。
- 允许修改范围：`metaos/tasks/queueing.py`、一个聚焦的 queueing retry 测试文件、任务和路线图文档。
- 禁止修改范围：任务 worker 实现、数据库 schema 迁移、Streamlit UI、API 路由、根配置和 `pyproject.toml`。
- 输入：失败 job id。
- 输出：同一个 job 被重置为 `pending`，由 `JobRepository` 记录重试历史，并通过原任务路径/队列映射执行 RQ 入队。
- 接口：`enqueue_retry_job(job_id)` 和 `retry_dispatch_for_job(job)`。
- 验收标准：重试复用同一个 job id，把支持的 job 类型映射到正确队列和任务，拒绝非失败或不支持的任务且不入队，并保留重试历史。
- 测试命令：`python -m pytest test/test_queueing_retry.py`。
- 回滚方式：删除 `enqueue_retry_job`、`retry_dispatch_for_job` 和 `test/test_queueing_retry.py`。
- 文档更新：本任务条目和 `ROADMAP.md` 状态说明。

## A11-OPS-003：任务重试接口

- 价值：通过 HTTP 暴露已测试的失败任务重试路径，让操作员和 UI 可以触发重试。
- 依赖：A11-OPS-002 和现有 FastAPI job 路由。
- 允许修改范围：`metaos/app/api.py`、一个聚焦的 retry API 测试文件、任务/API/路线图文档。
- 禁止修改范围：队列分发映射、任务 worker 实现、数据库 schema 迁移、Streamlit UI、根配置和 `pyproject.toml`。
- 输入：`POST /jobs/{job_id}/retry` 中的失败 job id。
- 输出：重新入队后的 `Job` JSON，保留原 id 和重试历史。
- 接口：`POST /jobs/{job_id}/retry`。
- 验收标准：路由返回重新入队后的 job，把不存在的 job 映射为 404，把无效重试状态和 Redis 入队失败映射为 400，并且测试不依赖真实 Redis。
- 测试命令：`python -m pytest test/test_job_retry_api.py`。
- 回滚方式：删除 `/jobs/{job_id}/retry` 路由/import 和 `test/test_job_retry_api.py`。
- 文档更新：本任务条目、`ROADMAP.md` 和 `API_CONTRACTS.md`。

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

## A11-WEEKLY-001：周报打包

- 价值：把 Alpha 闭环沉淀为结构化周报，汇总与 Intent 相关的证据、行动、风险、认知陷阱和视频导出。
- 依赖：A2-LEDGER-003、A3-WORKSHOP-002、A7-RESEARCH-002、A11-CHAN-001。
- 允许修改范围：`metaos/chancellor` 周报 schema/service、一个聚焦周报测试、任务和领域模型文档。
- 禁止修改范围：检索排序、视频渲染、RQ worker 行为、迁移、根配置、`.vscode/`、`pyproject.toml`。
- 输入：`Intent`、周内 `DailySummary`、`ChancellorBriefing`、`ResearchAnswer`、`VideoExport`。
- 输出：`WeeklyReport`，包含来源 ID、已完成行动、待处理行动、证据亮点、风险、认知陷阱、内容导出和下周重点。
- 接口：`generate_weekly_report(week_start, week_end, *, intent, daily_summaries=None, briefings=None, research_answers=None, video_exports=None)`。
- 验收标准：只纳入闭区间周内记录；行动按结构化 `ActionStatus` 归类；成功 MP4 可回链；失败导出和不行动原因进入风险；非法周范围被拒绝。
- 测试命令：`python -m pytest test/test_weekly_report.py`。
- 回滚方式：删除 `WeeklyReport`、`generate_weekly_report`、导出项、`test/test_weekly_report.py` 和本文档条目。
- 文档更新：`DOMAIN_MODEL.md` 记录新的周报契约。

## A11-WEEKLY-002：周报同步 API

- 价值：让 UI、操作员或后续 Worker 能通过结构化 HTTP 请求生成周报闭环产物。
- 依赖：A11-WEEKLY-001 和现有 FastAPI app 接线。
- 允许修改范围：`metaos/app/api.py`、一个聚焦的 weekly report API 测试文件、任务/API/路线图文档。
- 禁止修改范围：周报聚合规则、数据库持久化、RQ worker、检索、视频渲染、根配置、`.vscode/` 和 `pyproject.toml`。
- 输入：`week_start`、`week_end`、`Intent`、可选 `DailySummary`、`ChancellorBriefing`、`ResearchAnswer`、`VideoExport` 列表。
- 输出：schema 合法的 `WeeklyReport` JSON。
- 接口：`POST /alpha/chancellor/weekly-reports`。
- 验收标准：接口返回带来源 ID、证据亮点、待处理行动和 MP4 回链的周报；非法周范围返回 HTTP 400；请求和响应均通过 Pydantic schema 校验。
- 测试命令：`python -m pytest test/test_alpha_weekly_report_api.py`。
- 回滚方式：删除 `/alpha/chancellor/weekly-reports` 路由、请求 schema、测试文件和文档条目。
- 文档更新：`API_CONTRACTS.md` 和 `ROADMAP.md` 记录同步 API 接线状态。

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
