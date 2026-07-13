# 盐铁会议 A2 材料补强门禁

状态：A2 材料门禁文档  
任务 ID：`YT-A2-000`  
文档性质：材料缺口、交付边界和后续任务契约；已记录 A2 材料入包进度，后续任务仍需按任务契约控制 evidence pack、UI 与运行代码边界。

## 1. 门禁目标

A1 已完成可试玩闭环。A2 的第一步不是继续增加页面功能，而是先冻结材料缺口和进入边界：哪些材料可以进入证据包，哪些只能作为退朝后的深度探索，哪些只能作为思想透镜或后世评说。

当前材料状态：

- evidence pack 当前有 34 个 source、154 条 EvidenceUnit、13 条 Claim。
- 《盐铁论》相关 EvidenceUnit 约 70 条。
- `YT-A2-MAT-001` 执行后，《资治通鉴》卷023 已补入 1 个 chronicle source 和 4 条会议纪事 EvidenceUnit，用于校验会议召问、贤良文学请罢、桑弘羊答辩和七月罢榷酤结果。
- `YT-A2-MAT-002` 执行后，《汉书·食货志》已扩至 9 条 EvidenceUnit，《史记·平准书》已扩至 11 条 EvidenceUnit，首轮覆盖盐铁官营、均输、平准、算缗、告缗、商贾财富、官营弊端和边费逻辑。
- `YT-A2-MAT-003` 执行后，《四库全书总目提要》已扩至 8 条 EvidenceUnit，首轮补入桓宽作者信息、六十篇编纂、问答结构、杂论列名、儒家目录归类和千顷堂食货类归属争议。
- `YT-A2-MAT-004` 执行后，新增 `docs/YANTIE_A2_MODERN_RESEARCH_INDEX.md`，形成 7 张现代研究书目卡；现代研究只作退朝后延伸阅读和研究史定位，暂不进入 evidence pack。
- `YT-A2-MAT-005` 执行后，新增 `docs/YANTIE_A2_HUANG_LAO_MATERIAL_PLAN.md`，将汉初黄老与《黄帝四经》列为思想史补强第一优先级；本轮只冻结候选透镜和进入边界，不入 evidence pack。
- `YT-A2-MAT-005A` 执行后，新增 `docs/YANTIE_A2_HUANGDI_SIJING_VERIFICATION.md`，核验 5 个来源层和 7 条候选短摘；本轮仍不入 evidence pack。
- `YT-A2-MAT-005B` 执行后，`src_huangdi_sijing` 和 6 条《黄帝四经》黄老思想透镜已进入 evidence pack；它们只作为 `philosophy_lens`，不支撑 `original_fact` Claim。
- `YT-A2-MAT-005C` 执行后，退朝后思想透镜已新增黄老分组，用户可以从黄老组查看 6 条《黄帝四经》思想透镜材料。
- `YT-A2-MAT-006` 执行后，新增 `docs/YANTIE_A2_CLASSICS_CONTEXT_PLAN.md`，将董仲舒、经学语境和武帝文治正当性列为思想史第二优先级；本轮只冻结候选来源、6 个经学透镜和进入边界，不入 evidence pack。
- `YT-A2-MAT-006A` 执行后，新增 `docs/YANTIE_A2_HANSHU_CLASSICS_VERIFICATION.md`，核验《汉书·董仲舒传》《汉书·武帝纪》《汉书·儒林传》12 条经学语境候选短摘；本轮仍不入 evidence pack。
- `YT-A2-MAT-006B` 执行后，新增 `docs/YANTIE_A2_CHUNQIU_FANLU_VERIFICATION.md`，核验《春秋繁露》的文本性质、版本风险和 12 条候选短摘；本轮仍不入 evidence pack。
- `YT-A2-MAT-006C` 执行后，新增 `src_hanshu_dong_zhongshu`、`src_hanshu_wudi`、`src_hanshu_rulin`、`src_chunqiu_fanlu` 4 个 source 和 6 条经学语境 EvidenceUnit；它们只作为 `philosophy_lens`/`classics_context`，不支撑 `original_fact` Claim。
- `YT-A2-MAT-006D` 执行后，退朝后思想透镜已新增 `classics_context` 分组，用户可以从经学语境分组查看 6 条经学透镜材料。
- `YT-A2-MAT-006E` 执行后，退朝后深度探索已新增“材料导览”入口，按会议纪事、制度背景、文本与后世评价、黄老思想、经学语境和现代研究六类说明材料边界。
- `YT-A2-MAT-006F` 执行后，Playwright 静态验收已覆盖材料导览入口、`post_court_only` 边界和材料卡片可见性，desktop、mobile、reduced-motion 三种视口均纳入检查。
- `YT-A2-MAT-006G` 执行后，本材料门禁文档与任务拆分文档已同步到 A2 当前状态。
- `YT-A2-MAT-007` 执行后，孔仅、东郭咸阳、卜式已作为 `background_actor` 进入双份 evidence pack，并关联现有 verified 制度证据、盐铁官营形成事件和 lexical index。
- `YT-A2-MAT-008` 执行后，《汉书·武帝纪》“初榷酒酤”和《通典·食货十一·榷酤》制度解释已进入双份 evidence pack，用作酒榷制度背景，不作为会议现场发言。
- `YT-A2-MAT-009` 执行后，贤良文学身份材料已归并到 `actor_literati`，并补充 `贤良`、`文学`、`郡国文学`、`文学高第` 等 lexical index 入口；本轮不新增 EvidenceUnit 或 Claim。
- `YT-A2-MAT-010` 执行后，本材料门禁文档的 source、EvidenceUnit、Claim 计数由自动化测试和真实 evidence pack 对齐，后续入包必须同步更新计数行。
- `YT-A2-MAT-011` 执行后，本材料门禁文档补齐 `YT-A2-MAT-005C` 黄老透镜分组完成状态；本轮不修改 evidence pack 或 UI。

