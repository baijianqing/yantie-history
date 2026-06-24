# MetaOS Core Alpha Golden Cases 与质量门

状态：A0-GATE 前冻结候选

任务标识：`A0-EVAL-001`

评测契约版本：`core-alpha-eval-v1-candidate`

依赖：业务架构 `A0-DOC-001-R7.1`、技术架构 `A0-DOC-002-R4.1`、领域模型 `A0-DOC-003-R1.2.2`、API 契约 `A0-DOC-004-R1.2.1`、检索策略 `A0-DOC-006-R1.3`

## 1. 权威范围与任务边界

本文是 Core Alpha Golden Case、fixture 规范、指标口径和发布质量门的唯一权威。它把冻结业务场景转换为可实现的评测契约，不重新定义领域状态、检索算法、HTTP 语义或测试实现。

跨文档所有权：

- 用户价值、业务不变量和场景意图以 `docs/BUSINESS_ARCHITECTURE.md` 为准。
- 对象、状态和聚合不变量以 `docs/DOMAIN_MODEL.md` 为准。
- HTTP 与 Outcome 边界以 `docs/API_CONTRACTS.md` 为准。
- 来源路由、Admission、候选融合、预算和停止策略以 `docs/RAG_RETRIEVAL_STRATEGY.md` 为准。
- 本文只拥有案例输入、fixture 标注规范、分层断言、指标公式、重复执行协议和发布门禁。

任务契约：

- 价值：在实现前固定真实失败案例，防止为了通过测试而降低来源、证据、审计或用户确认标准。
- 允许修改范围：首次交付新增本文；验收后机械更新 `docs/TASK_INDEX.md` 中 `A0-EVAL-001` 状态。
- 禁止修改范围：测试代码、fixture 数据、模型、索引、数据库、迁移、业务实现、配置和运行态数据。
- 输入：业务冻结场景、领域状态机、API Outcome、检索 R1.3 和真实失败案例。
- 输出：Golden Case 契约、fixture 规范、指标口径、执行记录契约及 Minimum Slice/Core Complete 发布门。
- 接口：后续 fixture builder、evaluation runner、人工语义复核和发布报告的文档契约。
- 回滚：删除本文，并把 A0-EVAL-001 恢复为 pending；不涉及运行态回滚。

本文完成只表示评测规范已冻结，不表示案例已经执行。实际 fixture 文件、runner、快照和评测报告在阶段1任务中实现。

## 2. 评测对象与结果契约

### 2.1 Golden Case 必填字段

每个案例必须可序列化为以下逻辑结构；字段名是评测语义，不提前冻结 Pydantic 类名：

| 字段 | 含义 |
| --- | --- |
| `case_id` | 本文唯一稳定 ID；案例语义改变必须产生评测勘误版本 |
| `delivery_layer` | `minimum_slice / core_alpha_complete` |
| `objective` | 本案例要证明或阻断的产品行为 |
| `business_invariants` | 关联业务不变量 |
| `fixture_refs` | 第 4 章逻辑 fixture ID |
| `question` | 原始问题或命令输入 |
| `research_mode` | 五种研究模式之一；非研究案例为 `not_applicable` |
| `explicit_constraints` | required、allowed、excluded、版本和用途约束 |
| `evidence_requirements` | 强制支持、反证、替代解释、定位和覆盖要求 |
| `expected_behavior` | 系统必须行为 |
| `forbidden_behavior` | 系统禁止行为 |
| `expected_observables` | UI/API/Trace/领域对象可观察结果 |
| `layer_assertions` | 第 2.2 节七层断言 |
| `trace_requirements` | 必须记录的检索、预算、版本和停止事实 |
| `metric_ids` | 参与第 8 章哪些指标 |
| `severity` | Minimum Slice 固定 `blocking`；Complete 按 A2 Gate 决定 |
| `repeat_policy` | `once / three_runs` |

任何一层明确不适用时必须写成 `N/A` 并说明原因，不得用空字段掩盖未设计的断言。

### 2.2 七层断言

Minimum Slice 每个案例都必须覆盖：

1. **来源解析**：SourceResolution、版本、锚点和失败是否正确。
2. **来源路由**：显式/自动来源、Admission、required/excluded 和选择理由是否正确。
3. **检索执行**：ResearchAttempt、RetrievalRun、通道、候选和停止事实是否正确。
4. **证据使用**：EvidenceUnit、IndependentEvidenceGroup、ResearchEvidenceUse、定位与 provenance 是否正确。
5. **判断**：Claim、evidence status、JudgmentRationale 和 JudgmentCard 是否正确。
6. **审计与用途**：AuditFinding、audit status、warning 和 DecisionFitness 是否正确。
7. **Outcome/API**：ResearchRunOutcome、ResearchDisposition 边界和 HTTP/响应是否正确。

分层失败必须保留实际层级。上游检索失败不能伪造成 Judgment 审计失败；领域 Outcome 不能伪造成 HTTP 错误。

### 2.3 CaseExecutionRecord

后续 runner 每次执行必须形成一条不可变结果记录，至少包含：

- case ID、fixture version、执行时间和实现提交。
- 业务/领域/API/检索/评测文档版本。
- IndexGeneration、策略/参数、Capability、Prompt、模型、审计和用途政策版本。
- ResearchCase、ResearchRun、Attempt 和 Trace 引用。
- 七层断言的 `pass / fail / not_applicable` 与失败详情。
- 指标原始计数，不只保存聚合百分比。
- 总结果：`passed / failed / inconclusive / not_run`。
- 人工复核者、复核依据和时间；不需要人工复核时明确标记。

