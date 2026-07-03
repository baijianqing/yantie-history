# 盐铁会议历史复原：API 契约设计

状态：阶段0设计文档
任务标识：`YT-A0-004`
文档性质：本文件定义目标 REST 契约和知乎外部接口边界，不表示接口已经实现。

## 1. 任务契约

- 任务 ID：`YT-A0-004`
- 价值：为可试玩 Web 项目提供稳定、轻量、只读优先的接口设计，并把知乎 REST 接入限制在“当代回声”能力内。
- 依赖：`YT-A0-001`、`YT-A0-002`、`YT-A0-003`。
- 允许修改范围：本设计文档。
- 禁止修改范围：业务代码、公共 Schema、迁移、根配置、`AGENTS.md`、运行态 `library/` 数据、向量库和原始大部头史料。
- 输入：`evidence_pack` 数据契约、知乎开放平台接口信息、Web 体验需求。
- 输出：内部 REST API、外部知乎适配器契约、错误语义、降级策略和验收标准。
- 接口：下游前端只依赖本文列出的路由；外部知乎调用必须经过单独 adapter，不得写入历史 EvidenceUnit。
- 验收标准：核心体验离线可用；知乎失败不影响历史证据；所有返回体可 Schema 校验。
- 测试命令：`git diff --check -- docs/YANTIE_API_CONTRACT.md`。
- 回滚方式：删除或回退本文件。
- 文档更新：本文件即该任务的交付物。

## 2. 服务边界

核心 API 读取随作品交付的 `evidence_pack.json`。它不访问 Chroma、Embedding、OCR、运行态 `library/` 数据或原始史料。

外部知乎 API 只用于：

- 当代回声搜索。
- 用户追问的现代解释。
- 展示公共讨论链接。

外部知乎 API 不得用于：

- 创建或修改 `EvidenceUnit`。
- 支撑历史事实 Claim。
- 覆盖人工策展证据。

## 3. 通用响应

成功响应：

```json
{
  "data": {},
  "meta": {
    "pack_id": "yantie_meeting_v1",
    "schema_version": "yantie_evidence_pack_v1",
    "served_at": "2026-07-03T00:00:00Z"
  }
}
```

错误响应：

```json
{
  "error": {
    "code": "archive_insufficient",
    "message": "No verified evidence matches this query.",
    "details": {},
    "retryable": false
  }
}
```

错误码：

| code | HTTP | 说明 |
| --- | ---: | --- |
| `validation_error` | 422 | 请求参数不符合契约 |
| `not_found` | 404 | 对象不存在 |
| `archive_insufficient` | 200/404 | 档案不足；查询型接口可用 200 返回空结果和提示 |
| `external_unavailable` | 503 | 知乎或外部接口不可用 |
| `external_auth_missing` | 401 | 未配置或未提供外部接口密钥 |
| `external_rate_limited` | 429 | 外部接口限流 |

## 4. 核心只读 API

### `GET /api/yantie/manifest`

返回包身份、版本、来源统计、核验状态和功能开关。

### `GET /api/yantie/theme`

返回 `ThemeSpec`、核心问题、价值轴、输出契约。

### `GET /api/yantie/sources`

查询来源列表。支持筛选：

- `source_type`
- `authority_level`
- `delivery_policy`
- `human_verified`

### `GET /api/yantie/actors`

返回角色卡列表，可带 `include=evidence_summary`。

### `GET /api/yantie/events`

返回时间线事件。支持：

- `event_type`
- `actor_id`
- `topic_id`

### `GET /api/yantie/map-layers`

返回地图图层和 feature。MVP 允许简化坐标。

### `GET /api/yantie/topics`

返回辩题列表，例如盐铁、均输、平准、酒榷、边防财政、民生与德治。

### `GET /api/yantie/evidence/{evidence_id}`

返回单条 EvidenceUnit。若来源不允许摘录，`excerpt_original=null`，但保留定位和转述。

### `GET /api/yantie/evidence/search`

参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `q` | string | 否 | 关键词，空则按筛选返回 |
| `topic_id` | string | 否 | 辩题 |
| `actor_id` | string | 否 | 角色 |
| `source_id` | string | 否 | 来源 |
| `claim_type` | string | 否 | Claim 类型 |
| `limit` | integer | 否 | 默认 20，最大 50 |

