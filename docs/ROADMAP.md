# MetaOS Alpha 路线图

状态：阶段0冻结审查已通过

任务标识：`A0-DOC-005-R1.1.2`

依赖：业务架构 `A0-DOC-001-R7.1`、技术架构 `A0-DOC-002-R4.1`、领域模型 `A0-DOC-003-R1.2.2`、API 契约 `A0-DOC-004-R1.2.1`

本文只维护交付顺序、阶段门和退出条件。业务对象语义、技术承载和 HTTP 契约分别以对应权威文档为准。

## 1. 交付原则

MetaOS 按以下层级交付：

```text
阶段0：冻结契约与评测基线
-> Core Alpha Minimum Slice：可靠判断最小闭环
-> Core Alpha Complete：注意力、复核、行动与知识沉淀
-> Extended Alpha：意图显影、认知视角、画像与有限榜单
-> Beta Ready：稳定性、隐私、成本和统一体验
```

任何后置能力失败不得破坏已经交付的前置闭环。现有代码中的旧对象、旧路由或旧阶段名称不代表新路线图已经完成。

## 2. 阶段0：契约与评测冻结

目标：在不修改业务代码和运行态数据的前提下，冻结 Core Alpha 的价值边界、领域模型、技术控制、API 和实施顺序。

已完成：

- 业务架构：三项一级能力、Minimum Slice 与 Complete 边界、业务不变量和验收场景。
- 技术架构：模块化单体、统一命令入口、Outbox、幂等、并发、出站治理和证据生命周期。
- 领域模型：聚合、对象、字段、状态、版本、证据、审计、用途与用户确认。
- API 契约：公开、Developer、Internal 三层路由与精确 JSON 契约。

已完成同步：

- `A0-DOC-005-R1.1.2`：Roadmap 与任务索引已切换到冻结 Core Alpha 主线，并完成实施责任归属勘误。
- `A0-DOC-006-R1.3`：来源感知检索、上下文打包、预算、停止与降级策略已形成冻结候选，并经 `A0-GATE-001` 确认。
- `A0-EVAL-001-R1.1`：Golden Cases、fixture 规范、四类发布套件、指标与质量门已形成冻结候选，并经 `A0-GATE-001` 确认。
- `A0-GATE-001`：阶段0权威文档、任务 DAG 与质量门已通过严格冻结审查。

剩余交付：

- 无。阶段0已经退出，后续按第 3 章和 `docs/TASK_INDEX.md` 的依赖顺序进入 Minimum Slice 实现。

退出条件：

- 权威文档之间不存在旧对象、旧路由和状态语义冲突。
- Minimum Slice 的任务 DAG、输入输出、允许修改范围和回滚方式明确。
- 真实失败案例形成可执行评测规范。
- 人工确认阶段0完成后，才允许开始公共 Schema、迁移或业务实现。

Non-Goals：不修改代码、迁移、依赖、Streamlit、Worker、索引或 `library/` 数据。

### 2.1 Gate Record

A0-GATE-001 执行时在本节追加唯一审查记录，至少包含：审查日期、业务/技术/领域/API/检索/评测文档版本、审查结论、未决风险和首个获授权实现任务。未形成该记录时，阶段0不得视为完成。

#### A0-GATE-001 首次审查记录

- 审查日期：`2026-06-24`。
- 审查结论：`blocked`。阶段0尚未退出，不授权阶段1实现。
- 上游版本与提交：
  - 业务架构 `A0-DOC-001-R7.1`：`78883fb`。
  - 技术架构 `A0-DOC-002-R4.1`：`1cb4682`。
  - 领域模型 `A0-DOC-003-R1.2.2`：`58cde24`。
  - API 契约 `A0-DOC-004-R1.2.1`：`686437a`。
  - 检索策略 `A0-DOC-006-R1.3`：`97cc475`。
  - 评测契约 `A0-EVAL-001-R1.1`：`0aa203e`。
