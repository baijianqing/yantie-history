# 盐铁会议 YT-A1-UI-001A 实现启动单

状态：阶段0实现前启动单
任务 ID：`YT-A1-UI-001A-KICKOFF`
日期：2026-07-13

## 1. 结论

`YT-A1-GATE-001` 已完成门禁复核，设计门禁通过，但当前仓库仍处于阶段0。本文只为后续 `YT-A1-UI-001A：静态主体验纵切片` 做实现前启动准备，不修改前端代码。

如果用户明确授权进入 A1，实现任务应从 `YT-A1-UI-001A` 开始，而不是直接做完整 `YT-A1-UI-001`。

首个实现目标应控制为：

```text
开场地图
-> 北边压力
-> 第一次取舍
-> 生成视角
-> 入朝
-> 财政/民生最小冲突
-> 一条关键证据
-> 判断动摇/坚持
-> 霍光沉默
-> 退朝案牍
```

## 2. 任务契约

- 任务 ID：`YT-A1-UI-001A-KICKOFF`
- 价值：把未来 `YT-A1-UI-001A` 的代码实施入口、允许文件、禁止事项、最小体验路径和测试出口提前写清楚，避免一进入实现阶段就扩展完整图谱、透镜、外部回声或框架迁移。
- 依赖：`YT-A1-GATE-001`、`YT-A1-UI-001A`、`YT-V3-017A`、`YT-V3-017D`、`YT-V3-017E`、`YT-V3-017F`、`YT-V3-017G`、`YT-V3-017H`。
- 允许修改范围：本启动单文档。
- 禁止修改范围：`docs/yantie/index.html`、`test/test_yantie_ui.py`、`metaos/yantie/web.py`、证据包、API 契约、公共 Schema、迁移、依赖配置、根配置、运行态 `library/` 数据。
- 输入：`docs/YANTIE_A1_GATE_REVIEW.md`、`docs/YANTIE_TASK_BREAKDOWN.md`、现有 `docs/yantie/index.html` 结构、现有 `test/test_yantie_ui.py`。
- 输出：现状审计表、未来实现触点表、首个纵切片执行顺序、测试与验收出口、禁止扩展清单。
- 接口：本启动单不授权实现；后续只有用户明确授权进入 A1 后，才能按此启动单执行 `YT-A1-UI-001A`。
- 验收标准：能明确指出未来实现将改哪些文件、不改哪些文件、收束哪些入口、保留哪些能力、跑哪些测试。
- 测试命令：`git diff --check -- docs/YANTIE_UI001A_KICKOFF.md`。
- 回滚方式：删除 `docs/YANTIE_UI001A_KICKOFF.md`。
- 文档更新：本文件即阶段0交付物；真正实现 `YT-A1-UI-001A` 时，应同步更新产品体验文档的实现状态。

## 3. 现状审计

| 项目 | 现状 | 对 `YT-A1-UI-001A` 的含义 |
|------|------|---------------------------|
| 静态页面 | `docs/yantie/index.html` 已存在，约 5652 行，约 220 KB | 不宜继续堆新功能，应优先收束主路径和状态入口 |
| 静态证据包 | `docs/yantie/data/evidence_pack.json` 已存在，约 190 KB | 首个纵切片只引用证据 ID，不扩写证据 |
| 音频资产 | `narrative.mp3`、`debate.mp3`、`reflection.mp3` 已存在 | 可继续使用，但静音模式必须完整可用 |
| UI 测试 | `test/test_yantie_ui.py` 已存在 | 未来实现可在该文件补充主路径断言 |
| 运行方式 | 静态页和 FastAPI 渲染均已有基础 | 第一阶段不需要 React、Vite、GIS SDK 或后端账户 |

## 4. 未来实现触点

