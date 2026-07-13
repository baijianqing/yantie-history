# 盐铁会议 A1 交付说明

状态：A1 静态核心体验已可试玩
更新日期：2026-07-13

## 1. 一句话定位

《盐铁会议：西汉朝堂复原》不是历史问答工具，而是一条基于精选史证的沉浸式主体验路径：用户先经历边防、府库、盐铁、均输和民生压力，再以特定视角进入朝堂，最终形成自己的“退朝案牍”。

## 2. 当前可试玩入口

静态体验入口：

```text
https://baijianqing.github.io/yantie-history/yantie/
```

本地运行态入口：

```bash
python -m uvicorn metaos.yantie.web:create_yantie_web_app --factory --reload
```

打开：

```text
http://127.0.0.1:8000/yantie
```

静态版和运行态使用同一套前端体验。区别在于：

| 形态 | 数据来源 | 外部回声 | 适用场景 |
|---|---|---|---|
| GitHub Pages 静态版 | `docs/yantie/data/evidence_pack.json` | 默认降级，不请求外部接口 | 参赛展示、公开试玩 |
| FastAPI 运行态 | `/api/yantie/*` | 可在服务端配置后启用 | 本地演示、接口调试、后续扩展 |

## 3. 主体验路径

当前主体验冻结为 5-8 分钟路径：

```text
历史压力出现
-> 第一次取舍
-> 生成视角
-> 入朝
-> 财政 / 民生冲突
-> 关键证据
-> 判断动摇或坚持
-> 霍光沉默
-> 退朝案牍
-> 退朝后深度探索
```

首次体验中默认不展开完整六十篇图谱、完整哲学透镜、长文证据阅读或当代回声，避免把产品变成资料库。它们被放在退朝后或用户主动探索时开放。

## 4. 已实现能力

| 能力 | 状态 | 说明 |
|---|---|---|
| 静态主体验纵切片 | 已实现 | `YT-A1-UI-001A` |
| 退朝后深度探索入口 | 已实现 | `YT-A1-UI-001B` |
| 截图与移动端验收入口 | 已实现 | `YT-A1-UI-001C` |
| 静态验收 runner | 已实现 | `scripts/check-yantie-acceptance.mjs` |
| 参赛包 / E2E 门禁 | 已实现 | `YT-A1-E2E-001` |
| 知乎外部回声 Adapter | 已实现最小闭环 | 只作为 `external_echo`，不进入史证链 |
| 运行态 external_echo mock 验收 | 已实现 | 验证启用、返回和不改写证据包 |

## 5. 史证边界

本项目严格区分四类信息：

| 类型 | 可进入主体验 | 可进入退朝后探索 | 可作为历史 Claim 证据 |
|---|---:|---:|---:|
| 史实证据 | 是 | 是 | 是 |
| 策展解释 | 是 | 是 | 否，必须回链证据 |
| 思想透镜 | 轻量出现 | 是 | 否 |
| 外部回声 | 否 | 是 | 否 |
| 用户判断 | 是 | 是 | 否 |

外部回声的硬边界：

- `source_boundary=external_echo`
- `can_support_claims=false`
- `writes_to_evidence_pack=false`
- 不写入 `EvidenceUnit`
- 不支撑历史 `Claim`
- 不自动写入退朝案牍

## 6. 验收命令

核心盐铁测试：

```bash
python -m pytest test -k yantie
```

完整测试：

```bash
python -m pytest test
```

静态页面浏览器验收：

```bash
node scripts/check-yantie-acceptance.mjs
```

如使用 Codex bundled Node，需要先设置 `NODE_PATH` 到 bundled runtime 的 node modules。

可生成截图：

```bash
node scripts/check-yantie-acceptance.mjs --screenshot-dir tmp/yantie-acceptance
```

检查线上 Pages：

```bash
node scripts/check-yantie-acceptance.mjs --base-url https://baijianqing.github.io/yantie-history/yantie/
```

## 7. 最近一次验收记录

最近完成的验收结果：

| 命令 | 结果 |
|---|---|
| `python -m pytest test -k yantie_ui` | 24 passed |
| `python -m pytest test -k yantie` | 56 passed |
| `python -m pytest test` | 351 passed |
| `node scripts/check-yantie-acceptance.mjs` | 27/27 passed |

`power-silence` 场景仍建议人工复核，因为它依赖“霍光沉默”的留白表达，自动化只能确认无遮挡和入口可达，不能完全判断叙事效果。

## 8. 发布方式

静态发布文件位于：

```text
docs/yantie/
```

发布分支：

```text
yantie-static-github-pages
```

如果修改了 `metaos/yantie/web.py` 中的静态页面模板，需要重新导出：

```bash
python -c "from metaos.yantie.web import export_yantie_static_site; export_yantie_static_site()"
```

然后提交并推送到发布分支：

```bash
git push origin HEAD:yantie-static-github-pages
```

## 9. 当前不做的事

为了保持 A1 可控，当前仍不做：

- 不引入 React/Vite/TypeScript。
- 不接入运行时 RAG。
- 不提交向量库、Chroma、原始大部头语料或运行态 `library/` 数据。
- 不让用户选择改写盐铁会议历史结果。
- 不把知乎或其他外部讨论作为古代史证据。
- 不把完整图谱和长文阅读提前塞进首次主体验。

## 10. 下一步建议

下一步不宜继续加大功能面，而应做收尾打磨：

1. 生成一组参赛截图，覆盖桌面、移动端、退朝案牍和退朝后探索。
2. 人工复核 `power-silence` 留白场景，确认沉默不被 UI 噪音破坏。
3. 为项目首页补一段 300-500 字产品背书，直接说明“为什么值得打开”。
4. 如需要现场演示外部回声，再配置服务端密钥；公开静态版保持降级即可。