`inconclusive` 不能算通过。依赖不可用、Trace 缺失或无法判断证据支持关系时，案例必须保持 inconclusive 并阻断对应 Gate。

## 3. 执行与变更协议

### 3.1 固定版本

一次评测批次必须固定：

- fixture manifest 与内容 Hash。
- KnowledgeItemVersion、Chunk strategy 和 IndexGeneration。
- retrieval policy、parameter set、Admission、normalization、grouping 和 context strategy。
- Capability、tokenizer、Embedding、reranker、Provider、Prompt、输出 Schema、审计和 DecisionFitness policy。
- feature flag、execution mode 和系统安全预算。

版本变化必须形成新批次，不得把不同版本的结果直接聚合成同一分母。

### 3.2 重复与人工复核

- 纯确定性案例执行一次。
- 任何涉及概率模型、reranker、语义审计或自由生成的案例执行三次。
- 三次运行的自然语言无需逐字一致，但全部硬不变量每次都必须通过。
- 语义正确性按 EvidenceUnit、ClaimEvidenceLink 和 JudgmentRationale 人工复核，不以字符串包含或模型自评代替。
- 评测者只能判断案例是否符合冻结契约，不能在结果阶段修改 fixture 或期望。

### 3.3 案例变更

- 实现失败不得通过降低期望、删除反证或改写 fixture 标签解决。
- 修正拼写、引用和机械矛盾可以形成评测勘误。
- 改变业务不变量、领域状态、Admission、发布阈值或案例结论必须升级评测契约版本，并按影响重新审查 A0-GATE。
- 旧案例和旧执行记录保留，不原地覆盖。

## 4. Fixture 规范

本章只定义 fixture manifest，不创建原文、JSON、数据库、索引或测试文件。

### 4.1 知识来源 fixture

| fixture_id | 逻辑资料 | 必须固定的属性 | 主要用途 |
| --- | --- | --- | --- |
| `FX-KNOW-001` | 《鬼谷子》短资料 | 单一可用版本；15 个 active Chunk；已标注相关、无关和概念上下文定位 | 短资料公平、单来源解释、比较 |
| `FX-KNOW-002` | 《理想国》长资料 | 单一可用版本；399 个 active Chunk；与 FX-KNOW-001 存在共同主题但不可替代 | 长短公平、比较、excluded 污染 |
| `FX-KNOW-003` | 《传习录》 | 单一可用版本；概念原文、相邻上下文、无证据主题 | source_interpretation、required 无证据 |
| `FX-KNOW-004` | 《资治通鉴》受控子集 | 声明候选全集；至少一个纳入、一个排除、一个未决候选；支持和反证定位 | enumerate_pattern、因果审计 |
| `FX-KNOW-005` | 高长恭／兰陵王材料 | 标题、人物别名和稳定定位；原文只使用其中一个名称 | 别名召回 |
| `FX-KNOW-006` | 多译本作品 | 两个可用版本、一个不可用版本；版本提示和歧义候选 | 版本歧义、不可用版本 |
| `FX-KNOW-007` | 重叠与相邻 Chunk 集 | 同版本重叠范围、相同 Hash、相邻高相似文本和无关章节 | IndependentEvidenceGroup |
| `FX-KNOW-008` | allowed/excluded 同文集 | 两个版本含相同文本，但 access policy 不同 | provenance 与 excluded 防洗白 |
| `FX-KNOW-009` | 无关来源集 | 所有来源低于 source admission floor，并保存边界分数 | no_admissible_source |
| `FX-KNOW-010` | 单候选来源 | 只有一个证据组通过 candidate admission，其余低于 floor | 不填充弱证据 |
| `FX-KNOW-011` | 通道降级来源 | FTS 可用、vector IndexGeneration 失效；另有全部必要通道失效变体 | 降级与 execution_failed |
| `FX-KNOW-012` | 可复用证据集 | 已有 valid EvidenceUnit、稳定版本/定位/Hash；另有 invalid 变体 | 零 RetrievalRun 复用 |
| `FX-KNOW-013` | 多包预算集 | required 最低覆盖超过 20；至少五个 ContextPack；固定 Token/Cost 估算 | 双预算、多阶段矩阵 |
| `FX-KNOW-014` | 古文短句集 | 短于 3 字、近似 3-gram、同文异标点和跨章节相似句 | 分组错误合并/拆分 |

### 4.2 Manifest 必填信息

每项 fixture 必须固定：

- logical ID、KnowledgeItem/Version/Chunk 逻辑映射和可用性。
- title、aliases、language、edition/translator 条件。
- active Chunk 数、Token 估算、chunk strategy、IndexGeneration 和通道能力。
- 预期 relevant、counterevidence、alternative、failure-condition 和 irrelevant locator 标签。
- duplicate group、canonical range、跨版本同文和 provenance 标签。
- source/candidate admission 的边界 rank、score、floor、通过规则和拒绝原因。
- required、allowed、excluded 和 analysis role 的用例绑定。
- 敏感内容级别和是否允许进入外部 Provider。

实际 fixture 构建时必须产生 manifest version 与内容 Hash；不得从用户运行态 `library/` 直接抽取未固定内容作为发布门输入。

## 5. Minimum Slice Golden Cases

