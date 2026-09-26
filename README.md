# cursor-harness-money-sim

Cursor Harness 小实验仓库：测「人只定边界 + 目标，Agent 自主完成软件并连续迭代 3 版（V1→V2→V3）」能走到哪。
目标产物是一个**不依赖美术的赚钱模拟器**（玩家入口为浏览器本地页或桌面窗体：面板、按钮、资产数字/简单图；终端只用于测试与批量模拟；不碰真钱、不替人下单）。

> 本 README 目前只描述实验脚手架。**游戏本体的安装、图形界面启动、测试、批量模拟说明由实现 Agent 在迭代中补充**（见 `ACCEPTANCE.md` 第 9 条）。终端不能当作唯一玩法入口。

## 给实现 Agent

先读这两份，再自主开工（技术栈、目录、数值公式由你决定）：

- [`HARNESS.md`](./HARNESS.md) — 权限、安全边界、工作方式（**只在本仓；可 push 功能分支并开/更新 PR；禁 force-push、其他仓、CardRPG、真金账户**）。
- [`ACCEPTANCE.md`](./ACCEPTANCE.md) — 产品定位与验收标准（图形界面可玩 / 能测 / 批量模拟三指标 / 自主洞察 / 反 Goodhart）。

每轮把进度写进 [`PROGRESS.md`](./PROGRESS.md)（含 What I learned / failed / changed / Why）。

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
├── PROGRESS.md         # 每轮进度与学习记录（V1/V2/V3）
└── references/         # 参考知识骨架
    ├── LINKS.md
    ├── harness/
    ├── game-design/
    └── examples/
```
