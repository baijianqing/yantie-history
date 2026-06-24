# MetaOS Alpha API 契约

状态：Core Alpha 目标 API 契约冻结候选

任务标识：`A0-DOC-004-R1`

依赖：业务架构 `A0-DOC-001-R7.1`、技术架构 `A0-DOC-002-R4.1`、领域模型 `A0-DOC-003-R1.2.2`

文档性质：本文描述目标 HTTP 与应用命令契约，不表示运行时代码已经提供这些接口。

## 1. 权威边界与非目标

本文是以下内容的唯一权威来源：

- 路由、HTTP 方法与成功状态码；
- JSON 字段名称和表示方式；
- 请求条件、幂等、并发与读后写规则；
- HTTP 错误与领域 Outcome 的边界；
- 普通用户、开发者和内部调用边界。

对象含义、聚合边界、字段语义、状态机和领域不变量以 `docs/DOMAIN_MODEL.md` 为唯一权威。本文引用这些规则，但不定义另一套领域模型。

本文只冻结 Core Alpha Minimum Slice 与 Core Alpha Complete。不定义 Extended Alpha API，不维护旧接口兼容清单，也不修改 FastAPI、公共 Schema、存储、Worker 或运行态数据。

## 2. HTTP 与 JSON 通用规则

### 2.1 路由与方法

- 普通产品路由使用 `/alpha` 前缀。
- 开发者诊断路由使用 `/alpha/developer` 前缀。
- 内部结果提交仅在启用 HTTP Adapter 时使用 `/internal/alpha` 前缀。
- 查询使用 GET；创建和状态转换使用 POST。
- 不使用通用状态字段更新接口；每个状态转换必须对应显式领域命令。
- 请求与响应使用 UTF-8 JSON，时间使用 UTC ISO 8601 字符串。

### 2.2 成功状态码

| 场景 | HTTP |
| --- | ---: |
| 创建资源或新聚合 | 201 |
| 同步领域命令完成 | 200 |
| 异步执行被接受 | 202 |
| 查询成功 | 200 |
| 幂等重放 | 首次请求的原始状态码 |

所有成功命令均返回响应体，不使用空响应表示成功。

### 2.3 服务端拥有字段

客户端不得提交：

- 资源 ID、command ID 或 Trace ID；
- `created_at / updated_at / started_at / ended_at / completed_at`；
- `revision` 或 `version` 的目标值；
- lifecycle、audit、validity、execution 等状态字段；
- `created_by / confirmed_by / acknowledged_by / committed_by`；
- AuditFinding、DecisionFitness、ResearchRunOutcome 等系统判定结果。

客户端只提交用户输入、用户选择、当前版本引用、`expected_revision`、条件参数和 `Idempotency-Key`。actor 字段由认证上下文产生。

### 2.4 命令响应

```json
{
  "data": {},
  "command": {
    "command_id": "cmd_...",
    "trace_id": "trace_...",
    "idempotency_key": "string",
    "idempotent_replay": false
  },
  "consistency": {
    "source": "authoritative_store",
    "aggregate_revision": 7,
    "projection_checkpoint": null,
    "is_stale": false,
    "observed_at": "2026-06-24T01:00:00Z"
  }
}
```

命令响应直接返回本次事务形成的权威资源。`aggregate_revision` 是命令完成后的聚合 revision。

### 2.5 查询响应与分页

单资源响应：

```json
{
  "data": {},
  "consistency": {
    "source": "authoritative_store",
    "aggregate_revision": 7,
    "projection_checkpoint": null,
    "is_stale": false,
    "observed_at": "2026-06-24T01:00:00Z"
  }
}
```

列表响应：

```json
{
  "data": [],
  "page": {
    "next_cursor": null
  },
  "consistency": {
    "source": "projection",
    "aggregate_revision": null,
    "projection_checkpoint": "cursor_...",
    "is_stale": false,
    "observed_at": "2026-06-24T01:00:00Z"
  }
}
```

- 单聚合或明确聚合范围查询可以使用 `minimum_revision`。
- 列表投影使用 `minimum_checkpoint`，不得把多个聚合压缩为一个 revision。
- 权威存储响应必须为 `source=authoritative_store` 且 `is_stale=false`。
- 投影无法在等待窗口内达到要求时返回 `409 projection_not_ready`，不得返回旧数据冒充满足一致性要求。
- 列表使用不透明 cursor；`limit` 默认 50，最大 200。

