# MetaOS Alpha 路线图

## 阶段0：仓库审计和架构文档

目标：

- 不改业务代码。
- 审计现有架构和运行数据。
- 文档化 Alpha 范围、业务架构、技术架构、领域模型、API 契约、任务索引和协作规则。

交付：

- `CURRENT_ARCHITECTURE_AUDIT.md`
- `AGENTS.md`
- `ALPHA_SCOPE.md`
- `BUSINESS_ARCHITECTURE.md`
- `TECHNICAL_ARCHITECTURE.md`
- `DOMAIN_MODEL.md`
- `API_CONTRACTS.md`
- `ROADMAP.md`
- `TASK_INDEX.md`

完成后等待人工审查。

## 阶段1：用户主权层

目标：

- 实现 `CognitiveConstitution`。
- 实现 `Intent`。
- 实现 `CurrentRole`。
- 实现 `AttentionBudget`。
- 实现 `NotToDoItem`。

验收：

- 可创建、读取、更新当前意图和角色。
- 可设置注意力预算和不做清单。
- 后续研究任务能关联当前意图。

## 阶段2：每日认知账本

目标：

- 实现 `DailyPlan`、`WorkEvent`、`Advice`、`Decision`、`Action`、`AttentionDrift`、`DailyReview`。
- 支持采集 Git 提交。
- 支持采集 Markdown 变更。
- 生成 `DailySummary`。

验收：

- 每日记录可回放。
- `DailySummary` 区分事实、判断、反思和行动。

## 阶段3：内容工坊

目标：

- 实现 `EpisodeSpec`。
- 生成脚本、旁白、字幕、图卡。
- 接入 Remotion 模板和 FFmpeg 渲染。
- 支持人工审核和 MP4 导出。

验收：

- 从 `DailySummary` 到可审核视频闭环可运行。
- 未审核不得导出正式 MP4。

## 阶段4：知识底座标准化

目标：

- 标准化 `Source`、`DocumentVersion`、`Chunk`。
- 引入稳定 ID。
- 支持父子块、前后块。
- 引入索引版本。
- 支持增量入库。

验收：

- 新主题不需要重切块。
- 文档更新只影响变更范围。
- chunk 可回链原文位置。

## 阶段5：检索增强

目标：

- 实现全文检索。
- 保留现有向量检索。
- 实现元数据过滤。
- 实现 RRF 融合。
- 实现引用回链。
- 建立回归评测。

验收：

- 多路检索结果可解释。
- 每个结果可回链原文。
- 检索回归测试可重复运行。

## 阶段6：议题编译器和认知算子

目标：

- 把自然语言问题转换为 `ResearchTask`、`CognitiveOperator`、`ThemeSpec`、`EvidenceRequirement`、`ResearchScope`。
- 实现首版认知算子。

验证主题：

- 功高震主。
- 小人得志陷害忠良。
- 听信谗言。
- 功成身退。
- 角色转换失败。

验收：

- 五个主题共用同一套代码。
- 新主题只改变 `ThemeSpec` 数据。

## 阶段7：研究执行器

目标：

- 候选召回。
- 证据矩阵。
- 缺失证据检测。
- 补充检索。
- 反证。
- 评分。
- 分类。
- 带引用回答。
- 进度展示。

验收：

- 研究结果区分事实、推断、争议、反思。
- 无来源结论被明确标记。
- 研究结果生成 Action 或“不行动”。

## 阶段8：实体、事件、主张和多级摘要

目标：

- 实现 `Entity`、`Alias`、`Event`、`Claim`、`EvidenceLink`。
- 实现多级摘要。

验收：

- 研究可按实体、事件和主张组织证据。
- 主张支持证据和反证链接。

## 阶段9：御史台

目标：

- 检查引用。
- 检查范围。
- 检查反证。
- 检查证据完整性。
- 检查确认偏误。
- 检查研究成本。

验收：

- 研究回答必须经过审计或明确标记未审计。
- 审计失败阻止进入最终结论。

## 阶段10：三部有限推荐

目标：

- 实现技术部、认知部、商业部。
- 每部每日最多 3 条，整体最多 5 条。
- 支持“今日无事上奏”。

验收：

- 推荐不形成无限信息流。
- 每条推荐有目标关联、阅读成本、不读损失、建议行动和有效期。

## 阶段11：宰相和完整闭环

目标：

- 结合当前 `Intent`、角色、时间预算和研究结果输出今日重点。
- 输出暂缓事项、应忽略事项和认知陷阱提醒。
- 形成季度意图到周报的完整闭环。

