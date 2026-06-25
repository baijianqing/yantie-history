# A1-API-001B 勘误记录

状态：完成，无冻结 API 语义变更。

依赖：`docs/API_CONTRACTS.md`（A0-DOC-004-R1.2.1）与 `docs/DOMAIN_MODEL.md`（A0-DOC-003-R1.2.2）。

## 实现映射

- 新增独立 Core Alpha Judgment API router 子模块，覆盖 ResearchRun、Evidence、Judgment、Audit、WarningAcknowledgement、DecisionFitness 与普通 Public Trace。
- Router 未接入公共 FastAPI 入口；统一接线、OpenAPI 汇总和公共 app 修改由 `A1-API-001D` 负责。
- 普通 API 不暴露内部 JudgmentDraft 或 RunJudgmentAudit 创建命令。
- Source/Retrieval/Run Outcome 与 HTTP 错误保持分离；Run 创建后的业务失败由 ResearchRunOutcome 表达。
- 用户设置 Claim attitude 不改变 Claim evidence status。
- blocking AuditFinding 不允许通过 acknowledge 放行。

## Errata

本任务未发现需要回写冻结 API 契约的机械勘误，也未提出语义变更。