以下 35 个案例均为 blocking。案例目录固定输入和业务期望；第 6 章固定七层断言。

组级字段规则：

- `delivery_layer=minimum_slice`、`severity=blocking` 适用于全部 35 个案例。
- `repeat_policy=three_runs` 为默认值。
- 以下纯确定性契约案例固定为 `repeat_policy=once`：`GC-SRC-006`、`GC-SRC-008`、`GC-RET-002..007`、`GC-RET-011..014`、`GC-JDG-003`、`GC-API-001..003`。
- 全部案例继承检索策略第 14 章 Trace 要求；没有检索、判断或审计对象的层必须在第 6 章标记 N/A。

### 5.1 来源与范围 `GC-SRC-001..008`

| case_id | 输入、模式与 fixture | 显式约束与 EvidenceRequirement | 必须行为 | 禁止行为与最终结果 | 不变量 / 指标 |
| --- | --- | --- | --- | --- | --- |
| `GC-SRC-001` | “只根据《鬼谷子》解释捭阖”；source_interpretation；FX-KNOW-001/002 | 鬼谷子 required+primary；默认 excluded 其他来源；原文与上下文 | 只在指定版本取证并定位 | 不得用理想国代答；形成仅引用鬼谷子的判断或 insufficient_evidence | 显式约束优先；M-SRC-REQ、M-SRC-EXC |
| `GC-SRC-002` | 比较《鬼谷子》《理想国》的权力观；compare_sources；001/002 | 两者 required+comparison；固定比较维度 | 两边独立取证并报告终态 | 不得只检索一方或制造假对称 | 双维度来源治理；M-SRC-REQ |
| `GC-SRC-003` | 要求《传习录》回答一个无相关证据主题；fact_lookup；003 | 传习录 required | 独立执行并报告 no_evidence | 不得找其他书代答或生成处置 | 无证据不得代答；M-SRC-REQ |
| `GC-SRC-004` | 相关答案同时存在于鬼谷子与理想国；fact_lookup；001/002 | 鬼谷子 allowed；理想国 excluded | excluded ID 仅用于过滤和审计 | excluded 内容不得进入候选、ContextPack、EvidenceUnit 或 Claim | excluded 零污染；M-SRC-EXC |
| `GC-SRC-005` | 查询“高长恭”；fact_lookup；005 | 未显式指定资料 | 通过人物别名定位“兰陵王长恭”材料 | 不得因原文缺少查询名返回全库无结果 | 别名解析；M-RET-RECALL |
| `GC-SRC-006` | 指定有多个译本的作品；source_interpretation；006 | 版本未明确；另运行指定不可用版本变体 | ambiguous/unavailable 均形成 SourceResolution | 不得随机选择或静默替换版本 | 版本用户可见；M-SRC-FALLBACK |
| `GC-SRC-007` | 无关问题；fact_lookup；009 | 无显式来源 | 正常路由后 0 RetrievalRun，stop=no_admissible_source | 不得硬选来源；通常 insufficient_evidence | Admission 不填满；M-ADM |
| `GC-SRC-008` | 来源分数位于 floor 上下边界；五种模式参数化；009 | 无显式来源 | 等于 floor 按规则准入，低于 floor 拒绝；不填满 max | 不得动态放宽或用 RRF 让未准入来源进入 | Admission 确定性；M-ADM、M-DET |

### 5.2 检索与证据 `GC-RET-001..014`

