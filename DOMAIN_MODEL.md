# MetaOS Alpha 领域模型

本文档是阶段0领域模型设计，不代表代码已经实现。

## 命名约定

- 所有业务对象必须有 `id`。
- 新增稳定底座对象必须区分 `id` 和 `stable_id`。
- 时间字段使用 UTC 存储。
- 模型输出对象必须记录 `schema_version`。
- Prompt 驱动对象必须记录 `prompt_version`。
- 索引相关对象必须记录 `index_version`。

## 用户主权层

### CognitiveConstitution

用户认知宪法。

字段：

- `id`
- `version`
- `principles`
- `decision_rules`
- `attention_rules`
- `not_to_do_defaults`
- `risk_preferences`
- `created_at`
- `updated_at`

### Intent

阶段性意图。

字段：

- `id`
- `title`
- `description`
- `horizon`
- `status`
- `priority`
- `success_criteria`
- `constraints`
- `constitution_id`
- `created_at`
- `updated_at`

状态：

- `draft`
- `active`
- `paused`
- `completed`
- `abandoned`

### CurrentRole

当前角色。

字段：

- `id`
- `name`
- `responsibilities`
- `allowed_focus`
- `forbidden_focus`
- `active_from`
- `active_to`

### AttentionBudget

注意力预算。

字段：

- `id`
- `date`
- `total_minutes`
- `research_minutes`
- `build_minutes`
- `review_minutes`
- `content_minutes`
- `hard_limits`

### NotToDoItem

不做清单。

字段：

- `id`
- `title`
- `reason`
- `scope`
- `active`
- `expires_at`
- `related_intent_id`

A1-SOV-001 实现说明：

- 用户主权层 Schema 位于 `metaos/sovereignty/schemas.py`。
- `Intent.status` 使用 `draft`、`active`、`paused`、`completed`、`abandoned`。
- `Intent.horizon` 使用 `day`、`week`、`month`、`quarter`、`year`、`project`。
- `AttentionBudget` 会校验已分配分钟数不得超过 `total_minutes`。
- `CurrentRole` 会校验 `active_to` 晚于 `active_from`。
- `NotToDoItem` 在 `scope=intent` 时必须提供 `related_intent_id`。

## 每日认知账本

### DailyPlan

字段：

- `id`
- `date`
- `intent_id`
- `role_id`
- `focus_items`
- `deferred_items`
- `ignored_items`
- `budget_id`

### WorkEvent

字段：

- `id`
- `date`
- `event_type`
- `title`
- `description`
- `source`
- `source_ref`
- `started_at`
- `ended_at`
- `related_intent_id`

来源：

- `manual`
- `git_commit`
- `markdown_change`
- `research_task`
- `system`

### Advice

字段：

- `id`
- `source`
- `advisor`
- `content`
- `evidence`
- `valid_until`
- `accepted_status`

### Decision

字段：

- `id`
- `title`
- `context`
- `options`
- `chosen_option`
- `reasoning`
- `evidence_links`
- `reversibility`
- `decided_at`

### Action

字段：

- `id`
- `title`
- `description`
- `status`
- `owner`
- `due_at`
- `source_type`
- `source_id`
- `intent_id`
- `review_id`

状态：

- `proposed`
- `accepted`
- `in_progress`
- `done`
- `canceled`
- `no_action`

### AttentionDrift

字段：

- `id`
- `date`
- `trigger`
- `description`
- `cost_minutes`
- `detected_by`
- `countermeasure`

### DailyReview

字段：

- `id`
- `date`
- `facts`
- `judgments`
- `reflections`
- `actions_done`
- `actions_missed`
- `lessons`

### DailySummary

字段：

- `id`
- `date`
- `source_review_id`
- `fact_summary`
- `judgment_summary`
- `reflection_summary`
- `action_summary`
- `citations`

A2-LEDGER-001 实现说明：