### 2.6 幂等

所有 POST 请求必须携带 `Idempotency-Key` 请求头。

幂等作用域为：认证主体 + HTTP 方法 + 标准化路由。服务端保存请求体规范化 Hash、状态码和完整响应。

- 相同 Key 与相同请求体：返回首次响应，`idempotent_replay=true`。
- 相同 Key 与不同请求体：返回 `409 idempotency_conflict`。
- 重放不得重复创建版本、TraceEvent、确认事实或其他领域对象。
- `Idempotency-Key` 不替代 `expected_revision`。
- 内部应用命令使用独立幂等键，不能复用外部请求 Key 作为不同操作的幂等身份。

### 2.7 乐观并发与版本

- 创建新聚合时不传 `expected_revision`。
- 修改既有聚合时，`expected_revision` 必须放在 JSON 请求体中。
- adjust 命令同时绑定当前具体 `*_version_id` 和所属聚合 `expected_revision`。
- revision 不一致返回 `409 concurrency_conflict`，不允许最后写入获胜。
- 新版本、旧 current 进入 superseded、current pointer 更新和 TraceEvent 必须原子提交。
- 已被 ResearchRun 绑定的历史 KnowledgeScope 或 ResearchPlan 版本不可修改。

## 3. 公共表示

### 3.1 资源引用

```json
{
  "resource_type": "judgment_card_version",
  "resource_id": "jcv_..."
}
```

所有需要历史复现的引用使用具体 `*_version_id`。逻辑 `*_id` 只用于版本序列和 current 查询。

### 3.2 SourceAnchorInput

```json
{
  "raw_anchor": "鬼谷子",
  "requested_access_policy": "required",
  "requested_version_hint": null
}
```

`requested_access_policy` 为 `required / allowed / excluded`。

### 3.3 KnowledgeScopeBindingInput

```json
{
  "source_resolution_id": "sr_...",
  "knowledge_item_id": "ki_...",
  "knowledge_item_version_id": "kiv_...",
  "access_policy": "required",
  "analysis_role": "primary"
}
```

excluded 绑定可以省略版本和分析角色；required/allowed 必须绑定可用版本。

### 3.4 ErrorResponse

```json
{
  "error": {
    "code": "concurrency_conflict",
    "message": "string",
    "details": {},
    "trace_id": "trace_...",
    "retryable": false
  }
}
```

## 4. Minimum Slice API

### 4.1 Knowledge Catalog

这些接口只读取知识身份，不在本任务中定义导入、删除、切块或重建命令。

| 方法与路由 | 成功 | 输入 | 输出 |
| --- | ---: | --- | --- |
| `GET /alpha/knowledge-items` | 200 | `cursor, limit, item_type, lifecycle_status` | KnowledgeItem 列表 |
| `GET /alpha/knowledge-items/{knowledge_item_id}` | 200 | `minimum_revision` 可选 | KnowledgeItem |
| `GET /alpha/knowledge-items/{knowledge_item_id}/versions` | 200 | `cursor, limit, availability_status` | KnowledgeItemVersion 列表 |
| `GET /alpha/knowledge-item-versions/{knowledge_item_version_id}` | 200 | 无 | KnowledgeItemVersion |
| `GET /alpha/knowledge-item-versions/{knowledge_item_version_id}/chunks` | 200 | `cursor, limit` | Chunk 列表，不默认返回完整原文 |

普通响应可以返回标题、版本、结构、定位和可用性。IndexGeneration 只通过 Developer API 查询。

### 4.2 ResearchCase 与问题

#### `POST /alpha/research-cases`

状态码：`201`。不传 `expected_revision`。

```json
{
  "title": "隐藏真实意图",
  "question_text": "如何理解隐藏真实意图？",
  "question_role": "root"
}
```

同一事务创建 ResearchCase 与 root ResearchQuestion。

#### 查询与命令