| case_id | 输入、模式与 fixture | 关键条件 | 必须行为 | 禁止行为与最终结果 | 不变量 / 指标 |
| --- | --- | --- | --- | --- | --- |
| `GC-RET-001` | 球迷落泪类比问题；claim_evaluation；001/002 | 两来源相关；15 vs 399 Chunk | 先来源路由、各来源内检索；短资料获得合法候选机会 | 不得全库 Chunk 直接竞争或让长资料占满 | 篇幅不决定权重；M-RET-SHORT |
| `GC-RET-002` | 单来源问题；fact_lookup；010 | 仅 1 个候选通过 admission | 只保留 1 个候选 | 不为 min_source_candidate_groups 填充弱内容 | 准入优先于配额；M-ADM |
| `GC-RET-003` | 命中同版本重叠 Chunk；fact_lookup；007 | Hash 相同、range 重叠、相邻高相似 | 合并为独立证据组并保留成员 provenance | 不得把重叠 Chunk 算多份证据 | 证据不膨胀；M-EVD-DUP |
| `GC-RET-004` | allowed/excluded 同文；fact_lookup；008 | 文本 Hash 相同 | 保留 allowed provenance，排除 excluded 内容 | 不得通过 Hash 把 excluded 洗成 allowed | 来源边界；M-SRC-EXC |
| `GC-RET-005` | 向量索引失效；fact_lookup；011 | FTS valid、vector unavailable | vector RetrievalRun 失败并降级到 FTS；来源仍可用 | 不得标记整本来源 unavailable | 通道级降级；M-RET-DEGRADE |
| `GC-RET-006` | 所有必要通道不可用；fact_lookup；011 | 无合法复用证据 | 记录通道失败并形成 execution_failed | 不得伪造成 no_evidence | 失败分类；M-OUTCOME |
| `GC-RET-007` | 复用已有有效证据；fact_lookup；012 | 版本、Scope、定位、Hash 均有效 | 0 RetrievalRun；新建 use_type=reused 并重校验 | 不得复制 EvidenceUnit 或使用历史回答文本 | 产生/使用关系分离；M-EVD-TRACE |
| `GC-RET-008` | 比较大量 required 来源；compare_sources；013 | 最低覆盖 >20 Chunk | 多 ContextPack + 原始 EvidenceUse 回链矩阵 | 不得静默删除 required 或把矩阵当证据 | 双预算/required；M-BUDGET、M-SRC-REQ |
| `GC-RET-009` | 连续及并发五个 ContextPack；enumerate_pattern；013 | 固定 Evidence/Total/Cost 预算 | 原子预留、结算并共享剩余预算 | 不得每包重置预算或未记录超支 | Run 总预算；M-BUDGET |
| `GC-RET-010` | 小 Provider 窗口与超长证据组；source_interpretation；013 | 可用 Evidence Token <512 与超长组两个变体 | 低于阈值不调用；合法摘录保持定位和支持语义 | 不得越窗或截断到改变含义 | Context 安全；M-BUDGET |
| `GC-RET-011` | 古文短句与相似段；fact_lookup；014 | 短于 3 字、3-gram 相似、跨章节 | 按 grouping version 正确合并/分离 | 不得跨无关章节合并 | 分组可重复；M-EVD-DUP、M-DET |
| `GC-RET-012` | 第二轮无新组但补齐 mandatory 映射；claim_evaluation；004 | Coverage 首次满足/required 进入终态 | 计为 coverage gain，继续到成功条件 | 不得触发 no_coverage_gain | 停止条件正确；M-COVERAGE |
| `GC-RET-013` | 相同候选，reranker 启用/禁用/部分缺失；fact_lookup；001 | 固定 candidates | 遵守 skip/null-last/source-RRF 规则，排序可解释 | 不得混合未定义 relevance 分数 | 稳定排序；M-DET |
| `GC-RET-014` | 一般多来源综合；claim_evaluation；001/002/003 | 单来源 Context 比例可能 >0.60 | 记录 concentration 与相关性解释 | 不得把观测线当硬删减；不得由 Chunk 数解释优先级 | 公平性观察；O-SRC-CONC |

### 5.3 研究模式 `GC-MODE-001..003`

| case_id | 输入与 fixture | 必须行为 | 禁止行为 | 可观察结果 | 不变量 / 指标 |
| --- | --- | --- | --- | --- | --- |
| `GC-MODE-001` | 《资治通鉴》中功高震主案例；enumerate_pattern；004 | 声明候选全集，逐项验证支持、反证、条件、排除和未决 | 一次 Top-K 后宣称穷尽；把先后关系写成因果 | EvidenceMatrix 回链原 EvidenceUse，包含纳入/排除/未决 | 枚举不是普通问答；M-COUNTER、M-EVD-TRACE |
| `GC-MODE-002` | 评估一个可争议 Claim；claim_evaluation；004 | 支持、反驳、替代解释和失效条件分别查询 | 无反驳等于成立或无支持等于为假 | Claim 可为 mixed/contradicted/insufficient | 认识状态与检索失败分离；M-COUNTER |
| `GC-MODE-003` | 固定来源与自动来源比较两个变体；001/002/003 | Plan 预先固定维度；自动来源固化到 RunExecutionSpec | 检索后新增来源或维度；制造假对称 | 每来源 evidence_found/no_evidence/unavailable 独立报告 | compare_sources 契约；M-SRC-REQ |

### 5.4 判断、审计与用途 `GC-JDG-001..007`

| case_id | 输入与前置 | 必须行为 | 禁止行为 | 可观察结果 | 不变量 / 指标 |
| --- | --- | --- | --- | --- | --- |
| `GC-JDG-001` | 核心 inference Claim 有 EvidenceUnit 但无完整 Rationale | 阻断并指出前提、推理、边界或反证缺失 | 仅凭有引用标为可靠 | audit_status=blocked，blocking finding 指向 Claim | 推断必须有理由链；M-CLAIM-RAT、M-AUDIT |
| `GC-JDG-002` | 简单 source fact | 只要求来源、定位、事实映射和版本限制 | 强制填入无意义假设/竞争解释 | fact Rationale 与类型相称 | 理由链裁剪；M-CLAIM-RAT |
| `GC-JDG-003` | partially_supported 或 mixed Claim；用户接受 | 只改变 user_attitude，保留 evidence status/warning | 把接受改成 supported | 两个状态维度分别可见 | 用户主权不覆盖证据；M-USER-STATE |
| `GC-JDG-004` | 合法支持和强反证并存 | 形成 mixed/contradicted、uncertainty 和审计说明 | 把冲突当 retrieval failure 或强行共识 | JudgmentCard 显示冲突与适用边界 | 冲突是研究结果；M-COUNTER |
| `GC-JDG-005` | 核心 Claim 无支持证据且用户终止 | blocked JudgmentCard + audit_blocked RunOutcome | 生成 reliable disposition 或用户处置 | Outcome 存在，ResearchDisposition 不存在 | Outcome/Disposition 分离；M-AUDIT、M-OUTCOME |
| `GC-JDG-006` | 判断仅适合理解，用户请求高成本行动 | DecisionFitness 禁止高风险用途并给 escalation | 用“可采纳”放行任意行动 | allowed/forbidden uses 和 risk ceiling 可见 | 可采纳不等于无限用途；M-FITNESS |
| `GC-JDG-007` | Claim 同时引用原 EvidenceUse 与模型记忆候选 | 只让合法 ResearchEvidenceUse 进入 Link | 把模型记忆、矩阵或 KnowledgeAsset 算新证据 | ClaimEvidenceLink 回到本 Run、Scope、Evidence revision | 证据链闭合；M-EVD-TRACE |

