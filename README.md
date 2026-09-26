# cursor-harness-money-sim

Cursor Harness 小实验仓库：测「人只定边界 + 目标，Agent 自主完成 3 个大版本（V1→V2→V3；每版须有版本命题，不能只修 bug / 调参 / 改文案）」能走到哪。
目标产物是一个**不依赖美术的赚钱模拟器**，体量对齐普通小型模拟/经营游戏，禁止为交差做成技术 Demo。V1 就必须能独立玩完约 9 年（开局→中期→终局，核心行动不是摆设）；V2、V3 是两次大版本更新，不是补丁。玩家入口为浏览器本地页或桌面窗体（面板、按钮、资产数字/简单图）；终端只用于测试与批量模拟；不碰真钱、不替人下单。

> 本 README 目前只描述实验脚手架。**游戏本体的安装、图形界面启动、测试、批量模拟说明由实现 Agent 在迭代中补充**（见 `ACCEPTANCE.md` 第 9 条）。终端不能当作唯一玩法入口。

## 给实现 Agent

先读这两份，再自主开工（技术栈、目录、数值公式由你决定）：

- [`HARNESS.md`](./HARNESS.md) — 权限、安全边界、工作方式（**只在本仓写代码；可 push 功能分支并开/更新 PR；禁 force-push、push `main`、自行合并、其他仓、CardRPG、真金账户**）。
- [`ACCEPTANCE.md`](./ACCEPTANCE.md) — 产品定位与验收标准（小型模拟游戏体量 / V1 可独立游玩 / 收工 DoD / 非 Demo 硬标准 / 能测 / 批量模拟三指标 / 自主洞察 / 反 Goodhart）。

每版开工前把版本命题拆成小目标。每个小目标按调研 → 短设计（含 3～5 条验收用例）→ 实现 → 测试 → 自评审 → 小步 commit 做，禁止没写设计要点就大面积写代码，也禁止先写长篇设计再开工。质量手段不可省（全量回归、改经济必跑模拟、UI 与引擎同一状态、缺陷台账、收工检查表、PR 带证据、`docs/dev/FEATURES.json` 的 passes 纪律）。脚手架护栏：`python3 -m unittest tests/test_features_floor.py`。定栈后把格式或 lint、游戏测试和这条护栏一起写进 README。收工前须同时满足 Definition of Done（可玩路径通、相关测试绿、版本命题已写入、自 review 过 ACCEPTANCE、有手玩记录）；缺一项继续本版，不进下一版。小步可以 commit，并可以 push 本仓功能分支、更新 PR；未达 DoD 时 PR 标明未完成，不要自行合并，也不要 push `main`。进度写进 [`PROGRESS.md`](./PROGRESS.md)（含版本命题、小目标、决策密度、手玩记录、版级自 review，以及 What I learned / failed / changed / Why；四行要能看出设计或测试反馈改了什么）。

## 参考知识（卡住再读，非必读作业）

- [`references/LINKS.md`](./references/LINKS.md) — 外部链接汇总。
- `references/harness/` — 如何搭执行环境与反馈闭环。
- `references/game-design/` — 经济取舍、过强策略、用模拟找洞。
- `references/examples/` — 开源标本（**只许学结构，禁止整仓复制**）。

## 目录结构

```text
.
├── README.md
├── HARNESS.md          # Agent 权限与工作方式
├── ACCEPTANCE.md       # 验收标准
├── PROGRESS.md         # 每版进度、版本命题与学习记录（V1/V2/V3）
├── docs/dev/FEATURES.json  # 功能清单；passes 只有按 steps 真人级验证后才能改为 true
├── docs/dev/FEATURES.floor.json  # 底线快照，禁止改写来放宽
├── docs/dev/评审/BUGS.md  # 缺陷台账（实现中维护；其他 docs/dev 目录按需创建）
├── tests/test_features_floor.py  # 防止删 FEATURES 条目或改写既有 steps
└── references/         # 参考知识骨架
    ├── LINKS.md
    ├── harness/
    ├── game-design/
    └── examples/
```
