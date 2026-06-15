# MetaOS Alpha API 契约

本文档描述 Alpha 目标 API。标注“现有”的接口已在当前 FastAPI 中存在；标注“目标”的接口仅为阶段0契约设计。

## 通用规则

- 请求和响应使用 JSON。
- 所有模型输出必须通过 Pydantic Schema 校验。
- 所有写接口返回创建或更新后的资源。
- 所有后台任务返回 `job_id` 和资源引用。
- 所有研究输出必须包含引用或明确的证据不足标记。
- 所有 Alpha API 错误返回统一结构：

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## 现有 API

### `GET /health`

用途：健康检查。

响应：

```json
{
  "status": "ok",
  "version": "string"
}
```

### `GET /workspace`

用途：返回本地工作区路径。

### `GET /runtime/status`

用途：返回 Redis、队列、Worker 状态。

### `GET /jobs`

用途：列出任务。

查询参数：

- `limit`

### `GET /jobs/{job_id}`

用途：读取任务状态。

### `POST /jobs/{job_id}/retry`

Purpose: retry a failed job through its original RQ queue and task path.

Response: `Job` JSON with `status=pending`, preserved `id`, and `result.retry_history`.

Errors:
- `404` when the job id does not exist.
- `400` when the job is not failed, the job type cannot be retried, or Redis enqueue fails.

### `POST /ingest/documents`

用途：上传文件并提交入库任务。

输入：multipart file。

输出：

- `job`
- `source`
- `asset`

### `GET /knowledge`

用途：列出知识条目。

### `GET /knowledge/{item_id}/chunks`

用途：列出知识条目的 chunks。

### `DELETE /knowledge/{item_id}`

用途：删除知识条目、chunks 和 Chroma 索引。

### `POST /knowledge/{item_id}/chunks/rebuild`

用途：提交 chunk 重建任务。

注意：Alpha 后新主题不得调用该能力作为研究前置条件。

### `POST /knowledge/{item_id}/index`

用途：同步索引单个知识条目。

### `POST /knowledge/{item_id}/index/jobs`

用途：异步索引单个知识条目。

### `POST /index/rebuild`

用途：同步重建或续建全部索引。

注意：Alpha 后新主题不得调用该能力作为研究前置条件。

### `POST /index/rebuild/jobs`

用途：异步重建或续建全部索引。

### `GET /index/status`

用途：查看向量索引状态。

### `GET /search`

用途：向量检索。

查询参数：

- `q`
- `top_k`

### `POST /rag/answer/jobs`

用途：提交单轮 RAG 问答任务。

请求：

```json
{
  "question": "string",
  "top_k": 5
}
```

## 目标 API：用户主权层

### `POST /alpha/constitution`

创建或更新认知宪法。

请求：

```json
{
  "principles": ["string"],
  "decision_rules": ["string"],
  "attention_rules": ["string"],
  "not_to_do_defaults": ["string"],
  "risk_preferences": {}
}
```

响应：`CognitiveConstitution`。

### `POST /alpha/intents`

创建意图。

请求：

```json
{
  "title": "string",
  "description": "string",
  "horizon": "quarter",
  "priority": 1,
  "success_criteria": ["string"],
  "constraints": ["string"]
}
```

响应：`Intent`。

### `GET /alpha/intents/active`

返回当前 active 意图列表。

### `POST /alpha/current-role`

设置当前角色。

### `POST /alpha/attention-budgets`

创建每日注意力预算。

### `POST /alpha/not-to-do`

创建不做清单项。

A1-SOV-003 implementation note:

- `POST /alpha/constitution` is implemented and persists `CognitiveConstitution`.
- `GET /alpha/constitution` is implemented for local review.
- `POST /alpha/intents`, `GET /alpha/intents`, `GET /alpha/intents/active`, and `POST /alpha/intents/{intent_id}/activate` are implemented.
- `POST /alpha/current-role` and `GET /alpha/current-role` are implemented; setting a current role closes other open roles.
- `POST /alpha/attention-budgets` and `GET /alpha/attention-budgets` are implemented.
- `POST /alpha/not-to-do`, `GET /alpha/not-to-do`, and `PATCH /alpha/not-to-do/{item_id}/active` are implemented.
- These endpoints only expose the sovereignty layer. They do not modify RAG, retrieval, workers, Streamlit, or runtime knowledge data.

## 目标 API：每日认知账本

### `POST /alpha/daily-plans`

创建今日计划。

### `POST /alpha/work-events`

记录工作事件。

### `POST /alpha/work-events/collect/git/jobs`

提交 Git commit 采集任务。

请求：

```json
{
  "repo_path": "string",
  "date_from": "2026-06-15",
  "date_to": "2026-06-15"
}
```

### `POST /alpha/work-events/collect/markdown/jobs`

提交 Markdown 变更采集任务。

A2-LEDGER-002 implementation note:

- Collector-level support is implemented in `metaos/ledger/collectors.py`.
- `GitCommitCollectionPayload` accepts `repo_path`, `date_from`, `date_to`, and optional `related_intent_id`.
- `MarkdownChangeCollectionPayload` accepts `markdown_dir`, `date_from`, `date_to`, optional `related_intent_id`, and Markdown extensions.
- `collect_git_commits(...)` and `collect_markdown_changes(...)` return `WorkEvent` lists.
- This task does not expose background jobs or write ledger records yet; the `/alpha/work-events/collect/*/jobs` endpoints remain target API contracts for a later task.

### `POST /alpha/decisions`

记录决策。

### `POST /alpha/actions`

创建行动。

### `PATCH /alpha/actions/{action_id}`

更新行动状态。

### `POST /alpha/daily-reviews`

创建每日复盘。

### `POST /alpha/daily-summaries/jobs`

生成 DailySummary。

## 目标 API：知识底座

### `GET /alpha/sources/{source_id}/versions`

列出文档版本。

### `POST /alpha/document-versions`

注册标准化文档版本。

### `GET /alpha/chunks/{chunk_id}/citation`

返回 chunk 的可审计引用。

### `GET /alpha/entities`

按名称、类型或 alias 查询实体。

### `GET /alpha/claims`

按主题、实体、来源或 stance 查询主张。

## 目标 API：多路检索

### `POST /alpha/search`

请求：

```json
{
  "query": "string",
  "theme_spec": {},
  "filters": {
    "source_ids": [],
    "entity_ids": [],
    "date_range": null,
    "categories": []
  },
  "top_k": 20,
  "channels": ["vector", "full_text"],
  "rrf": {
    "enabled": true,
    "k": 60
  },
  "rerank": {
    "enabled": false
  }
}
```

响应：

```json
{
  "retrieval_run_id": "string",
  "results": [
    {
      "chunk_id": "string",
      "score": 0.0,
      "channel_scores": {},
      "citation": {}
    }
  ]
}
```

A5-SEARCH-002 implementation note:

- RRF fusion support is implemented in `metaos/search/fusion.py`.
- `SearchCandidate` is the channel-neutral input contract for vector, full-text, and future rerank candidates.
- `rrf_fuse({"vector": [...], "full_text": [...]}, filters, top_k, k)` applies metadata filters before fusion, computes reciprocal-rank scores, and returns `EvidenceCandidate` results.
- `EvidenceCandidate` preserves `citation`, `channel_ranks`, and `channel_scores`.
- The `/alpha/search` HTTP endpoint is implemented in `metaos/app/api.py`.
- It returns fused `EvidenceCandidate` payloads from current chunks, optional dense vector retrieval, metadata filters, and RRF ranking.
- It can disable the vector channel with `include_vector=false` for deterministic full-text-only calls.

## 目标 API：议题编译器

### `POST /alpha/research/compile`

请求：

```json
{
  "question": "string",
  "intent_id": "string",
  "role_id": "string",
  "attention_budget_id": "string"
}
```

响应：

```json
{
  "research_task": {},
  "operator": "causal_analysis",
  "theme_spec": {},
  "evidence_requirements": [],
  "research_scope": {},
  "research_plan": {}
}
```

验收要求：

- 输入五个不同主题时，使用同一套代码生成不同 `ThemeSpec`。
- 不新增主题分支。

A6-COMPILER-002 implementation note:

- Runtime compiler service support is implemented in `metaos/compiler/service.py`.
- `IssueCompiler` accepts a `CompilerModelProvider`; tests use a fake provider that returns structured JSON.
- `CompileResearchRequest` is converted into a prompt payload with allowed operators and required output contracts.
- Provider output is converted into `ResearchCompilation` and validated by Pydantic schemas.
- The five required themes compile through the same `IssueCompiler.compile(...)` code path; theme differences live in `ThemeSpec` data.
- The `/alpha/research/compile` HTTP endpoint is implemented in `metaos/app/api.py`.
- It runs the same `IssueCompiler.compile(...)` path and returns schema-validated `ResearchCompilation` JSON.
- Invalid structured provider output is rejected with HTTP 400.

## 目标 API：研究执行器

### `POST /alpha/research/tasks`

创建研究任务。

### `POST /alpha/research/tasks/{task_id}/run/jobs`

提交研究执行任务。

### `GET /alpha/research/tasks/{task_id}`

读取研究任务状态。

### `GET /alpha/research/tasks/{task_id}/evidence-matrix`

读取证据矩阵。

### `GET /alpha/research/tasks/{task_id}/answer`

读取最终带引用回答。

响应必须区分：

```json
{
  "fact_statements": [],
  "model_inferences": [],
  "disputed_views": [],
  "personal_reflections": [],
  "actions": [],
  "no_action_reason": null,
  "citations": []
}
```

A7-RESEARCH-002 implementation note:

- Research answer drafting is implemented in `metaos/research/answer.py`.
- `ResearchAnswer` separates facts, model inferences, disputed views, personal reflections, actions, no-action reason, and citations.
- Each `AnswerStatement` carries `source_status=cited|uncited`.
- `draft_research_answer(...)` creates a ledger `Action` when `action_title` is provided, or requires/sets `no_action_reason` when no action is proposed.
- This task does not perform censorate audit; audited final answer gating remains a later task.

