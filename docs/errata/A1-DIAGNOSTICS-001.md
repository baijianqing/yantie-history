# A1-DIAGNOSTICS-001 勘误记录

状态：完成，无冻结 API 语义变更。

依赖：`docs/API_CONTRACTS.md`（A0-DOC-004-R1.2.1）、`docs/DOMAIN_MODEL.md`（A0-DOC-003-R1.2.2）与 `docs/TECHNICAL_ARCHITECTURE.md`（A0-DOC-002-R4.1）。

## 实现映射

- 新增 Core Alpha Developer Diagnostics 查询模块，提供 Run 级 DeveloperResearchTrace、MaterialManifest、IndexGeneration metadata 与 Projection status。
- 新增 Developer router 注册函数，通过 `A1-API-001D` 的 `DeveloperExtensionRegistry` 注册扩展；最终挂载由 `A1-DIAGNOSTICS-002` 负责。
- Developer 路由要求独立 `X-Developer-Actor-Id` 身份，不与普通用户 API 权限混用。
- Developer Trace 返回 TraceEvent 的类型、聚合、版本、actor、correlation 与 payload hash，不返回完整 event payload。
- MaterialManifest 查询只返回对象引用、Hash、版本、定位、长度、敏感级别和已存储的脱敏预览字段，不返回完整 Prompt、完整原文、API Key 或认证 Header。
- Minimum Slice 不注册 CaseActivityLog 与 `/alpha/developer/research-runs/{id}/budget`，Complete Diagnostics 后续扩展。

## Errata

本任务未发现需要回写冻结 API 契约的机械勘误，也未提出语义变更。