### 5.5 API 与 Outcome `GC-API-001..003`

| case_id | 输入 | 必须行为 | 禁止行为 | 可观察结果 | 不变量 / 指标 |
| --- | --- | --- | --- | --- | --- |
| `GC-API-001` | SourceResolution ambiguous/not_found/unavailable 三变体 | 创建成功领域记录并返回规范状态 | 映射为 HTTP 404/503 或回退全库 | 成功响应含 SourceResolution | 领域结果不是 HTTP 错误；M-API |
| `GC-API-002` | Run 已持久化后依赖失败、证据不足、审计阻断三变体 | 通过 ResearchRunOutcome 表达 | 返回迟到 HTTP 503 或伪造处置 | outcome_type 与终态映射合法 | Run 后失败是 Outcome；M-OUTCOME、M-API |
| `GC-API-003` | 资源不存在、revision 冲突、条件字段错误、接受前依赖不可用 | 分别返回 404/409/422/503 | 混用领域 Outcome 或错误码 | code、retryable 和 details 符合 API 契约 | HTTP 边界唯一；M-API |

## 6. Minimum Slice 七层断言矩阵

表中分号分隔同层关键断言；`N/A` 表示该层无对象，但仍说明原因。

### 6.1 来源案例断言

| case_id | 来源解析 | 来源路由 | 检索执行 | 证据使用 | 判断 | 审计与用途 | Outcome/API |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GC-SRC-001 | 鬼谷子 resolved 到指定版本 | explicit required；其他 excluded | 只在绑定内执行 | EvidenceUse 全部来自鬼谷子 | 可解释或无判断 | 越界即 blocking | judgment 或 insufficient；无替代来源 |
| GC-SRC-002 | 两来源均 resolved | 两个 required+comparison | 各来源独立 RetrievalRun | 双方 EvidenceUse 分离 | 统一维度比较 | 缺边不得伪装完整 | completed judgment 或明确缺边 |
| GC-SRC-003 | 传习录 resolved | required 独立执行 | completed/no_evidence | 无伪 EvidenceUnit | 不生成来源事实 Claim | N/A—无判断可审计 | insufficient_evidence；无 disposition |
| GC-SRC-004 | excluded 身份可解析 | excluded 只作过滤 | excluded 无内容候选 | 证据链零 excluded 内容 | Claim 不依赖 excluded | 泄漏必须 blocking | Trace 有排除事实，结果可继续 |
| GC-SRC-005 | 别名解析到同一作品/实体 | 合格来源入选 | 查询扩展不另算轮次 | 定位到原文名称 | 事实 Claim 保留别名说明 | 引用可验证 | 成功或真实证据不足 |
| GC-SRC-006 | ambiguous/unavailable 精确记录 | 不自动选择版本 | 不启动错误版本 RetrievalRun | 无跨版本混用 | 不生成伪来源 Claim | N/A 或版本越界 blocking | 成功 SourceResolution 记录 |
| GC-SRC-007 | 无显式锚点 | 0 admissible source | Attempt 含 0 RetrievalRun | 无 EvidenceUse | 不生成 Judgment | N/A—无判断 | 通常 insufficient；Plan 可 awaiting_user |
| GC-SRC-008 | 无显式锚点 | floor 边界确定；max 不填满 | 只对 admitted 来源执行 | 仅 admitted 候选可形成证据 | 取决于 Coverage | 动态放宽视为违规 | Trace 有 score/floor/reason |

### 6.2 检索案例断言

