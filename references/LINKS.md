# 高质量参考链接（按需阅读）

> 用途：Agent + Harness + 外部知识 + 反馈。
> 规则：卡住再读；禁止整仓复制 examples。

## harness/

### 必读优先（先这 3 个）

| 标题 | URL | 为什么有用 |
| --- | --- | --- |
| OpenAI · Harness engineering | https://openai.com/index/harness-engineering/ | 人定环境/反馈，Agent 写代码；人类稀缺注意力 |
| Anthropic · Effective harnesses for long-running agents | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents | 跨会话进度文件、增量推进、留给下一轮的干净状态 |
| Cursor · What we've learned building cloud agents | https://cursor.com/blog/cloud-agent-lessons | Cloud Agent 本质是环境与闭环，不只是搬家到云端 |

### 补充

| 标题 | URL | 为什么有用 |
| --- | --- | --- |
| Cursor · Cloud Agents 文档 | https://cursor.com/docs/cloud-agent | 本实验建议用的运行形态 |
| Cursor · Cloud Agent setup | https://cursor.com/docs/cloud-agent/setup | 环境/依赖/可测闭环怎么配 |
| Cursor · Background Agents 说明（现称 Cloud Agents） | https://cursor.com/help/ai-features/background-agents | 长跑、产物、人工何时介入 |
| OpenAI · AGENTS.md | https://developers.openai.com/codex/guides/agents-md | 仓内短指令如何分层，避免百科全书式 Prompt |
| Anthropic · autonomous-coding quickstart | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding | 长程 harness 的可运行标本（学模式，别抄成游戏本体） |

同目录短索引：[`harness/INDEX.md`](./harness/INDEX.md)

## game-design/

| 标题 | URL | 为什么有用 |
| --- | --- | --- |
| Ian Schreiber · Game Balance Concepts（课程总览） | https://gamebalanceconcepts.wordpress.com/ | 免费、偏数值与经济，适合做「取舍/过强策略」词汇 |
| Level 2 · Numeric Relationships | https://gamebalanceconcepts.wordpress.com/2010/07/14/level-2-numeric-relationships/ | 反馈环、资源与成长如何咬合 |
| Level 3 · Transitive Mechanics and Cost Curves | https://gamebalanceconcepts.wordpress.com/2010/07/21/level-3-transitive-mechanics-and-cost-curves/ | 成本曲线、支配策略直觉 |
| Level 7 · Advancement, Progression and Pacing | https://gamebalanceconcepts.wordpress.com/2010/08/18/level-7-advancement-progression-and-pacing/ | 正和/零和/负和与节奏 |
| Level 10 · Final Boss（含经济系统讨论） | https://gamebalanceconcepts.wordpress.com/2010/09/08/level-10-final-boss/ | 造钱/销毁、通胀、财富监控 |

同目录短索引：[`game-design/INDEX.md`](./game-design/INDEX.md)

## examples/

| 标题 | URL | 为什么有用 | 禁令 |
| --- | --- | --- | --- |
| Anthropic autonomous-coding | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding | 看 initializer / progress 文件 / 多会话循环 | 不要把它改成你的游戏交付物 |
| xrayian/Life-Simulator | https://github.com/xrayian/Life-Simulator | 看文字/终端向人生+金钱循环的目录与状态大致长什么样 | **禁止整仓复制**；只许学结构 |
| liamellison02/Fin-Lit-Fun | https://github.com/liamellison02/Fin-Lit-Fun | 另一份金融素养模拟向标本 | 同上 |

同目录短索引：[`examples/INDEX.md`](./examples/INDEX.md)
