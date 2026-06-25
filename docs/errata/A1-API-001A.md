# A1-API-001A 勘误记录

状态：完成，无冻结 API 语义变更。

依赖：`docs/API_CONTRACTS.md`（A0-DOC-004-R1.2.1）与 `docs/DOMAIN_MODEL.md`（A0-DOC-003-R1.2.2）。

## 实现映射

- 新增独立 Core Alpha Scope API router 子模块，覆盖 Knowledge Catalog、ResearchCase、SourceResolution、KnowledgeScope 和 ResearchPlan。
- Router 未接入公共 FastAPI 入口；统一接线、OpenAPI 汇总和公共 app 修改由 `A1-API-001D` 负责。
- 写命令复用 ApplicationCommandHandler，保持 Idempotency-Key、Command envelope、TraceEvent 和 revision consistency。
- SourceResolution 的 `not_found / ambiguous / unavailable` 作为成功创建的领域记录返回，不映射为 HTTP 404 或 503。
- Knowledge Catalog 只读接口不返回 `storage_ref`、完整原文或完整 Chunk 文本。

## Errata

本任务未发现需要回写冻结 API 契约的机械勘误，也未提出语义变更。
