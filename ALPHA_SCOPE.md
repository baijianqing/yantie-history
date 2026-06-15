# MetaOS Alpha 范围说明

## Alpha 定义

MetaOS Alpha 是一个本地优先、模块化单体的个人意图操作系统。它把用户的长期意图、当前角色、时间预算和注意力边界作为最高约束，把知识库作为证据底座，把模型作为议题编译和研究规划工具，把审计模块作为反证和引用检查工具，最终推动行动或复盘。

## Alpha 主链路

1. 用户设定或更新 `Intent`。
2. 系统生成今日重点、暂缓事项、应忽略事项和认知陷阱提醒。
3. 用户提出问题或系统发现议题。
4. 议题编译器生成 `ResearchTask`、`CognitiveOperator`、`ThemeSpec`、`EvidenceRequirement`、`ResearchScope`。
5. 研究执行器根据计划召回候选证据。
6. 检索系统执行向量检索、全文检索、元数据过滤、RRF 融合和可选重排。
7. 研究执行器生成证据矩阵，检测缺失证据，补充检索，查找反证，评分和分类。
8. 御史台检查引用、范围、反证、证据完整性、确认偏误和研究成本。
9. 输出区分原文事实、模型推断、争议观点和个人反思。
10. 结果必须关联 `Intent`，并生成 `Action`、明确“不行动”或进入复盘。
11. 每日记录汇总为 `DailySummary`。
12. 内容工坊把 `DailySummary` 转换为可审核视频。
13. 周期性复盘汇入下一轮意图和角色调整。

## Alpha 包含内容

### 用户主权层

- `CognitiveConstitution`
- `Intent`
- `CurrentRole`
- `AttentionBudget`
- `NotToDoItem`

### 每日认知账本

- `DailyPlan`
- `WorkEvent`
- `Advice`
- `Decision`
- `Action`
- `AttentionDrift`
- `DailyReview`
- Git 提交采集。
- Markdown 变更采集。
- `DailySummary`。

### 内容工坊

- `EpisodeSpec`
- 脚本。
- 旁白。
- 字幕。
- 图卡。
- 人工审核。
- Remotion 模板。
- FFmpeg 渲染。
- MP4 导出。

### 知识底座

- `Source`
- `DocumentVersion`
- `Chunk`
- `Entity`
- `EntityAlias`
- `Event`
- `Claim`
- `Relationship`
- `Citation`
- 多级摘要。
- 稳定 ID。
- 父子块。
- 前后块。
- 索引版本。
- 增量入库。

### 检索系统

- 稠密向量检索。
- 全文检索。
- 元数据过滤。
- RRF 融合。
- 可选重排。
- 引用回链。
- 回归评测。

### 议题编译器

- `ResearchTask`
- `CognitiveOperator`
- `ThemeSpec`
- `EvidenceRequirement`
- `ResearchScope`

首版认知算子：

- `fact_lookup`
- `enumerate_pattern`
- `compare`
- `causal_analysis`
- `decision_support`
- `reflection`
- `recommend`

### 研究执行器

- 候选召回。
- 证据矩阵。
- 缺失证据检测。
- 补充检索。
- 反证。
- 评分。
- 分类。
- 带引用回答。
- 进度展示。

### 御史台

- 引用检查。
- 范围检查。
- 反证检查。
- 证据完整性检查。
- 确认偏误检查。
- 研究成本检查。

### 三部有限推荐

Alpha 只做：

- 技术部。
- 认知部。
- 商业部。

限制：

- 每部每日最多 3 条。
- 整体每日最多 5 条。
- 可以返回“今日无事上奏”。

### 宰相

结合当前 `Intent`、角色、时间预算和研究结果，输出：

- 今日重点。
- 暂缓事项。
- 应忽略事项。
- 认知陷阱提醒。

## Alpha 明确不做

- 不做通用知识库。
- 不做聊天机器人。
- 不做新闻聚合器。
- 不为每个主题写硬编码分支。
- 不因新主题重切块或重建索引。
- 不在 Alpha 阶段引入微服务。
- 不在没有评测收益的情况下引入新技术。
- 不把模型输出当作无需审计的事实。
- 不把推荐做成无限信息流。

## Alpha 验收

1. 新主题无需改代码、重切块或重建索引。
2. 能生成 `ThemeSpec`、`ResearchPlan` 和证据要求。
3. 能执行多路检索，支持证据和反证聚合。
4. 最终回答可追溯原文，无来源结论被明确标记。
5. 研究结果能关联 `Intent`，并生成 `Action` 或“不行动”。
6. 每日记录能生成 `DailySummary` 和可审核视频。
7. 三部推荐严格限量，并允许无内容。
8. 宰相能输出重点、暂缓、忽略和认知陷阱提醒。
9. 核心流程具备测试、日志、版本记录、失败重试，且现有功能无明显回归。

## 阶段0完成定义

阶段0完成只表示以下文档已经产出并可供人工审查：

- `CURRENT_ARCHITECTURE_AUDIT.md`
- `AGENTS.md`
- `ALPHA_SCOPE.md`
- `BUSINESS_ARCHITECTURE.md`
- `TECHNICAL_ARCHITECTURE.md`
- `DOMAIN_MODEL.md`
- `API_CONTRACTS.md`
- `ROADMAP.md`
- `TASK_INDEX.md`

阶段0不表示任何 Alpha 业务能力已经实现。

