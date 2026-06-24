# A1-CONTRACT-001B Case、Scope 与 Plan 契约映射记录

状态：完成，无冻结语义勘误

依赖：`docs/API_CONTRACTS.md`（`A0-DOC-004-R1.2.1`）与 `docs/DOMAIN_MODEL.md`（`A0-DOC-003-R1.2.2`）

## 映射结果

- 本切片公共模块为 `metaos.core_alpha.contracts.scope`；统一包导出留给 `A1-CONTRACT-001` Epic Gate，避免并行子任务修改共享导出文件。
- 创建和调整 KnowledgeScope/ResearchPlan 都携带所属 ResearchCase 的 `expected_revision`；路径中的具体 version ID 由 Router 传给 Handler，不在请求体重复。
- 创建请求不接受服务端 ID、时间、版本目标值或状态字段；响应完整返回逻辑 ID、版本 ID、version、revision 和 nullable 字段。
- required/allowed Binding 必须固定版本；excluded Binding 不得携带 analysis role。Binding 与 SourceResolution 的作品、版本和访问政策真实性仍由领域 Handler 跨对象校验。
- Minimum Slice 的 SourceResolution 创建请求只接受 `resolution_stage=full`；响应仍能表示 Complete 后续使用的 preliminary 记录。
- ResearchPlan 的正式 stop conditions 与 research budget 属于 Core Alpha Complete；本切片响应显式返回 null，请求不得提前提交任意结构占位。

## Errata

本任务没有发现需要回写冻结 API 或领域模型的机械矛盾，也没有提出语义变更。