| 触点 | 当前角色 | 未来 `YT-A1-UI-001A` 处理方式 |
|------|----------|-------------------------------|
| `state` | 保存场景、音频、压力、身份、访问记录 | 对齐 `ExperienceState`，避免组件各自维护独立真相源 |
| `pressureTimeline` | 开场压力序列 | 保留为主体验序章，但只服务开场压力和第一次取舍 |
| `standpointRoles` | 身份/视角生成 | 保留，但文案避免人格测试和阵营评分 |
| `conflictActs` | 五幕争论与选择 | 收束为财政/民生最小冲突和一条判断轨迹 |
| `advanceScene` | 主推进按钮 | 成为唯一主动作入口，不与图谱、透镜、外部回声争抢 |
| `revealEvidence` | 证据入口 | 主线只开放一条关键证据，其余证据进入退朝后探索 |
| `chapterMapToggle` | 六十篇图谱入口 | 主线默认隐藏，退朝后才开放 |
| `renderScene` | 核心渲染 | 增加一屏三要素约束：主视觉、主问题、主动作 |
| `openEvidence` | 证据展示 | 支持阅读后回到现场，不把证据正文写入用户状态 |
| `judgmentForm` | 退朝案牍 | 聚焦初判、转折点、证据 ID、未解矛盾和个人反思 |

## 5. 首个实现顺序

未来进入 A1 后，建议按以下顺序实施：

1. 在 `docs/yantie/index.html` 中明确主体验阶段列表，不新增完整新模块。
2. 让 `pressure_entry -> standpoint_choice -> court_debate -> power_reveal -> judgment` 的推进只暴露一个主动作。
3. 在主体验中默认隐藏完整章节图谱、哲学透镜全文、当代回声和搜索式探索。
4. 把关键证据限制为一条可回到现场的案卷，其他证据只作为退朝后入口。
5. 退朝案牍展示初判、进入视角、转折点、证据 ID、最终判断和未解矛盾。
6. 补充 `test/test_yantie_ui.py`，至少断言主体验入口、深度入口隐藏、案牍字段和禁止技术栈。
7. 运行最小 UI 测试和 `git diff --check`。

## 6. 未来允许修改范围

真正执行 `YT-A1-UI-001A` 时，建议只允许：

| 文件 | 允许动作 |
|------|----------|
| `docs/yantie/index.html` | 收束主体验路径、隐藏主线外入口、调整状态和文案 |
| `test/test_yantie_ui.py` | 增加主路径、入口隐藏、案牍字段和静态承载断言 |
| `docs/YANTIE_PRODUCT_EXPERIENCE.md` | 追加实现状态、截图或已知不足 |

除非另开任务，不应修改其他文件。

## 7. 未来禁止扩展清单

`YT-A1-UI-001A` 不应做：

- 不做完整六十篇图谱体验。
- 不做完整哲学透镜阅读器。
- 不接入知乎或任何外部实时回声。
- 不扩写 evidence pack。
- 不改 API 契约。
- 不引入 React、Vite、TypeScript、MapLibre、Three.js、GSAP、PixiJS 或新的音频库。
- 不做账户、分享、跨设备保存或多次历史记录。
- 不把用户选择写成历史事实。

## 8. 测试出口

未来实现完成后，最小测试应包括：

```powershell
python -m pytest test -k yantie_ui
git diff --check -- docs/yantie/index.html test/test_yantie_ui.py docs/YANTIE_PRODUCT_EXPERIENCE.md
```

若只改 UI 文案和静态页面，也应至少人工检查：

- 桌面端开场地图可进入主路径。
- 移动端主动作不被遮挡。
- 主线中不默认显示完整图谱、透镜或当代回声。
- 关键证据可打开并返回现场。
- 退朝案牍显示判断轨迹和证据 ID。
- 静音和减少动态不阻断主路径。

## 9. 当前停点

本启动单完成后，项目停在一个清晰边界上：

> 阶段0文档准备已经足以支撑 `YT-A1-UI-001A`；但除非用户明确说“解除阶段0，进入 A1，实现 `YT-A1-UI-001A`”，否则仍不开始代码实现。
