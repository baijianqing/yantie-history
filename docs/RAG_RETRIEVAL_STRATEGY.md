# MetaOS Core Alpha 来源感知检索策略

状态：A0-GATE 前冻结候选

任务标识：`A0-DOC-006`

修订标识：`A0-DOC-006-R1.2`

策略版本：`core-alpha-v1.2-candidate`

参数集版本：`core-alpha-v1.2-defaults`

依赖：`A0-DOC-005-R1.1.2`、业务架构 `A0-DOC-001-R7.1`、技术架构 `A0-DOC-002-R4.1`、领域模型 `A0-DOC-003-R1.2.2`、API 契约 `A0-DOC-004-R1.2.1`

## 1. 文档权威与任务边界

本文是 Core Alpha 来源路由、来源内检索、候选融合、证据分组、ContextPack、预算和停止策略的唯一权威。它回答“从哪里找、怎样找、何时停止、怎样把证据交给后续判断”，不重新定义领域对象、状态机、HTTP 契约或存储结构。

跨文档所有权如下：

- 业务价值和用户控制权以 `docs/BUSINESS_ARCHITECTURE.md` 为准。
- 技术模块、Port、Worker 和出站控制以 `docs/TECHNICAL_ARCHITECTURE.md` 为准。
- 对象、字段、状态和不变量以 `docs/DOMAIN_MODEL.md` 为准。
- HTTP、JSON、幂等和并发语义以 `docs/API_CONTRACTS.md` 为准。
- 本文只拥有检索策略不变量、算法顺序、Alpha 默认参数和可评测决策规则。

任务契约：

- 价值：消除知识篇幅和 Chunk 数量对来源发言权的支配，使显式来源、短资料、比较研究、反证检索和证据复用都可解释、可追踪、可评测。
- 允许修改范围：首次交付新增本文；验收通过后机械更新 `docs/TASK_INDEX.md` 中 `A0-DOC-006` 的状态。后续勘误只修改本文并升级相应版本。
- 禁止修改范围：代码、测试、索引、Embedding、Chroma、数据库、迁移、配置和运行态数据。
- 输入：`ResearchQuestion`、`SourceResolution`、`KnowledgeScope`、`ResearchPlan`、`RunExecutionSpec`、Knowledge Catalog 和可用检索 Capability。
- 输出：来源路由决策、`RetrievalRun`、候选证据组、`ContextPack`、`EvidenceUnit`、`ResearchEvidenceUse` 及检索决策 Trace。
- 接口：Retrieval Router、Knowledge Access Port、Capability Provider、Evidence Validity Checker 和 Context Packer 的策略输入输出。
- 回滚：本次勘误回退修订提交；首次交付整体回滚时才删除本文并把 `A0-DOC-006` 状态恢复为 `pending`。两种情况都不涉及运行态回滚。
- 文档更新：首次交付维护本文和任务状态；后续勘误只维护本文，不回写其他冻结文档的语义。

### 1.1 冻结层级

本文区分两类权威内容：

1. **策略不变量**：来源优先于 Chunk、显式约束不可替代、先来源路由再来源内检索、required 独立报告、excluded 零内容污染、证据分组去重、Chunk 与 Token 双预算、停止原因可解释。改变这些不变量必须修改本文、升级 `retrieval_policy_version` 并重新执行 `A0-GATE-001`。
2. **Alpha 默认参数集**：本文第 5 章给出的数值与算法标识属于 `core-alpha-v1.2-defaults`。`A0-EVAL-001` 只能提供调整证据，不能在评测文档中直接产生新参数。任何参数调整必须回写本文、升级 `parameter_set_version`，并重新通过 A0 Gate。

同一 ResearchRun 必须在不可变 `RunExecutionSpec` 中固定实际使用的策略版本和参数集版本。运行中的 Run 不因本文后续修改而改变行为。

### 1.2 核心策略不变量

1. 用户显式解析成功的来源是硬约束，不参加是否选中的竞争。
2. 显式来源解析失败、歧义或版本不可用时，不得静默回退全库。
3. 无显式来源时必须先做来源级路由，再在每个候选来源内独立检索；禁止所有 Chunk 直接竞争唯一全局 Top-K。
4. 来源相关度不得通过累加该来源全部 Chunk 分数计算。
5. `required / allowed / excluded` 与 `primary / comparison / background` 是两个正交维度。
6. required 来源必须独立进入终态并独立报告，其他来源不得替代其无证据或不可用结果。
7. excluded 来源的内容不得进入候选、ContextPack、EvidenceUnit、引用或判断证据链；其 ID 可以仅作为过滤条件和审计记录传递。
8. 全扫描只扩大本地候选排序范围，不增加 Provider 上下文特权。
9. 重叠或重复 Chunk 不得虚增独立证据数量；跨版本 provenance 不得因内容相同而被抹去。
10. `max_context_chunks` 与 Evidence Token 预算必须同时满足；Chunk 数量不能替代 Token 成本。
11. 降级不等价。缺失能力、fallback 路径和质量影响必须进入 Trace，并由后续确定性 Gate 判断是否仍满足计划。
12. 模型参数知识、历史回答文本和 KnowledgeAsset 不能替代 EvidenceUnit。

## 2. 策略输入、输出与术语

### 2.1 策略输入

一次检索执行至少接收：

- 原始 `ResearchQuestion` 及其稳定 ID。
- 已完成的 `SourceResolution` 和具体 `KnowledgeScope` 版本。
- `KnowledgeScopeSourceBinding` 的 access policy 与 analysis role。
- 具体 `ResearchPlan` 版本、研究模式和 `EvidenceRequirement`。
- `RunExecutionSpec` 中固定的知识版本、IndexGeneration、允许 Capability、降级政策、总预算、策略版本和参数集版本。
- 当前可用 Knowledge Catalog、全文检索、向量检索、可选 reranker、Evidence Catalog 与有效性校验能力。

任何输入版本与 RunExecutionSpec 不一致时，不得继续本次 Attempt。变更 Scope、Plan、核心证据要求或研究目标必须产生新 ResearchRun，而不是在当前 Run 内悄然采用新策略输入。

### 2.2 策略输出

检索策略输出不是一段自由文本，而是一组可追踪事实：

- 来源路由结果与每个来源的通道贡献。
- 每轮 QueryVariant、来源集合、能力状态和停止判断。
- 每个来源绑定、检索通道和 QueryVariant 对应的 `RetrievalRun` 结果。
- 经有效性检查和去重后的 `IndependentEvidenceGroup`。
- 新建或复用的 `EvidenceUnit`。
- 当前 Run/Attempt 对 EvidenceUnit 的 `ResearchEvidenceUse`。
- 一个或多个 `ContextPack` 及其排序、保留和丢弃理由。
- `EvidenceRequirementCoverage` 的策略投影。
- 最终停止类型、降级影响，以及映射到领域记录所需的事实。

`IndependentEvidenceGroup`、`ContextPack`、`EvidenceRequirementCoverage` 和 `SourceRoutingView` 是检索执行中的技术视图或值对象，不是新增领域聚合，也不拥有业务状态转换权。

### 2.3 SourceRoutingView