| 方法与路由 | 成功 | 请求要点 |
| --- | ---: | --- |
| `GET /alpha/research-cases` | 200 | cursor、limit、lifecycle_status、attention_status、minimum_checkpoint |
| `GET /alpha/research-cases/{research_case_id}` | 200 | minimum_revision 可选 |
| `POST /alpha/research-cases/{research_case_id}/questions` | 201 | expected_revision、question_text、question_role、parent_question_id 可选 |
| `POST /alpha/research-cases/{research_case_id}/commands/archive` | 200 | expected_revision |
| `POST /alpha/research-cases/{research_case_id}/commands/reopen` | 200 | expected_revision |
| `POST /alpha/research-cases/{research_case_id}/commands/derive` | 201 | expected_revision、source_question_id 或 judgment_card_version_id、title、question_text |

question_role 为 `root / follow_up / clarification / derived`。derive 创建新 Case，不移动原 Case 历史。

### 4.3 SourceResolution

#### `POST /alpha/research-cases/{research_case_id}/source-resolutions`

状态码：`201`。Minimum Slice 仅接受 `resolution_stage=full`。

```json
{
  "expected_revision": 3,
  "research_question_id": "rq_...",
  "resolution_stage": "full",
  "anchors": [
    {
      "raw_anchor": "鬼谷子",
      "requested_access_policy": "required",
      "requested_version_hint": null
    }
  ]
}
```

响应 data 为 SourceResolution 数组。`ambiguous / not_found / unavailable` 是成功创建的领域记录，不映射为 HTTP 错误。显式锚点失败不得回退全库。

`GET /alpha/research-cases/{research_case_id}/source-resolutions` 返回该 Case 的解析记录。

### 4.4 KnowledgeScope

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `POST /alpha/research-cases/{research_case_id}/knowledge-scopes` | 201 | 创建初始 Scope 版本 |
| `GET /alpha/research-cases/{research_case_id}/knowledge-scopes/current` | 200 | 读取 current 版本 |
| `GET /alpha/knowledge-scopes/{knowledge_scope_version_id}` | 200 | 读取历史或当前版本 |
| `POST /alpha/knowledge-scopes/{knowledge_scope_version_id}/commands/adjust` | 200 | 创建新版本并 supersede 旧版本 |

创建和 adjust 请求包含 `expected_revision`、`default_access_policy`、`scope_mode=evidence_only` 和 bindings。default policy 只能是 allowed/excluded。adjust 必须绑定路径中的 current version ID。

### 4.5 ResearchPlan

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `POST /alpha/research-cases/{research_case_id}/research-plans` | 201 | 创建初始计划版本 |
| `GET /alpha/research-cases/{research_case_id}/research-plans/current` | 200 | 读取 current 版本 |
| `GET /alpha/research-plans/{research_plan_version_id}` | 200 | 读取指定版本 |
| `POST /alpha/research-plans/{research_plan_version_id}/commands/adjust` | 200 | 创建新版本并 supersede 旧版本 |

请求字段：`expected_revision`、`knowledge_scope_version_id`、`research_mode`、`primary_objective`、`evidence_requirements`、`minimum_completion_condition`；stop conditions 与正式预算为 Core Complete 可选字段。

adjust 不得修改已被 Run 绑定的历史版本，只能创建新的 plan version ID。

### 4.6 ResearchRun

#### `POST /alpha/research-cases/{research_case_id}/research-runs`

```json
{
  "expected_revision": 6,
  "research_question_id": "rq_...",
  "knowledge_scope_version_id": "ksv_...",
  "research_plan_version_id": "rpv_...",
  "execution_mode": "synchronous"
}
```

execution_mode 为 `synchronous / asynchronous`，默认 synchronous。

- 同步：创建并完成可执行流程后返回 `201`，data 包含 ResearchRun、当前 JudgmentCard 或 RunOutcome 引用。
- 异步：持久化 ResearchRun 后返回 `202`，data 只包含领域 Run 与已知引用，不返回通用任务标识。
- 异步能力未启用：`503 async_execution_unavailable`。
- Run 创建前必要依赖不可用：HTTP 503。
- Run 创建后执行失败：形成 `ResearchRunOutcome.execution_failed`。

#### 查询与取消