A2 材料默认不进入首次主体验。它们只进入退朝后深度探索，除非后续单独验收为主线关键证据。

## 2. 五类材料缺口

| 材料层 | 当前状态 | 主要缺口 | A2 补强目标 | 默认入口 | 可否支撑历史 Claim |
|---|---|---|---|---|---|
| 会议纪事 | `YT-A2-MAT-001` 已补《资治通鉴》卷023 4 条纪事 EvidenceUnit | 仍需在后续 UI 中决定是否只作退朝后探索，或验收为主线关键证据 | 已覆盖始元六年二月召问、贤良文学请罢、桑弘羊答辩、秋七月罢榷酤 | 退朝后深度探索；可候选为主线关键证据 | 可，已形成可定位 EvidenceUnit |
| 制度背景 | `YT-A2-MAT-002` 执行后，《汉书·食货志》已扩至 9 条 EvidenceUnit，《史记·平准书》已扩至 11 条 EvidenceUnit；`YT-A2-MAT-007` 已完成孔仅、东郭咸阳、卜式首轮 Actor 化；`YT-A2-MAT-008` 已补酒榷初设和制度含义 | 如需进入主线轻提示，需另开任务验收；更细财政操作可留作后续延伸 | 首轮已覆盖国家财政制度、商贾征收、山海资源、官营弊端、均输和平准、酒榷机制，并可按制度人物回看盐铁官营形成与批评 | 退朝后深度探索；少量可作为场景轻提示 | 可，需标明制度背景而非会议现场 |
| 文本与人物 | `YT-A2-MAT-003` 执行后，《四库全书总目提要》已扩至 8 条文本史 EvidenceUnit；孔仅、东郭咸阳、卜式已进入 actors；贤良文学身份材料已归并到 `actor_literati` | 如需补具体姓名、地域或社会构成，需另开候选材料核验任务 | 首轮已区分会议事实、文本编纂、制度人物背景、贤良文学参与来源和后世目录学评价 | 退朝后深度探索 | 部分可；文本性质多为策展解释 |
| 思想史 | 已有哲学透镜；`YT-A2-MAT-005B` 已补入 6 条《黄帝四经》黄老透镜；`YT-A2-MAT-005C` 已完成退朝后黄老分组；`YT-A2-MAT-006C` 已补入 6 条《汉书》/《春秋繁露》经学语境透镜；`YT-A2-MAT-006D` 至 `YT-A2-MAT-006F` 已完成退朝后经学分组、材料导览和验收覆盖 | 如需进入主线轻提示，需另开任务验收；当前仍默认留在退朝后 | 解释儒法、黄老、经学、义利、国家能力和政治正当性等思想来源 | 退朝后思想透镜；退朝后材料导览 | 不直接支撑会议事实 |
| 后世评说 | 《四库提要》已完成首轮补强，`YT-A2-MAT-004` 已建立现代研究书目卡和版权边界 | 历代序跋仍可后续补充；现代研究如需入包需另开契约任务 | 作为退朝后延伸阅读和研究史定位 | 退朝后延伸阅读 | 通常不支撑会议事实；可支撑接受史或研究史说明 |