`SourceRoutingView` 是可重建的来源级技术投影，不是 `KnowledgeItemProfile`、领域事实或新聚合。它至少包含：

- `KnowledgeItem` 的 ID、标题、别名和语言。
- 当前可用 `KnowledgeItemVersion` 的 ID 与可用性。
- 可用于路由的摘要、主题词和章节标题结构。
- 当前 `IndexGeneration`、chunk strategy version、active Chunk 数量和 Token 估算。
- 可选的来源级全文与向量信号。
- projection version、生成时间和输入版本集合。

投影规则：

- 它只能由权威 KnowledgeItem、KnowledgeItemVersion、Chunk 和有效 IndexGeneration 重建。
- 它不能覆盖、改写或替代显式 `SourceResolution`。
- 投影缺失时，可以从权威标题、别名、语言、版本可用性和结构元数据临时构建最小视图；不得退化为全库 Chunk 直接竞争。
- 投影过期但所引用 KnowledgeItemVersion 与 IndexGeneration 仍有效时，可以降级使用，并记录 warning、投影年龄和质量影响。
- 投影引用的版本或 IndexGeneration 已失效时，不得继续使用；必须重建，或报告来源路由能力不可用。

## 3. 来源路由

### 3.1 显式来源路径

成功解析的显式来源直接形成可检索集合：

```text
SourceResolution
-> KnowledgeScopeSourceBinding
-> required 来源与被选中的 allowed 来源分别检索
-> 按 access policy、analysis role 和证据质量融合
```

规则：

- `required` 和 `allowed` 必须固定具体可用 KnowledgeItemVersion。
- `excluded` 可以只固定作品身份，不读取内容版本。
- 显式 required 来源不受 `max_routed_sources` 限制。
- `required` 必须执行并独立报告终态。
- `allowed + primary` 默认执行。
- `allowed + comparison` 在 ResearchPlan 的比较对象或 EvidenceRequirement 引用该来源时必须执行；没有计划引用时不自动执行。
- `allowed + background` 只有在来源路由选中且预算允许时执行。
- 未设置 analysis role 的普通 allowed 来源，由 ResearchPlan、EvidenceRequirement 和来源路由共同决定是否执行。
- 未执行的 allowed 来源记录为 `not_selected` 或 `not_executed`，但不构成 required Coverage 缺口。
- 被计划引用的显式 comparison 来源不得由 primary 来源替代，也不得因为相关度较低而跳过。
- required 来源无证据、来源不可用和检索通道失败是三个不同结果，必须分别报告。
- 显式来源数量导致单包不可行时，进入多 ContextPack 路径，不得静默删减来源。

### 3.2 无显式来源路径

无显式来源时，每个路由通道先独立产生来源排名：

1. 标题和别名。
2. 摘要和主题词。
3. 章节标题与结构。
4. 来源级全文信号。
5. 来源级向量信号。

来源 RRF 分数为：

```text
source_rrf_score(source)
= sum(1 / (rrf_k + channel_rank(source)))
```

其中 `rrf_k=60`。执行规则：

- 每个来源在每个通道最多贡献一次。
- 标题或别名精确查询命中是无显式来源路径中的路由硬优先级，不只是普通 RRF 加分；它不自动获得 required 语义。
- Chunk 级信号必须先按来源折叠。主排序采用该来源最佳 Chunk rank；同分时参考该来源 Top-3 Chunk 的平均 reciprocal rank。
- 不得累加同一来源所有 Chunk 的分数、相似度或命中数。
- 缺失某个可选通道时，在剩余通道上计算，并记录 missing capability 与质量影响；不得为缺失通道伪造最低分。

`source_admission_policy_version=core-alpha-source-admission-v1`。来源进入自动路由候选前至少满足一项可解释准入条件：

- 标题或别名精确查询命中。
- 至少一个来源级通道达到该通道在当前 admission policy 中登记的最低相关性要求。
- 命中 ResearchPlan 预先固定的来源选择条件。
- 命中由 A0-EVAL 提出、回写本文并升级版本的其他可解释规则。

`max_routed_sources` 是上限，不是必须填满的配额。没有来源通过准入时，记录 `no_admissible_source`、各通道最高候选和拒绝理由，并进入澄清或证据不足路径；不得从全库中强行选择“最不差”的来源。通道相关性门槛必须由 admission policy 与 Capability 版本共同固定在 RunExecutionSpec 中，不能在一次 Run 内动态放宽。

来源稳定排序固定为：

```text
exact_title_query_match DESC
-> source_rrf_score DESC
-> knowledge_item_id ASC
```

`resolved_source_anchor_match` 属于显式 SourceResolution 路径，不参与上述无显式来源排序。若 SourceResolution 阶段已经确认来源没有当前可用版本，即使路由相关也不能进入检索集合；其 `unavailable` 结果保存在 SourceResolution 和路由 Trace 中，不生成伪 RetrievalRun。若 Run 已绑定的 KnowledgeItemVersion 随后失效，或某个通道所需 IndexGeneration 失效，则按第 4.3 与第 12 章分别记录来源不可用或通道失败。

### 3.3 自动来源数量

`max_routed_sources` 只约束无显式来源时自动选入的来源数量，不要求填满：

| research_mode | max_routed_sources | max_rounds | 说明 |
| --- | ---: | ---: | --- |
| `fact_lookup` | 3 | 2 | 少量高相关来源，优先直接事实 |
| `source_interpretation` | 3 | 3 | 优先原始来源和必要上下文 |
| `compare_sources` | ResearchPlan 明确，默认 4 | 3 | 不得在检索后偷偷增加比较对象 |
| `enumerate_pattern` | 6 | 4 | 允许较宽候选来源，但仍需声明候选边界 |
| `claim_evaluation` | 5 | 4 | 为支持、反驳和竞争解释保留来源空间 |

ResearchPlan 明确的来源数量优先于自动默认，但不得突破 RunExecutionSpec 的总预算。无法容纳时必须在执行前报告可行性问题或采用多阶段执行。

## 4. Query 派生与检索轮次

### 4.1 evidence_query

`evidence_query` 不能通过对问题文本做全局字符串替换得到。SourceResolution 必须保留原始问题中被确认解析为来源锚点的 span；只允许移除这些已确认 span，同时保留同名概念在其他位置的语义。

最低 Trace 内容：

- original question。
- resolved anchor spans，包括起止位置、原文本和解析结果。
- derived evidence query。
- query transformation version。
- 保留或删除每个 span 的理由。

如果移除锚点后问题失去可解释语义，ResearchPlan 必须提供结构化 evidence query 或进入澄清路径，禁止向检索通道发送空查询。

### 4.2 QueryVariant

QueryVariant 是一轮检索所使用的结构化查询变体，至少标识：

- 来源问题和 evidence query。
- `query_family`：`direct / targeted_retry / candidate_generation / candidate_verification`，表达执行动作。
- `evidence_purpose`：`support / counterevidence / alternative_interpretation / failure_condition`，表达证据认知目的。
- 目标 EvidenceRequirement。
- 目标来源绑定。
- 变体生成原因与版本。

