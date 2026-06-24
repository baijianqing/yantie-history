# MetaOS Alpha API 契约

状态：Core Alpha 目标 API 契约冻结候选

任务标识：`A0-DOC-004-R1.1`

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

命令响应直接返回本次事务形成的权威资源。`primary_aggregate` 表示命令的主要并发边界；同一事务改变的其他聚合放入 `affected_aggregates`。新建且不拥有 revision 的不可变事实可省略两者，只返回资源 ID。跨聚合命令不得用一个 revision 代表多个聚合。

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

- 单聚合或明确聚合范围查询可以使用 `minimum_revision`。
- 列表投影使用 `minimum_checkpoint`，不得把多个聚合压缩为一个 revision。
- 使用 `minimum_revision` 或 `minimum_checkpoint` 时可传 `consistency_wait_ms`；默认 `0`，最大 `5000`。
- 权威存储响应必须为 `source=authoritative_store` 且 `is_stale=false`。
- 投影无法在等待窗口内达到要求时返回 `409 projection_not_ready`，不得返回旧数据冒充满足一致性要求；错误 details 必须返回目标 checkpoint/revision、当前值和实际等待毫秒数。
- 列表使用不透明、签名 cursor；`limit` 默认 50，最大 200。cursor 绑定认证主体、筛选条件、排序和快照水位，默认稳定排序为 `created_at DESC, resource_id DESC`。
- cursor 不使用数据库 offset。无效、过期或与当前主体、筛选、排序不匹配时返回 `422 invalid_cursor`。
- 同一分页会话固定快照水位，防止翻页时重复或漏读；水位后新增记录只在新的分页会话中出现。

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

### 3.5 规范 JSON 类型

- ID、Hash、时间和开放代码值均序列化为 JSON string；时间必须是 UTC ISO 8601，Hash 使用带算法前缀的小写十六进制，例如 `sha256:...`。
- 枚举使用本文或 `docs/DOMAIN_MODEL.md` 冻结的英文代码值，不返回显示文案代替代码值。
- 资源间关系默认使用 ID，不嵌套另一份权威资源；需要显示信息时可附加非权威的 `display` 对象。
- `nullable` 字段必须显式返回 `null`；未声明为 nullable 的必填字段不得省略。列表字段始终返回数组，无值时返回 `[]`。
- 开放代码值表示为 `{ "code": "...", "registry_version": "..." }`。`location` 表示为 `{ "section_path": [], "page": null, "timestamp_seconds": null, "start_offset": null, "end_offset": null }`，至少一个定位维度非空。
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

### 3.6 其他资源表示

未在 3.5 单列的资源仍须完整返回 `docs/DOMAIN_MODEL.md` 中该对象的全部公开字段，并遵守相同的 R/N/C、枚举、ID 引用和隐藏字段规则。接口实现前必须把对应表示加入本章；路由表中的自然语言输出说明不能替代规范 Schema。

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
| `GET /alpha/knowledge-scopes/{knowledge_scope_version_id}` | 200 | 读取历史或当前版本 |
| `POST /alpha/knowledge-scopes/{knowledge_scope_version_id}/commands/adjust` | 200 | 创建新版本并 supersede 旧版本 |

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
| `GET /alpha/judgment-cards/{judgment_card_version_id}/audits` | 200 | 该判断版本的审计列表 |
| `GET /alpha/judgment-cards/{judgment_card_version_id}/audits/current` | 200 | 当前被领域规则接纳的审计或 null |
| `GET /alpha/judgment-audits/{judgment_audit_id}` | 200 | 指定 JudgmentAudit 与 Finding |
| `GET /alpha/judgment-cards/{judgment_card_version_id}/decision-fitness/current` | 200 | 当前被领域规则接纳的 DecisionFitness 或 null |
| `GET /alpha/decision-fitness/{decision_fitness_id}` | 200 | 指定 DecisionFitness |
| `POST /alpha/audit-findings/{audit_finding_id}/commands/acknowledge` | 200 | 创建 WarningAcknowledgement；expected_revision、judgment_card_version_id、acknowledgement_note |
| `POST /alpha/claims/{claim_version_id}/commands/set-user-attitude` | 200 | expected_revision、user_attitude |

blocking Finding 不允许 acknowledge。修改 user attitude 不改变 evidence status 或 Claim 语义版本。

### 4.8 Decision

DispositionProposal 在 JudgmentAudit 与 DecisionFitness 完成后，由内部 `CreateDispositionProposalCommand` 生成，不提供公开创建路由。“current”表示当前被领域规则接纳的版本，不表示按时间排序的最新记录。

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
| `POST /alpha/attention-backlog-items/{attention_backlog_item_id}/commands/activate` | 200 | 激活并关联或创建 Case；data 返回 `activation_result=associated_existing_case|created_new_case` 与 research_case_id |
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

`POST /alpha/research-dispositions/{research_disposition_id}/commands/create-action-proposal` 返回 `200`；它是命令端点，即使原子创建 ActionProposal 也不改用 201。

请求包含 `expected_revision`（目标为 ResearchCase）、`judgment_card_version_id`、`decision_fitness_id`、目标、步骤、预期收益、停止条件、复盘时间、风险输入和 warning acknowledgements。

只有当前有效且 disposition type 为 proceed_to_action 的处置可以调用；判断、用途、warning 或 risk ceiling 不满足时返回 409。

| 方法与路由 | 成功 | 行为 |
| --- | ---: | --- |
| `GET /alpha/research-dispositions/{research_disposition_id}/action-proposals/current` | 200 | 该处置下当前被领域规则接纳的 ActionProposal 或 null |
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

adjust 命令包含 `expected_revision`、当前 Candidate version ID、修订后的内容或证据关系，并产生新版本与重新校验。accept-as-knowledge、save-as-note、reject 只提交 `expected_revision`、`judgment_card_version_id` 和适用的 `warning_acknowledgement_ids`；它们使用当前 Candidate version 已冻结的 `evidence_unit_ids`，不得在决定命令中替换证据。若客户端额外提交证据引用，必须与当前版本完全一致，否则返回 `409 version_conflict`。validation failed 不能接受为知识，但可以保存为笔记。

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
