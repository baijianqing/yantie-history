# 盐铁会议历史复原：Evidence Pack Schema 设计

状态：阶段0设计文档
任务标识：`YT-A0-003`
文档性质：本文件定义目标数据契约，不表示对应 Pydantic、数据库或 API 已实现。

## 1. 任务契约

- 任务 ID：`YT-A0-003`
- 价值：用一个可校验、可审计、可直接交付的 `evidence_pack.json` 替代运行时 RAG、向量库和原始大部头史料。
- 依赖：`YT-A0-001`、`YT-A0-002`。
- 允许修改范围：本设计文档。
- 禁止修改范围：业务代码、公共 Schema、迁移、根配置、`AGENTS.md`、运行态 `library/` 数据、向量库和原始大部头史料。
- 输入：史料层级、产品体验、MetaOS ThemeSpec/证据/审计原则。
- 输出：`evidence_pack` 结构、对象字段、枚举、校验规则和切分策略。
- 接口：前端和只读 API 以本文档为数据契约；后续 Pydantic Schema 必须向本文收敛。
- 验收标准：每条 Claim 能绑定证据；每条证据能回链来源；每条关系有证据强度；包内不包含向量、全文大部头或未授权现代文本。
- 测试命令：`git diff --check -- docs/YANTIE_EVIDENCE_PACK_SCHEMA.md`。
- 回滚方式：删除或回退本文件。
- 文档更新：本文件即该任务的交付物。

## 2. 顶层结构

```json
{
  "schema_version": "yantie_evidence_pack_v1",
  "pack_id": "yantie_meeting_v1",
  "generated_at": "2026-07-03T00:00:00Z",
  "source_manifest": [],
  "theme_spec": {},
  "sources": [],
  "actors": [],
  "events": [],
  "topics": [],
  "evidence_units": [],
  "claims": [],
  "relations": [],
  "map_layers": [],
  "curated_paths": [],
  "lexical_index": {}
}
```

运行时只读取该包和用户本地判断卡状态，不需要 RAG、Chroma、Embedding、OCR 中间文件或原始全书文本。

## 3. ThemeSpec

`ThemeSpec` 在运行时生成或读取，不为盐铁会议增加 Python 分支。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `theme_id` | string | 是 | `theme_yantie_meeting` |
| `title` | string | 是 | 盐铁会议历史复原 |
| `historical_period` | string | 是 | 西汉昭帝始元六年 |
| `core_question` | string | 是 | 盐铁官营是否应罢，背后冲突是什么 |
| `experience_mode` | string | 是 | `meeting_reconstruction` |
| `evidence_requirements` | array | 是 | 事实、背景、反证、后世评价等要求 |
| `value_axes` | array | 是 | 例如 `fiscal_capacity_vs_livelihood`、`legalist_order_vs_confucian_morality` |
| `output_contract` | object | 是 | 判断卡必须分栏：事实、推断、争议、反思、行动/不行动 |

## 4. Source

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `source_id` | string | 是 | 稳定 ID，例如 `src_yantielun_wikisource` |
| `title` | string | 是 | 来源标题 |
| `source_type` | enum | 是 | `primary_text`、`chronicle`、`institutional_history`、`biography`、`later_commentary`、`modern_research`、`external_echo` |
| `authority_level` | enum | 是 | `core`、`background`、`comparison`、`echo` |
| `license_status` | enum | 是 | `public_domain_text`、`licensed_excerpt`、`link_only`、`blocked`、`unknown` |
| `canonical_url` | string/null | 否 | 可公开访问链接 |
| `citation_style` | string | 是 | 例如“《盐铁论·本议》” |
| `delivery_policy` | enum | 是 | `excerpt_allowed`、`metadata_only`、`link_only`、`exclude` |
| `human_verified` | boolean | 是 | 是否已人工核验 |

`delivery_policy != excerpt_allowed` 的来源不得提供原文长摘。

## 5. EvidenceUnit

稳定 ID 格式：

