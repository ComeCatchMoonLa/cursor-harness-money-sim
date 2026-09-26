"""无界面批量模拟。"""

from __future__ import annotations

import argparse
import statistics
from collections import Counter

from money_sim.constants import CONDITION_LOW, MONTHS, WORK_SLOTS
from money_sim.engine import resolve
from money_sim.policies import POLICIES, ensure_plan
from money_sim.state import Plan, net_worth, new_game, realizable_net


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
        plan.sign_months,
        plan.break_contract,
        plan.lock_amount > 0,
        plan.unlock,
        plan.buy_home,
        plan.sell_home,
        plan.accept_job,
        plan.consume_cash // 2_000,
    )


def play_once(policy, seed: int) -> dict:
    state = new_game(seed)
    previous = None
    early_changes = 0
    late_changes = 0
    early_steps = 0
    late_steps = 0
    max_jump = 0.0
    max_worth = realizable_net(state)
    slot_counter: Counter[str] = Counter()
    early_learn = 0
    late_learn = 0
    early_learn_steps = 0
    late_learn_steps = 0
    consume_months = 0
    early_consume = 0
    late_consume = 0
    lifestyle_sum = 0
    lifestyle_peak = state.lifestyle
    condition_sum = 0
    low_condition = 0
    autonomy_sum = 0
    intensity_sum = 0.0
    mid_months = 0
    mid_autonomy = 0
    mid_intensity = 0.0
    phase_employ = {"early": Counter(), "mid": Counter(), "late": Counter()}
    while state.status == "playing":
        plan = ensure_plan(state, policy(state))
        signature = plan_signature(plan)
        month = state.month
        learning = any(slot.startswith("learn_") for slot in plan.slots)
        consuming = "consume" in plan.slots
        if month <= 36:
            early_learn_steps += 1
            early_learn += int(learning)
            early_consume += int(consuming)
        if month >= 60:
            late_learn_steps += 1
            late_learn += int(learning)
            late_consume += int(consuming)
        consume_months += int(consuming)
        lifestyle_sum += state.lifestyle
        lifestyle_peak = max(lifestyle_peak, state.lifestyle)
        condition_sum += state.condition
        low_condition += int(state.condition < CONDITION_LOW)
        autonomy_sum += state.autonomy
        intensity_sum += WORK_SLOTS[plan.employment] / 3
        if month <= 36:
            phase_employ["early"][plan.employment] += 1
        elif month <= 72:
            phase_employ["mid"][plan.employment] += 1
            mid_months += 1
            mid_autonomy += state.autonomy
            mid_intensity += WORK_SLOTS[plan.employment] / 3
        else:
            phase_employ["late"][plan.employment] += 1
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
        before_book = net_worth(state)
        before = realizable_net(state)
        state, errors, _report = resolve(state, plan)
        if errors:
            raise RuntimeError(errors)
        after_book = net_worth(state)
        after = realizable_net(state)
        if before_book > 0:
            max_jump = max(max_jump, (after_book - before_book) / before_book)
        max_worth = max(max_worth, after)
        if month > MONTHS + 2:
            raise RuntimeError("月份没有停下")
    return {
        "status": state.status,
        "net_worth": realizable_net(state),
        "month": state.month,
        "max_jump": max_jump,
        "max_worth": max_worth,
        "early_change_rate": early_changes / early_steps if early_steps else 0.0,
        "late_change_rate": late_changes / late_steps if late_steps else 0.0,
        "reached_late": late_steps > 0,
        "early_learn_rate": early_learn / early_learn_steps if early_learn_steps else 0.0,
        "late_learn_rate": late_learn / late_learn_steps if late_learn_steps else 0.0,
        "consume_rate": consume_months / max(1, state.month - 1),
        "early_consume_rate": early_consume / early_learn_steps if early_learn_steps else 0.0,
        "late_consume_rate": late_consume / late_learn_steps if late_learn_steps else 0.0,
        "end_lifestyle": state.lifestyle,
        "mean_lifestyle": lifestyle_sum / max(1, state.month - 1),
        "peak_lifestyle": lifestyle_peak,
        "mean_condition": condition_sum / max(1, state.month - 1),
        "low_condition_rate": low_condition / max(1, state.month - 1),
        "end_condition": state.condition,
        "free_rate": slot_counter["free"] / max(1, state.month - 1),
        "light_rate": slot_counter["light"] / max(1, state.month - 1),
        "end_month": state.month - 1,
        "slots": slot_counter,
        "mean_autonomy": autonomy_sum / max(1, state.month - 1),
        "mean_intensity": intensity_sum / max(1, state.month - 1),
        # 没活到中段的局，用它实际活过的月份，避免把早破产记成自主为 0。
        "glide_autonomy": (mid_autonomy / mid_months) if mid_months else autonomy_sum / max(1, state.month - 1),
        "glide_intensity": (mid_intensity / mid_months) if mid_months else intensity_sum / max(1, state.month - 1),
        "win_month": (state.month - 1) if state.status == "won" else None,
        "phase_employ": {band: dict(counts) for band, counts in phase_employ.items()},
    }