两个字段正交组合，不得用 `refutation`、`support`、`interpretation` 等临时值扩张 query_family。例如 claim_evaluation 的反驳查询表达为 `query_family=direct` 与 `evidence_purpose=counterevidence`；候选反证验证表达为 `query_family=candidate_verification` 与 `evidence_purpose=counterevidence`。

别名展开可以在同一 QueryVariant 内形成通道查询，不单独增加研究轮次。

### 4.3 RetrievalRun 粒度

一个 `RetrievalRun` 的唯一粒度固定为：

```text
一个 ResearchAttempt
+ 一个 QueryVariant
+ 一个 KnowledgeScopeSourceBinding
+ 一个 retrieval_channel
+ 一个 IndexGeneration（该通道适用时）
```

因此，同一来源在同一轮通常分别产生全文 RetrievalRun、向量 RetrievalRun，以及计划启用的其他通道 RetrievalRun；来源内 RRF 聚合这些 RetrievalRun 的候选。规则如下：

- 一个 RetrievalRun 不得同时代表多个来源、多个 QueryVariant 或多个 retrieval_channel。
- 通道正常执行但没有合法候选时，记录 `status=completed`、`retrieval_outcome=no_evidence`。
- 通道自身执行失败时，记录 `status=failed`、`retrieval_outcome=failed`。
- Run 已绑定的 KnowledgeItemVersion 执行时失效，记录 `status=completed`、`retrieval_outcome=source_unavailable`。
- 当前通道依赖的 IndexGeneration 缺失或失效，记录 `status=failed`、`retrieval_outcome=failed` 和 `failure_category=index_unavailable`；这不代表 KnowledgeItemVersion 不可用。
- 某一索引通道不可用但其他通道可用时，继续执行可用通道并记录降级；只有全部必要通道不可用且没有合法复用证据时，才可能形成 execution_failed。
- Provider 重试和相同输入的基础设施重投属于该 RetrievalRun 的技术执行事实，不创建新的业务 RetrievalRun。

### 4.4 一轮检索的定义

一轮检索严格定义为：

```text
选择或生成 QueryVariant
-> 按 KnowledgeScope 对每个被选来源执行启用通道，并逐一形成 RetrievalRun
-> 通道内去重
-> 来源内 RRF
-> 通过权威 Knowledge Access Port 校验来源版本、定位和 Hash
-> 形成或复用 EvidenceUnit
-> 更新 EvidenceRequirementCoverage
-> 记录本轮新增 IndependentEvidenceGroup
```

以下操作不构成新轮次：

- Provider 网络重试。
- RQ 或其他基础设施对相同 Query 的重投。
- 同一 QueryVariant 内的别名展开。
- 同一候选集合上的排序重试。

以下操作可以形成新轮次：

- 基于上一轮缺口进行查询改写。
- 独立反证查询。
- 替代解释查询。
- 枚举候选的定向验证查询。

每轮必须记录输入 QueryVariant、来源集合、requested/available/missing capability、通道结果、本轮新增证据组和 Coverage 变化。相同 Query、相同来源、相同通道和相同索引代际的基础设施重投必须幂等，不得虚增 RetrievalRun 或证据数量。

## 5. Alpha 默认参数集

以下参数属于 `parameter_set_version=core-alpha-v1.2-defaults`：

| 参数 | 默认值 | 作用域 |
| --- | ---: | --- |
| `retrieval_policy_version` | `core-alpha-v1.2-candidate` | 策略不变量版本 |
| `parameter_set_version` | `core-alpha-v1.2-defaults` | Alpha 默认参数版本 |
| `rrf_k` | 60 | 来源路由与来源内 RRF |
| `source_chunk_signal_top_m` | 3 | Chunk 信号折叠到来源时的同分参考 |
| `full_scan_chunk_threshold` | 32 | 允许全扫描的 active Chunk 上限 |
| `full_scan_token_threshold` | 24000 | 允许全扫描的本地文本 Token 估算上限 |
| `max_candidate_groups` | 80 | 每 Attempt 每轮进入跨来源融合的证据组上限 |
| `max_source_candidate_groups` | 12 | 单来源进入跨来源候选池的组上限 |
| `min_source_candidate_groups` | 4 | 有足够准入候选时单来源的最低候选保留数，不是填充配额 |
| `max_context_chunks` | 20 | 单次 Provider Invocation 原始证据 Chunk 上限 |
| `max_context_tokens` | 由第 10.2 节公式动态计算 | 单次调用 Evidence Token 上限 |
| `per_invocation_evidence_cap` | 由 RunExecutionSpec 固定 | 单次调用不得突破的 Evidence Token 安全上限 |
| `provider_unknown_context_limit` | 8000 | Provider 未声明窗口时的保守能力默认值 |
| `minimum_executable_evidence_tokens` | 512 | 允许发起模型调用的最低 Evidence Token 预算 |
| `background_token_ratio` | 0.20 | background 使用单个 ContextPack Evidence Token 的上限 |
| `no_gain_round_limit` | 2 | 连续无新增独立证据组的停止阈值 |
| `adjacent_context_chunks` | 前后各 1 | source_interpretation 默认相邻窗口 |
| `evidence_normalization_version` | `core-alpha-normalization-v1` | 证据文本规范化规则版本 |
| `evidence_similarity_metric` | `character-3gram-jaccard-v1` | 同章节连续文本相似度算法 |
| `evidence_grouping_policy_version` | `core-alpha-grouping-v1` | 位置重叠、相似度和分组顺序版本 |
| `source_admission_policy_version` | `core-alpha-source-admission-v1` | 自动来源准入规则版本 |
| `candidate_admission_policy_version` | `core-alpha-candidate-admission-v1` | 来源内证据候选准入规则版本 |

`max_routed_sources` 和 `max_rounds` 按第 3.3 节模式表取值。

参数边界：

- `max_candidate_groups=80` 约束单轮自动融合池。required 最低覆盖本身超过该值时，必须分批构造候选与 ContextPack，并记录参数不可行性，不得删除 required。
- 所有数值是候选默认值，不是领域对象字段或用户承诺。
- A0-EVAL-001 必须基于固定 fixture 规范报告调整理由、收益、退化和受影响 Golden Case。

## 6. 允许全扫描与独立证据组

### 6.1 full_scan_eligible

“短资料”不是 KnowledgeItem 的永久属性。一个选定版本只有同时满足以下条件才为 `full_scan_eligible`：

```text
active_chunk_count <= full_scan_chunk_threshold
AND estimated_tokens <= full_scan_token_threshold
```

该判断绑定：

- `knowledge_item_version_id`。
- `index_generation_id`。
- `chunk_strategy_version`。
- active Chunk 集合与 Token 估算方式。

规则：

- 全扫描表示该版本全部 active Chunk 参与本地候选排序，不表示全部进入模型上下文。
- IndexGeneration、chunk strategy 或 active Chunk 集合变化后必须重新判断。
- 全扫描仍需执行去重、有效性检查、候选上限、ContextPack 双预算和出站政策。
- 不满足全扫描条件的资料使用章节/结构定位和来源内检索，不能因篇幅长而获得更多候选配额。