| case_id | 来源解析 | 来源路由 | 检索执行 | 证据使用 | 判断 | 审计与用途 | Outcome/API |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GC-RET-001 | N/A—无显式锚点 | 先来源路由；短来源可入选 | 每来源独立，非全局 Chunk Top-K | 短来源有合法组机会 | 不按 Chunk 数加权 | 长资料垄断可追踪 | Trace 显示来源分布 |
| GC-RET-002 | 来源 resolved | admitted source | 仅 1 合格组保留 | 不复制弱候选 | 只据真实证据 | 弱证据填充应告警/阻断 | 正常结果或不足 |
| GC-RET-003 | 来源 resolved | N/A—单来源 | 通道候选可重叠 | 合并为 1 独立组，成员可追溯 | 证据计数不膨胀 | 重复计数视为违规 | 结果保留 dedupe Trace |
| GC-RET-004 | allowed/excluded 均解析 | excluded 过滤 | excluded 内容不执行 | 同文不合并 provenance | Claim 仅连 allowed use | excluded 泄漏 blocking | 结果无 excluded 内容 |
| GC-RET-005 | 版本仍可用 | FTS 信号有效 | vector failed/index_unavailable；FTS 完成 | FTS EvidenceUse 合法 | 可形成判断 | 降级影响可见 | 不是 source_unavailable |
| GC-RET-006 | 版本可用 | 路由已完成 | 必要通道全部 failed | 无合法 EvidenceUse | 不生成伪判断 | N/A | execution_failed |
| GC-RET-007 | 来源/版本有效 | Scope 允许 | reuse Attempt，0 RetrievalRun | 新 ResearchEvidenceUse(reused) | 新 Claim 重新判断支持 | 重新审计 | 结果 Trace 解释零检索 |
| GC-RET-008 | required 均解析 | 全部 required 保留 | 多 ContextPack | 矩阵单元回链原 use | 综合 Claim 引用原 Evidence | 缺 required 阻断/不足 | 预算不足有真实 Outcome |
| GC-RET-009 | N/A | N/A—固定来源 | 并发预留不重复消费 | 全部 use 计入同一 Run | 只处理预算内证据 | 未记录超支违规 | budget stop 由执行层映射 |
| GC-RET-010 | 来源有效 | N/A—固定来源 | 小窗口不调用；长组合法摘录 | 摘录定位/Hash 可追溯 | 不据失真截断下结论 | 截断失义必须阻断 | insufficient 或正常结果 |
| GC-RET-011 | 来源有效 | N/A—固定来源 | 固定 grouping versions | 正确合并/拆分 | 证据数量稳定 | 分组漂移阻断可比较性 | 重跑结构一致 |
| GC-RET-012 | required 来源存在 | 路由不变 | 第二轮记录 Coverage gain | 旧组新映射合法 | 可在 Coverage 满足后判断 | 不提前 audit outcome | 不触发 no_coverage_gain |
| GC-RET-013 | 来源集合固定 | selection 稳定 | reranker 缺失按规则降级 | EvidenceUse 集合可比较 | 核心 Claim 不无故反转 | 质量影响可见 | 三变体排序符合契约 |
| GC-RET-014 | 多来源 admitted | 记录 selection 与浓度 | 不用比例线硬删候选 | 各来源 use 比例可算 | 判断依据相关性 | Chunk 数无法解释排序 | 观测指标，不单独失败 |

### 6.3 模式、判断与 API 案例断言

| case_id | 来源解析 | 来源路由 | 检索执行 | 证据使用 | 判断 | 审计与用途 | Outcome/API |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GC-MODE-001 | 资治通鉴 resolved | 候选全集固定 | 生成、逐项验证、反证分轮 | Matrix 回链 use | 纳入/排除/未决分别表达 | 因果不足不得纳入 | 不宣称穷尽 |
| GC-MODE-002 | 按 Plan 解析 | 支持/反驳来源可追踪 | purpose 分开记录 | 支持与反驳 use 分离 | mixed/contradicted/insufficient 合法 | 冲突不当失败 | Outcome 由 Coverage/审计决定 |
| GC-MODE-003 | 固定/自动两变体正确解析 | 实际来源固化 | 每来源每维度独立 | 来源证据分离 | 不制造假对称 | 缺边显式 | 不在 Run 中新增来源 |
| GC-JDG-001 | N/A—复用既有研究 | N/A | N/A—判断层注入 | 有 EvidenceUse 但理由链缺失 | inference Claim 不可采纳 | blocking Finding | audit_blocked |
| GC-JDG-002 | N/A | N/A | N/A | fact 有直接 use | 仅 fact Rationale 字段 | 不机械要求无关字段 | acceptable/provisional 取决其他条件 |
| GC-JDG-003 | N/A | N/A | N/A | EvidenceUse 不变 | user_attitude 变，evidence_status 不变 | warning 保留 | 命令成功，不提升可靠性 |
| GC-JDG-004 | 来源合法 | 支持/反驳均执行 | 通道正常 | 两类 use 均保留 | mixed/contradicted | 审计说明不确定性 | 冲突不是 execution_failed |
| GC-JDG-005 | N/A | N/A | N/A | 核心 Claim 无合法支持 | blocked card 可查询 | blocking 不可确认放行 | audit_blocked；无 disposition |
| GC-JDG-006 | N/A | N/A | N/A | 判断证据足以理解 | Claim 可采纳但用途有限 | DecisionFitness 禁止高风险 | 不创建越级 commitment |
| GC-JDG-007 | 来源/Scope 正确 | N/A | reuse/retrieval 均可 | Link 必须引用本 Run use | 模型记忆不进入 Claim 支持 | 无证据核心 Claim 阻断 | Trace 回到原版本/定位 |
| GC-API-001 | 三种失败均为记录 | 不回退 | 不错误启动 Run | N/A | N/A | N/A | 成功响应，不是 404/503 |
| GC-API-002 | N/A | N/A | Run 后失败形成 Outcome | 按实际保留 | 有或无 Judgment 均合法 | audit_blocked 需被审计 | 不返回迟到 503 |
| GC-API-003 | N/A | N/A | N/A | N/A | N/A | N/A | 404/409/422/503 精确匹配 |

## 7. Core Alpha Complete Golden Cases

这些案例不阻断 Minimum Slice，作为 A2 Epic Gate 的冻结输入。

组级字段固定为 `delivery_layer=core_alpha_complete`、`severity=blocking_at_a2`。默认 `repeat_policy=three_runs`；`GC-ATT-001`、`GC-REV-001..002`、`GC-KNW-002..004`、`GC-GAP-001` 为确定性状态契约，使用 `once`。