def phase_mainline(rows: list[dict]) -> dict:
    """每一段里出现最多的就业，以及次常见的那档占了多少。"""
    pooled = {"early": Counter(), "mid": Counter(), "late": Counter()}
    for row in rows:
        for band, counts in row.get("phase_employ", {}).items():
            pooled[band].update(counts)
    lines = {}
    for band, counts in pooled.items():
        if not counts:
            continue
        ranked = counts.most_common()
        total = sum(counts.values())
        employment, top = ranked[0]
        second = None
        if len(ranked) > 1:
            second = {"employment": ranked[1][0], "share": ranked[1][1] / total}
        lines[band] = {"employment": employment, "share": top / total, "second": second}
    return lines


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
    early_learn_rates = [row["early_learn_rate"] for row in rows]
    late_learn_rows = [row["late_learn_rate"] for row in rows if row["end_month"] >= 60]
    win_months = [row["win_month"] for row in rows if row.get("win_month")]
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
        "mean_early_learn": statistics.fmean(early_learn_rates) if early_learn_rates else 0.0,
        "mean_late_learn": statistics.fmean(late_learn_rows) if late_learn_rows else 0.0,
        "mean_consume": statistics.fmean(row["consume_rate"] for row in rows),
        "mean_early_consume": statistics.fmean(row["early_consume_rate"] for row in rows),
        "mean_late_consume": statistics.fmean(row["late_consume_rate"] for row in rows),
        "mean_end_lifestyle": statistics.fmean(row["end_lifestyle"] for row in rows),
        "mean_lifestyle": statistics.fmean(row["mean_lifestyle"] for row in rows),
        "mean_peak_lifestyle": statistics.fmean(row["peak_lifestyle"] for row in rows),
        "mean_condition": statistics.fmean(row["mean_condition"] for row in rows),
        "mean_low_condition": statistics.fmean(row["low_condition_rate"] for row in rows),
        "mean_end_condition": statistics.fmean(row["end_condition"] for row in rows),
        "mean_free": statistics.fmean(row["free_rate"] for row in rows),
        "mean_light": statistics.fmean(row["light_rate"] for row in rows),
        "late_games": len(late_rows),
        "median_end_month": statistics.median(end_months),
        "suspect_jump_games": sum(row["max_jump"] > 0.55 for row in rows),
        "suspect_wealth_games": sum(row["max_worth"] > 6_000_000 for row in rows),
        "mean_autonomy": statistics.fmean(row["mean_autonomy"] for row in rows),
        "mean_intensity": statistics.fmean(row["mean_intensity"] for row in rows),
        "glide_autonomy": statistics.fmean(row["glide_autonomy"] for row in rows),
        "glide_intensity": statistics.fmean(row["glide_intensity"] for row in rows),
        "median_win_month": statistics.median(win_months) if win_months else None,
        "mainline": phase_mainline(rows),
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
        "策略  达成率  硬失败率  破产率  过劳率  未达成  平均净资产  中位净资产  p10  p90  中位结束月  后半程样本  后半程改方案率  前期学习月占比  后期学习月占比  消费月占比  前期消费  后期消费  平均生活水准  峰值生活水准  终局生活水准  平均状态  低于40占比  终局状态  无工资占比  轻职占比  单月最大跳升  可疑暴富局",
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
                    f"{row['mean_early_learn']:.2f}",
                    f"{row['mean_late_learn']:.2f}",
                    f"{row['mean_consume']:.2f}",
                    f"{row['mean_early_consume']:.2f}",
                    f"{row['mean_late_consume']:.2f}",
                    f"{row['mean_lifestyle']:.0f}",
                    f"{row['mean_peak_lifestyle']:.0f}",
                    f"{row['mean_end_lifestyle']:.0f}",
                    f"{row['mean_condition']:.0f}",
                    f"{row['mean_low_condition']:.2f}",
                    f"{row['mean_end_condition']:.0f}",
                    f"{row['mean_free']:.2f}",
                    f"{row['mean_light']:.2f}",
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
    from money_sim.routes import starting_policies

    report = run_batch(args.games, args.seed, starting_policies())
    text = format_report(report)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
