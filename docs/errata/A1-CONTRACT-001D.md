# A1-CONTRACT-001D Decision 与 Internal Command 契约映射记录

状态：完成，发现三项待 Epic Gate 合并的机械勘误

依赖：`docs/API_CONTRACTS.md`（`A0-DOC-004-R1.2.1`）与 `docs/DOMAIN_MODEL.md`（`A0-DOC-003-R1.2.2`）

## 映射结果

- 本切片使用 `metaos.core_alpha.contracts.decision` 与 `metaos.core_alpha.contracts.internal`；统一包导出留给 `A1-CONTRACT-001` Epic Gate。
- DispositionProposal 与 ResearchDisposition 分别表示系统建议和用户确认事实；accept、adjust、reject 使用独立请求与固定 data 形状。
- `defer_decision` 只携带 `defer_until`，`observe` 只携带 `observation_condition`，其他处置不得夹带二者。
- accept 返回中的 Proposal、Disposition 和 ResearchCase 必须属于同一 Case，并引用同一 JudgmentCard 与 DecisionFitness。
- Internal Command Payload 不包含 actor、CommandContext、Idempotency-Key 或 Trace 字段；这些值只能由可信 Handler 或内部 HTTP Adapter 注入。
- `SubmitCandidateResultCommand` 使用 Run revision、Scope/Plan version、RunExecutionSpec 和 lifecycle generation 锁定输入；accepted 与 rejected 结果分别表达是否形成 CapabilityCandidateResult。
- 本切片仅映射 Minimum Slice 的 `SubmitCandidateResultCommand` 与 `CreateDispositionProposalCommand`。Core Alpha Complete 的 Review 和 Knowledge Contribution 内部命令由对应 A2 Contract 子任务定义，不在阶段1提前实现。

## Epic Gate 机械勘误

### 1. operation_type 表示

领域模型将 Capability operation 定义为开放代码值，API 通用规则也要求开放代码使用 `{code, registry_version}`，但第 6.2 节示例把 `operation_type` 写成裸字符串。

本切片采用 `OpenCodeValue`。Epic Gate 应机械修正示例，不改变 operation 语义。

### 2. rejected submission 的 CandidateResult ID

第 6.2 节固定结果示例始终返回 `capability_candidate_result_id`，同时又规定 rejected 结果不创建 CandidateResult。两者无法同时成立。

本切片采用：

```text
accepted_for_domain_processing -> capability_candidate_result_id 必填
任一 rejected_* -> capability_candidate_result_id = null
```

Epic Gate 应将该字段标为必填但 nullable，并补充条件规则。

### 3. ResearchCase revision 条件字段

第 6.3 节规定 CreateDispositionProposalCommand 在同步切换 Case current 引用时必须校验 ResearchCase revision，但其 Payload 字段表没有提供该值。

本切片增加可选 `expected_research_case_revision`：不更新 Case 时为 null，更新 Case current 引用时由 Handler 要求非 null。Epic Gate 应把该条件字段补入内部命令契约。