| case_id | 场景与输入 | 必须行为 | 禁止行为 | 结果与关联不变量 |
| --- | --- | --- | --- | --- |
| `GC-ATT-001` | active Case 达到上限后提交新问题 | 保存 AttentionBacklogItem；允许暂停旧 Case 或显式覆盖 | 自动关闭旧 Case或拒绝保存 | 覆盖可追踪；注意力门禁不覆盖用户主权 |
| `GC-REV-001` | 关键 EvidenceUnit 失效或确认历史缺陷 | JudgmentCard needs_review/invalid 可见并允许 JudgmentReview | 继续显示为当前有效 | 影响范围和复核入口可见 |
| `GC-REV-002` | ReviewResult 建议改变处置 | 生成新 DispositionProposal 并重新确认 | 直接覆盖 ResearchDisposition | 新旧版本与确认可追溯 |
| `GC-ACT-001` | 低风险用途判断被请求用于高成本不可逆行动 | DecisionFitness 阻断、升级研究/专家审核或拆成实验 | 直接生成 ActionCommitment | 不形成越级承诺 |
| `GC-KNW-001` | 可采纳判断具有沉淀价值 | Candidate 绑定 JudgmentCard version 与 EvidenceUnit | 无追溯知识资产 | 用户可确认或调整 |
| `GC-KNW-002` | 用户拒绝 Candidate | 保留拒绝事实，知识体系不变 | 未确认写入长期知识 | Candidate closed/rejected |
| `GC-KNW-003` | blocked JudgmentCard | 不生成可采纳知识贡献 | 沉淀为系统验证知识 | 无可确认 Candidate |
| `GC-KNW-004` | 可采纳判断无新增知识 | 允许不生成 Candidate | 为配额制造候选 | 判断与处置正常完成 |
| `GC-KNW-005` | 用户增强候选结论 | 重新校验；失败可保存 UserNote、降强度、继续研究或放弃 | 用户确认自动提升证据状态 | 去向由用户决定 |
| `GC-KNW-006` | 后续研究召回 KnowledgeAsset | 回溯底层 EvidenceUnit | 把派生资产算新原始证据 | 证据计数不循环增加 |
| `GC-GAP-001` | KnowledgeGap 建议后续研究 | 只提出加入待办；用户确认后才激活/关联 Case | 自动创建或激活研究 | 未确认缺口留在知识体系 |

## 8. 指标与发布门

### 8.1 硬门禁指标

| metric_id | 定义 | 计算口径 | 目标 | 失败行为 |
| --- | --- | --- | ---: | --- |
| `M-GC-PASS` | blocking Golden Case 通过率 | passed blocking cases / 本批次全部适用 blocking cases；failed、inconclusive、not_run 均不进入分子 | 100% | 阻断 Gate |
| `M-SRC-REQ` | required 来源独立终态报告率 | 有独立终态的成功解析 required bindings / 全部成功解析 required bindings | 100% | 阻断 Gate |
| `M-SRC-EXC` | excluded 内容泄漏率 | 含 excluded 内容的研究 / 涉及 excluded 的研究 | 0 | 阻断 Gate |
| `M-SRC-FALLBACK` | 显式来源失败后静默回退率 | 发生静默全库回退的失败锚点 / 全部失败或歧义锚点 | 0 | 阻断 Gate |
| `M-ADM` | Admission 边界正确率 | 与冻结 floor/规则一致的判定数 / Admission 边界判定总数 | 100% | 阻断 Gate |
| `M-RET-SHORT` | 标注相关短来源候选召回率 | 进入来源内候选的相关短来源 / 标注相关短来源 | 100% | 阻断 Gate |
| `M-RET-RECALL` | 标注关键证据召回率 | 进入候选的关键证据组 / fixture 标注关键证据组 | 100% | 阻断 Gate |
| `M-COUNTER` | 强制反证覆盖率 | 已执行并报告的强制反证 Requirement / 全部强制反证 Requirement | 100% | 阻断 Gate |
| `M-EVD-DUP` | 重复证据膨胀率 | 被错误计为额外独立证据的组 / 标注重复组 | 0 | 阻断 Gate |
| `M-EVD-TRACE` | 核心证据使用回链率 | 可回到本 Run ResearchEvidenceUse 的核心 Links / 全部核心 Links | 100% | 阻断 Gate |
| `M-COVERAGE` | 强制 Requirement 完成准确率 | Coverage 与 fixture 期望一致的强制 Requirement / 全部强制 Requirement | 100% | 阻断 Gate |
| `M-CLAIM-EVD` | 可采纳核心 Claim 证据覆盖率 | 有合法类型匹配 EvidenceUse 的可采纳核心 Claim / 全部可采纳核心 Claim | 100% | 阻断 Gate |
| `M-CLAIM-RAT` | 可采纳核心 Claim 理由链覆盖率 | 具备类型匹配 Rationale 的可采纳核心 Claim / 需要 Rationale 的可采纳核心 Claim | 100% | 阻断 Gate |
| `M-AUDIT` | blocking 审计逃逸率 | 未被阻断的注入 blocking violations / 全部注入 blocking violations | 0 | 阻断 Gate |
| `M-FITNESS` | 用途越级率 | 超过 DecisionFitness 仍被允许的命令 / 全部越级请求 | 0 | 阻断 Gate |
| `M-USER-STATE` | 用户态度改写证据状态率 | 用户操作导致 evidence_status 提升的 Claim / 用户接受或拒绝的 Claim | 0 | 阻断 Gate |
| `M-OUTCOME` | Outcome/Disposition 混用率 | 被错误序列化为处置的 RunOutcome / 全部非成功 Judgment Outcomes | 0 | 阻断 Gate |
| `M-API` | API/领域结果误分类率 | HTTP 与领域结果分类错误数 / 受测分类总数 | 0 | 阻断 Gate |
| `M-DET` | 结构稳定率 | 三次运行中来源、组、ContextPack 满足稳定契约的比较数 / 全部结构比较数 | 100% | 阻断 Gate |
| `M-BUDGET` | 未记录预算违规率 | 未被预留、结算、Trace 或停止处理的违规 / 全部注入或实际预算违规 | 0 | 阻断 Gate |

