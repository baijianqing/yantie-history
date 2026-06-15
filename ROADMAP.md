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

## A11-CLOSE-001 status

- Added a service-level Alpha closure regression test that runs the chain from sovereignty records to runtime issue compilation, standardized knowledge, full-text plus dense-channel RRF retrieval, evidence matrix construction, cited answer drafting, Censorate audits, limited ministry reports, Chancellor briefing, DailySummary, reviewable EpisodeSpec, human approval, and MP4 export.
- The closure test verifies that new themes are data-driven through ThemeSpec and do not require topic-specific Python branches, re-chunking, or index rebuilds.
- Remaining outer orchestration such as durable HTTP/RQ job wiring and weekly report packaging stays in the documented API contracts and should be implemented as separate narrow tasks.
- Test command: `python -m pytest test/test_alpha_end_to_end.py`.

## A5-SEARCH-003 status

- Added a vector retrieval adapter that converts existing Chroma/Ollama `RetrievalService.search` results into Alpha `SearchCandidate` objects with citation back-links and metadata filters.
- Dense vector results can now enter RRF fusion through the same evidence candidate path as full-text results.
- Test command: `python -m pytest test/test_vector_search.py`.

## A5-SEARCH-004 status

- Added `hybrid_search` as the Alpha evidence retrieval entrypoint for full-text, vector, metadata-filtered, RRF-fused results.
- Research execution can now consume one fused `EvidenceCandidate` list while preserving per-channel ranks, scores, and citation back-links.
- Test command: `python -m pytest test/test_hybrid_search.py`.

## A7-RESEARCH-003 status

- Added plan-driven candidate recall for `ResearchCompilation`, tagging candidates with requirement id, requirement type, query, and inferred support/counter stance before evidence matrix construction.
- Research execution now has a service entrypoint that can call hybrid search and return a `ResearchExecutionDraft` instead of requiring pre-tagged candidates.
- Test command: `python -m pytest test/test_research_service.py`.

## A7-RESEARCH-004 status

- Added `ResearchExecutionReport` with execution version, retrieval runs, progress events, recalled candidates, and evidence matrix output.
- Research execution now has structured data for progress display, logs, and later RQ/API job persistence without changing answer drafting or audit policy.
- Test command: `python -m pytest test/test_research_service.py`.

## A11-OPS-001 status

- Added `JobRepository.retry_failed` to reset failed jobs to pending while appending an auditable `result.retry_history` entry.
- This provides the tested retry-state foundation for later RQ/API re-enqueue wiring without changing worker behavior in this task.
- Test command: `python -m pytest test/test_job_repository_retry.py`.

## A11-OPS-002 status

- Added `enqueue_retry_job` to requeue supported failed jobs through the original RQ task path while keeping the same job id and retry history.
- Retry dispatch is covered for RAG, OCR PDF-page retries, unsupported job types, and non-failed jobs without requiring a live Redis instance in tests.
- Test command: `python -m pytest test/test_queueing_retry.py`.

## A5-SEARCH-005 status

- Added `POST /alpha/search` to expose hybrid full-text/vector/RRF evidence retrieval through FastAPI with metadata filters and citation back-links.
- The endpoint supports `include_vector=false` so tests and lightweight calls can run full-text-only without constructing vector retrieval.
- Test command: `python -m pytest test/test_alpha_search_api.py`.

## A6-COMPILER-003 status

- Added `POST /alpha/research/compile` to expose runtime IssueCompiler output through FastAPI.
- The endpoint returns schema-validated `ResearchCompilation` JSON and rejects invalid provider output with HTTP 400.
- Test command: `python -m pytest test/test_alpha_research_compile_api.py`.

## A11-OPS-003 status

- Added `POST /jobs/{job_id}/retry` to expose failed-job retry through FastAPI.
- The route maps missing jobs to 404 and invalid retry state or Redis enqueue failure to 400.
- Test command: `python -m pytest test/test_job_retry_api.py`.