- 每日认知账本 Schema 位于 `metaos/ledger/schemas.py`。
- 已实现 `DailyPlan`、`WorkEvent`、`Advice`、`Decision`、`Action`、`AttentionDrift`、`DailyReview`、`DailySummary`。
- `WorkEvent.source` 使用 `manual`、`git_commit`、`markdown_change`、`research_task`、`system`。
- `Action.status` 使用 `proposed`、`accepted`、`in_progress`、`done`、`canceled`、`no_action`。
- `DailySummary` 显式区分 `fact_summary`、`judgment_summary`、`reflection_summary`、`action_summary`。
- A2-LEDGER-001 只定义 Schema，不实现 Git/Markdown 采集、持久化或 DailySummary 生成逻辑。

A2-LEDGER-003 实现说明：

- `DailySummary` 生成逻辑位于 `metaos/ledger/summary.py`。
- `generate_daily_summary(summary_date, review, work_events, decisions, actions)` 以同一天的账本记录为输入，返回通过 Schema 校验的 `DailySummary`。
- 生成结果保持事实、判断、反思、行动四类边界：`WorkEvent` 进入事实摘要，`Decision` 进入判断摘要，`DailyReview.reflections` 和 `lessons` 进入反思摘要，`Action` 与完成/遗漏项进入行动摘要。
- 当前实现为规则聚合，不调用模型，不写入数据库，不触发视频渲染。

## 知识底座

### Source

沿用现有 `Source`，Alpha 需要补充：

- `stable_id`
- `source_scope`
- `source_owner`
- `license`
- `trust_level`

### DocumentVersion

字段：

- `id`
- `stable_id`
- `source_id`
- `asset_id`
- `version`
- `content_sha256`
- `structure_sha256`
- `title`
- `language`
- `created_at`

### Chunk

沿用现有 `Chunk`，Alpha 需要补充：

- `stable_id`
- `document_version_id`
- `parent_chunk_id`
- `previous_chunk_id`
- `next_chunk_id`
- `chunker_version`
- `index_version`
- `token_count`
- `section_path`
- `position`

A4-KB-001 实现说明：

- 文档版本与稳定 Chunk ID 标准化位于 `metaos/knowledge/versioning.py`。
- `DocumentVersion` 记录 `stable_id`、`source_stable_id`、内容与结构哈希、parser/chunker/index 版本。
- `StableChunk` 记录稳定 `id`、`document_version_id`、父块、前后块、token 估算、section path、position 和原文 `Citation`。
- `standardize_document(source, asset, document)` 复用现有 chunker 输出文本块，但重新计算稳定 ID；相同文档重复标准化得到相同 ID，局部内容变化只改变相关 chunk 的稳定 ID。
- 当前任务不替换现有 `KnowledgeService.create_from_document`、不删除旧 chunks、不重建 Chroma 索引。

### Entity

字段：

- `id`
- `stable_id`
- `name`
- `type`
- `description`
- `source_count`

类型示例：

- `person`
- `organization`
- `place`
- `concept`
- `work`
- `project`
- `event`

### EntityAlias

字段：

- `id`
- `entity_id`
- `alias`
- `language`
- `confidence`

### Event

字段：

- `id`
- `stable_id`
- `title`
- `description`
- `event_time`
- `time_precision`
- `participants`
- `location`
- `citations`

### Claim

字段：

- `id`
- `stable_id`
- `claim_text`
- `claim_type`
- `stance`
- `confidence`
- `source_id`
- `citations`

类型：

- `fact`
- `interpretation`
- `prediction`
- `recommendation`
- `self_reflection`

### Relationship

字段：

- `id`
- `subject_id`
- `predicate`
- `object_id`
- `qualifiers`
- `citations`
- `confidence`

### Citation

Alpha citation 必须支持：

- `source_id`
- `document_version_id`
- `asset_id`
- `chunk_id`
- `file_path`
- `page`
- `timestamp_seconds`
- `start_offset`
- `end_offset`
- `excerpt`
- `quote_hash`

### EvidenceLink

字段：

- `id`
- `source_object_type`
- `source_object_id`
- `target_object_type`
- `target_object_id`
- `support_type`
- `citation_id`
- `confidence`

支持类型：

- `supports`
- `contradicts`
- `mentions`
- `depends_on`
- `weak_support`

A8-KB-002 实现说明：

