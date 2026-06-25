# MetaOS Alpha API 契约

状态：Core Alpha 目标 API 契约正式冻结版

任务标识：`A0-DOC-004-R1.2.1`

关联机械勘误：`A1-CONTRACT-001`

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
| 集合资源创建端点 | 201 |
| `/commands/*` 同步命令端点 | 200，即使命令原子创建下游资源 |
| 异步执行被接受 | 202 |
| 查询成功 | 200 |
| 幂等重放 | 首次请求的原始状态码 |

状态码按“异步接受 > 命令端点 > 集合创建端点 > 查询”判定，每条路由只允许一个同步成功状态码。所有成功命令均返回响应体，不使用空响应表示成功。

### 2.3 服务端拥有字段

客户端不得提交：

- 资源 ID、command ID 或 Trace ID；
- `created_at / updated_at / started_at / ended_at / completed_at`；
- `revision` 或 `version` 的目标值；
- lifecycle、audit、validity、execution 等状态字段；
- `created_by / confirmed_by / acknowledged_by / committed_by`；
- AuditFinding、DecisionFitness、ResearchRunOutcome 等系统判定结果。

客户端只提交用户输入、用户选择、当前版本引用、`expected_revision` 或命名明确的上游 revision 断言、条件参数和 `Idempotency-Key`。actor 字段由认证上下文产生。

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
    "primary_aggregate": {
      "aggregate_type": "disposition_proposal",
      "aggregate_id": "dp_...",
      "revision": 7
    },
    "affected_aggregates": [
      {
        "aggregate_type": "research_case",
        "aggregate_id": "case_...",
        "revision": 12
      }
    ],
    "projection_checkpoint": null,
    "is_stale": false,
    "observed_at": "2026-06-24T01:00:00Z"
  }
}
```

命令响应直接返回本次事务形成的权威资源。每个命令必须返回 `primary_aggregate` 和 `affected_aggregates`；后者没有成员时返回 `[]`，不得省略。不可变事实不作为 primary aggregate，其 primary aggregate 使用拥有该事实与事务边界的聚合根。跨聚合命令不得用一个 revision 代表多个聚合。只有查询响应可以令 `primary_aggregate=null`。

例如，确认 warning 的 primary aggregate 是 JudgmentCard，WarningAcknowledgement 是新事实；确认处置的 primary aggregate 是 DispositionProposal，ResearchCase 如被同步更新则列入 affected aggregates，ResearchDisposition 是新事实。

#### 2.4.1 命令 data 的固定形状

单资源命令统一返回以资源类型 snake_case 命名的对象，不直接把资源字段摊平到 `data`。版本调整命令同时返回旧版本引用与新版本完整对象。以下跨资源命令固定返回：

| 命令 | `data` 必填键 | nullable / 条件键 |
| --- | --- | --- |
| 创建 ResearchCase | `research_case, research_question` | 无 |
| 派生 ResearchCase | `source_research_case_ref, research_case, research_question` | 无 |
| 创建 SourceResolution | `source_resolutions` | 无；始终为数组 |
| 创建或调整 KnowledgeScope | `knowledge_scope` | adjust 另含 `superseded_version_ref` |
| 创建或调整 ResearchPlan | `research_plan` | adjust 另含 `superseded_version_ref` |
| 启动 ResearchRun | `research_run` | `research_run_outcome, judgment_card`，规则见 3.5 |
| 确认 warning | `warning_acknowledgement, judgment_card` | 无 |
| accept DispositionProposal | `disposition_proposal, research_disposition, research_case` | 无 |
| adjust DispositionProposal | `disposition_proposal, superseded_version_ref` | 无 |
| reject DispositionProposal | `disposition_proposal` | 无 |
| activate AttentionBacklogItem | `attention_backlog_item, activation_result, research_case` | `research_question`；仅新建 Case 时非 null |
| complete JudgmentReview（内部） | `judgment_review, review_result, follow_up_commands` | 无；ReviewResult 自身可引用既有新 Run |
| create ActionProposal | `research_disposition, action_proposal` | 无 |
| adjust ActionProposal | `action_proposal, superseded_version_ref` | 无 |
| accept ActionProposal | `action_proposal, action_commitment` | 无 |
| accept-as-knowledge | `knowledge_contribution_candidate, knowledge_asset` | 无 |
| save-as-note | `knowledge_contribution_candidate, user_note` | 无 |
| reject Candidate | `knowledge_contribution_candidate` | 无 |

`*_ref` 使用 3.1 的资源引用；其他键使用 3.5 至 3.8 的规范响应。未列出的单资源命令返回该命令完成后的完整当前资源，例如 `{ "action_commitment": {} }`。所有键即使为 null 也必须出现，客户端不得依据字段缺失猜测执行分支。

### 2.5 查询响应与分页

单资源响应：

```json
{
  "data": {},
  "consistency": {
    "source": "authoritative_store",
    "primary_aggregate": {
      "aggregate_type": "research_case",
      "aggregate_id": "case_...",
      "revision": 7
    },
    "affected_aggregates": [],
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
    "primary_aggregate": null,
    "affected_aggregates": [],
    "projection_checkpoint": "cursor_...",
    "is_stale": false,
    "observed_at": "2026-06-24T01:00:00Z"
  }
}
```

单资源 GET 的 `data` 直接是对应规范资源对象，未形成可选资源时为 null；列表 GET 的 `data` 是规范资源对象数组。以下复合查询例外使用固定键：

| 查询 | `data` 形状 |
| --- | --- |
| JudgmentCard claims | `{ "claims": [{ "claim": {}, "rationale": null, "evidence_links": [] }] }` |
| 指定 JudgmentAudit | `{ "judgment_audit": {}, "audit_findings": [] }` |
| JudgmentReview | `{ "judgment_review": {}, "review_result": null }` |
| ResearchRun trace | `PublicResearchTraceResponse` |
| Developer Case activity | `CaseActivityLogResponse` |

`rationale` 只有在 Claim 引用 JudgmentRationale 时非 null。复合查询不得用可变的 include 参数改变顶层结构。

- 单聚合或明确聚合范围查询可以使用 `minimum_revision`。
- 列表投影使用 `minimum_checkpoint`，不得把多个聚合压缩为一个 revision。
- 使用 `minimum_revision` 或 `minimum_checkpoint` 时可传 `consistency_wait_ms`；默认 `0`，最大 `5000`。
- 权威存储响应必须为 `source=authoritative_store` 且 `is_stale=false`。
- 投影无法在等待窗口内达到要求时返回 `409 projection_not_ready`，不得返回旧数据冒充满足一致性要求；错误 details 必须返回目标 checkpoint/revision、当前值和实际等待毫秒数。
- 列表使用不透明、签名 cursor；`limit` 默认 50，最大 200。cursor 绑定认证主体、筛选条件、排序和快照水位，默认稳定排序为 `created_at DESC, resource_id DESC`。
- cursor 不使用数据库 offset。无效、过期或与当前主体、筛选、排序不匹配时返回 `422 invalid_cursor`。
- 同一分页会话固定快照水位，防止翻页时重复或漏读；水位后新增记录只在新的分页会话中出现。

`projection_not_ready` 的 details 固定为：

```json
{
  "target_type": "checkpoint",
  "target_value": "cursor_target_...",
  "current_value": "cursor_current_...",
  "waited_ms": 5000
}
```

`target_type=revision|checkpoint`；revision 值使用 JSON integer，checkpoint 值使用 string。

### 2.6 幂等

所有 POST 请求必须携带 `Idempotency-Key` 请求头。

幂等作用域为：认证主体 + HTTP 方法 + 标准化路由。服务端保存请求体规范化 Hash、状态码和完整响应。

- 相同 Key 与相同请求体：返回首次响应，`idempotent_replay=true`。
- 相同 Key 与不同请求体：返回 `409 idempotency_conflict`。
- 重放不得重复创建版本、TraceEvent、确认事实或其他领域对象。
- `Idempotency-Key` 不替代 `expected_revision` 或命名上游 revision 断言。
- 内部应用命令使用独立幂等键，不能复用外部请求 Key 作为不同操作的幂等身份。

### 2.7 乐观并发与版本

- 创建新聚合时不传 `expected_revision`。
- 创建新聚合依赖另一个可变聚合的当前状态时，可以携带命名明确的 `expected_<aggregate>_revision` 作为前置状态断言；它不是新聚合自身的 revision。
- 修改既有聚合时，`expected_revision` 必须放在 JSON 请求体中。
- adjust 命令同时绑定当前具体 `*_version_id` 和所属聚合 `expected_revision`。
- revision 不一致返回 `409 concurrency_conflict`，不允许最后写入获胜。
- 新版本、旧 current 进入 superseded、current pointer 更新和 TraceEvent 必须原子提交。
- 已被 ResearchRun 绑定的历史 KnowledgeScope 或 ResearchPlan 版本不可修改。

### 2.8 current 的唯一语义

- 版本化对象的 `/current` 返回唯一 `lifecycle_status=current` 的版本；它不表示用户已接受，也不表示对象已成为最终事实。
- JudgmentAudit 的 `/current` 返回当前被领域规则接纳并决定 JudgmentCard audit status 的审计。
- DecisionFitness 的 `/current` 返回当前对该 JudgmentCard version 生效的用途适配记录。
- 用户决定始终读取 `user_decision_status` 或最终事实对象，不得从 `/current` 推断。

## 3. 公共表示

### 3.1 资源引用

```json
{
  "resource_type": "judgment_card_version",
  "resource_id": "jcv_..."
}
```

所有需要历史复现的引用使用具体 `*_version_id`。逻辑 `*_id` 只用于版本序列和 current 查询。

通用基础类型：

- 所有 `*_id` 为非空 string；`revision`、`version`、`attempt_number` 为大于等于 1 的 integer。
- `*_at` 为 UTC ISO 8601 string；Hash 为 `算法:小写十六进制` string。
- `*_ids` 为 ID string 数组；`*_refs` 为 ResourceReference 数组。
- 所有布尔值使用 JSON boolean，计数和 offset 使用大于等于 0 的 integer。
- 请求与响应对象执行严格字段校验，未在对应 Schema 中声明的字段返回 `422 validation_error`。

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

服务端必须校验 Binding 与 SourceResolution 的一致性：`knowledge_item_id` 必须等于解析结果；非 excluded 的 `knowledge_item_version_id` 必须等于 full resolution 固定版本；`access_policy` 必须等于该 Resolution 的 `requested_access_policy`。改变访问政策必须先产生新的 SourceResolution，不得在 Binding 中单独改写。客户端不得手工组合字段绕过解析结果；不一致返回 `409 source_binding_conflict`。

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

### 3.5 规范 JSON 类型

- ID、Hash、时间和固定枚举代码值均序列化为 JSON string；时间必须是 UTC ISO 8601，Hash 使用带算法前缀的小写十六进制，例如 `sha256:...`。
- 枚举使用本文或 `docs/DOMAIN_MODEL.md` 冻结的英文代码值，不返回显示文案代替代码值。
- 资源间关系默认使用 ID，不嵌套另一份权威资源；需要显示信息时可附加非权威的 `display` 对象。
- `nullable` 字段必须显式返回 `null`；未声明为 nullable 的必填字段不得省略。列表字段始终返回数组，无值时返回 `[]`。
- 开放代码值统一使用 `OpenCodeValue={ "code": "...", "registry_version": "..." }`，不得返回裸字符串。`location` 表示为 `{ "section_path": [], "page": null, "timestamp_seconds": null, "start_offset": null, "end_offset": null }`，至少一个定位维度非空。
- 普通用户响应不返回 `storage_ref`、完整 Chunk 文本、完整私有原文、完整 Prompt、认证材料、Provider 配置或内部策略载荷；Developer API 也受第 8 章约束。

下列字段表是资源响应的规范表示。`R` 表示必填且非 null，`N` 表示必填但可为 null，`C` 表示满足领域条件时必填；未列字段不得出现在该资源的普通响应中。

#### KnowledgeItemResponse 与 KnowledgeItemVersionResponse

| 类型 | 字段 |
| --- | --- |
| `KnowledgeItemResponse` | R: `knowledge_item_id, title, item_type, language, owner_scope, lifecycle_status, revision, created_at, updated_at`；N: `current_knowledge_item_version_id` |
| `KnowledgeItemVersionResponse` | R: `knowledge_item_version_id, knowledge_item_id, version, content_hash, structure_hash, parser_version, language, availability_status, created_at`；N: `previous_version_id` |

`item_type` 使用开放代码对象；`lifecycle_status=active|archived|deleted`；`availability_status=available|unavailable|withdrawn`。`storage_ref` 不进入普通响应。

#### ResearchCaseResponse

R: `research_case_id, title, root_question_id, current_question_id, lifecycle_status, attention_status, revision, created_at, updated_at`。N: `current_knowledge_scope_version_id, current_judgment_card_version_id, current_research_disposition_id, parent_research_case_id, archived_at`。

`lifecycle_status=open|archived`；`attention_status=saved|active|paused|observing|deferred|closed`。

#### KnowledgeScopeVersionResponse 与 ResearchPlanVersionResponse

| 类型 | 字段 |
| --- | --- |
| `KnowledgeScopeVersionResponse` | R: `knowledge_scope_id, knowledge_scope_version_id, research_case_id, version, lifecycle_status, scope_mode, default_access_policy, source_bindings, created_by, created_at`；N: `previous_version_id` |
| `ResearchPlanVersionResponse` | R: `research_plan_id, research_plan_version_id, research_case_id, knowledge_scope_version_id, version, lifecycle_status, research_mode, primary_objective, evidence_requirements, minimum_completion_condition, created_at`；N: `previous_version_id, stop_conditions, research_budget` |

`source_bindings` 的每项完整返回 `knowledge_scope_source_binding_id, source_resolution_id, knowledge_item_id, knowledge_item_version_id, access_policy, analysis_role, created_at`，其中 excluded 绑定的版本和分析角色为 null。Plan 的 `research_mode=fact_lookup|source_interpretation|compare_sources|enumerate_pattern|claim_evaluation`；每项 EvidenceRequirement 完整返回其 ID、类型、说明、required binding IDs、反证要求、替代解释要求、完成条件和 nullable `minimum_count`。

#### ResearchRunResponse 与 ResearchRunOutcomeResponse

| 类型 | 字段 |
| --- | --- |
| `ResearchRunResponse` | R: `research_run_id, research_case_id, research_question_id, knowledge_scope_version_id, research_plan_version_id, run_execution_spec_id, status, revision, created_at`；N: `started_at, ended_at, superseded_by_run_id` |
| `ResearchRunOutcomeResponse` | R: `research_run_outcome_id, research_run_id, outcome_type, reason_code, reason_summary, created_at`；N: `judgment_card_version_id` |

Run `status=created|running|awaiting_user|completed|failed|cancelled|superseded`。Outcome `outcome_type=completed_with_judgment|insufficient_evidence|audit_blocked|execution_failed|cancelled_by_user|deferred_before_judgment|superseded_by_new_run`；`reason_code` 使用开放代码对象。

同步创建 Run 的 `data` 固定为：

```json
{
  "research_run": {},
  "research_run_outcome": null,
  "judgment_card": null
}
```

同步流程终止时 `research_run_outcome` 必须非 null；仅在 Outcome 引用判断时返回对应 `judgment_card`。异步 `202` 使用相同结构，但后两项均为 null。

#### EvidenceUnitResponse 与 ResearchEvidenceUseResponse

| 类型 | 字段 |
| --- | --- |
| `EvidenceUnitResponse` | R: `evidence_unit_id, knowledge_item_id, knowledge_item_version_id, location, excerpt, content_hash, origin_type, validity_status, revision, created_at, updated_at`；N: `chunk_id, origin_retrieval_run_id` |
| `ResearchEvidenceUseResponse` | R: `research_evidence_use_id, research_run_id, research_attempt_id, evidence_unit_id, evidence_revision, knowledge_scope_version_id, use_type, validity_checked_at, validity_result, created_at`；N: `retrieval_run_id` |

普通响应中的 `excerpt` 按访问策略脱敏并限制长度，但不得改变 `content_hash` 所指向的原始证据身份。`origin_type` 使用开放代码对象；`validity_status` 与 `validity_result=valid|needs_review|invalid`；`use_type=retrieved|reused`。

#### JudgmentCardVersionResponse 与 ClaimVersionResponse

| 类型 | 字段 |
| --- | --- |
| `JudgmentCardVersionResponse` | R: `judgment_card_id, judgment_card_version_id, research_case_id, research_run_id, version, revision, claim_version_ids, summary, uncertainties, evidence_gaps, audit_status, validity_status, lifecycle_status, created_at`；N: `previous_version_id, current_judgment_audit_id, decision_fitness_id` |
| `ClaimVersionResponse` | R: `claim_id, claim_version_id, judgment_card_version_id, claim_text, epistemic_type, expression_role, evidence_status, importance, confidence_level, lifecycle_status, user_attitude, version, created_at`；N: `judgment_rationale_id, previous_version_id` |

Judgment `audit_status=pending|auditing|provisionally_acceptable|acceptable|blocked`、`validity_status=valid|needs_review|invalid`、`lifecycle_status=draft|current|superseded|archived`。Claim 的枚举值完全采用领域模型；`user_attitude` 与 `evidence_status` 必须分别返回。

#### DispositionProposalVersionResponse 与 ResearchDispositionResponse

| 类型 | 字段 |
| --- | --- |
| `DispositionProposalVersionResponse` | R: `disposition_proposal_id, disposition_proposal_version_id, research_case_id, judgment_card_version_id, decision_fitness_id, proposed_disposition_type, reason, user_decision_status, lifecycle_status, version, revision, created_at`；N: `previous_version_id, expires_at, defer_until, observation_condition`；R list: `warning_acknowledgement_ids` |
| `ResearchDispositionResponse` | R: `research_disposition_id, research_case_id, source_disposition_proposal_version_id, judgment_card_version_id, decision_fitness_id, disposition_type, confirmed_by, confirmed_at`；N: `supersedes_disposition_id, defer_until, observation_condition` |

处置类型为 `proceed_to_action|continue_research|defer_decision|observe|discard|explicit_no_action|knowledge_only_closure`；defer 和 observe 的条件字段按领域模型条件必填。

#### ActionProposalVersionResponse 与 ActionCommitmentResponse

| 类型 | 字段 |
| --- | --- |
| `ActionProposalVersionResponse` | R: `action_proposal_id, action_proposal_version_id, research_case_id, research_disposition_id, judgment_card_version_id, decision_fitness_id, goal, proposed_steps, expected_benefit, stop_conditions, action_risk_profile, user_decision_status, lifecycle_status, version, revision, created_at`；N: `review_at, previous_version_id, expires_at`；R list: `audit_finding_ids, warning_acknowledgement_ids` |
| `ActionCommitmentResponse` | R: `action_commitment_id, action_proposal_version_id, status, committed_by, committed_at, revision`；N: `started_at, completed_at, deferred_until` |

`action_risk_profile` 内嵌该 Proposal version 的不可变风险快照：`action_risk_profile_id, cost_level, reversibility, time_commitment, external_impact, maximum_acceptable_loss, dependency_uncertainty, expert_review_required, risk_level, created_at`。Commitment `status=planned|in_progress|blocked|completed|cancelled|deferred`。

#### KnowledgeContributionCandidateVersionResponse

R: `knowledge_contribution_candidate_id, knowledge_contribution_candidate_version_id, research_case_id, judgment_card_version_id, contribution_type, proposed_content, evidence_unit_ids, validation_status, user_decision_status, lifecycle_status, version, revision, created_at, audit_finding_ids, warning_acknowledgement_ids`。N: `target_knowledge_asset_id, previous_version_id`。

`contribution_type=claim|evidence|gap`；`validation_status=not_required|pending|passed|failed`；`user_decision_status=pending|accepted_as_knowledge|saved_as_note|rejected`；`lifecycle_status=current|superseded|closed`。

#### KnowledgeAssetResponse 与 UserNoteResponse

| 类型 | 字段 |
| --- | --- |
| `KnowledgeAssetResponse` | R: `knowledge_asset_id, source_knowledge_contribution_candidate_version_id, asset_type, title, content, judgment_card_version_id, evidence_unit_ids, validity_status, lifecycle_status, revision, created_by, created_at, audit_finding_ids, warning_acknowledgement_ids`；N: `withdrawn_at` |
| `UserNoteResponse` | R: `user_note_id, source_knowledge_contribution_candidate_version_id, research_case_id, title, content, note_type, lifecycle_status, revision, created_by, created_at` |

Asset `asset_type=claim_note|evidence_note|knowledge_gap`、`validity_status=valid|needs_review|invalid`、`lifecycle_status=active|withdrawn|archived`。Note `note_type=personal_note|user_viewpoint`、`lifecycle_status=active|withdrawn|archived`；UserNote 响应不得含有“系统验证”标志。

### 3.6 其余 Minimum Slice 资源表示

| 类型 | 规范字段 |
| --- | --- |
| `ChunkResponse` | R: `chunk_id, knowledge_item_version_id, position, content_hash, chunker_version, created_at`；N: `parent_chunk_id, previous_chunk_id, next_chunk_id, section_path, page, timestamp_seconds, start_offset, end_offset, token_count`。普通响应不含完整 Chunk 文本。 |
| `ResearchQuestionResponse` | R: `research_question_id, research_case_id, question_text, question_role, created_by, created_at`；N: `parent_question_id`。`question_role=root|follow_up|clarification|derived`。 |
| `SourceResolutionResponse` | R: `source_resolution_id, research_question_id, resolution_stage, raw_anchor, requested_access_policy, resolution_status, candidate_knowledge_item_ids, created_at`；N: `requested_version_hint, resolved_knowledge_item_id, resolved_knowledge_item_version_id, ambiguity_reason, failure_reason`。条件必填遵循领域模型。 |
| `KnowledgeScopeSourceBindingResponse` | R: `knowledge_scope_source_binding_id, knowledge_scope_version_id, source_resolution_id, knowledge_item_id, access_policy, created_at`；N: `knowledge_item_version_id, analysis_role`。 |
| `ResearchAttemptResponse` | R: `research_attempt_id, research_run_id, attempt_number, attempt_mode, status, created_at`；N: `previous_attempt_id, started_at, ended_at, failure_category, failure_reason`。 |
| `RetrievalRunResponse` | R: `retrieval_run_id, research_attempt_id, knowledge_scope_source_binding_id, retrieval_channel, query_ref, status, created_at`；N: `retrieval_outcome, index_generation_id, started_at, ended_at, failure_reason`。`retrieval_channel` 使用开放代码对象。 |
| `JudgmentRationaleResponse` | R: `judgment_rationale_id, claim_version_id, rationale_profile, evidence_link_ids, reasoning_summary, created_at`。`rationale_profile` 是带 `profile_type=fact|interpretation|inference|hypothesis|recommendation` 的判别联合对象；analogy 使用 `profile_type=inference` 且固定 `reasoning_method=analogy`；不同 profile 的必填内容遵循领域模型，不返回与类型无关的空字段。 |
| `ClaimEvidenceLinkResponse` | R: `claim_evidence_link_id, claim_version_id, research_evidence_use_id, evidence_unit_id, evidence_role, support_strength, created_at`；N: `scope_note`。`support_strength={level, reason}`，level 为 `weak|moderate|strong`。 |
| `JudgmentAuditResponse` | R: `judgment_audit_id, judgment_card_version_id, audit_policy_version, audit_run_status, finding_ids, created_at`；N: `gate_result, started_at, completed_at`。 |
| `AuditFindingResponse` | R: `audit_finding_id, judgment_audit_id, affected_claim_version_ids, finding_type, severity, description, supporting_reason, policy_version, created_at`；N: `recommended_revision, risk_trigger_condition`。`finding_type` 使用开放代码对象；`severity=warning|blocking`。 |
| `WarningAcknowledgementResponse` | R: `warning_acknowledgement_id, audit_finding_id, judgment_card_version_id, acknowledged_by, acknowledged_at`；N: `acknowledgement_note`。 |
| `DecisionFitnessResponse` | R: `decision_fitness_id, judgment_card_version_id, policy_version, allowed_uses, forbidden_uses, required_conditions, risk_ceiling, escalation_triggers, created_at`。`risk_ceiling` 完整返回成本、可逆性、外部影响和专家复核限制，不使用单一分数。 |

Attempt `attempt_mode=retrieval|reuse_existing_evidence`，状态为 `created|running|completed|failed|cancelled|stale`。Retrieval 的 `created / running` 状态固定返回 `retrieval_outcome=null`；进入 `completed / failed / cancelled` 后 outcome 必须非 null，且合法组合符合领域模型。SourceResolution `resolution_stage=preliminary|full`、`resolution_status=resolved|ambiguous|not_found|unavailable`。

### 3.7 Core Alpha Complete 资源表示

| 类型 | 规范字段 |
| --- | --- |
| `ResearchTriageResponse` | R: `research_triage_id, research_case_id, preliminary_source_resolution_ids, recommended_path, estimated_attention_cost, estimated_resource_budget, activation_recommendation, reason, decision_status, created_at`；N: `selected_path, decided_at`。 |
| `AttentionBacklogItemResponse` | R: `attention_backlog_item_id, source_type, title, reason, status, revision, created_at`；N: `source_ref_id, question_text, external_source_ref, external_lead_summary, estimated_attention_cost, activated_research_case_id, resolved_at`。 |
| `JudgmentReviewResponse` | R: `judgment_review_id, research_case_id, judgment_card_version_id, trigger_type, status, revision, created_at`；N: `trigger_ref_id, completed_at`。 |
| `ReviewResultResponse` | R: `review_result_id, judgment_review_id, result_type, reason, affected_claim_version_ids, recommended_next_step, created_at`；N: `new_research_run_id`。 |
| `ActionReviewResponse` | R: `action_review_id, action_commitment_id, reviewed_at, expected_result, actual_result, assumption_failures, stop_condition_triggered, judgment_review_required, created_at`。 |

Triage path 为 `direct_answer|quick_research|standard_research|deep_research|clarification_required`，decision status 为 `pending|accepted|adjusted|overridden`。Backlog、Review 与 ReviewResult 的枚举完全采用领域模型，条件字段不满足时不得以 null 规避必填约束。

### 3.8 Trace 与 Developer 技术记录表示

`PublicResearchTraceResponse` 用于普通产品 API；其余技术记录主要用于 Developer API。所有 payload、预览和实现配置仍受第 8 章脱敏边界限制。

| 类型 | 规范字段 |
| --- | --- |
| `IndexGenerationResponse` | R: `index_generation_id, index_type, knowledge_item_version_id, chunk_strategy_version, index_strategy_version, status, expected_item_count, actual_item_count, validation_summary, created_at`；N: `embedding_model, embedding_dimension, previous_generation_id, ready_at, invalidated_at`。 |
| `TraceEventResponse` | R: `trace_event_id, event_type, occurred_at, actor_type, aggregate_type, aggregate_id, aggregate_revision, correlation_id, causation_id, payload_ref, payload_hash, schema_version`；N: `actor_id, research_case_id, research_run_id, research_attempt_id`。 |
| `PublicResearchTraceResponse` | R: `research_run_id, projection_checkpoint, knowledge_scope_version_id, research_plan_version_id, attempt_summaries, retrieval_summaries, research_evidence_use_ids, judgment_card_version_ids, judgment_audit_ids, research_disposition_ids, domain_timeline, observed_at`；N: `research_run_outcome_id`。普通响应不含 Provider、模型、索引策略、Capability、fallback 或技术失败载荷。 |
| `DeveloperResearchTraceResponse` | R: `research_run_id, projection_checkpoint, events, input_snapshot_refs, requested_capabilities, available_capabilities, missing_capabilities, provider_invocations, model_and_index_versions, fallback_path, quality_impact, technical_failures, observed_at`。 |
| `CaseActivityLogResponse` | R: `research_case_id, projection_checkpoint, events, observed_at`。 |
| `MaterialManifestResponse` | R: `material_manifest_id, invocation_type, invocation_id, provider, purpose, policy_version, policy_decision, materials, contains_profile_data, created_at`；N: `research_case_id, research_run_id, research_attempt_id, capability_invocation_id, intake_or_import_context_ref`。每个 `materials` 元素完整包含 `material_ref, source_version_id, content_hash, location, length, sensitivity_level, redacted_preview`，其中 `source_version_id, location, redacted_preview` 可为 null。 |
| `RunExecutionSpecResponse` | R: `run_execution_spec_id, research_run_id, knowledge_scope_version_id, source_resolution_ids, research_plan_version_id, source_version_ids, index_generation_ids, retrieval_strategy_version, context_strategy_version, embedding_contract, reranker_contract, capability_contracts, allowed_implementations, fallback_policy, prompt_version, output_schema_version, audit_policy_version, decision_fitness_policy_version, egress_policy_version, system_safety_limits, created_at`；N: `budget_snapshot_id`。 |
| `ExecutionCheckpointResponse` | R: `execution_checkpoint_id, research_run_id, checkpoint_type, input_revision, completed_at, result_ref_id, idempotency_key`；N: `research_attempt_id`。 |
| `CapabilityCandidateResultResponse` | R: `capability_candidate_result_id, invocation_ref, execution_status, candidate_payload_ref, output_schema_version, implementation_version, provider, resource_consumption, idempotency_identity, fallback_path, quality_impact, warnings, failure_category, created_at`。 |
| `BudgetSnapshotResponse` | R: `budget_snapshot_id, research_run_id, limits, created_at`。 |
| `BudgetConsumptionRecordResponse` | R: `budget_consumption_record_id, research_run_id, consumption_type, consumed_amount, remaining_budget, occurred_at, invocation_ref`。 |
| `ResearchBudgetStatusResponse` | R: `budget_snapshot, consumed, remaining, consumption_records, observed_at`。`budget_snapshot` 使用 `BudgetSnapshotResponse`，`consumption_records` 使用 `BudgetConsumptionRecordResponse`。 |
| `ProjectionStatusResponse` | R: `projection_name, checkpoint, lag, status, observed_at`；N: `failure_summary`。 |

`events` 使用 `TraceEventResponse`。每项 material 是不可拆分的出站审计单元，不使用平行数组；`redacted_preview` 默认 null，仅在本地策略允许且有诊断必要时返回。技术记录不是领域状态权威。

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
| `POST /alpha/research-cases/{research_case_id}/commands/derive` | 200 | expected_revision、source_question_id 或 judgment_card_version_id、title、question_text；data 返回新 Case |

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
| `GET /alpha/knowledge-scope-versions/{knowledge_scope_version_id}` | 200 | 读取历史或当前版本 |
| `POST /alpha/knowledge-scope-versions/{knowledge_scope_version_id}/commands/adjust` | 200 | 创建新版本并 supersede 旧版本 |

创建和 adjust 请求包含 `expected_revision`、`default_access_policy`、`scope_mode=evidence_only` 和 bindings。default policy 只能是 allowed/excluded。adjust 必须绑定路径中的 current version ID。

### 4.5 ResearchPlan

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `POST /alpha/research-cases/{research_case_id}/research-plans` | 201 | 创建初始计划版本 |
| `GET /alpha/research-cases/{research_case_id}/research-plans` | 200 | 列出该 Case 的逻辑 Plan 与版本引用 |
| `GET /alpha/research-plans/{research_plan_id}/current` | 200 | 读取该逻辑 Plan 的 current 版本 |
| `GET /alpha/research-plan-versions/{research_plan_version_id}` | 200 | 读取指定版本 |
| `POST /alpha/research-plan-versions/{research_plan_version_id}/commands/adjust` | 200 | 创建新版本并 supersede 旧版本 |

请求字段：`expected_revision`、`knowledge_scope_version_id`、`research_mode`、`primary_objective`、`evidence_requirements`、`minimum_completion_condition`；stop conditions 与正式预算为 Core Complete 可选字段。

adjust 不得修改已被 Run 绑定的历史版本，只能创建新的 plan version ID。

### 4.6 ResearchRun

#### `POST /alpha/research-cases/{research_case_id}/research-runs`

```json
{
  "expected_research_case_revision": 6,
  "research_question_id": "rq_...",
  "knowledge_scope_version_id": "ksv_...",
  "research_plan_version_id": "rpv_...",
  "execution_mode": "synchronous"
}
```

execution_mode 为 `synchronous / asynchronous`，默认 synchronous。

ResearchRun 是新聚合，不传自身 `expected_revision`。`expected_research_case_revision` 只断言启动时所依据的 Case 仍是用户看到的版本；它不表示 Run revision，也不因名称简化为通用 `expected_revision`。

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
| `GET /alpha/judgment-card-versions/{judgment_card_version_id}` | 200 | JudgmentCard、Claim version 引用、状态与缺口 |
| `GET /alpha/judgment-card-versions/{judgment_card_version_id}/claims` | 200 | Claim、Rationale、ClaimEvidenceLink；Link 保留 research_evidence_use_id |
| `GET /alpha/claims/{claim_id}/current` | 200 | Claim 当前语义版本 |
| `GET /alpha/claim-versions/{claim_version_id}` | 200 | Claim 指定历史版本 |
| `GET /alpha/judgment-card-versions/{judgment_card_version_id}/audits` | 200 | 该判断版本的审计列表 |
| `GET /alpha/judgment-card-versions/{judgment_card_version_id}/audits/current` | 200 | 当前被领域规则接纳的审计或 null |
| `GET /alpha/judgment-audits/{judgment_audit_id}` | 200 | 指定 JudgmentAudit 与 Finding |
| `GET /alpha/judgment-card-versions/{judgment_card_version_id}/decision-fitness/current` | 200 | 当前被领域规则接纳的 DecisionFitness 或 null |
| `GET /alpha/decision-fitness/{decision_fitness_id}` | 200 | 指定 DecisionFitness |
| `POST /alpha/audit-findings/{audit_finding_id}/commands/acknowledge` | 200 | 创建 WarningAcknowledgement；expected_revision、judgment_card_version_id、acknowledgement_note |
| `POST /alpha/claim-versions/{claim_version_id}/commands/set-user-attitude` | 200 | expected_revision、user_attitude |

blocking Finding 不允许 acknowledge。修改 user attitude 不改变 evidence status 或 Claim 语义版本。

### 4.8 Decision

DispositionProposal 在 JudgmentAudit 与 DecisionFitness 完成后，由内部 `CreateDispositionProposalCommand` 生成，不提供公开创建路由。其 `/current` 仅表示 `lifecycle_status=current`，不表示用户已经接受。

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `GET /alpha/research-cases/{research_case_id}/disposition-proposals` | 200 | Case 下 Proposal 列表，可按 lifecycle_status 筛选 |
| `GET /alpha/disposition-proposals/{disposition_proposal_id}/current` | 200 | 逻辑 Proposal 当前版本或 null |
| `GET /alpha/disposition-proposal-versions/{disposition_proposal_version_id}` | 200 | 指定版本 |
| `POST /alpha/disposition-proposal-versions/{disposition_proposal_version_id}/commands/accept` | 200 | 形成 ResearchDisposition |
| `POST /alpha/disposition-proposal-versions/{disposition_proposal_version_id}/commands/adjust` | 200 | 形成新 Proposal 版本 |
| `POST /alpha/disposition-proposal-versions/{disposition_proposal_version_id}/commands/reject` | 200 | 记录拒绝，不形成 Disposition |
| `GET /alpha/research-dispositions/{research_disposition_id}` | 200 | 最终处置事实 |

三个决定命令都包含 DispositionProposal 聚合的 `expected_revision`。accept 还包含 `judgment_card_version_id`、`decision_fitness_id` 和有效 `warning_acknowledgement_ids`；adjust 还包含新的 disposition type、reason 及 defer/observe 条件。

### 4.9 普通 ResearchTrace

`GET /alpha/research-runs/{research_run_id}/trace` 返回 `PublicResearchTraceResponse`：Scope、Plan、Attempt/Retrieval 摘要、证据使用、判断、审计、Outcome、处置引用和领域时间线。普通响应不暴露 Capability、Provider、模型、索引参数、fallback、技术失败载荷、完整 Prompt 或完整私有原文。

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
| `POST /alpha/attention-backlog-items/{attention_backlog_item_id}/commands/activate` | 200 | 激活并关联或创建 Case；data 返回 `activation_result=associated_existing_case|created_new_case` 与 research_case_id |
| `POST /alpha/attention-backlog-items/{attention_backlog_item_id}/commands/discard` | 200 | 丢弃 |
| `POST /alpha/attention-backlog-items/{attention_backlog_item_id}/commands/archive` | 200 | 归档 |

创建 AttentionBacklogItem 不传 `expected_revision`；activate、discard、archive 要求该 Item 的 `expected_revision`。saved question 激活时原子创建 ResearchCase 与 ResearchQuestion。

### 5.3 JudgmentReview

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `POST /alpha/judgment-card-versions/{judgment_card_version_id}/reviews` | 201 | 发起 JudgmentReview |
| `GET /alpha/judgment-reviews/{judgment_review_id}` | 200 | Review 与 ReviewResult |
| `POST /alpha/judgment-reviews/{judgment_review_id}/commands/cancel` | 200 | 取消未完成复核 |

创建 JudgmentReview 不传 `expected_revision`，但必须绑定具体 JudgmentCard version；cancel 要求 JudgmentReview 的 `expected_revision`。ReviewResult 由内部 `CompleteJudgmentReviewCommand` 与 Review 完成状态原子创建，不提供公开创建路由。需要改变处置时生成新的 DispositionProposal。

### 5.4 Action

#### 创建与调整 ActionProposal

`POST /alpha/research-dispositions/{research_disposition_id}/commands/create-action-proposal` 返回 `200`；它是命令端点，即使原子创建 ActionProposal 也不改用 201。

请求包含 `expected_research_case_revision`、`judgment_card_version_id`、`decision_fitness_id`、目标、步骤、预期收益、停止条件、复盘时间、风险输入和 warning acknowledgements。ActionProposal 是新聚合，不传自身 `expected_revision`；命名 revision 只断言该 ResearchDisposition 仍属于 Case 的当前有效处置。

只有当前有效且 disposition type 为 proceed_to_action 的处置可以调用；判断、用途、warning 或 risk ceiling 不满足时返回 409。

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `GET /alpha/research-dispositions/{research_disposition_id}/action-proposals/current` | 200 | 该处置下唯一 lifecycle_status=current 的 ActionProposal 或 null |
| `GET /alpha/research-cases/{research_case_id}/action-proposals` | 200 | Case 下 Proposal 列表，可按 research_disposition_id、lifecycle_status 筛选 |
| `GET /alpha/action-proposal-versions/{action_proposal_version_id}` | 200 | 指定版本 |
| `POST /alpha/action-proposal-versions/{action_proposal_version_id}/commands/adjust` | 200 | 新版本、重新风险和用途校验 |
| `POST /alpha/action-proposal-versions/{action_proposal_version_id}/commands/accept` | 200 | 创建 ActionCommitment |
| `POST /alpha/action-proposal-versions/{action_proposal_version_id}/commands/reject` | 200 | 记录拒绝 |

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

adjust 命令包含 `expected_revision`、当前 Candidate version ID、修订后的内容或证据关系，并产生新版本与重新校验。accept-as-knowledge、save-as-note、reject 只提交 `expected_revision`、`judgment_card_version_id` 和适用的 `warning_acknowledgement_ids`；它们使用当前 Candidate version 已冻结的 `evidence_unit_ids`，不得在决定命令中替换证据。决定命令出现 EvidenceUnit 字段属于请求 Schema 错误，返回 `422 validation_error`。validation failed 不能接受为知识，但可以保存为笔记。

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

### 6.1 CommandContext 与内部 HTTP 身份

进程内命令使用可信 `CommandContext`，包含：`command_id, actor_type, actor_id, idempotency_key, correlation_id, causation_id, trace_id`。这些字段由 Application Command Handler 注入，不属于业务 Payload。

启用内部 HTTP Adapter 时：

- 服务身份来自 mTLS、服务令牌或等价内部认证上下文；请求体不得自声明身份。
- 幂等键只来自 `Idempotency-Key` Header；请求体不得重复携带。
- correlation ID、causation ID 与 trace ID 来自可信传输元数据或由服务端生成，不进入 Payload。
- HTTP Adapter 将已认证身份、Header 与可信追踪元数据映射为 `CommandContext`。
- TraceEvent 记录已认证 actor，而不是 Payload 中的字符串。
- 缺少身份返回 `401 authentication_required`；无权执行 operation 返回 `403 forbidden`。

### 6.2 SubmitCandidateResultCommand

进程内调用优先；启用 HTTP Adapter 时固定为 `POST /internal/alpha/candidate-results`，成功处理返回 `200`。

Payload：

```json
{
  "operation_type": {
    "code": "judgment_candidate",
    "registry_version": "core-alpha-v1"
  },
  "research_run_id": "run_...",
  "research_attempt_id": "attempt_...",
  "run_execution_spec_id": "spec_...",
  "input_versions": {
    "research_run_revision": 7,
    "knowledge_scope_version_id": "ksv_...",
    "research_plan_version_id": "rpv_..."
  },
  "lifecycle_generation": 3,
  "capability_implementation_version": "string",
  "output_schema_version": "string",
  "candidate_result": {}
}
```

前置校验：Run revision、Attempt 归属与状态、RunExecutionSpec、Scope/Plan 版本、生命周期代数、Tombstone、输出 Schema 和 operation 权限必须全部匹配。

结果：

```json
{
  "data": {
    "submission_status": "accepted_for_domain_processing",
    "capability_candidate_result_id": "ccr_...",
    "follow_up_commands": []
  },
  "command": {},
  "consistency": {}
}
```

`submission_status` 固定为 `accepted_for_domain_processing|rejected_stale|rejected_version_mismatch|rejected_lifecycle|rejected_tombstoned|rejected_schema`。`capability_candidate_result_id` 始终出现在响应中：accepted 时必须非 null，任一 rejected 状态固定为 null。幂等重放完整返回首次 `submission_status`，仅通过 `command.idempotent_replay=true` 表示本次是重放，不创造第二种处理结果。rejected 结果不产生权威领域状态，只追加受限的拒绝 TraceEvent。accepted 结果创建技术 CandidateResult 与 TraceEvent，并可列出待执行的后续内部命令；它本身仍不是 JudgmentCard、Claim 或其他领域事实。外层 JSON 无效返回 422；通过 Schema 后的候选拒绝使用上述 200 结果，不混用 HTTP 错误。

### 6.3 CreateDispositionProposalCommand

Payload 必填：`research_case_id, judgment_card_version_id, judgment_card_revision, judgment_audit_id, decision_fitness_id, proposed_disposition_type, reason`；可选：`expected_research_case_revision, warning_acknowledgement_ids, expires_at, defer_until, observation_condition`。仅当命令同步切换 ResearchCase 的 current 引用时，`expected_research_case_revision` 条件必填；不改变 Case 时固定为 null 或省略。

前置条件：JudgmentCard 为 current、有效且可采纳；指定 Audit 与 DecisionFitness 当前生效；warning 确认仍有效；处置类型满足用途和条件字段。命令校验 JudgmentCard revision；若同时切换 Case 的相关 current 引用，还必须校验 ResearchCase revision。

成功原子创建 DispositionProposal、追加 TraceEvent，并返回 `{ "disposition_proposal": {} }`。领域拒绝原因固定为 `judgment_not_current|judgment_not_acceptable|audit_not_current|decision_fitness_not_current|warning_not_acknowledged|disposition_not_allowed|version_mismatch`，映射为 409。命令只影响新 Proposal 聚合；若改变 Case current 引用，则同时在 consistency 中返回 Case 新 revision。

### 6.4 CreateKnowledgeContributionCandidateCommand

Payload 必填：`research_case_id, judgment_card_version_id, judgment_card_revision, contribution_type, proposed_content, evidence_unit_ids`；可选：`target_knowledge_asset_id, audit_finding_ids, warning_acknowledgement_ids`。

前置条件：JudgmentCard 为 current、有效且非 blocked；EvidenceUnit 与该判断的 ResearchEvidenceUse/ClaimEvidenceLink 可追溯；候选不提升 Claim evidence status。命令校验 JudgmentCard revision 与所有 EvidenceUnit revision 快照。

成功原子创建 Candidate 与 TraceEvent，返回 `{ "knowledge_contribution_candidate": {} }`。拒绝原因固定为 `judgment_not_current|judgment_blocked|judgment_invalid|evidence_not_linked|evidence_invalid|version_mismatch`，映射为 409。没有沉淀价值是合法的“未触发命令”，不得伪造空 Candidate。

### 6.5 CompleteJudgmentReviewCommand

Payload 必填：`judgment_review_id, expected_revision, result_type, reason, affected_claim_version_ids, recommended_next_step`；可选：`new_research_run_id`。

前置条件：Review 当前为可完成状态；目标 JudgmentCard version 与触发依据仍匹配；`new_research_run_id` 如存在必须属于同一 Case。命令校验 JudgmentReview revision。

成功时 Review 进入 completed、ReviewResult 创建并追加同一因果链的 TraceEvent，三者原子提交；固定 data 见 2.4.1。拒绝原因固定为 `review_not_completable|judgment_version_mismatch|research_run_mismatch|concurrency_conflict`，映射为 409。若结果建议重新研究或改变处置，`follow_up_commands` 只返回命令引用，不在本事务中静默创建新 Run 或 Proposal。

### 6.6 内部命令共同规则

- 每个命令使用独立内部幂等身份；重放不重复创建领域对象或 TraceEvent。
- 每个成功结果返回 `command`、`consistency.primary_aggregate` 和所有 `affected_aggregates`。
- `SubmitCandidateResultCommand` 的 primary aggregate 为 ResearchRun；`CreateDispositionProposalCommand` 为新 DispositionProposal；`CreateKnowledgeContributionCandidateCommand` 为新 Candidate；`CompleteJudgmentReviewCommand` 为 JudgmentReview。同步改变其他聚合时必须逐项列入 affected aggregates。
- 只有 Domain Module 可以形成权威状态；Worker、HTTP Adapter 和 CandidateResult 不得直接写 Repository。
- 内部命令产生的 TraceEvent 必须包含 correlation、causation、已认证 actor、聚合 revision 和 payload hash。

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
| 409 | concurrency_conflict | expected_revision 或命名上游 revision 断言不匹配 |
| 409 | version_conflict | version ID 非 current 或上游版本不匹配 |
| 409 | source_binding_conflict | Binding 与 SourceResolution 的作品、版本或访问政策不一致 |
| 409 | lifecycle_conflict | 当前状态不允许该命令 |
| 409 | projection_not_ready | 投影未达到 minimum revision/checkpoint |
| 409 | decision_fitness_violation | 用途或风险超过 DecisionFitness |
| 409 | warning_acknowledgement_required | 缺少有效 warning 确认 |
| 422 | validation_error | JSON、枚举或字段类型错误 |
| 422 | condition_required | 条件必填字段缺失或互斥字段冲突 |
| 422 | invalid_cursor | cursor 无效、过期或与主体、筛选、排序不匹配 |
| 503 | async_execution_unavailable | 请求异步但能力未启用 |
| 503 | dependency_unavailable | 命令接受前所需依赖不可用 |

409 projection_not_ready 与 503 错误必须设置 `retryable=true`；其余错误根据 details 明确是否可重试。

## 8. Developer Diagnostics

Developer API 使用独立访问策略，不属于普通产品 API。

### 8.1 Minimum Slice Developer API

| 方法与路由 | 输出 |
| --- | --- |
| `GET /alpha/developer/research-runs/{research_run_id}/trace` | `DeveloperResearchTraceResponse` |
| `GET /alpha/developer/material-manifests` | 按 Run、Provider、purpose 查询 MaterialManifest |
| `GET /alpha/developer/index-generations` | IndexGeneration metadata |
| `GET /alpha/developer/projections/status` | checkpoint、lag 和失败摘要 |

Minimum Slice 不注册 CaseActivityLog 与预算诊断路由，也不得返回伪造的空活动投影或 BudgetSnapshot。

### 8.2 Core Alpha Complete Developer API

| 方法与路由 | 输出 |
| --- | --- |
| `GET /alpha/developer/research-cases/{research_case_id}/activity` | CaseActivityLog |
| `GET /alpha/developer/research-runs/{research_run_id}/budget` | `ResearchBudgetStatusResponse` |

这两类路由只能在 Complete 对象和预算记录正式存在后由 Complete Diagnostics 扩展注册。

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

$legacyTerms = @(
  "Research" + "Task",
  "Research" + "Answer",
  "Audit" + "Report",
  "Ministry" + "Report",
  "Chancellor" + "Briefing",
  "Episode" + "Spec",
  "实现" + "说明",
  "implementation" + " note"
)
$legacyHits = Select-String -Path docs/API_CONTRACTS.md -Pattern $legacyTerms
if ($legacyHits) { $legacyHits; throw "发现旧契约残留" }

$requiredTerms = @(
  "ResearchCase", "KnowledgeScope", "ResearchRunOutcome",
  "JudgmentCard", "DecisionFitness", "DispositionProposal",
  "expected_revision", "Idempotency-Key",
  "KnowledgeContributionCandidate", "SubmitCandidateResultCommand",
  "OpenCodeValue", "PublicResearchTraceResponse",
  "DeveloperResearchTraceResponse", "ResearchBudgetStatusResponse",
  "expected_research_case_revision"
)
foreach ($term in $requiredTerms) {
  if (-not (Select-String -Path docs/API_CONTRACTS.md -SimpleMatch $term)) {
    throw "缺少关键契约：$term"
  }
}

$ambiguousStatus = @("200" + " 或 " + "201", "200" + "/" + "201", "视情况" + "返回")
$ambiguousHits = Select-String -Path docs/API_CONTRACTS.md -Pattern $ambiguousStatus
if ($ambiguousHits) { $ambiguousHits; throw "发现模糊成功状态码" }

$oldVersionRoutes = @(
  "/alpha/knowledge-" + "scopes/{knowledge_scope_version_id}",
  "/alpha/judgment-" + "cards/{judgment_card_version_id}",
  "/alpha/claims/{claim_" + "version_id}/commands"
)
$routeHits = Select-String -Path docs/API_CONTRACTS.md -SimpleMatch $oldVersionRoutes
if ($routeHits) { $routeHits; throw "发现逻辑资源名与版本 ID 混用" }
```

人工验收：

- 每个版本化对象具有 current 与历史版本查询；每个允许用户调整的版本化对象具有 adjust 契约；
- 每个 Proposal 具有明确产生入口和用户决定命令；
- 每个 POST 标明状态码、幂等与适用的 revision 并发断言；
- 异步响应返回 ResearchRun，不出现通用任务对象；
- SourceResolution 与 RunOutcome 不被映射成 HTTP 404/503；
- 行动与知识命令绑定 JudgmentCard version、DecisionFitness 和 warning；
- 3.5 至 3.8 覆盖所有公开和 Developer 查询资源，不存在“实现时再补 Schema”的保留条款；
- 每个跨聚合命令具有固定 data 键、primary aggregate 与 affected aggregates；
- 内部 HTTP Payload 不含自声明身份或重复幂等键；
- 仅 `docs/API_CONTRACTS.md` 发生变化。