| 方法与路由 | 成功 | 输出或请求 |
| --- | ---: | --- |
| `GET /alpha/research-runs/{research_run_id}` | 200 | ResearchRun |
| `POST /alpha/research-runs/{research_run_id}/commands/cancel` | 200 | expected_revision、reason |
| `GET /alpha/research-runs/{research_run_id}/outcome` | 200 | ResearchRunOutcome；未结束时 data=null |
| `GET /alpha/research-runs/{research_run_id}/attempts` | 200 | Attempt 列表 |
| `GET /alpha/research-attempts/{research_attempt_id}/retrieval-runs` | 200 | RetrievalRun 列表 |
| `GET /alpha/research-runs/{research_run_id}/evidence-uses` | 200 | ResearchEvidenceUse 列表 |

### 4.7 Evidence 与 Judgment

| 方法与路由 | 成功 | 输出或请求 |
| --- | ---: | --- |
| `GET /alpha/evidence-units/{evidence_unit_id}` | 200 | 脱敏 EvidenceUnit 与来源定位 |
| `GET /alpha/research-evidence-uses/{research_evidence_use_id}` | 200 | Scope、evidence revision 和有效性快照 |
| `GET /alpha/research-cases/{research_case_id}/judgment-cards/current` | 200 | Case 当前 JudgmentCard version 或 null |
| `GET /alpha/judgment-cards/{judgment_card_version_id}` | 200 | JudgmentCard、Claim version 引用、状态与缺口 |
| `GET /alpha/judgment-cards/{judgment_card_version_id}/claims` | 200 | Claim、Rationale、ClaimEvidenceLink；Link 保留 research_evidence_use_id |
| `GET /alpha/claims/{claim_id}/current` | 200 | Claim 当前语义版本 |
| `GET /alpha/claim-versions/{claim_version_id}` | 200 | Claim 指定历史版本 |
| `GET /alpha/judgment-cards/{judgment_card_version_id}/audit` | 200 | JudgmentAudit 与 Finding |
| `GET /alpha/judgment-cards/{judgment_card_version_id}/decision-fitness` | 200 | DecisionFitness |
| `POST /alpha/audit-findings/{audit_finding_id}/commands/acknowledge` | 201 | 创建 WarningAcknowledgement；expected_revision、judgment_card_version_id、acknowledgement_note |
| `POST /alpha/claims/{claim_version_id}/commands/set-user-attitude` | 200 | expected_revision、user_attitude |

blocking Finding 不允许 acknowledge。修改 user attitude 不改变 evidence status 或 Claim 语义版本。

### 4.8 Decision

DispositionProposal 在 JudgmentAudit 与 DecisionFitness 完成后，由内部 `CreateDispositionProposalCommand` 生成，不提供公开创建路由。

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `GET /alpha/research-cases/{research_case_id}/disposition-proposals/current` | 200 | 当前 Proposal 或 null |
| `GET /alpha/disposition-proposals/{disposition_proposal_version_id}` | 200 | 指定版本 |
| `POST /alpha/disposition-proposals/{disposition_proposal_version_id}/commands/accept` | 200 | 形成 ResearchDisposition |
| `POST /alpha/disposition-proposals/{disposition_proposal_version_id}/commands/adjust` | 200 | 形成新 Proposal 版本 |
| `POST /alpha/disposition-proposals/{disposition_proposal_version_id}/commands/reject` | 200 | 记录拒绝，不形成 Disposition |
| `GET /alpha/research-dispositions/{research_disposition_id}` | 200 | 最终处置事实 |

三个决定命令都包含 DispositionProposal 聚合的 `expected_revision`。accept 还包含 `judgment_card_version_id`、`decision_fitness_id` 和有效 `warning_acknowledgement_ids`；adjust 还包含新的 disposition type、reason 及 defer/observe 条件。

### 4.9 普通 ResearchTrace

`GET /alpha/research-runs/{research_run_id}/trace` 返回领域级过程：Scope、Plan、Attempt、证据使用、判断、审计、Outcome 和处置引用。普通响应不暴露 Provider、模型、索引参数、完整 Prompt 或完整私有原文。

## 5. Core Alpha Complete API

### 5.1 ResearchTriage

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `POST /alpha/research-cases/{research_case_id}/triages` | 201 | 创建 preliminary 解析与 Triage 建议 |
| `GET /alpha/research-triages/{research_triage_id}` | 200 | 读取建议与用户决定 |
| `POST /alpha/research-triages/{research_triage_id}/commands/accept` | 200 | 采用 recommended_path |
| `POST /alpha/research-triages/{research_triage_id}/commands/adjust` | 200 | 提交 selected_path |
| `POST /alpha/research-triages/{research_triage_id}/commands/override` | 200 | 用户显式覆盖建议 |