## 3. 交付边界

1. 古籍材料可以进入 evidence pack，但必须有来源、卷篇、短摘、白话说明、材料类型和人工核验状态。
2. 现代研究只交付书目卡、观点摘要、公开链接、版权边界和核验状态，不交付全文或长段摘录。
3. 思想史材料只能作为思想透镜，不能冒充盐铁会议事实。
4. 后世评说只能作为接受史、目录学评价或研究史材料，不能改写会议结果。
5. 外部当代讨论继续保持 `external_echo` 边界，不作为历史证据，不进入首次主体验。
6. 未核验材料只能进入候选清单，不得进入主线、EvidenceUnit 或 Claim。
7. A2 材料不得让用户选择改变真实历史结果，只能改变进入视角、证据发现顺序和退朝反思。

## 4. 优先级

| 优先级 | 材料 | 原因 | 第一交付物 |
|---|---|---|---|
| P0 | 《资治通鉴》卷023 会议纪事 | 已完成首轮入包，后续只需验收进入位置 | 4 条会议纪事 EvidenceUnit |
| P0 | 《汉书·食货志》《史记·平准书》制度背景 | 已完成首轮入包，并完成孔仅、东郭咸阳、卜式首轮 Actor 化和酒榷制度背景补强；后续只需决定是否作为主线轻提示 | 14 条制度背景 EvidenceUnit、3 个制度背景 Actor 与标签体系 |
| P0 | 后世评价边界 | 退朝后探索需要可信边界，避免混入主线事实 | 后世评价材料分级规则 |
| P1 | 《盐铁论》文本性质与人物背景 | 已完成首轮文本性质入包、制度人物 Actor 化和贤良文学身份 Actor 证据归并；具体姓名、地域或社会构成可后续扩展 | 8 条四库提要文本史 EvidenceUnit、3 个制度背景 Actor、贤良文学身份索引 |
| P1 | 汉初至武帝思想语境 | 黄老与《黄帝四经》已完成计划冻结、候选短摘核验、首轮入包和退朝后黄老分组；经学、董仲舒和财政国家语境已完成计划冻结、《汉书》候选短摘核验、《春秋繁露》候选短摘核验、首轮入包、退朝后分组和材料导览验收 | 6 条黄老 EvidenceUnit、6 条经学语境 EvidenceUnit、黄老材料计划、经学语境计划与核验文档、退朝后思想透镜分组、材料导览入口和 Playwright 验收 |
| P2 | 现代研究书目卡 | 已完成首轮书目卡与版权边界；后续如需入包另开任务 | `docs/YANTIE_A2_MODERN_RESEARCH_INDEX.md` 7 张书目卡 |
| P2 | 当代回声 | 只作退朝后反思，不作历史证据 | `external_echo` 候选清单 |

## 5. A2 首批任务