### 6.2 IndependentEvidenceGroup

独立证据组的基础身份为：

```text
knowledge_item_version_id
+ canonical location range
+ normalized content hash
```

分组计算必须固定并记录：

- `evidence_normalization_version`：`core-alpha-normalization-v1` 使用 Unicode NFKC、统一换行、折叠连续空白、拉丁字母小写；保留中文标点、繁简体和原词形，不做语义改写。
- `evidence_similarity_metric`：`character-3gram-jaccard-v1`，在规范化文本的字符 3-gram 集合上计算 Jaccard 相似度；文本短于 3 个字符时退化为规范化全文精确比较。
- `evidence_grouping_policy_version`：`core-alpha-grouping-v1`，固定本节条件的判断顺序和阈值。
- location overlap：同一定位坐标系中，交集长度除以较短 range 长度；无法映射到同一坐标系时不得仅凭位置合并。

这三个版本必须进入 RunExecutionSpec、ResearchTrace 和 IndependentEvidenceGroup 计算记录。分组算法版本变化且可能改变证据计数或代表摘录时，必须创建新 ResearchRun；只有 RunExecutionSpec 已明确允许且不会改变分组结果的实现 fallback 才能留在同一 Run。

同一 KnowledgeItemVersion 内，候选满足任一条件时合并为同一组：

- normalized content hash 相同。
- canonical location range 重叠不少于 50%。
- 位于同一章节、位置连续，且规范化文本相似度不低于 0.90。

合并限制：

- 不得跨无关章节合并。
- 不同 KnowledgeItemVersion 的相同文本保持独立 provenance，不直接合并为同一来源证据。
- 同一作品不同版本不能因 Hash 相同而失去版本身份。
- excluded 来源的内容即使与 allowed 来源 Hash 相同，也不得成为 allowed EvidenceUnit 的来源关系或使用关系。
- 引用转载与原始来源可以被识别为内容相关，但证据数量和来源独立性必须分别报告。

独立证据数量按组计数；合法候选的全部来源、Chunk 和位置关系仍保留在 Trace 中。组内选择代表摘录时，优先选择定位完整、支持语义完整、版本有效且上下文成本更低的片段。

## 7. 来源内检索与跨来源融合

### 7.1 来源内检索

每个 required 来源和被 ResearchPlan、EvidenceRequirement 或来源路由选中的 allowed 来源独立执行：

```text
全文检索 + 向量检索
-> 来源内 RRF
-> IndependentEvidenceGroup
-> 来源内稳定排序
```

来源内 RRF 使用 `rrf_k=60`。每个通道只贡献该来源内部候选排名，不要求不同通道的原始分数同尺度。

来源内稳定排序：

```text
EvidenceRequirement match DESC
-> counterevidence need DESC
-> source-internal RRF DESC
-> canonical location ASC
-> evidence group id ASC
```

`candidate_admission_policy_version=core-alpha-candidate-admission-v1`，并由 RunExecutionSpec 固定。证据组进入来源候选池前必须：来源和定位有效、符合 KnowledgeScope，并与至少一个 EvidenceRequirement 具有可解释匹配；匹配理由、Requirement ID 和 admission policy version 必须进入 Trace。

每个来源最多保留 12 个候选组。`min_source_candidate_groups=4` 只适用于已经通过候选准入的合法证据；来源只有 1 个合格组时就只保留 1 个。禁止为了填满 4 个而降低相关性、证据用途、定位、有效性或 Scope 要求，也不得复制候选凑配额。

### 7.2 access policy 与 analysis role

执行顺序固定为：

1. access policy 决定来源内容是否可进入执行。
2. required 决定来源必须独立检索并报告终态。
3. analysis role 决定 ContextPack 打包优先级。
4. background 只使用剩余预算。

一个来源可以同时是 `required + comparison`。required 与 comparison 不是互斥枚举，primary 也不自动等于 required。

### 7.3 来源覆盖槽位

进入全局竞争前先保留来源覆盖：

- 每个 required 来源针对相关强制 EvidenceRequirement 至少保留 1 个合法证据组；没有证据时保留独立终态报告，而不是伪造候选。
- primary 来源至少保留 2 个组；不足 2 个时保留全部。
- comparison 来源至少保留 2 个组；不足 2 个时保留全部。
- background 没有最低配额，单包 Evidence Token 使用上限为 20%。未使用的 background 预算回流给 required、primary、comparison 或反证证据。

来源最低覆盖不是 required、analysis role 和 Requirement 配额的简单相加：

```text
effective_minimum_coverage =
满足全部强制 EvidenceRequirement 所需的最小不同证据组集合
UNION
满足 analysis role 最低数量要求所需的补充证据组集合
```

同一证据组可以满足多个 Requirement，但只有其内容和定位分别通过每个 Requirement 的候选准入校验时才能复用。Coverage 必须分别记录映射，不得只复制标签，也不得因多重标签虚增证据数量。存在多个同样大小的最小集合时，按第 7.4 节稳定排序选择。

### 7.4 全局融合和 reranker

保留最低覆盖后，剩余槽位由全局竞争产生。稳定全局排序为：

```text
required coverage need DESC
-> source selection priority
-> analysis role priority
-> counterevidence need DESC
-> evidence relevance DESC
-> automatically routed source_rrf_score DESC（仅自动路由来源）
-> knowledge_item_version_id ASC
-> canonical location ASC
-> evidence group id ASC
```

`source_selection_priority` 固定为：

1. `explicit_required`。
2. `explicit_plan_selected_allowed`。
3. `automatically_routed`。

`explicit_plan_selected_allowed` 包括由 allowed + primary 默认规则、ResearchPlan、EvidenceRequirement 或显式比较计划选中执行的 allowed 来源。显式来源不需要伪造 `source_rrf_score`，该值保持不适用；只有自动路由来源之间才比较 source_rrf_score。显式 allowed 的剩余候选按 source selection priority、analysis role、counterevidence need 和 evidence relevance 排序。analysis role priority 固定为 `primary > comparison > background`；未设置角色的 allowed 来源位于 comparison 与 background 之间，只参与剩余槽位竞争。

可选 reranker 只在来源最低覆盖已保留后重排剩余候选。它不得：

- 引入 excluded 来源。
- 移除 required 来源最低覆盖。
- 改变 SourceResolution 或 KnowledgeScope。
- 改写 EvidenceUnit 的有效性结果。
- 通过单个长资料的密集相似片段占满 ContextPack。

reranker 不可用但规则/RRF 可用时属于可记录降级，不是检索失败。

## 8. 五种研究模式契约

五种模式共享来源治理、有效性、预算和 Trace 不变量，但不得共享完全相同的单次 Top-K 流程。

### 8.1 fact_lookup