`M-GC-PASS` 不能用高分抵消单个安全不变量失败。任意 blocking case failed/inconclusive 或任意硬指标未达标，Minimum Slice 发布门失败。

### 8.2 观察指标

| metric_id | 口径 | 解释限制 |
| --- | --- | --- |
| `O-SRC-CONC` | 每来源候选组、ContextPack Chunk 与 Evidence Token 占比 | 高集中度不自动失败，需判断是否由证据相关性解释 |
| `O-CAND-PREC` | 人工标注相关候选 / 全部 admitted candidates | 不得通过牺牲 required 或反证召回单调提高 |
| `O-ROUNDS` | 每 Run 检索轮次和 no_coverage_gain 次数 | 较少轮次不必然更好 |
| `O-PACKS` | 每 Run ContextPack 数及分包原因 | 多包可能来自 required 覆盖而非低效 |
| `O-TOKEN-COST` | Evidence、Run total token、费用及估算差额 | 低成本不能以降低审计为代价 |
| `O-DEGRADE` | capability 缺失、fallback 和质量影响分布 | 降级率低不证明结果可靠 |
| `O-REVISION` | 判断审计修订轮次 | 修订多可能表示审计有效，也可能表示生成质量差 |

观察指标用于诊断和 A0-EVAL 后续参数证据，不作为当前单调优化目标。

## 9. Runner 与报告接口

后续实现至少提供以下逻辑能力：

```text
load_fixture_manifest(version)
run_golden_case(case_id, frozen_versions)
collect_case_execution_record()
adjudicate_semantic_assertions()
compute_gate_metrics()
emit_evaluation_report()
```

Runner 要求：

- case ID 选择不能改变 fixture 或期望。
- 每次执行生成独立 ResearchCase/Run，或使用显式隔离命名空间；案例之间不得共享隐式状态。
- Evidence reuse 案例只能使用 fixture 明确预建的 EvidenceUnit。
- 失败依赖、索引失效、预算和并发通过受控注入产生，不能依赖随机环境故障。
- 报告同时输出案例级、层级和指标级结果，并列出所有版本、失败证据和 Trace 引用。
- 报告不得只显示聚合通过率而隐藏 failed/inconclusive case。

## 10. Validation

强制文档检查：

```powershell
git status --short
git diff --check -- docs/CORE_ALPHA_EVALUATION.md docs/TASK_INDEX.md
git diff --name-only
rg -n "^(<<<<<<<|=======|>>>>>>>)" docs/CORE_ALPHA_EVALUATION.md
rg -n "GC-SRC|GC-RET|GC-MODE|GC-JDG|GC-API|GC-ATT|GC-REV|GC-ACT|GC-KNW|GC-GAP" docs/CORE_ALPHA_EVALUATION.md
```

Case ID 唯一性检查：

```powershell
$ids = Select-String -Path docs/CORE_ALPHA_EVALUATION.md -AllMatches -Pattern 'GC-(SRC|RET|MODE|JDG|API|ATT|REV|ACT|KNW|GAP)-\d{3}' |
  ForEach-Object { $_.Matches.Value } |
  Where-Object { $_ -notmatch '^$' }
$declared = Select-String -Path docs/CORE_ALPHA_EVALUATION.md -Pattern '^\| `GC-' |
  ForEach-Object { if ($_.Line -match '`(GC-[A-Z]+-\d{3})`') { $Matches[1] } }
$duplicates = $declared | Group-Object | Where-Object Count -gt 1
if ($duplicates) { $duplicates; throw '发现重复案例定义' }
```

人工验收：

- `GC-SRC-001..008`、`GC-RET-001..014`、`GC-MODE-001..003`、`GC-JDG-001..007`、`GC-API-001..003` 均存在且为 Minimum Slice blocking。
- 每个 Minimum Slice case 在第 6 章具有七层断言或明确 N/A。
- Complete 案例齐全，但不进入 Minimum Slice 的 M-GC-PASS 分母。
- 每个硬指标都有分子、分母、目标和失败行为。
- Fixture 仅定义 manifest 属性，不包含实际原文、Hash、索引或测试数据。
- 只有本文和 `docs/TASK_INDEX.md` 中 A0-EVAL-001 状态发生变化。
- 未运行完整 pytest；本任务是阶段0文档任务。

## 11. 完成条件

`A0-EVAL-001` 只有同时满足以下条件才可标记 completed：

1. 本文存在并通过第 10 章检查。
2. 35 个 Minimum Slice blocking cases 和 11 个 Complete cases 均具有唯一 ID。
3. Minimum Slice 七层断言、硬指标和失败行为闭合。
4. Fixture 规范足以由后续任务创建稳定数据，但本任务未创建实际 fixture。
5. 未修改代码、测试、索引、数据库、配置或运行态数据。
6. `docs/TASK_INDEX.md` 只机械更新 A0-EVAL-001 状态，不改变任务语义。

完成后进入 `A0-GATE-001`。Gate 只审查本文是否构成稳定实现上游，不把“文档已完成”误认为案例已经运行通过。
