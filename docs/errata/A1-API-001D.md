# A1-API-001D 勘误记录

状态：完成，无冻结 API 语义变更。

依赖：`docs/API_CONTRACTS.md`（A0-DOC-004-R1.2.1）与 `docs/DOMAIN_MODEL.md`（A0-DOC-003-R1.2.2）。

## 实现映射

- 新增 Core Alpha API assembly 模块，统一挂载 Scope、Judgment、Decision 和 Internal candidate result router。
- 新增只读 Feature 状态查询，用于确认异步执行、Developer Diagnostics 和 Complete 能力默认关闭。
- 新增 Developer extension registry 作为后续 Diagnostics 接线点；默认不开启 `core_alpha.developer_diagnostics` 时，不暴露 `/alpha/developer` 扩展路由。
- Assembly 未实现 Diagnostics 具体查询，也未修改子 router 业务逻辑。
- OpenAPI 汇总由 assembly 生成，并验证 route path 与 operationId 无重复。

## Errata

本任务未发现需要回写冻结 API 契约的机械勘误，也未提出语义变更。