创建 Triage 与三个决定命令都包含所属 ResearchCase 的 `expected_revision`。

### 5.2 AttentionBacklogItem

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `POST /alpha/attention-backlog-items` | 201 | 保存问题、Case 引用、知识缺口、复核建议或外部线索 |
| `GET /alpha/attention-backlog-items` | 200 | cursor 列表查询 |
| `GET /alpha/attention-backlog-items/{attention_backlog_item_id}` | 200 | 单项查询 |
| `POST /alpha/attention-backlog-items/{attention_backlog_item_id}/commands/activate` | 200 或 201 | 激活并关联或创建 Case |
| `POST /alpha/attention-backlog-items/{attention_backlog_item_id}/commands/discard` | 200 | 丢弃 |
| `POST /alpha/attention-backlog-items/{attention_backlog_item_id}/commands/archive` | 200 | 归档 |

创建 AttentionBacklogItem 不传 `expected_revision`；activate、discard、archive 要求该 Item 的 `expected_revision`。saved question 激活时原子创建 ResearchCase 与 ResearchQuestion。

### 5.3 JudgmentReview

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `POST /alpha/judgment-cards/{judgment_card_version_id}/reviews` | 201 | 发起 JudgmentReview |
| `GET /alpha/judgment-reviews/{judgment_review_id}` | 200 | Review 与 ReviewResult |
| `POST /alpha/judgment-reviews/{judgment_review_id}/commands/cancel` | 200 | 取消未完成复核 |

创建 JudgmentReview 不传 `expected_revision`，但必须绑定具体 JudgmentCard version；cancel 要求 JudgmentReview 的 `expected_revision`。ReviewResult 由内部 `CompleteJudgmentReviewCommand` 与 Review 完成状态原子创建，不提供公开创建路由。需要改变处置时生成新的 DispositionProposal。

### 5.4 Action

#### 创建与调整 ActionProposal

`POST /alpha/research-dispositions/{research_disposition_id}/commands/create-action-proposal` 返回 `201`。

请求包含 `expected_revision`（目标为 ResearchCase）、`judgment_card_version_id`、`decision_fitness_id`、目标、步骤、预期收益、停止条件、复盘时间、风险输入和 warning acknowledgements。

只有当前有效且 disposition type 为 proceed_to_action 的处置可以调用；判断、用途、warning 或 risk ceiling 不满足时返回 409。

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `GET /alpha/research-cases/{research_case_id}/action-proposals/current` | 200 | 当前 ActionProposal 或 null |
| `GET /alpha/action-proposals/{action_proposal_version_id}` | 200 | 指定版本 |
| `POST /alpha/action-proposals/{action_proposal_version_id}/commands/adjust` | 200 | 新版本、重新风险和用途校验 |
| `POST /alpha/action-proposals/{action_proposal_version_id}/commands/accept` | 200 | 创建 ActionCommitment |
| `POST /alpha/action-proposals/{action_proposal_version_id}/commands/reject` | 200 | 记录拒绝 |

#### ActionCommitment 与复盘

ActionProposal 的 adjust、accept、reject 都要求 ActionProposal 聚合的 `expected_revision`。

| 方法与路由 | 成功 | 请求或输出 |
| --- | ---: | --- |
| `GET /alpha/action-commitments/{action_commitment_id}` | 200 | Commitment |
| `POST /alpha/action-commitments/{action_commitment_id}/commands/start` | 200 | expected_revision |
| `POST /alpha/action-commitments/{action_commitment_id}/commands/block` | 200 | expected_revision、reason |
| `POST /alpha/action-commitments/{action_commitment_id}/commands/defer` | 200 | expected_revision、deferred_until、reason |
| `POST /alpha/action-commitments/{action_commitment_id}/commands/resume` | 200 | expected_revision |
| `POST /alpha/action-commitments/{action_commitment_id}/commands/complete` | 200 | expected_revision、completion_summary |
| `POST /alpha/action-commitments/{action_commitment_id}/commands/cancel` | 200 | expected_revision、reason |
| `POST /alpha/action-commitments/{action_commitment_id}/reviews` | 201 | expected_revision、expected_result、actual_result、assumption_failures |

