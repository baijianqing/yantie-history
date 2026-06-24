# A1-CONTRACT-001C Run、Evidence 与 Judgment 契约映射记录

状态：完成，发现一项待 Epic Gate 合并的机械勘误

依赖：`docs/API_CONTRACTS.md`（`A0-DOC-004-R1.2.1`）与 `docs/DOMAIN_MODEL.md`（`A0-DOC-003-R1.2.2`）

## 映射结果

- 本切片使用 `metaos.core_alpha.contracts.execution` 与 `metaos.core_alpha.contracts.judgment`；统一包导出留给 `A1-CONTRACT-001` Epic Gate，避免并行子任务修改共享导出文件。
- ResearchRun、ResearchAttempt、RetrievalRun 与 JudgmentAudit 分别校验创建、运行和终态时间条件；ResearchRunOutcome 只在领域允许的类型中引用 JudgmentCard 版本。
- ResearchEvidenceUse 保留本次 Run 的证据 revision、Scope、有效性快照和 RetrievalRun 关系；`use_type=retrieved` 必须引用 RetrievalRun，`reused` 支持零检索路径。
- EvidenceUnit 的公开 `location` 使用冻结 API 的五个定位维度，并要求至少一个维度非空。
- JudgmentRationale 使用以 `profile_type` 为判别字段的封闭联合；各 profile 只返回自身字段。analogy 通过 inference profile 与 `reasoning_method.code=analogy` 表达。
- Claim 的 evidence status、user attitude 与 lifecycle status 分别建模；用户接受 mixed、insufficient 或 contradicted Claim 不会改变证据状态。
- JudgmentCard 的 audit、validity 与 lifecycle 三套状态分别建模；只有 `acceptable / provisionally_acceptable` 可以绑定 DecisionFitness。
- DecisionFitness 的 risk ceiling 映射为 `maximum_cost_level`、`minimum_reversibility`、`maximum_external_impact` 与 `expert_review_required`，不使用单一风险分数。

## Epic Gate 机械勘误

`docs/API_CONTRACTS.md` 第 3.6 节把 `RetrievalRunResponse.retrieval_outcome` 列为必填且非 null，同时领域模型允许 RetrievalRun 处于 `created / running`，而冻结 outcome 枚举只包含终态结果。二者无法同时成立。

本切片采用以下唯一可序列化规则：

```text
created / running -> retrieval_outcome = null
completed / failed / cancelled -> retrieval_outcome 必须非 null 且与 status 匹配
```

`A1-CONTRACT-001` Epic Gate 应将该字段从 R 调整为 N，并补充上述条件规则。这是字段可空性的机械闭合，不改变领域状态机或检索语义。

