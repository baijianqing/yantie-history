# YT-A1-ZHIHU-001 API 勘误：知乎外部回声 Adapter

状态：A1 最小实现勘误
任务 ID：`YT-A1-ZHIHU-001`
更新日期：2026-07-13

## 1. 本轮实现范围

本轮只实现“当代回声”薄适配层，不改变盐铁会议的史实证据包。

新增内部代理路由：

| 路由 | 用途 | 历史边界 |
|---|---|---|
| `GET /api/yantie/external/zhihu/search?q=&count=` | 查询知乎站内当代讨论 | `external_echo` |
| `GET /api/yantie/external/global/search?q=&count=&filter=` | 查询全网当代讨论 | `external_echo` |
| `GET /api/yantie/external/zhihu/hot-list?limit=` | 查询外部热榜 | `external_echo` |
| `POST /api/yantie/external/zhihu/zhida` | 获取现代解释型回答 | `external_echo` |

所有成功响应都必须包含：

```json
{
  "source_boundary": "external_echo",
  "can_support_claims": false,
  "writes_to_evidence_pack": false
}
```

## 2. 配置与降级

服务端只从环境变量读取 Access Secret：

- `YANTIE_ZHIHU_ACCESS_SECRET`
- `ZHIHU_ACCESS_SECRET`

未配置密钥时：

- `/api/yantie/manifest` 中 `features.external_echo_enabled=false`。
- 外部回声接口返回 `external_auth_missing`。
- 核心历史体验、证据搜索、Claim、判断卡接口不受影响。

## 3. 不变边界

知乎或其他外部结果不得：

- 写入 `EvidenceUnit`。
- 支撑任何历史 `Claim`。
- 自动写入退朝案牍。
- 覆盖人工策展证据。
- 在 UI 中伪装成会议现场史料。

外部结果只能作为退朝后的延伸讨论入口，供用户主动查看。

## 4. 错误映射

| 情况 | HTTP | code | retryable |
|---|---:|---|---|
| 未配置或鉴权失败 | 401 | `external_auth_missing` | false |
| 外部限流 | 429 | `external_rate_limited` | true |
| 外部服务不可用、网络异常、JSON 非法 | 503 | `external_unavailable` | true |

## 5. 验收

本轮新增 mock API 测试：

```bash
python -m pytest test -k yantie_zhihu
```

验收重点：

- 未配置密钥时核心 manifest 仍可读取。
- mock 搜索结果始终标记为 `external_echo`。
- 外部结果不改变 Evidence Pack 中的 Claim 或 EvidenceUnit 数量。
- 外部限流映射为可重试错误。

## 6. 回滚

若需要回滚本轮实现：

- 删除 `metaos/yantie/zhihu_adapter.py`。
- 回退 `metaos/yantie/api.py` 中外部回声 router 挂载和 manifest 开关。
- 删除 `test/test_yantie_zhihu_adapter.py`。
- 删除本勘误文档。
