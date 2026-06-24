# A1-CONTRACT-001A 公共契约映射记录

状态：完成，无冻结语义勘误

依赖：`docs/API_CONTRACTS.md`（`A0-DOC-004-R1.2.1`）与 `docs/DOMAIN_MODEL.md`（`A0-DOC-003-R1.2.2`）

## 映射结果

- 公共导入路径固定为 `metaos.core_alpha.contracts`；旧 `metaos.core.schemas` 不作为 Core Alpha 目标契约来源。
- JSON 对象默认拒绝未声明字段；开放扩展只允许出现在契约明确声明的 `details` 等 JSON 容器中。
- UTC 时间拒绝无时区和非零偏移输入；Hash 使用“算法前缀 + 小写十六进制”表示。
- revision 从 1 开始；分页 limit 为 1 至 200，consistency wait 为 0 至 5000 毫秒。
- authoritative consistency 不允许 stale 或 projection checkpoint；projection consistency 必须提供 checkpoint。
- primary 与 affected aggregate 引用不得重复；CommandResponse 必须来自 authoritative store 且具有 primary aggregate。
- ListResponse 固定使用 projection consistency，primary aggregate 必须为空。

## Errata

本任务没有发现需要回写冻结 API 或领域模型的机械矛盾，也没有提出语义变更。