| 任务 ID | 名称 | 目标 | 默认进入位置 |
|---|---|---|---|
| `YT-A2-MAT-001` | 《资治通鉴》会议纪事证据补强 | 解决卷023 已列入来源但 evidence pack 为 0 条的问题 | 退朝后深度探索；候选主线证据 |
| `YT-A2-MAT-002` | 盐铁/均输/平准/酒榷制度背景补强 | 扩充财政制度与边费背景 | 退朝后深度探索；少量可做主线轻提示 |
| `YT-A2-MAT-003` | 《盐铁论》文本性质与后世评价补强 | 补文本成书、人物背景和后世目录学评价 | 退朝后深度探索 |
| `YT-A2-MAT-004` | 现代研究书目卡与版权边界 | 已建立现代研究只交付书目卡和观点定位的规则 | 退朝后延伸阅读 |
| `YT-A2-MAT-005` | 汉初黄老与《黄帝四经》思想史补强 | 冻结黄老材料边界、候选来源层和候选思想透镜 | 退朝后思想透镜 |
| `YT-A2-MAT-005A` | 《黄帝四经》版本、来源、版权和候选短摘核验 | 核验候选来源层、候选短摘和 005B 入包条件 | 退朝后思想透镜候选 |
| `YT-A2-MAT-005B` | 《黄帝四经》思想透镜入包 | 将 6 条黄老短摘写入双份 evidence pack，并用测试约束边界 | 退朝后思想透镜 |
| `YT-A2-MAT-005C` | 退朝后思想透镜分组入口 | 将黄老透镜纳入退朝后“换个角度看”的分组入口 | 退朝后思想透镜 |
| `YT-A2-MAT-006` | 董仲舒、经学语境与政治正当性材料补强计划 | 冻结经学候选来源层、6 个候选透镜和进入边界 | 退朝后思想透镜 |
| `YT-A2-MAT-006A` | 《汉书》经学语境候选短摘核验 | 核验《董仲舒传》《武帝纪》《儒林传》12 条候选短摘和入包边界 | 退朝后思想透镜候选 |
| `YT-A2-MAT-006B` | 《春秋繁露》版本性质与候选短摘核验 | 核验《春秋繁露》文本风险、12 条候选短摘和入包边界 | 退朝后思想透镜候选 |
| `YT-A2-MAT-006C` | 经学语境思想透镜入包 | 将 6 条《汉书》/《春秋繁露》短摘写入双份 evidence pack，并用测试约束边界 | 退朝后思想透镜 |
| `YT-A2-MAT-006D` | 退朝后经学语境透镜分组入口 | 将 006C 经学透镜放入退朝后 `classics_context` 分组 | 退朝后思想透镜 |
| `YT-A2-MAT-006E` | 退朝后 A2 材料导览入口 | 用材料导览说明 A2 六类材料的入口、边界和状态 | 退朝后深度探索 |
| `YT-A2-MAT-006F` | 材料导览验收场景覆盖 | 用 Playwright 验证材料导览在三类视口下真实可见 | 退朝后验收矩阵 |
| `YT-A2-MAT-006G` | A2 材料状态文档收口 | 同步 006D/006E/006F 完成状态，防止材料缺口文档继续保留过期判断 | 材料门禁文档 |
| `YT-A2-MAT-007` | 制度人物 Actor 补强 | 将孔仅、东郭咸阳、卜式作为背景人物接入 actors、事件和 lexical index | 退朝后深度探索；可支持制度人物检索 |
| `YT-A2-MAT-008` | 酒榷制度背景补强 | 补武帝时期初设酒榷和榷酤制度含义，解释会议有限让步对象 | 退朝后深度探索；可候选为主线轻提示 |
| `YT-A2-MAT-009` | 贤良文学身份 Actor 证据归并 | 将现有贤良文学身份材料接入 `actor_literati` 和 lexical index | 退朝后深度探索；可支持身份检索 |
| `YT-A2-MAT-010` | A2 材料状态计数一致性测试 | 用测试绑定材料门禁计数和真实 evidence pack 数量 | 材料门禁文档 |
| `YT-A2-MAT-011` | 黄老透镜分组状态收口 | 补登 005C 黄老透镜退朝后分组的完成状态 | 材料门禁文档 |

## 6. 本轮验收

