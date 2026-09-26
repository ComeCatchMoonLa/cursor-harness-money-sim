# Cursor Agent Harness · 本实验备忘（5～10 条）

> 我自己的短笔记，供本仓 Agent 参考。
> 相关背景：Cursor · What we've learned building cloud agents — https://cursor.com/blog/cloud-agent-lessons

1. **Cloud Agent 的本质是「环境 + 闭环」**，不是把本地 Agent 搬到云上。环境能否让 Agent 跑、测、验、演示，才是关键。
2. **只在本仓工作**。不碰其他仓（尤其不碰 CardRPG），不改仓库外文件。
3. **禁止 git push**、禁止接真实券商/支付/账户。需要越权时先停，在 `PROGRESS.md` 写原因，等人类。
4. **自主选栈**：技术栈、目录结构、数值公式全由 Agent 决定，不要反问人类用什么框架。
5. **反馈优先于功能**：先建成「可玩 + 可测 + 可批量模拟」的闭环，再谈内容广度；不要为加系统而加系统。
6. **每轮留痕**：跑测试 →（尽量）批量模拟 → 记录洞察 → 更新 `PROGRESS.md`（含四行学习）→ commit。
7. **反 Goodhart**：不许靠降低难度 / 抬高所有收益 / 取消风险来刷指标；要解释经济为什么有取舍。
8. **人类只在越权、高危、卡死、明显失控时介入**；正式验收在 V3 之后。
9. **references/ 是随手翻的知识，不是必读作业**；examples 只许学结构，禁止整仓复制。
10. **诚实**：做不到的（比如批量局数上不去）就在 `PROGRESS.md` 写清瓶颈，不要掩盖。