## 目标 API：御史台

### `POST /alpha/audit/research/{task_id}/jobs`

提交研究审计任务。

### `GET /alpha/audit/reports/{audit_report_id}`

读取审计报告。

## 目标 API：三部推荐

### `POST /alpha/ministries/daily/jobs`

生成每日三部推荐。

请求：

```json
{
  "date": "2026-06-15",
  "intent_id": "string",
  "attention_budget_id": "string"
}
```

响应任务完成后必须满足：

- 每部最多 3 条。
- 总数最多 5 条。
- 可以为空，并给出“今日无事上奏”。

A10-MIN-001 implementation note:

- Limited ministry recommendation contracts are implemented in `metaos/ministries/schemas.py`.
- Alpha ministries are restricted to `technology`, `cognition`, and `business`.
- `generate_ministry_reports(...)` filters candidates by current `Intent`, obeys `AttentionBudget`, caps each ministry at 3 items, caps all items at 5, and returns `empty_reason="今日无事上奏"` for empty ministries.
- The `/alpha/ministries/daily/jobs` HTTP endpoint remains a target API contract for a later wiring task.

## 目标 API：宰相

### `POST /alpha/chancellor/daily/jobs`

生成今日简报。

### `POST /alpha/chancellor/daily-briefings`

同步生成今日简报。

请求：

```json
{
  "date": "2026-06-16",
  "intent": {},
  "role": {},
  "attention_budget": {},
  "daily_review": {},
  "research_answers": [],
  "ministry_reports": []
}
```

### `GET /alpha/chancellor/briefings/{briefing_id}`

读取宰相简报。

响应：

```json
{
  "today_focus": [],
  "deferred_items": [],
  "ignored_items": [],
  "cognitive_traps": []
}
```

### `POST /alpha/chancellor/weekly-reports`

同步生成周报打包结果。

请求：

```json
{
  "week_start": "2026-06-15",
  "week_end": "2026-06-21",
  "intent": {},
  "daily_summaries": [],
  "briefings": [],
  "research_answers": [],
  "video_exports": []
}
```

响应：

```json
{
  "id": "weekly_...",
  "week_start": "2026-06-15",
  "week_end": "2026-06-21",
  "intent_id": "intent_alpha",
  "daily_summary_ids": [],
  "briefing_ids": [],
  "research_answer_ids": [],
  "video_export_ids": [],
  "completed_actions": [],
  "pending_actions": [],
  "evidence_highlights": [],
  "disputed_or_risk_items": [],
  "cognitive_traps": [],
  "content_exports": [],
  "next_week_focus": []
}
```

A11-CHAN-001 implementation note:

- Chancellor briefing support is implemented in `metaos/chancellor/schemas.py`.
- `generate_chancellor_briefing(...)` combines current `Intent`, optional `CurrentRole`, `AttentionBudget`, optional `DailyReview`, `ResearchAnswer` items, and `MinistryReport` items.
- The output includes today focus, deferred items, ignored items, cognitive trap reminders, source research ids, and source review id.
- The `/alpha/chancellor/daily/jobs` HTTP endpoint remains a target API contract for a later wiring task.

A11-CHAN-002 implementation note:

- `POST /alpha/chancellor/daily-briefings` is implemented as a synchronous schema-validated API in `metaos/app/api.py`.
- The endpoint calls `generate_chancellor_briefing(...)` with caller-provided structured records and returns a `ChancellorBriefing` JSON payload.
- The endpoint does not create a durable RQ job or persist briefings; durable job orchestration remains a later task.

A11-WEEKLY-002 implementation note:

- `POST /alpha/chancellor/weekly-reports` is implemented as a synchronous schema-validated API in `metaos/app/api.py`.
- The endpoint calls `generate_weekly_report(...)` with caller-provided structured records and returns a `WeeklyReport` JSON payload.
- Invalid week ranges are mapped to HTTP 400.
- The endpoint does not create a durable RQ job or persist reports; durable job orchestration remains a later task.

## 目标 API：内容工坊

### `POST /alpha/workshop/episodes/jobs`

从 `DailySummary` 生成 `EpisodeSpec`。

### `POST /alpha/workshop/episodes/{episode_id}/render/jobs`

提交视频渲染任务。

### `PATCH /alpha/workshop/episodes/{episode_id}/review`

人工审核 Episode。

### `GET /alpha/workshop/video-exports/{export_id}`

读取 MP4 导出结果。

A3-WORKSHOP-002 implementation note:

- Workshop service-level support is implemented in `metaos/workshop/service.py`.
- `generate_episode_assets(...)` writes script, voiceover text, SRT subtitles, visual card JSON, and Remotion props JSON for human review.
- `review_episode(...)` records structured human review state on `EpisodeSpec`.
- `render_episode_video(...)` returns a `VideoExport` with `render_status=succeeded` and `mp4_path`, or `render_status=failed` and `error`.
- The HTTP endpoints above remain target API contracts for a later API/RQ wiring task.