验收：

- 季度意图 -> 今日重点 -> 研究/开发 -> 证据与结论 -> 行动 -> 每日复盘 -> 视频 -> 每周报告可运行。

## 已完成任务状态

### A5-SEARCH-003：向量检索适配器

- 已新增向量检索适配器，把现有 Chroma/Ollama `RetrievalService.search` 结果转换为 Alpha `SearchCandidate`，并保留引用回链和元数据过滤能力。
- 稠密向量结果现在可以和全文检索结果进入同一条 RRF 融合链路。
- 测试命令：`python -m pytest test/test_vector_search.py`。

### A5-SEARCH-004：混合证据检索入口

- 已新增 `hybrid_search`，作为 Alpha 证据检索的统一入口，支持全文、向量、元数据过滤和 RRF 融合。
- 研究执行器现在可以消费统一的 `EvidenceCandidate` 列表，同时保留各检索通道的排名、分数和引用回链。
- 测试命令：`python -m pytest test/test_hybrid_search.py`。

### A5-SEARCH-005：Alpha 搜索接口

- 已新增 `POST /alpha/search`，通过 FastAPI 暴露全文、向量和 RRF 融合后的证据检索结果，并支持元数据过滤和引用回链。
- 接口支持 `include_vector=false`，测试和轻量调用可以在不构造向量检索的情况下只走全文检索。
- 测试命令：`python -m pytest test/test_alpha_search_api.py`。

### A6-COMPILER-003：Alpha 研究编译接口

- 已新增 `POST /alpha/research/compile`，通过 FastAPI 暴露运行时 IssueCompiler 输出。
- 接口返回通过 schema 校验的 `ResearchCompilation` JSON，并把无效 provider 输出映射为 HTTP 400。
- 测试命令：`python -m pytest test/test_alpha_research_compile_api.py`。

### A7-RESEARCH-003：研究候选证据召回服务

- 已新增面向 `ResearchCompilation` 的计划驱动候选召回，在证据矩阵构建前为候选证据标记需求 ID、需求类型、查询和支持/反驳立场。
- 研究执行器现在可以调用混合检索并返回 `ResearchExecutionDraft`，不再要求调用方预先标注候选证据。
- 测试命令：`python -m pytest test/test_research_service.py`。

### A7-RESEARCH-004：研究执行轨迹

- 已新增 `ResearchExecutionReport`，记录执行版本、检索运行记录、进度事件、召回候选和证据矩阵输出。
- 研究执行现在具备面向进度展示、日志和后续 RQ/API 持久化的结构化数据，同时不改变答案起草和审计策略。
- 测试命令：`python -m pytest test/test_research_service.py`。

### A11-OPS-001：任务重试元数据

- 已新增 `JobRepository.retry_failed`，可把失败任务重置为 pending，并追加可审计的 `result.retry_history` 记录。
- 这为后续 RQ/API 重新入队提供了已测试的重试状态基础，不改变当前 worker 行为。
- 测试命令：`python -m pytest test/test_job_repository_retry.py`。

### A11-OPS-002：RQ 重试入队

- 已新增 `enqueue_retry_job`，可通过原始 RQ 任务路径重新入队支持重试的失败任务，同时保留原 job id 和重试历史。
- 重试分发已覆盖 RAG、OCR PDF 分页重试、不支持的任务类型和非失败任务，并且测试不依赖真实 Redis。
- 测试命令：`python -m pytest test/test_queueing_retry.py`。

### A11-OPS-003：任务重试接口

- 已新增 `POST /jobs/{job_id}/retry`，通过 FastAPI 暴露失败任务重试能力。
- 路由把不存在的任务映射为 404，把无效重试状态或 Redis 入队失败映射为 400。
- 测试命令：`python -m pytest test/test_job_retry_api.py`。

### A11-CLOSE-001：完整闭环验收

- 已新增服务级 Alpha 闭环回归测试，覆盖从主权记录、运行时议题编译、标准化知识、全文与向量 RRF 检索、证据矩阵、带引用答案、御史台审计、有限推荐、宰相简报、DailySummary、可审核 EpisodeSpec、人工批准到 MP4 导出的完整链路。
- 闭环测试确认新主题由 `ThemeSpec` 数据驱动，不需要新增主题专用 Python 分支、重新分块或重建索引。
- 持久化 HTTP/RQ 编排、周报打包等外围能力仍保留在 API 契约中，后续应作为独立窄任务实现。
- 测试命令：`python -m pytest test/test_alpha_end_to_end.py`。
