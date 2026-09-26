"""无界面批量模拟。"""

from __future__ import annotations

import argparse
import statistics
from collections import Counter

from money_sim.constants import MONTHS
from money_sim.engine import resolve
from money_sim.policies import POLICIES, ensure_plan
from money_sim.state import Plan, new_game, net_worth


def plan_signature(plan: Plan) -> tuple:
    return (
        plan.employment,
        tuple(plan.slots),
        plan.to_index > 0,
        plan.from_index > 0,
        plan.to_business > 0,
        plan.risk_pct // 25,
        plan.automate,
        plan.exit_business or plan.accept_offer,
    )


def play_once(policy, seed: int) -> dict:
    state = new_game(seed)
    previous = None
    early_changes = 0
    late_changes = 0
    early_steps = 0
    late_steps = 0
    max_jump = 0.0
    max_worth = net_worth(state)
    slot_counter: Counter[str] = Counter()
    while state.status == "playing":
        plan = ensure_plan(state, policy(state))
        signature = plan_signature(plan)
        month = state.month
        if previous is not None:
            changed = signature != previous
            if month <= 24:
                early_steps += 1
                early_changes += int(changed)
            if month >= 73:
                late_steps += 1
                late_changes += int(changed)
        else:
            if month <= 24:
                early_steps += 1
            if month >= 73:
                late_steps += 1
        previous = signature
        for slot in plan.slots:
            slot_counter[slot] += 1
        slot_counter[plan.employment] += 1
        before = net_worth(state)
        state, errors, _report = resolve(state, plan)
        if errors:
            raise RuntimeError(errors)
        after = net_worth(state)
        if before > 0:
            max_jump = max(max_jump, (after - before) / before)
        max_worth = max(max_worth, after)
        if month > MONTHS + 2:
            raise RuntimeError("月份没有停下")
    return {
        "status": state.status,
        "net_worth": net_worth(state),
        "month": state.month,
        "max_jump": max_jump,
        "max_worth": max_worth,
        "early_change_rate": early_changes / early_steps if early_steps else 0.0,
        "late_change_rate": late_changes / late_steps if late_steps else 0.0,
        "reached_late": late_steps > 0,
        "end_month": state.month - 1,
        "slots": slot_counter,
    }


def summarize(name: str, rows: list[dict]) -> dict:
    worths = [row["net_worth"] for row in rows]
    wins = sum(row["status"] == "won" for row in rows)
    hard = sum(row["status"] in ("bankrupt", "burnout") for row in rows)
    bankrupt = sum(row["status"] == "bankrupt" for row in rows)
    burnout = sum(row["status"] == "burnout" for row in rows)
    shortfall = sum(row["status"] == "shortfall" for row in rows)
    jumps = [row["max_jump"] for row in rows]
    late_rows = [row for row in rows if row["reached_late"]]
    late_rates = [row["late_change_rate"] for row in late_rows]
    end_months = [row["end_month"] for row in rows]
    return {
        "name": name,
        "games": len(rows),
        "win_rate": wins / len(rows),
        "hard_fail_rate": hard / len(rows),
        "bankrupt_rate": bankrupt / len(rows),
        "burnout_rate": burnout / len(rows),
        "shortfall_rate": shortfall / len(rows),
        "mean_net": statistics.fmean(worths),
        "median_net": statistics.median(worths),
        "p10_net": statistics.quantiles(worths, n=10)[0] if len(worths) >= 10 else min(worths),
        "p90_net": statistics.quantiles(worths, n=10)[-1] if len(worths) >= 10 else max(worths),
        "max_net": max(worths),
        "max_jump": max(jumps),
        "mean_late_change": statistics.fmean(late_rates) if late_rates else 0.0,
        "late_games": len(late_rows),
        "median_end_month": statistics.median(end_months),
        "suspect_jump_games": sum(row["max_jump"] > 0.55 for row in rows),
        "suspect_wealth_games": sum(row["max_worth"] > 6_000_000 for row in rows),
    }


def dominates(rows: list[dict]) -> str | None:
    """三项同时最好才算全面碾压。"""
    for row in rows:
        others = [other for other in rows if other["name"] != row["name"]]
        better = all(
            row["win_rate"] > other["win_rate"] + 0.05
            and row["hard_fail_rate"] < other["hard_fail_rate"] - 0.02
            and row["mean_net"] > other["mean_net"] * 1.05
            for other in others
        )
        if better:
            return row["name"]
    return None


def run_batch(games: int, seed: int, policies=POLICIES) -> dict:
    summaries = []
    for index, (name, policy) in enumerate(policies):
        rows = [play_once(policy, seed + game) for game in range(games)]
        summaries.append(summarize(name, rows))
    return {"games": games, "seed": seed, "strategies": summaries, "dominant": dominates(summaries)}


def format_report(report: dict) -> str:
    lines = [
        f"局数 {report['games']}  种子 {report['seed']}",
        "策略  达成率  硬失败率  破产率  过劳率  未达成  平均净资产  中位净资产  p10  p90  中位结束月  后半程样本  后半程改方案率  单月最大跳升  可疑暴富局",
    ]
    for row in report["strategies"]:
        lines.append(
            "  ".join(
                [
                    f"{row['name']:<8}",
                    f"{row['win_rate']:.1%}",
                    f"{row['hard_fail_rate']:.1%}",
                    f"{row['bankrupt_rate']:.1%}",
                    f"{row['burnout_rate']:.1%}",
                    f"{row['shortfall_rate']:.1%}",
                    f"{row['mean_net']:.0f}",
                    f"{row['median_net']:.0f}",
                    f"{row['p10_net']:.0f}",
                    f"{row['p90_net']:.0f}",
                    f"{row['median_end_month']:.0f}",
                    str(row["late_games"]),
                    f"{row['mean_late_change']:.2f}",
                    f"{row['max_jump']:.1%}",
                    str(row["suspect_wealth_games"]),
                ]
            )
        )
    lines.append(f"全面碾压策略：{report['dominant'] or '没有'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="九年账批量模拟")
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    report = run_batch(args.games, args.seed)
    text = format_report(report)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