- required inputs：明确的事实目标、KnowledgeScope、至少一个可执行 EvidenceRequirement。
- query families：首轮使用 `direct + support`；不足时最多一次 `targeted_retry + support`。别名展开属于同轮通道查询。
- source coverage：显式 required 独立报告；无显式来源按最多 3 个自动来源执行。
- counterevidence：默认不强制；ResearchPlan 要求或事实存在冲突信号时执行。
- max rounds：2。
- success condition：至少一个有效、可精确定位的证据组满足强制事实 Requirement；required 来源全部进入终态。
- partial outcome：无定位、仅有间接背景或 required 无证据时为 `insufficient_evidence`，而不是凭模型记忆补答。
- context strategy：单 ContextPack 优先；required 来源过多时按来源拆包。
- output：事实候选、版本、定位、支持强度和来源终态。
- forbidden shortcut：把“无结果”当成反证；省略定位；用相似主题来源替代 required。

### 8.2 source_interpretation

- required inputs：待解释概念或段落、目标来源、解释所需上下文 Requirement。
- query families：概念、章节和相邻上下文使用 `direct + support`；补检使用 `targeted_retry + support`；替代解释使用 direct 或 targeted_retry 与 `alternative_interpretation` 组合。
- source coverage：优先显式/primary 原始来源；无显式来源最多自动路由 3 个来源。
- counterevidence：替代解释或争议是计划要求时强制；否则记录可用的替代解释信号。
- max rounds：3。
- success condition：原文证据与必要上下文均有定位，解释路径能回到 EvidenceUnit，required 来源全部终态。
- partial outcome：只有原文无足够上下文时降低解释强度；替代解释可以作为明确假设，但不能伪装成原文观点。
- context strategy：原文组加前后各 1 个 Chunk 的默认相邻窗口；跨章节时按结构拆包。
- output：原文、上下文、解释、替代解释/假设的分层结果。
- forbidden shortcut：把模型推断写成来源事实；只检索命中句而忽略必要上下文；让其他来源替代指定原文。

### 8.3 compare_sources

- required inputs：ResearchPlan 必须选择固定来源比较或自动来源比较，并预先定义比较维度。固定来源比较还必须固定来源 Binding；自动来源比较必须固定目标来源数量、来源选择条件和允许的最大数量。
- query families：每个比较维度在每个来源内独立执行 `direct + support`；必要反证使用 `direct + counterevidence`；补检使用对应 purpose 的 targeted_retry。
- source coverage：固定来源比较按 Plan 中的 Binding 执行；自动来源比较由来源路由选择实际来源，并在 RunExecutionSpec 中固化。每个实际来源独立返回 `evidence_found / no_evidence / unavailable`；自动来源比较默认最多 4 个来源。
- counterevidence：对每个比较维度检索差异、冲突和不适用证据。
- max rounds：3。
- success condition：每个 required 比较来源进入终态；至少一个计划维度具备可对齐证据，缺边情况被明确报告。
- partial outcome：某来源无证据时可以形成不完整比较，但不能制造假对称或用其他来源代答。
- context strategy：每个来源独立 ContextPack 和结构化比较矩阵，再进行综合。
- output：逐来源证据状态、维度矩阵、共识、差异、空缺与版本限制。
- forbidden shortcut：所有来源共用一次全局 Top-K；RunExecutionSpec 固化后新增比较来源；检索后临时创造比较维度；把 no_evidence 写成来源持相反观点。

### 8.4 enumerate_pattern

- required inputs：候选全集边界、模式判定条件、每个候选的支持/反证 Requirement 和排除规则。
- query families：候选生成使用 `candidate_generation + support`；候选验证分别使用 candidate_verification 与 support/counterevidence；未决候选使用对应 purpose 的 targeted_retry。
- source coverage：按 ResearchPlan 声明的候选全集来源；无显式来源最多自动路由 6 个来源。
- counterevidence：每个候选必须执行，至少检查关键条件的反证或替代解释。
- max rounds：4。
- success condition：候选生成范围已执行；每个纳入候选完成条件验证、反证检查和独立证据映射；required 来源终态完整。
- partial outcome：候选可以标记纳入、排除或未决；预算停止时报告已验证范围和剩余缺口。
- context strategy：候选生成包、逐候选验证包和 EvidenceMatrix 分阶段执行；综合时优先矩阵与证据摘要。
- output：候选全集来源、逐候选支持、反证、条件满足、排除理由、未决状态和覆盖边界。
- forbidden shortcut：一次 Top-K 后宣称完成枚举；把“未发现更多”写成“已经穷尽”；只有事件先后而无因果证据时强行纳入因果模式。

### 8.5 claim_evaluation

- required inputs：待评估 Claim、支持条件、反驳条件、竞争解释和失效条件。
- query families：query_family 首轮使用 direct、缺口补检使用 targeted_retry；evidence_purpose 分别使用 support、counterevidence、alternative_interpretation 和 failure_condition。
- source coverage：显式 required 独立执行；无显式来源最多自动路由 5 个来源。
- counterevidence：强制。
- max rounds：4。
- success condition：支持、反驳、竞争解释和失效条件的强制 Coverage 均已执行，required 来源进入终态。
- partial outcome：允许形成 mixed、contradicted 或 insufficient 证据结果；冲突本身不是检索失败。
- context strategy：支持包与反驳包分离，最后形成 Claim-Evidence 矩阵和结构化综合。
- output：支持与反驳证据、竞争解释、失效条件、空缺、来源与版本限制。
- forbidden shortcut：把无反驳证据当成 Claim 成立；把无支持证据当成 Claim 为假；把竞争解释隐藏在最终摘要之外。

## 9. EvidenceRequirementCoverage

Coverage 是当前 ResearchAttempt 的可重建策略投影，至少逐项记录：

- EvidenceRequirement ID。
- 相关 KnowledgeScopeSourceBinding ID。
- mandatory / optional。
- support、counterevidence、alternative interpretation 的执行状态。
- 已映射 IndependentEvidenceGroup 和 EvidenceUnit。
- 来源执行状态：`evidence_found / no_evidence / unavailable / channel_failed / not_selected / not_executed`。
- 是否满足 completion condition。
- 未满足理由和下一轮 QueryVariant 原因。

`no_evidence` 只表示在固定策略、来源、版本、通道、轮次和预算内未找到合法证据，不证明事实不存在。`unavailable` 表示来源或必要能力不可用；它不能与 no_evidence 合并。`not_selected` 表示 allowed 来源未被计划或路由选中，`not_executed` 表示已选来源因明确的执行条件未运行；二者都不能用于 required 来源的成功终态。

Coverage 不是新的领域状态。ResearchRun 结束时，由领域模型已有对象表达最终结果；Coverage 只为停止、审计和 Trace 提供决策事实。

## 10. ContextPack 与预算

### 10.1 Chunk 与 Run 边界

`max_context_chunks=20` 适用于一次 Provider Invocation 的原始证据上下文，不是整个 ResearchRun 的总 Chunk 上限。一个 Run 可以使用多个 ContextPack，但必须同时受 RunExecutionSpec 的总时间、调用、Token 和成本预算约束。

每个 ContextPack 至少保存：

- ContextPack ID、ResearchRun/Attempt 和调用目的。
- EvidenceRequirement 与来源绑定。
- 证据组、EvidenceUnit 和 ResearchEvidenceUse 引用。
- 原始 Chunk 数、Evidence Token 估算和实际值。
- 排序、最低覆盖、截断和丢弃理由。
- provider、tokenizer/估算方式和 MaterialManifest 引用。

