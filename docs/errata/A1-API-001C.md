# A1-API-001C 勘误记录

状态：完成，无冻结 API 语义变更。

依赖：`docs/API_CONTRACTS.md`（A0-DOC-004-R1.2.1）与 `docs/DOMAIN_MODEL.md`（A0-DOC-003-R1.2.2）。

## 实现映射

- 新增独立 Core Alpha Decision/Internal API router 子模块，覆盖 DispositionProposal 查询、用户 accept/adjust/reject、ResearchDisposition 查询与受信 candidate result 提交。
- Router 未接入公共 FastAPI 入口；统一接线、OpenAPI 汇总和公共 app 修改由 `A1-API-001D` 负责。
- 普通用户 API 不暴露 DispositionProposal 创建路由；处置提案仍由审计和 DecisionFitness 完成后的内部领域命令生成。
- `/internal/alpha/candidate-results` 使用独立服务身份头，不与普通用户身份混用。
- Candidate result 写入仍走 `ApplicationCommandHandler`，保留幂等、TraceEvent、版本校验、lifecycle 校验和防复活语义。
- 用户确认处置不会绕过 JudgmentCard、DecisionFitness 或 warning acknowledgement 的领域门禁。

## Errata

本任务未发现需要回写冻结 API 契约的机械勘误，也未提出语义变更。