行为：

- 只搜索 `review_status=verified` 的 EvidenceUnit。
- 先使用 `lexical_index`，缺失时线性过滤。
- 无命中返回 `data.items=[]` 和 `archive_insufficient` 提示，不调用模型补答。

### `GET /api/yantie/claims`

返回 Claim 列表。支持 `topic_id`、`stance`、`display_zone` 筛选。

### `GET /api/yantie/relations`

返回 Evidence Graph 边。支持 `from_id`、`to_id`、`relation_type`、`strength`。

### `GET /api/yantie/curated-paths/{path_id}`

返回策展路径，例如：

- `path_opening_context`
- `path_salt_iron_policy`
- `path_confucian_legalist_conflict`
- `path_power_network`
- `path_afterlife`

## 5. 判断卡 API

### `POST /api/yantie/judgment-cards`

创建用户本地判断卡，不写入历史证据包。

请求：

```json
{
  "selected_claim_ids": ["claim_..."],
  "selected_evidence_ids": ["ev:..."],
  "personal_reflection": "string",
  "disposition": "continue_research"
}
```

`disposition` 取值：

- `continue_research`
- `historical_understanding_complete`
- `no_action`
- `modern_analogy_with_caution`

规则：

- `selected_claim_ids` 中所有非反思类 Claim 必须能回链证据。
- 用户反思必须单独保存，不得成为历史事实。
- 若选择当代类比，响应必须附带 caution 文案：历史材料不能直接推出当代政策结论。

## 6. 知乎 REST Adapter

知乎开放平台当前可用 REST 能力：

| 能力 | 方法与 URL | 用途 |
| --- | --- | --- |
| 知乎搜索 | `GET https://developer.zhihu.com/api/v1/content/zhihu_search` | 站内当代讨论 |
| 全网搜索 | `GET https://developer.zhihu.com/api/v1/content/global_search` | 外部参考 |
| 热榜 | `GET https://developer.zhihu.com/api/v1/content/hot_list` | 当前公共议题 |
| 直答 | `POST https://developer.zhihu.com/v1/chat/completions` | 现代解释或追问 |

鉴权：

- `Authorization: Bearer <your_access_secret>`
- `X-Request-Timestamp: <unix_seconds>`
- `Content-Type: application/json`

内部代理路由：

| 路由 | 行为 |
| --- | --- |
| `GET /api/yantie/external/zhihu/search?q=&count=` | 调用 `zhihu_search`，结果标记为 `external_echo` |
| `GET /api/yantie/external/global/search?q=&count=&filter=` | 调用 `global_search`，结果标记为 `external_echo` |
| `GET /api/yantie/external/zhihu/hot-list?limit=` | 调用 `hot_list` |
| `POST /api/yantie/external/zhihu/zhida` | 调用 `zhida` 或兼容 chat completions，只返回现代解释 |

安全规则：

- Access Secret 只能由服务端环境提供，前端不得接触。
- 所有外部响应必须带 `source_boundary=external_echo`。
- 外部结果不得出现在 `Claim.evidence_ids` 或 `EvidenceUnit`。
- 外部失败只影响当代回声区。

## 7. MCP 与 Skill 选择结论

本作品的主要交付是可试玩 Web 项目，不以 MCP 或 Skill 为主形态。

- MCP 适合 Agent 或开发者工作流，适合作为后续“让其他 Agent 调用盐铁证据查询”的扩展。
- Skill 适合封装给模型使用，但无法承担地图、席位、关系网和判断卡体验。
- REST + 静态证据包最符合 AI Works 试玩、低交付重量和无 RAG 运行依赖的约束。

## 8. API 验收场景

- 离线读取 `manifest/theme/actors/topics/evidence/claims/relations/map-layers` 均成功。
- 搜索“桑弘羊 财政”返回桑弘羊相关证据，不调用外部模型。
- 搜索无证据问题返回档案不足提示。
- 未配置知乎 Access Secret 时，当代回声接口返回 `external_auth_missing`，核心接口不受影响。
- 配置知乎 Access Secret 后，当代回声返回结果并明确标注 `external_echo`。