- 阻断项：
  1. `docs/TECHNICAL_ARCHITECTURE.md` 在“架构定位”“JudgmentCard”“Audit 与 DecisionFitness”“API 架构”“降级与失败类型”“可观测性、质量门与业务不变量控制”中，仍以 `ready` 表达 JudgmentCard 或核心 Claim 状态；`docs/DOMAIN_MODEL.md` 对判断只冻结 `acceptable / provisionally_acceptable / blocked` 等精确审计状态。该术语差异会重新引入未定义的判断状态。
  2. 本章“剩余交付”仍将任务索引中已经完成的 `A0-DOC-006` 和 `A0-EVAL-001` 列为未完成，阶段0状态表达不一致。
- 未决风险：若直接进入实现，Contract、Audit、UI 和评测可能分别把 `ready` 映射成不同状态；Roadmap 与任务索引也会对阶段0进度给出不同结论。
- 阶段1授权：无。`A1-CONTRACT-001A` 保持 `pending`，不得启动。
- 建议修复：
  1. 建立技术架构机械勘误，将 JudgmentCard/Claim 的 `ready` 替换为领域模型的精确审计状态表达；`IndexGeneration.status=ready` 保留。
  2. 机械同步本章阶段0交付状态，不改变阶段划分或任务语义。
  3. 修复完成后重新执行 `A0-GATE-001`，形成新的审查记录；本记录不得覆盖或删除。

#### A0-GATE-001 第二次审查记录

- 审查日期：`2026-06-25`。
- 审查结论：`passed`。阶段0退出条件已经满足，可以按任务 DAG 进入阶段1。
- 上游版本与提交：
  - 业务架构 `A0-DOC-001-R7.1`：`78883fb`。
  - 技术架构 `A0-DOC-002-R4.1`，机械勘误 `A0-DOC-002-R4.1.1`：`c306667`。
  - 领域模型 `A0-DOC-003-R1.2.2`：`58cde24`。
  - API 契约 `A0-DOC-004-R1.2.1`：`686437a`。
  - 检索策略 `A0-DOC-006-R1.3`：`97cc475`。
  - 评测契约 `A0-EVAL-001-R1.1`：`0aa203e`。
  - Roadmap 阶段0状态同步：`f1705f0`。
- 首次审查阻断项关闭：
  1. JudgmentCard/Claim 的未定义 `ready` 表述已全部替换为 `audit_status=acceptable / provisionally_acceptable / blocked` 等领域模型精确语义；仅保留 `IndexGeneration.status=ready`。
  2. `A0-DOC-006-R1.3` 与 `A0-EVAL-001-R1.1` 已进入完成记录，Roadmap 与任务索引状态一致。
- 审查证据：8 份阶段0权威文档均存在且无本地断链；未发现旧对象或旧路由残留；任务 DAG 共 40 个节点、69 条边且无环；评测契约包含 62 个案例定义、51 个 Minimum Slice 七层断言和 40 个已定义指标。
- 未决风险：现有代码尚未实现冻结目标，Golden Cases 也尚未运行；这属于阶段1交付风险，不构成阶段0契约阻断。实现不得通过反向修改冻结语义规避失败。
- 首个获授权实现任务：`A1-CONTRACT-001A`。本授权不自动放行其后继任务；后续任务仍须分别满足 `docs/TASK_INDEX.md` 的依赖、修改边界和验收条件。
- 重新审查条件：新增领域对象、改变状态机、放宽审计或用户确认门禁、改变阶段边界或无法通过机械勘误解决的契约冲突时，必须建立 ADR 并重新执行 `A0-GATE-001`。

## 3. Core Alpha Minimum Slice

核心命题：用户主动提出问题后，MetaOS 能在明确来源范围内形成可定位、可审计、用途受限且由用户确认处置的判断。

主链：

```text
ResearchCase
-> SourceResolution
-> KnowledgeScope
-> ResearchPlan
-> ResearchRun / ResearchAttempt / RetrievalRun
-> EvidenceUnit / ResearchEvidenceUse
-> Claim / JudgmentRationale / JudgmentCard
-> JudgmentAudit / DecisionFitness
-> ResearchRunOutcome
```