ActionReview 发现判断前提错误时返回 `judgment_review_required=true`，后续由独立命令发起 JudgmentReview。

### 5.5 Knowledge Contribution

KnowledgeContributionCandidate 由内部 `CreateKnowledgeContributionCandidateCommand` 生成，不提供公开创建路由。

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `GET /alpha/research-cases/{research_case_id}/knowledge-contribution-candidates` | 200 | Case 候选列表；默认只返回 current，可显式包含历史版本 |
| `GET /alpha/knowledge-contribution-candidates/{knowledge_contribution_candidate_id}/current` | 200 | 逻辑候选的 current 版本 |
| `GET /alpha/knowledge-contribution-candidate-versions/{knowledge_contribution_candidate_version_id}` | 200 | 指定候选版本 |
| `POST /alpha/knowledge-contribution-candidate-versions/{knowledge_contribution_candidate_version_id}/commands/adjust` | 200 | 新版本并重新校验 |
| `POST /alpha/knowledge-contribution-candidate-versions/{knowledge_contribution_candidate_version_id}/commands/accept-as-knowledge` | 200 | 创建 KnowledgeAsset |
| `POST /alpha/knowledge-contribution-candidate-versions/{knowledge_contribution_candidate_version_id}/commands/save-as-note` | 200 | 创建 UserNote |
| `POST /alpha/knowledge-contribution-candidate-versions/{knowledge_contribution_candidate_version_id}/commands/reject` | 200 | 关闭候选 |

命令包含 `expected_revision`、`judgment_card_version_id`、EvidenceUnit 引用和 warning acknowledgements。validation failed 不能接受为知识，但可以保存为笔记。

### 5.6 KnowledgeAsset 与 UserNote

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `GET /alpha/knowledge-assets` | 200 | cursor 列表 |
| `GET /alpha/knowledge-assets/{knowledge_asset_id}` | 200 | 资产及证据回溯 |
| `POST /alpha/knowledge-assets/{knowledge_asset_id}/commands/withdraw` | 200 | expected_revision |
| `POST /alpha/knowledge-assets/{knowledge_asset_id}/commands/archive` | 200 | expected_revision |
| `GET /alpha/user-notes` | 200 | cursor 列表 |
| `GET /alpha/user-notes/{user_note_id}` | 200 | 普通笔记 |
| `POST /alpha/user-notes/{user_note_id}/commands/withdraw` | 200 | expected_revision |
| `POST /alpha/user-notes/{user_note_id}/commands/archive` | 200 | expected_revision |

KnowledgeAsset 必须保留 JudgmentCard version、EvidenceUnit 和 warning 引用；UserNote 不得显示为系统验证知识。

## 6. 内部应用契约

### 6.1 SubmitCandidateResultCommand

该命令不是普通用户 API。进程内调用优先；启用 HTTP Adapter 时固定为：

`POST /internal/alpha/candidate-results`

请求至少包含：

```json
{
  "service_identity": "research-worker",
  "operation_type": "judgment_candidate",
  "research_run_id": "run_...",
  "research_attempt_id": "attempt_...",
  "run_execution_spec_id": "spec_...",
  "input_versions": {},
  "idempotency_key": "internal-key",
  "lifecycle_generation": 3,
  "capability_implementation_version": "string",
  "output_schema_version": "string",
  "candidate_result": {},
  "correlation_id": "string",
  "causation_id": "string"
}
```

Handler 必须重新校验版本、Scope、生命周期、幂等、Tombstone 和 Schema。合法候选也不能直接成为权威领域状态。

### 6.2 内部对象产生命令

| 命令 | 原子结果 |
| --- | --- |
| CreateDispositionProposalCommand | 绑定已完成 Audit 与 DecisionFitness，创建 Proposal |
| CreateKnowledgeContributionCandidateCommand | 判断具有沉淀价值时创建 Candidate |
| CompleteJudgmentReviewCommand | Review completed 与 ReviewResult 同事务提交 |

内部 HTTP Adapter 要求服务身份。缺少身份返回 401；身份无权执行对应 operation 返回 403。