### 10.2 Evidence Token 预算

Minimum Slice 必须由 RunExecutionSpec 提供 `system_evidence_budget` 或等价系统安全上限。用户预算是可选输入；未提供用户预算不等于无限预算。多个 ContextPack 共享同一份 Run 总预算，不能让每次调用重新获得完整额度。

每次构建 ContextPack 前先计算剩余预算：

```text
remaining_system_evidence_budget =
system_evidence_budget
- consumed_system_evidence_tokens
- reserved_system_evidence_tokens

remaining_user_evidence_budget =
user_evidence_budget
- consumed_user_evidence_tokens
- reserved_user_evidence_tokens
  if ResearchPlan 提供用户预算
  else unbounded_by_user

effective_evidence_budget =
min(
  remaining_system_evidence_budget,
  remaining_user_evidence_budget,
  per_invocation_evidence_cap
)
```

单次调用的 `max_context_tokens` 再动态计算为：

```text
evidence_token_budget =
min(
  effective_evidence_budget,
  provider_input_limit
  - system_prompt_reserve
  - output_reserve
  - query_and_instruction_tokens
  - schema_and_tool_reserve
  - safety_margin
)
```

规则：

- 优先使用实际 Provider tokenizer。
- 没有 tokenizer 时使用保守估算，并记录估算器版本和误差来源。
- RunExecutionSpec 的系统安全预算始终存在；用户预算只能收紧该安全边界，不能放宽它。
- Core Alpha Complete 的 ResearchBudgetGuard 可以依据剩余总预算进一步收紧本次调用，但不能突破 RunExecutionSpec 的系统安全上限。
- ContextPack 构建前必须从权威 Run 执行记录读取剩余量，并以乐观并发令牌原子预留“估算 Token + safety margin”；并发调用不得同时占用同一份剩余预算。
- 调用完成后以 Provider 实际 Token 使用量原子结算预留：实际消耗较低时释放差额；实际消耗较高时扣除差额。
- 估算不足导致实际消耗超过预留时，必须记录 `budget_estimation_overrun`、估算器版本和差额。若差额使 Run 达到或超过硬上限，将剩余预算视为 0、禁止后续调用并保留本次已发生消费；不得通过负预算继续执行。
- Provider 调用失败但已经产生可计量 Token 消耗时，实际消耗仍计入 Run 总预算。
- Provider 未声明上下文窗口时，`provider_unknown_context_limit=8000` 是保守输入能力默认值，不是 Evidence Token 预算本身。
- 计算结果为负数或低于 `minimum_executable_evidence_tokens=512` 时，不得发起模型调用。
- background 的 20% 是上限，不是必须占满；未使用预算回流给高优先级证据。
- 单个证据组超过剩余预算时，允许选择可定位摘录，但必须保留支持语义、上下文边界和原 EvidenceUnit 引用；不得截断成改变含义的片段。
- Token 预算不能通过减少 required 来源覆盖来满足。

### 10.3 最低覆盖超过 20

执行前必须计算 minimum required context。若 required 来源和强制 Requirement 的最低覆盖超过 20 个原始 Chunk，按以下顺序处理：

1. 按来源或 EvidenceRequirement 拆成多个 ContextPack。
2. 每个包产生带 EvidenceUnit/ResearchEvidenceUse 引用的结构化中间矩阵。
3. 最终综合调用优先使用矩阵和已验证证据摘要，不把全部原始 Chunk 再次塞入同一包。
4. 若 Run 总调用或 Token 预算仍不足，记录 `context_budget_insufficient` 决策事实。
5. 根据已有证据映射为 `insufficient_evidence` 或 `execution_failed`；不得用 background 或其他来源替代 required。

结构化中间矩阵、EvidenceMatrix 和证据摘要都是派生技术产物，不是 EvidenceUnit，也不是新的独立证据。它们必须满足：

- 每个矩阵单元保留原始 `research_evidence_use_id`，并可回到 EvidenceUnit、版本和定位。
- 最终 ClaimEvidenceLink 必须引用原始 EvidenceUnit 和本次 ResearchEvidenceUse，不能只引用矩阵或摘要。
- 矩阵内容与原始证据冲突时，以原始证据、版本和定位为准。
- 中间摘要不得提高 evidence status、support strength 或置信度。
- 模型生成的归纳不能在下一阶段被计为新的独立证据或增加证据数量。

比较、枚举和 Claim 评估默认允许多阶段 ContextPack；fact_lookup 和简单 source_interpretation 优先单包，但仍适用上述可行性检查。

## 11. 停止条件

停止条件分为成功停止、无增益停止和强制停止，三者不得混为“任意命中即成功”。

### 11.1 成功停止

成功停止必须同时满足：

```text
全部强制 EvidenceRequirement 已满足
AND 所有 required 来源已进入终态
AND ResearchPlan 要求的反证检索已执行
AND 当前 research_mode 的最小覆盖要求已满足
```

成功停止只说明检索计划完成，不自动代表 JudgmentCard 可采纳。Claim 生成、审计和 DecisionFitness 仍由下游领域规则决定。

### 11.2 无增益停止

连续 `no_gain_round_limit=2` 轮没有新增 IndependentEvidenceGroup 时停止继续自动检索。检索层只输出：

- `stop_reason=no_gain`。
- 当前 EvidenceRequirementCoverage。
- required 来源终态和 retrieval quality facts。
- 尚未满足的 Requirement 与降级影响。

Coverage 满足最低条件时，结果交给后续 Claim/Judgment/Audit 流水线；Coverage 不足时，Research Execution 依据领域命令形成相应 Run 结束结果。检索层不能直接创建 `completed_with_judgment` 或 `audit_blocked`，后者只有 JudgmentCard 已形成并完成审计后才能确定。

无增益不等于穷尽整个知识库，也不得在枚举结果中表述为“已找到全部案例”。

### 11.3 强制停止

以下任一情况触发强制停止：

- 达到模式 `max_rounds`。
- RunExecutionSpec 的时间、调用、Token 或成本预算耗尽。
- 必要 Capability 不可恢复。
- 用户取消。

强制停止不自动等于 `execution_failed`。检索层输出 stop_reason、Coverage 和质量事实；如果已经形成足够证据，可以交给判断与审计。强制 Requirement 未满足时，Research Execution 通常形成 `insufficient_evidence`；只有执行能力使计划无法继续且没有足够合法证据时才形成 `execution_failed`；用户取消由执行层映射为 `cancelled_by_user`。检索策略本身不越权决定审计 Outcome。

## 12. 失败、降级与领域映射

本文不新增平行状态体系。策略事实必须映射到冻结领域对象：