```text
ev:<source_id>:<canonical_location>:<argument_or_event_slug>:<hash8>
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `evidence_id` | string | 是 | 稳定证据 ID |
| `source_id` | string | 是 | 必须存在于 `sources` |
| `canonical_location` | string | 是 | 篇章、卷、年号、段落或页码 |
| `excerpt_original` | string/null | 否 | 允许交付的原文短摘 |
| `paraphrase_zh` | string | 是 | 自写白话转述 |
| `evidence_kind` | enum | 是 | `event_record`、`policy_record`、`speech_argument`、`biographical_context`、`later_evaluation` |
| `speaker_actor_id` | string/null | 否 | 发言者，如 `actor_sang_hongyang` |
| `topic_ids` | array | 是 | 关联辩题 |
| `value_tags` | array | 是 | 价值立场标签 |
| `certainty` | enum | 是 | `direct_text`、`high_confidence_context`、`contested`、`needs_review` |
| `copyright_note` | string | 是 | 摘录依据或限制 |
| `review_status` | enum | 是 | `candidate`、`verified`、`blocked` |

只有 `review_status=verified` 且来源允许交付的 EvidenceUnit 能进入主路径。

## 6. Claim

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `claim_id` | string | 是 | 稳定 ID |
| `claim_type` | enum | 是 | `original_fact`、`curatorial_inference`、`contested_view`、`personal_reflection_prompt` |
| `statement` | string | 是 | 用户可读表述 |
| `stance` | enum | 是 | `supports_state_monopoly`、`opposes_state_monopoly`、`explains_context`、`evaluates_afterlife`、`neutral` |
| `evidence_ids` | array | 是 | 非反思类 Claim 至少一条 |
| `counterevidence_ids` | array | 否 | 反证或限制 |
| `reasoning_note` | string/null | 否 | 推断型 Claim 必填 |
| `display_zone` | enum | 是 | `meeting`、`map`、`power_network`、`later_echo`、`judgment_card` |

校验规则：

- `claim_type=original_fact` 必须至少绑定一条 `direct_text` EvidenceUnit。
- `claim_type=curatorial_inference` 必须有 `reasoning_note`，并至少绑定两类证据或说明证据不足。
- `claim_type=personal_reflection_prompt` 不得伪装为历史事实。
- 外部知乎结果不得出现在 `evidence_ids`，只能通过 `external_reference_ids` 出现在当代回声区。

## 7. Actor、Event、Relation

`Actor` 表达角色，不表达“历史人物聊天人格”。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `actor_id` | string | 是 | 稳定 ID |
| `name` | string | 是 | 名称 |
| `role_title` | string | 是 | 身份 |
| `meeting_position` | enum | 是 | `state_policy_defender`、`literati_opposition`、`regent_power`、`imperial_center`、`mediator`、`background_actor` |
| `stance_summary` | string | 是 | 立场摘要 |
| `interest_constraints` | array | 是 | 财政、政治、道德、身份约束 |
| `evidence_ids` | array | 是 | 支撑角色设定的证据 |

`Event` 用于时间线和地图：

- `event_id`
- `title`
- `date_label`
- `event_type`
- `summary`
- `location_id`
- `actor_ids`
- `evidence_ids`

`Relation` 用于 Evidence Graph：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `relation_id` | string | 是 | 稳定 ID |
| `from_id` | string | 是 | Actor、Claim、Event、Topic 或 EvidenceUnit |
| `to_id` | string | 是 | Actor、Claim、Event、Topic 或 EvidenceUnit |
| `relation_type` | enum | 是 | `supports`、`opposes`、`contextualizes`、`caused_by`、`actor_interest`、`value_conflict`、`power_constraint` |
| `evidence_ids` | array | 是 | 支撑关系的证据 |
| `strength` | enum | 是 | `explicit_source`、`contextual_inference`、`interpretive_hypothesis` |
| `note` | string | 否 | 解释 |

## 8. MapLayer

地图图层由数据驱动：

- `layer_id`
- `title`
- `layer_type`: `region`、`route`、`resource_point`、`military_frontier`、`capital`、`policy_pressure`
- `time_scope`
- `features`
- `evidence_ids`
- `display_style`

MVP 可以使用简化坐标或相对坐标，不要求精确 GIS；但每个历史含义必须能打开证据。

## 9. 切分策略

- 《盐铁论》：先按篇名，再按发言方、论点、反驳、价值词切分。
- 编年体：按年号和事件切分，保留前后事件关系。
- 政书：按制度主题切分，例如盐铁、均输、平准、酒榷、算缗、边费。
- 纪传体：按人物、政治关系、职务变迁、事件牵连切分。
- 后世评价：按评价主体和评价对象切分，不混入核心事实层。

切分产物不是通用 Chunk，而是可审计 EvidenceUnit。EvidenceUnit 可以包含 `adjacent_context_note`，但不携带整段上下文全文。

## 10. 轻量检索索引

`lexical_index` 是交付包内可选派生结构：

```json
{
  "tokenization": "char_bigram_zh_v1",
  "entries": {
    "盐铁": ["ev:..."],
    "桑弘羊": ["ev:..."]
  }
}
```

它只服务前端快速过滤，不是向量索引，也不是 RAG 语义召回。生成规则必须可重建；索引缺失时，前端仍可通过线性过滤运行。