- 新增本文件，明确五类材料缺口、优先级和交付边界。
- `YT-A2-MAT-004` 新增现代研究索引文档，并确认现代研究默认不进入首次主体验、史证抽屉或 evidence pack。
- `YT-A2-MAT-005` 新增黄老材料计划文档，并确认《黄帝四经》默认只作退朝后思想透镜。
- `YT-A2-MAT-005A` 新增《黄帝四经》核验文档，并确认候选短摘只有通过 `YT-A2-MAT-005B` 才能入包。
- `YT-A2-MAT-005B` 新增 6 条《黄帝四经》黄老 EvidenceUnit，并确认它们不作为会议事实证据。
- `YT-A2-MAT-005C` 新增退朝后黄老思想透镜分组，并确认黄老材料仍不进入首次主体验。
- `YT-A2-MAT-006` 新增经学语境计划文档，并确认董仲舒、《春秋公羊传》和《春秋繁露》默认只作退朝后思想透镜或深度探索，不作为盐铁会议现场事实。
- `YT-A2-MAT-006A` 新增《汉书》经学语境候选短摘核验文档，并确认 12 条候选短摘不支撑 `original_fact` Claim。
- `YT-A2-MAT-006B` 新增《春秋繁露》版本性质与候选短摘核验文档，并确认传世文本和作者归属风险。
- `YT-A2-MAT-006C` 新增 6 条经学语境 EvidenceUnit，并确认它们不作为会议事实证据，不被 `original_fact` Claim 引用。
- `YT-A2-MAT-006D` 新增退朝后 `classics_context` 思想透镜分组，并确认经学语境材料仍不进入首次主体验。
- `YT-A2-MAT-006E` 新增退朝后材料导览入口，并确认材料导览只说明来源层级和边界，不写入 evidence pack。
- `YT-A2-MAT-006F` 新增 `material-guide` Playwright 验收场景，并确认材料导览入口、边界标记和卡片在三种视口下可见。
- `YT-A2-MAT-006G` 同步本材料门禁文档和任务拆分文档中的 A2 当前状态。
- `YT-A2-MAT-007` 新增 3 个制度背景 Actor，并确认孔仅、东郭咸阳、卜式不作为始元六年会议发言者。
- `YT-A2-MAT-008` 新增 2 条酒榷制度背景 EvidenceUnit，并确认《通典》只作后出制度解释，不作为会议现场材料。
- `YT-A2-MAT-009` 不新增 EvidenceUnit 或 Claim，只将现有贤良文学身份材料归并到 Actor 和 lexical index。
- `YT-A2-MAT-010` 新增材料状态计数一致性测试，防止本文件的 source、EvidenceUnit、Claim 计数与真实 evidence pack 漂移。
- `YT-A2-MAT-011` 补齐 `YT-A2-MAT-005C` 在本材料门禁文档中的完成状态，并用材料文档测试守住该状态。
- 在 `docs/YANTIE_TASK_BREAKDOWN.md` 登记 A2 首批任务卡。
- 本轮涉及 evidence pack 的改动仅限 `YT-A2-MAT-006C` 经学透镜入包、`YT-A2-MAT-007` 制度人物 Actor 化、`YT-A2-MAT-008` 酒榷制度背景补强和 `YT-A2-MAT-009` 贤良文学身份归并；涉及 UI 的改动仅限 `YT-A2-MAT-005C`、`YT-A2-MAT-006D`、`YT-A2-MAT-006E` 的退朝后只读入口；涉及验收脚本的改动仅限 `YT-A2-MAT-006F`；`YT-A2-MAT-010` 和 `YT-A2-MAT-011` 只新增文档测试和门禁说明；不修改 Schema、API、搜索逻辑、迁移或运行态数据。
- 每个 A2 任务卡都包含：任务 ID、价值、依赖、允许修改范围、禁止修改范围、输入、输出、接口、验收标准、测试命令、回滚方式、文档更新。
- 执行：

```powershell
git diff --check -- docs/YANTIE_A2_CHUNQIU_FANLU_VERIFICATION.md docs/YANTIE_A2_HANSHU_CLASSICS_VERIFICATION.md docs/YANTIE_A2_CLASSICS_CONTEXT_PLAN.md docs/YANTIE_A2_MATERIAL_GAP.md docs/YANTIE_TASK_BREAKDOWN.md metaos/yantie/data/evidence_pack.json docs/yantie/data/evidence_pack.json test/test_yantie_pack.py test/test_yantie_material_docs.py test/test_yantie_ui.py test/test_yantie_e2e.py scripts/check-yantie-acceptance.mjs
python -m pytest test -k yantie_pack
python -m pytest test/test_yantie_material_docs.py
```