- 结构化知识底座首版位于 `metaos/knowledge/foundation.py`。
- 已实现 `Entity`、`EntityAlias`、`Event`、`Claim`、`EvidenceLink`、`KnowledgeSummary` 与 `KnowledgeFoundation`。
- `extract_knowledge_foundation(standardized_document)` 从标准化 chunks 中解析显式标注行：`Entity:`、`Alias:`、`Event:`、`Claim:`、`Summary:`。
- 事件、主张、摘要和证据链接都会保留原始 chunk 的 `Citation`，满足回链原文要求。
- 当前任务不引入 NER、指代消解、微调或 PyTorch Model Worker；后续必须由评测结果驱动升级。

## 议题编译

### ResearchTask

字段：

- `id`
- `question`
- `intent_id`
- `role_id`
- `operator`
- `theme_spec_id`
- `scope_id`
- `status`
- `created_at`

状态：

- `draft`
- `planned`
- `running`
- `audit_required`
- `completed`
- `failed`

### CognitiveOperator

枚举：

- `fact_lookup`
- `enumerate_pattern`
- `compare`
- `causal_analysis`
- `decision_support`
- `reflection`
- `recommend`

### ThemeSpec

运行时主题规格。

字段：

- `id`
- `task_id`
- `theme_name`
- `theme_description`
- `key_terms`
- `synonyms`
- `positive_patterns`
- `negative_patterns`
- `required_dimensions`
- `excluded_dimensions`
- `evidence_preferences`

关键约束：

- `ThemeSpec` 是数据，不是代码分支。
- 新主题只新增数据实例。

### EvidenceRequirement

字段：

- `id`
- `task_id`
- `requirement_type`
- `description`
- `required_count`
- `source_constraints`
- `freshness`
- `counterevidence_required`

### ResearchScope

字段：

- `id`
- `task_id`
- `included_sources`
- `excluded_sources`
- `time_range`
- `entity_filters`
- `cost_limit`
- `depth`

### ResearchPlan

字段：

- `id`
- `task_id`
- `steps`
- `query_plan`
- `evidence_requirements`
- `stop_conditions`
- `prompt_version`

A6-COMPILER-001 实现说明：

- 议题编译 Schema 位于 `metaos/compiler/schemas.py`。
- 已实现 `ResearchTask`、`CognitiveOperator`、`ThemeSpec`、`EvidenceRequirement`、`ResearchScope`、`ResearchPlan` 与 `ResearchCompilation`。
- `CognitiveOperator` 包含 `fact_lookup`、`enumerate_pattern`、`compare`、`causal_analysis`、`decision_support`、`reflection`、`recommend`。
- `ThemeSpec` 保持运行时数据契约；“功高震主”“小人得志陷害忠良”“听信谗言”“功成身退”“角色转换失败”均可作为 `ThemeSpec` 实例表达，不需要新增 Python 分支。
- 当前任务不调用 LLM，不生成真实研究计划，不执行检索。

## 研究执行

### EvidenceCandidate

字段：

- `id`
- `task_id`
- `retrieval_run_id`
- `chunk_id`
- `claim_id`
- `citation`
- `score`
- `channel`
- `rank`

### EvidenceMatrixRow

字段：

- `id`
- `task_id`
- `claim_or_question`
- `supporting_evidence`
- `counter_evidence`
- `missing_evidence`
- `assessment`

A7-RESEARCH-001 实现说明：

- 研究执行器首版位于 `metaos/research/executor.py`。
- `build_evidence_matrix(compilation, candidates)` 接收 `ResearchCompilation` 与检索候选，输出 `ResearchExecutionDraft`。
- `EvidenceMatrixRow` 按 `EvidenceRequirement` 聚合 supporting evidence、counter evidence、missing evidence 和 assessment。
- 当前实现能检测支持证据数量不足和缺失反证；候选引用通过 `EvidenceCandidate.citation` 保留。
- 当前任务不生成最终 `ResearchAnswer`，不做御史台审计，不创建 ledger action。

### ResearchAnswer

字段：

- `id`
- `task_id`
- `fact_statements`
- `model_inferences`
- `disputed_views`
- `personal_reflections`
- `actions`
- `no_action_reason`
- `citations`
- `audit_report_id`

A7-RESEARCH-002 实现说明：