当 Outcome 表明已经形成可采纳判断时，才进入用户处置支线：

```text
-> DispositionProposal
-> 用户接受 / 调整 / 拒绝
-> ResearchDisposition 或不形成处置
```

ResearchRunOutcome 只表达研究如何结束；ResearchDisposition 只表达用户如何处理判断。blocked、证据不足、取消和执行失败不得伪造为用户处置。

### 3.1 基础契约映射

- 将冻结领域对象映射为 Pydantic Schema。
- 建立聚合 revision、双 ID 版本、命令幂等和统一事件信封。
- 建立逻辑持久化集合、Repository Port 和最小迁移。
- 所有外部 Provider 调用经过共享出站策略，并形成 MaterialManifest。

阶段门：Schema 校验、Repository 并发、幂等重放和迟到结果测试通过。

### 3.2 Case、来源与研究计划

- 实现 ResearchCase 与 ResearchQuestion。
- 实现 SourceResolution、KnowledgeScope 版本和 ResearchPlan 版本。
- 显式来源解析失败、歧义或不可用时不得静默回退全库。
- SourceResolution 可以先依赖只读 Knowledge Catalog 身份读取；真正进入检索评测前，必须完成版本化知识底座，确保 ResearchRun 绑定固定 KnowledgeItemVersion、chunk strategy 和 IndexGeneration。

阶段门：指定、比较、排除和版本选择均有契约测试；旧 Scope/Plan 版本不可原地修改。

### 3.3 研究执行与来源感知检索

- 在来源感知检索前实现 A1-KNOWLEDGE-002：复用旧上传、OCR、切片和索引生成执行能力，但对 Core Alpha 暴露不可原地覆盖的 KnowledgeItemVersion、Chunk 集合和 IndexGeneration 代际。
- 实现 Run、Attempt、零或多个 RetrievalRun、Outcome 与 Trace。
- 有锚点时在指定来源内检索；无锚点时先做来源级路由。
- 支持 `fact_lookup / source_interpretation / compare_sources / enumerate_pattern / claim_evaluation` 的差异化执行。
- 形成 ResearchEvidenceUse，区分证据产生关系与本次使用关系。

阶段门：同一检索评测绑定固定 KnowledgeItemVersion、chunk strategy、IndexGeneration 和策略版本；短资料公平性、required 独立报告、excluded 污染、零检索证据复用和失败降级评测通过。

### 3.4 判断、审计与处置

- 实现 EvidenceUnit、ClaimEvidenceLink、JudgmentRationale、Claim 和 JudgmentCard。
- 实现确定性预检、语义审计和确定性 Decision Gate。
- 实现 WarningAcknowledgement、DecisionFitness、DispositionProposal 和 ResearchDisposition。
- blocked、证据不足、用户终止和执行失败只形成真实 Outcome，不伪造可靠处置。

阶段门：核心 Claim 证据覆盖、理由链裁剪、阻断不可覆盖、用途越级和用户接受不改变证据状态等评测通过。

### 3.5 Minimum Slice 工作台

- Streamlit 第一屏支持提问、来源约束、研究状态、判断、证据、警告和处置确认。
- 默认隐藏 Provider、索引、Prompt 和底层降级细节；Developer 视图可查看技术 Trace。
- Developer 后端提供 Run 级 Technical Trace、MaterialManifest、IndexGeneration metadata 和 projection status，并使用独立访问策略。
- 草稿、审计中、可采纳、阻断和失效状态视觉上可区分。

Minimum Slice 退出条件：

- 正式回答全部关联 ResearchCase 和 ResearchTrace。
- required source compliance 为 100%，excluded source violation 为 0。
- 对 `audit_status=acceptable` 或 `provisionally_acceptable` 且用途匹配的 JudgmentCard，核心 Claim 证据覆盖率为 100%。
- 不存在缺少匹配证据或理由链、却被标记为可采纳的核心 Claim。
- 用户能确认、调整或拒绝处置；未确认 Proposal 不成为最终事实。
- 固定 Golden Cases 回归通过，旧 RAG 与 Streamlit 基础能力无明显回归。

