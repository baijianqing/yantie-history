# YT-A2-DEPLOY-001 盐铁会议 A2 Pages 静态部署记录

状态：`deployed_static_preview`

部署日期：`2026-07-14`

## 1. 范围

本报告记录《盐铁会议：西汉朝堂复原》A2 静态预览版的 GitHub Pages 部署结果。

本轮不修改 UI、证据包、API、外部 adapter、验收脚本、部署配置或运行态数据；只记录推送与线上复验结果。

## 2. 推送记录

本轮已将当前提交推送到远端工作分支：

```text
codex/yantie-main-experience-slice -> a637871
```

本轮已将同一提交快进到 Pages 发布分支：

```text
yantie-static-github-pages -> a637871
```

发布分支是当前提交的祖先后快进更新，不是强制覆盖。

## 3. 线上地址

当前线上静态预览地址：

```text
https://baijianqing.github.io/yantie-history/yantie/
```

## 4. 线上复验

部署后线上验收通过：

```text
Yantie acceptance: 36/36 checks passed.
Manual review recommended: desktop/power-silence, mobile/power-silence, reduced-motion/power-silence
```

这说明线上 Pages 已经包含 A2 退朝后材料导览、思想透镜、外部回声边界等最新静态入口，不再停留在旧版本。

## 5. 当前发布状态

当前适合：

- 作为 GitHub Pages 静态预览版对外打开。
- 作为 A2 材料增强后的体验演示版。
- 用于小范围用户体验反馈和参赛展示。

当前仍不适合：

- 声称为最终产品版。
- 声称为生产级公开发布。
- 声称外部回声 live adapter 已正式开放。

## 6. 剩余风险

仍需人工复核：

- `desktop/power-silence`
- `mobile/power-silence`
- `reduced-motion/power-silence`

原因：霍光沉默场景的核心是留白、节奏和权力压迫感，自动验收只能证明结构和可达性，不能替代观感判断。

外部回声状态：

- 静态版继续默认禁用。
- 继续标记为 `external_echo`。
- 不进入史证链、Claim、EvidenceUnit 或退朝案牍。

## 7. 下一步建议

如果目标是继续提高发布可信度，下一步应做：

1. `YT-A2-E2E-002`：线上截图与 `power-silence` 人工复核记录。
2. `YT-A2-REL-002`：Playwright 验收依赖可复现说明或脚本包装。
3. `YT-A2-DOC-001`：面向普通用户的发布说明和 README 收口。

如果目标是继续打磨产品体验，再进入：

4. `YT-A2-MAIN-001`：决定哪些 A2 材料进入首次主体验轻提示。

## 8. 结论

当前项目已经适合发布为线上静态预览版：

```text
YT-A2-DEPLOY-001 = deployed_static_preview
```

它已经可以让用户通过 GitHub Pages 进入完整体验；但最终版发布还需要人工复核沉默场景、整理面向用户的发布说明，并决定 A2 材料是否进入主线轻提示。