- 带引用回答草案位于 `metaos/research/answer.py`。
- `ResearchAnswer` 将输出分为 `fact_statements`、`model_inferences`、`disputed_views`、`personal_reflections`、`actions`、`no_action_reason` 和 `citations`。
- `AnswerStatement.source_status` 显式标记 `cited` 或 `uncited`，无来源推断不会伪装成事实。
- `draft_research_answer(...)` 可生成 ledger `Action(source_type=research_answer)`；若没有行动，则必须给出 `no_action_reason`。
- 当前任务不执行御史台审计，`audit_report_id` 保持可选。

## 御史台

### AuditReport

字段：

- `id`
- `task_id`
- `status`
- `citation_checks`
- `scope_checks`
- `counterevidence_checks`
- `completeness_checks`
- `bias_checks`
- `cost_checks`
- `required_fixes`
- `residual_risks`

状态：

- `passed`
- `passed_with_risk`
- `requires_revision`
- `failed`

A9-AUDIT-001 实现说明：

- 御史台引用与范围审计位于 `metaos/censorate/audit.py`。
- 已实现 `AuditReport`、`CitationAuditItem`、`ScopeAuditItem`、`AuditStatus` 与 `audit_research_answer(...)`。
- 审计会标记无引用陈述、引用不在证据矩阵中的陈述、来源超出 `ResearchScope.included_sources` 或命中 `excluded_sources` 的引用。
- 当前任务不检查反证完整性、确认偏误或研究成本；这些由 A9-AUDIT-002 实现。

## 推荐与宰相

### MinistryReport

字段：

- `id`
- `date`
- `ministry`
- `items`
- `empty_reason`

部门：

- `technology`
- `cognition`
- `business`

### RecommendationItem

字段：

- `id`
- `ministry`
- `title`
- `reason`
- `intent_alignment`
- `reading_cost_minutes`
- `cost_of_ignoring`
- `suggested_action`
- `valid_until`
- `citations`

### ChancellorBriefing

字段：

- `id`
- `date`
- `intent_id`
- `role_id`
- `today_focus`
- `deferred_items`
- `ignored_items`
- `cognitive_traps`
- `source_research_ids`
- `source_review_id`

## 内容工坊

### EpisodeSpec

字段：

- `id`
- `daily_summary_id`
- `title`
- `angle`
- `facts`
- `judgments`
- `reflections`
- `actions`
- `citations`
- `review_status`
- `reviewer_id`
- `reviewed_at`
- `review_notes`
- `created_at`
- `updated_at`

A3-WORKSHOP-001 实现说明：

- 内容工坊 Schema 位于 `metaos/workshop/schemas.py`。
- 已实现 `EpisodeSpec` 与 `EpisodeReviewStatus`。
- `review_status=approved`、`changes_requested`、`rejected` 属于终态审核状态，必须提供 `reviewer_id` 和 `reviewed_at`。
- `assert_episode_can_export(episode)` 作为正式视频导出的 Schema 级门禁：只有 `approved` 的 Episode 才允许导出。
- 当前任务只定义 Episode 规格和审核状态，不生成脚本、旁白、字幕、图卡或 MP4。

### VideoExport

字段：

- `id`
- `episode_spec_id`
- `script_path`
- `voiceover_path`
- `subtitle_path`
- `cards_path`
- `remotion_props_path`
- `mp4_path`
- `render_status`
- `review_record_id`
- `error`
- `created_at`
- `updated_at`

A3-WORKSHOP-002 实现说明：

- 内容工坊资产生成与本地渲染入口位于 `metaos/workshop/service.py`。
- `generate_episode_assets(episode, output_dir)` 生成可审核的脚本、旁白文本、SRT 字幕、图卡 JSON 和 Remotion props JSON。
- `review_episode(...)` 生成带审核元数据的新 `EpisodeSpec`。
- `render_episode_video(...)` 使用 FFmpeg 生成最小 MP4；未审核、FFmpeg 不可用或渲染失败时返回 `render_status=failed` 和 `error`。
- 当前任务不接入 FastAPI、RQ 或真实 TTS 音频引擎；这些入口保持在后续任务中接线。
