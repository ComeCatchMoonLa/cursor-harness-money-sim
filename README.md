# 九年账

不依赖美术的月度赚钱模拟。开局净资产 72 万，共 108 个月，目标是可兑现净资产做到 150 万（比开局多约 78 万）。每月在就业、时间槽和资金之间取舍。副业是一家会亏、要先试营业、退出要打折的店，不是第二份工资。任期会把你锁在全职上；封闭的指数不能拿来救急。

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

这是 Cursor Harness 实验仓库：人定边界，Agent 连续做 V1 到 V3。权限和验收见 [`HARNESS.md`](./HARNESS.md)、[`ACCEPTANCE.md`](./ACCEPTANCE.md)。进度在 [`PROGRESS.md`](./PROGRESS.md)。不接真实账户。

## 给实现 Agent

先读 [`HARNESS.md`](./HARNESS.md) 和 [`ACCEPTANCE.md`](./ACCEPTANCE.md)。可以 commit，并向本仓功能分支 push、更新 PR。禁止 force-push，禁止 push `main`，禁止自行合并，禁止接真实账户。

参考知识在 `references/`。标本只许学结构，禁止整仓复制。
