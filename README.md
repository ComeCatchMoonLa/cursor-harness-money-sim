# 九年账

不依赖美术的月度赚钱模拟。开局净资产 72 万，共 108 个月，目标是可兑现净资产做到 150 万（比开局多约 78 万）。每月在就业、时间槽和资金之间取舍。副业是一家会亏、要先试营业、退出要打折的店，不是第二份工资。任期会把你锁在全职上，合同月的休息回血跟时间自主有关。封闭的指数不能拿来救急。技能会过时；收缩期里，指数、店和身体可能在同一个月一起挨打。自住房要付首付和停不下来的月供，卖掉要打折，刚买下的可兑现会先掉一截。外部报价只维持十二个月，接手的那个月没有工资，技能不加。

不需要安装第三方包，Python 3.11 及以上即可。

## 启动

```bash
python3 -m money_sim.server
```

浏览器打开 http://127.0.0.1:8765 。页面上的金额来自模拟引擎。结算、胜利和失败会追加到 `logs/game.jsonl`。

## 测试

```bash
python3 -m unittest discover -s tests
```

其中 `python3 -m unittest tests/test_features_floor.py` 锁住验收底线，不能删。

## 批量模拟

```bash
python3 -m money_sim.sim --games 1000 --seed 1
```

终端比较至少四条策略，并打印达成率、破产或过劳率、平均终局净资产。`--games 100` 是下限，正式记录用 1000。

## 实验边界

这是 Cursor Harness 实验仓库：人定边界，Agent 先连续做完 V1 到 V3。V3 不是停止点，之后按 [`HARNESS.md`](./HARNESS.md)「做到 V20」筛选，V20 是上限。本阶段收到 V16。现在能玩的是第 1 月、可兑现 72 万那一局，五条留下的路线，对局对照，以及中途存档打分。权限和验收见 [`HARNESS.md`](./HARNESS.md)、[`ACCEPTANCE.md`](./ACCEPTANCE.md)。进度在 [`PROGRESS.md`](./PROGRESS.md)。不接真实账户。

## 给实现 Agent

先读 [`HARNESS.md`](./HARNESS.md) 和 [`ACCEPTANCE.md`](./ACCEPTANCE.md)。`HARNESS.md` 里「做到 V20」是必读：V20 是上限。本阶段已在 V16 结项。在人再指定下一版之前，不按「版本号小于 20」开工。人指定下一版之后，仍用四问筛选；筛过了就开工，筛不过就把原因写进候选池然后停。不要为了凑版数发明需求。可以 commit，并向本仓功能分支 push、更新 PR。禁止 force-push，禁止 push `main`，禁止自行合并，禁止接真实账户。

参考知识在 `references/`。标本只许学结构，禁止整仓复制。