| 情况 | 领域记录或结果 | 说明 |
| --- | --- | --- |
| SourceResolution 阶段来源未找到、歧义或没有可用版本 | `SourceResolution.resolution_status=not_found / ambiguous / unavailable` | 不启动该来源的 RetrievalRun |
| Run 已绑定的 KnowledgeItemVersion 在执行时失效 | `RetrievalRun.status=completed`、`retrieval_outcome=source_unavailable` | 来源内容版本不可继续使用 |
| 当前通道所需 IndexGeneration 缺失或失效 | `RetrievalRun.status=failed`、`retrieval_outcome=failed`、`failure_category=index_unavailable` | 只影响该通道；其他可用通道继续执行 |
| 通道正常执行并形成合法候选 | `RetrievalRun.status=completed`、`retrieval_outcome=completed_with_candidates` | 候选仍需有效性、去重和融合 |
| 通道正常执行但没有合法候选 | `RetrievalRun.status=completed`、`retrieval_outcome=no_evidence` | no_evidence 不是反证 |
| 通道自身执行失败 | `RetrievalRun.status=failed`、`retrieval_outcome=failed` | 不得改写成 source_unavailable |
| required 来源完成检索但无证据 | 来源级终态报告；通常 `ResearchRunOutcome.insufficient_evidence` | 不得由其他来源代答 |
| 强制 Coverage 不足 | `ResearchRunOutcome.outcome_type=insufficient_evidence` | 保留已完成证据与 Trace |
| 审计阻断 | `ResearchRunOutcome.outcome_type=audit_blocked` | 必须引用被阻断 JudgmentCard 版本 |
| ResearchPlan 所需的全部必要通道均不可用且无合法复用证据 | `ResearchRunOutcome.outcome_type=execution_failed` | 必要能力不可恢复；单个索引通道失败不满足该条件 |
| 上下文预算不足 | insufficient_evidence 或 execution_failed | 由已有合法证据是否足够决定 |
| 证据相互冲突 | Claim 的 mixed/contradicted、uncertainty 和 Audit | 冲突不是检索失败 |
| reranker 不可用但 RRF 可用 | ResearchTrace 降级事实 | 可继续，但记录 quality impact |
| 用户取消 | `ResearchRunOutcome.outcome_type=cancelled_by_user` | 不伪装成 ResearchDisposition |

每个 RetrievalRun 必须记录 requested、available、missing capability，以及本通道实际 outcome。fallback 不得覆盖原失败事实。

## 13. EvidenceUnit 复用与零 RetrievalRun

只有同时满足以下条件才允许复用 EvidenceUnit：

- EvidenceUnit 当前 `validity_status=valid`；`needs_review` 或 `invalid` 不得走无条件复用路径。
- 原 KnowledgeItemVersion 仍然可用且内容身份不变。
- 当前 KnowledgeScope 允许该来源，且来源不是 excluded。
- canonical location 仍可验证。
- content hash 仍匹配。
- 当前 Attempt 重新执行有效性校验。
- 当前 ResearchQuestion、research mode、EvidenceRequirement、KnowledgeScope 和适用审计政策允许该证据参与本次研究。

复用规则：

- 不复制内容相同的 EvidenceUnit。
- 新 ResearchRun/Attempt 创建新的 `ResearchEvidenceUse`，`use_type=reused`，并记录当前 `validity_checked_at` 与结果。
- EvidenceUnit 原有产生关系保持不变；本次使用关系与原始产生关系分开。
- 复用发生时可以尚未存在 Claim。后续形成 Claim 时，必须重新判断 EvidenceUnit 是否支持该具体 Claim，创建新的 ClaimEvidenceLink 并接受审计。
- EvidenceUnit 可复用不代表它必然支持新的 Claim，也不提高其证据状态或支持强度。
- 模型记忆、历史回答文本、JudgmentCard 摘要和 KnowledgeAsset 不能伪装为 EvidenceUnit。

零 RetrievalRun 的 Attempt 必须在 ResearchTrace 中说明：

- 为什么本次不检索。
- 复用了哪些 EvidenceUnit 和 ResearchEvidenceUse。
- 如何校验版本、Scope、定位、Hash 和 validity。
- 哪些 EvidenceRequirement 已满足或仍未满足。
- 复用路径对质量和适用范围的影响。

两个主要检索通道都不可用时，只有存在满足上述条件的合法复用证据才可以走零 RetrievalRun 路径。

## 14. Trace 决策事实

本文不重复定义 TraceEvent Schema，但要求 ResearchTrace 至少能够还原以下策略事实：

1. `retrieval_policy_version`、`parameter_set_version`、`source_admission_policy_version` 和 `candidate_admission_policy_version`。
2. original question、resolved anchor spans、evidence query 和 transformation version。
3. SourceRoutingView version、生成时间和输入版本。
4. 每个来源的 selection type、准入结果与理由、路由排名、`exact_title_query_match`、各通道 rank 和折叠信号；显式路径另记录 `resolved_source_anchor_match`。
5. 每轮 QueryVariant、来源集合、目标 Requirement 和生成原因。
6. 各通道 requested/available/missing capability、实现版本和 fallback。
7. `evidence_normalization_version`、`evidence_similarity_metric`、`evidence_grouping_policy_version`，每个证据组的 candidate admission 结果与理由，以及每个来源去重前候选数、去重后 IndependentEvidenceGroup 数和保留数。
8. required 来源及 EvidenceRequirementCoverage 的逐轮变化。
9. 是否使用 reranker、作用范围和降级原因。
10. 每个 ContextPack 的证据、顺序、Token/Chunk 使用、构建前剩余预算、预留量、实际结算量、估算差额和保留理由。
11. 每个被丢弃候选的主要原因，例如 excluded、invalid、duplicate、quota、token_budget、lower_priority。
12. 命中的成功、无增益或强制停止条件。
13. fallback path、missing capability 和 quality impact。
14. 最终领域映射所依据的策略事实。

Trace 默认保存引用、Hash、版本、定位和必要摘要；完整私有原文是否保存受技术架构中的出站和数据最小化政策约束。

## 15. 确定性与可比较性

在原始问题、SourceResolution、KnowledgeScope/Plan/RunExecutionSpec 版本、Knowledge Catalog、IndexGeneration、Capability 版本、策略版本、参数集和候选集合相同的条件下，必须保证：

- 来源排名采用固定 tie-break。
- 来源内证据组排名采用固定 tie-break。
- 跨来源覆盖槽位与全局排序稳定。
- ContextPack 中证据顺序稳定。
- `evidence_normalization_version`、`evidence_similarity_metric`、`evidence_grouping_policy_version` 和 Hash 规范化版本稳定。
- 相同基础设施重投不新增业务 Attempt、EvidenceUnit 或 ResearchEvidenceUse。

最终自然语言可以不同，但核心来源、EvidenceRequirementCoverage 和实际使用的 EvidenceUnit 发生变化时，Trace 必须能指出变化来自输入、索引、Capability、策略、参数或模型版本中的哪一项。

## 16. 验收场景

本策略至少通过以下文档级闭合检查；具体 fixture 和自动化指标由 `A0-EVAL-001` 冻结。

### 16.1 短资料公平

给定《鬼谷子》15 个 Chunk、《理想国》399 个 Chunk，问题显式要求《鬼谷子》或比较两者时：

- 两本资料不得直接进入唯一全局 Chunk Top-K 竞争。
- 《鬼谷子》满足 full_scan_eligible 时，全部 Chunk 参与本地候选排序，但仍受 ContextPack 预算约束。
- 比较模式分别检索并报告两边证据，不允许《理想国》用更多 Chunk 填满上下文。