#### A1-E2E-001 发布门记录

- 审查日期：`2026-06-26`。
- 审查结论：`blocked`。
- 已通过：本地 Core Alpha API 入口、公开 API 创建 ResearchCase、SourceResolution 领域失败记录、工作台快照读取路径、Developer Diagnostics 权限边界、桌面与移动工作台冒烟检查。
- 阻断原因：`docs/CORE_ALPHA_EVALUATION.md` 定义的完整 Golden Cases runner、固定 fixture、CaseExecutionRecord 和 51 个 Minimum Slice blocking 案例尚未执行。
- 阶段发布授权：无；Minimum Slice 不得以本次冒烟检查作为发布通过。
- 报告位置：`docs/reports/A1-E2E-001.md`。

Non-Goals：不实现画像、三部榜单、LensSkill、知识图谱、复杂行动工作流或自动知识合并。

## 4. Core Alpha Complete

在 Minimum Slice 稳定后，按独立纵向切片增加：

### 4.1 注意力约束

- ResearchTriage 只建议研究深度、预算和执行策略。
- AttentionBacklogItem 管理未激活问题、Case、缺口、复核建议和外部线索。
- 在办上限采用可追溯软门禁，用户始终可以暂停、延后或显式覆盖。

### 4.2 判断复核

- 用户主动发起 JudgmentReview。
- 证据删除、定位失效、内容变化或确认历史缺陷时提示复核。
- ReviewResult 不直接覆盖原处置；需要改变处置时重新生成 Proposal 并确认。

### 4.3 低风险行动闭环

- 只有 `proceed_to_action` 处置可以创建 ActionProposal。
- ActionRiskProfile 与 DecisionFitness 共同限制用途和风险。
- 用户接受后才形成 ActionCommitment；ActionReview 可触发判断复核。

### 4.4 最小知识沉淀

- 可靠判断可选地产生 KnowledgeContributionCandidate。
- 用户确认、调整或拒绝候选；语义或证据关系变化必须重新校验。
- KnowledgeAsset 是可撤回的证据支持知识笔记，不成为新的独立原始证据。
- 校验失败内容只能进入 UserNote 或继续研究。

Core Alpha Complete 退出条件：四个新增切片均可独立关闭或失败而不破坏 Minimum Slice；用户主权、证据状态和审计门禁保持不变。

Complete Diagnostics 扩展在四个业务 Epic 后统一增加 CaseActivityLog 与正式预算/消费诊断；这些能力不得反向成为 Minimum Slice 工作台或发布门的前置依赖。

## 5. Extended Alpha

方向性能力：IntentTrace、BookProfile/CognitiveLens、认知画像与更新候选、InformationIntake 和三部有限榜单。

这些能力在进入实施前必须另立 ADR、任务和评测，不沿用 Core Alpha 的字段推测。三部每部最多 3 条、总数最多 5 条；无足够价值时返回“今日无事上奏”。画像只提供先验，不能覆盖当前问题。

## 6. Beta Ready

只处理产品化收敛：性能、稳定性、隐私、出站治理、移动端、备份恢复、可观测性和失败降级，不新增核心业务闭环。

退出条件：关键路径 P95、成本、幂等、并发、删除防复活、数据出站、恢复演练和 Golden Cases 回归达到发布门禁。

## 7. 全局阶段门

每个阶段和任务必须提供：

- 进入条件与依赖。
- 明确输入、输出和接口。
- 允许与禁止修改范围。
- 自动化测试与 Golden Cases。
- 失败降级和回滚方式。
- 对权威文档的同步要求。

不得以“已有类似代码”替代契约验收，也不得为了通过完成率而降低审计、来源边界或用户确认标准。