## 7. Outcome、错误与降级

### 7.1 领域结果不是 HTTP 错误

- SourceResolution 的 ambiguous、not_found、unavailable 返回成功创建的记录。
- insufficient_evidence、audit_blocked、cancelled_by_user 和 Run 创建后的 execution_failed 通过 ResearchRunOutcome 表达。
- blocked JudgmentCard 可以查询，但不得显示成可靠判断或生成可采纳处置。

### 7.2 错误码

| HTTP | code | 含义 |
| ---: | --- | --- |
| 401 | authentication_required | 缺少调用主体或服务身份 |
| 403 | forbidden | 主体无权访问内部或诊断能力 |
| 404 | resource_not_found | 路由引用的 API 资源不存在 |
| 409 | idempotency_conflict | 同一 Key 使用不同请求体 |
| 409 | concurrency_conflict | expected_revision 不匹配 |
| 409 | version_conflict | version ID 非 current 或上游版本不匹配 |
| 409 | lifecycle_conflict | 当前状态不允许该命令 |
| 409 | projection_not_ready | 投影未达到 minimum revision/checkpoint |
| 409 | decision_fitness_violation | 用途或风险超过 DecisionFitness |
| 409 | warning_acknowledgement_required | 缺少有效 warning 确认 |
| 422 | validation_error | JSON、枚举或字段类型错误 |
| 422 | condition_required | 条件必填字段缺失或互斥字段冲突 |
| 503 | async_execution_unavailable | 请求异步但能力未启用 |
| 503 | dependency_unavailable | 命令接受前所需依赖不可用 |

409 projection_not_ready 与 503 错误必须设置 `retryable=true`；其余错误根据 details 明确是否可重试。

## 8. Developer Diagnostics

Developer API 使用独立访问策略，不属于普通产品 API。

| 方法与路由 | 输出 |
| --- | --- |
| `GET /alpha/developer/research-runs/{research_run_id}/trace` | 技术 Trace、Capability、降级与失败 |
| `GET /alpha/developer/research-cases/{research_case_id}/activity` | CaseActivityLog |
| `GET /alpha/developer/material-manifests` | 按 Run、Provider、purpose 查询 MaterialManifest |
| `GET /alpha/developer/index-generations` | IndexGeneration metadata |
| `GET /alpha/developer/research-runs/{research_run_id}/budget` | BudgetSnapshot 与消费记录 |
| `GET /alpha/developer/projections/status` | checkpoint、lag 和失败摘要 |

默认只返回对象引用、Hash、版本和脱敏摘要。不返回完整 Prompt、完整私有原文、API Key 或认证 Header。

## 9. 跨接口不变量

1. API 不得混用 ResearchRunOutcome、JudgmentCard 状态和 ResearchDisposition。
2. 未确认 Proposal 不得序列化为最终处置或承诺。
3. 所有判断、行动和知识接口绑定具体 JudgmentCard version 与 DecisionFitness。
4. ClaimEvidenceLink 响应必须保留 ResearchEvidenceUse，使历史判断回到当时 Scope 和 evidence revision。
5. adjust 只能创建新版本，不能原地修改历史版本。
6. 幂等重放不产生新命令副作用。
7. 普通 API 不允许直接提交审计结论、用途适配或内部候选结果。
8. Diagnostics 和内部接口必须与普通用户权限隔离。
9. Extended Alpha 缺失不得改变 Core Alpha 路由语义。

## 10. 验收

强制检查：

```powershell
git status --short
git diff --check -- docs/API_CONTRACTS.md
git diff --name-only
rg -n "^(<<<<<<<|=======|>>>>>>>)" docs/API_CONTRACTS.md
```

人工验收：

- 每个版本化对象具有 current 与历史版本查询；每个允许用户调整的版本化对象具有 adjust 契约；
- 每个 Proposal 具有明确产生入口和用户决定命令；
- 每个 POST 标明状态码、幂等与 expected_revision 要求；
- 异步响应返回 ResearchRun，不出现通用任务对象；
- SourceResolution 与 RunOutcome 不被映射成 HTTP 404/503；
- 行动与知识命令绑定 JudgmentCard version、DecisionFitness 和 warning；
- 仅 `docs/API_CONTRACTS.md` 发生变化。