### 16.2 required 最低覆盖超过 20

当 required 来源最低合法覆盖超过单包 20 Chunk：

- 必须分包和形成结构化矩阵。
- 不得静默删除 required 来源。
- 总预算不足时形成明确决策事实并映射 Outcome。

### 16.3 超长证据组

当单个证据组超过剩余 Token：

- 只允许产生仍可定位且语义完整的摘录。
- 不允许截断到改变支持含义。
- 无法形成合法摘录时不得进入 ContextPack。

### 16.4 background 上限

background 最多使用单包 Evidence Token 的 20%，没有最低配额；未使用预算必须能够回流，不能为填满比例引入弱内容。

### 16.5 小 Provider 窗口

Provider 实际窗口小于默认值时，以实际能力计算；未知时使用 8000 保守能力默认值。Evidence Token 预算低于 512 时不得调用模型。

### 16.6 多轮预算耗尽

达到总预算时，检索层记录 `stop_reason=budget_exhausted`、已有 Coverage 和质量事实；Research Execution、Judgment 与 Audit 再据此形成适当 Outcome，不得由检索层统一返回“资料不足”或直接决定 audit_blocked。

### 16.7 excluded 同文污染

allowed 与 excluded 来源包含相同文本时：

- Hash 去重不能把 excluded provenance 合并到 allowed 证据链。
- excluded 内容不得进入候选、ContextPack、EvidenceUnit 产生关系或引用。
- excluded ID 仅可作为过滤和审计条件出现。

### 16.8 确定性复跑

同输入、同版本、同候选集重复执行时，来源、证据组和 ContextPack 顺序一致；若 Capability 返回概率性分数，进入稳定排序前必须固定候选集合和 tie-break，并记录实现版本。

### 16.9 R1.2 勘误评测输入

`A0-EVAL-001` 至少将以下情况纳入 fixture 规范：

1. 所有来源均未达到准入门槛时，不强行选满 max_routed_sources。
2. 来源只有一个合格证据组时，不为满足 min_source_candidate_groups 填充弱证据。
3. 向量 IndexGeneration 失效而全文通道正常时，来源仍可通过全文通道检索。
4. 五个 ContextPack 连续或并发调用不突破同一 Run 总预算。
5. required + primary + 多个 Requirement 的最低覆盖按不同证据组集合并集计算，不重复计数。
6. 古文短句在字符 3-gram 分组下的错误合并与错误拆分。
7. 显式来源与自动路由来源共同竞争剩余槽位时排序稳定，显式来源不伪造 source_rrf_score。
8. 无增益停止后，检索层不越权创建 audit_blocked 或 completed_with_judgment。

## 17. Non-Goals

本任务不做：

- 不修改现有 RAG、Streamlit、FastAPI、Redis/RQ 或入库代码。
- 不重新切块，不重算 Embedding，不重建 Chroma 或 FTS 索引。
- 不引入知识图谱、专用 reranker 模型、OpenSearch、Neo4j 或新工作流引擎。
- 不把 SourceRoutingView、IndependentEvidenceGroup、ContextPack 或 Coverage 提升为领域聚合。
- 不冻结数据库表、Pydantic 类名、HTTP Schema 或物理队列。
- 不在本文定义 Golden Case fixture 文件和具体评测阈值。
- 不允许 A0-EVAL-001 在其他文档中静默覆盖本文参数。

## 18. Validation

强制文档检查：

```powershell
git status --short
git diff --check -- docs/RAG_RETRIEVAL_STRATEGY.md docs/TASK_INDEX.md
git diff --name-only
rg -n "^(<<<<<<<|=======|>>>>>>>)" docs/RAG_RETRIEVAL_STRATEGY.md
```

术语闭合检查：

```powershell
rg -n "SourceRoutingView|QueryVariant|query_family|evidence_purpose|IndependentEvidenceGroup|EvidenceRequirementCoverage|ContextPack|ResearchEvidenceUse|retrieval_policy_version|parameter_set_version|source_admission_policy_version|candidate_admission_policy_version" docs/RAG_RETRIEVAL_STRATEGY.md
```

领域枚举映射检查：

```powershell
rg -n "completed_with_candidates|no_evidence|source_unavailable|insufficient_evidence|audit_blocked|execution_failed|cancelled_by_user" docs/RAG_RETRIEVAL_STRATEGY.md
```

人工检查：

- required 与 allowed 的执行义务不同，普通 allowed 不会触发全库逐来源检索。
- RetrievalRun 的 Attempt、QueryVariant、来源 Binding、通道和 IndexGeneration 粒度唯一。
- SourceResolution 阶段不可用与 Run 执行时来源失效映射不同。
- Minimum Slice 在没有用户预算时仍具有系统安全预算。
- 多 ContextPack 读取、预留和结算同一份 Run 剩余预算，并发调用不能重复占用。
- 中间矩阵不能成为二手 EvidenceUnit，最终 ClaimEvidenceLink 能回到原始 ResearchEvidenceUse。
- 证据规范化、相似度和分组策略均有版本并进入 RunExecutionSpec 与 Trace。
- `max_routed_sources` 与 `min_source_candidate_groups` 都是上限/保留规则，不会强行填充低相关来源或证据。
- IndexGeneration 故障只影响依赖它的通道，不自动把 KnowledgeItemVersion 标记为不可用。
- 检索停止只输出 stop_reason、Coverage 和质量事实，最终 Outcome 仍由执行、判断和审计领域产生。
- 本次勘误只修改 `docs/RAG_RETRIEVAL_STRATEGY.md`；首次交付允许同时机械更新 `docs/TASK_INDEX.md` 的任务状态。除此之外不得出现文件变化。

## 19. 完成条件

### 19.1 首次交付完成

`A0-DOC-006` 首次交付只有同时满足以下条件才可标记 completed：

1. 本文存在且通过 `git diff --check`。
2. 来源路由、五种模式、证据分组、双预算、停止、领域映射和复用路径闭合。
3. 默认参数集中定义且版本明确。
4. 《鬼谷子》与《理想国》的短资料公平问题不再依赖全局 Chunk Top-K。
5. 未修改代码、索引、数据库、测试或运行态数据。
6. `docs/TASK_INDEX.md` 只机械更新 A0-DOC-006 状态，不改变任务语义。

### 19.2 后续勘误完成

R1.1、R1.2 及后续勘误必须满足：

1. 只修改 `docs/RAG_RETRIEVAL_STRATEGY.md`。
2. 根据变化范围升级修订标识、`retrieval_policy_version` 或 `parameter_set_version`。
3. 不重复修改已经 completed 的 A0-DOC-006 任务状态，也不把它改回 pending。
4. 勘误如果改变策略不变量，必须重新审查 A0-GATE；若 Gate 尚未执行，则纳入首次 Gate 审查。
5. 通过第 18 章 Validation，且不修改代码、索引、数据库、测试或运行态数据。

本文完成后，下一项阶段0工作为 `A0-EVAL-001`。评测结果如要求改变策略或参数，必须按第 1.1 节执行版本升级和 Gate 复审。
