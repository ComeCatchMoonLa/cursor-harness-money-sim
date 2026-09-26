# harness/ 索引

关于「如何搭 Agent 执行环境与反馈闭环」的摘录与备忘。卡在流程/自主循环设计时翻这里。

| 文件 | 内容 | 一句话 |
| --- | --- | --- |
| [OpenAI-Harness-Engineering.md](./OpenAI-Harness-Engineering.md) | 人定环境/反馈，Agent 写代码 | harness = 环境 + 约束 + 工具 + 可验证反馈 |
| [Anthropic-Long-Running-Agents.md](./Anthropic-Long-Running-Agents.md) | 长程 Agent：进度文件、增量推进、少打断人类 | 用 PROGRESS.md 留干净可续状态 |
| [Cursor-Agent-Harness.md](./Cursor-Agent-Harness.md) | 本实验 10 条规则备忘 | 只在本仓、可 push 功能分支、V1 可独立游玩、收工 DoD、反 Goodhart |

外部链接汇总见上一级 [`../LINKS.md`](../LINKS.md)。
