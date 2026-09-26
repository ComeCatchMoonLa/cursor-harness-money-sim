"""有界的条件策略搜索。不是通用优化器，也不是逐月动作序列。

留下一条，要和已经留下的每一条在至少两个轴上分开。
轴是达成、达标时间、硬失败、工作强度、时间自主。终局财富更高单独不算。
把规则打穿的（全面碾压，或单月跳升、终局超过 600 万）记成漏洞，不留下。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

from money_sim.batch import dominates, play_once, run_batch, summarize
from money_sim.engine import ease_of, validate
from money_sim.policies import (
    POLICIES,
    _spend_on_consume,
    ensure_plan,
    policy_ease,
    policy_nest,
    policy_owner,
)
from money_sim.state import GameState, Plan

EMPLOY_TEXT = {
    "full": "全职",
    "light": "轻职",
    "part": "兼职",
    "free": "不拿固定工资",
}

# 开工前定下的门槛。看到模拟结果之后不改这些数。
WIN_GAP = 0.05
MONTH_GAP = 6
FAIL_GAP = 0.02
INTENSITY_GAP = 0.05
AUTONOMY_GAP = 3

TITLES = {
    "steady": "一直上班",
    "grind": "只上班不保养",
    "yolo": "辞职压进店",
    "owner": "把店做起来",
    "nest": "先买自住",
    "ease": "到位置就轻职",
    "coast": "盖住之后停薪",
    "dwell": "自住并且轻职",
    "after_shop": "店交给人再轻职",
    "craft": "先把职业学高",
}


def axis_gaps(left: dict, right: dict) -> list[str]:
    """两个摘要差在哪些轴上。不看平均净资产。"""
    gaps = []
    if abs(left["win_rate"] - right["win_rate"]) >= WIN_GAP:
        gaps.append("达成")
    left_month = left.get("median_win_month")
    right_month = right.get("median_win_month")
    if left_month is not None and right_month is not None and abs(left_month - right_month) >= MONTH_GAP:
        gaps.append("达标时间")
    if abs(left["hard_fail_rate"] - right["hard_fail_rate"]) >= FAIL_GAP:
        gaps.append("硬失败")
    if abs(_intensity(left) - _intensity(right)) >= INTENSITY_GAP:
        gaps.append("工作强度")
    if abs(_autonomy(left) - _autonomy(right)) >= AUTONOMY_GAP:
        gaps.append("时间自主")
    return gaps


def _intensity(row: dict) -> float:
    return row.get("glide_intensity", row["mean_intensity"])


def _autonomy(row: dict) -> float:
    return row.get("glide_autonomy", row["mean_autonomy"])


def different(left: dict, right: dict) -> bool:
    return len(axis_gaps(left, right)) >= 2


def breaks_rules(row: dict, others: list[dict]) -> bool:
    if row["name"] == dominates(others + [row]):
        return True
    if row["suspect_wealth_games"] > 0 or row["max_jump"] > 0.55:
        return True
    return False


def _open_slots(state: GameState, count: int) -> list[str]:
    slots: list[str] = []
    refresh_at = 3 if state.month >= 48 else 1
    career_stale = state.career_fresh <= refresh_at
    for index in range(count):
        if state.condition < 48 or state.energy < 36:
            slots.append("rest")
        elif (state.career < 58 or career_stale) and index == 0:
            slots.append("learn_career")
        elif state.regime == "bear":
            slots.append("rest")
        else:
            slots.append("invest")
    return slots


def _wage_pause_blocked(state: GameState, plan: Plan) -> bool:
    position = ease_of(state)
    return (
        not position["open"]
        or not position["covered"]
        or state.regime == "bull"
        or state.offer_left > 0
        or plan.accept_job
        or state.contract_left > 0
        or state.condition < 40
        or state.energy < 24
    )


def policy_coast(state: GameState) -> Plan:
    """轻职储蓄已经盖住 150 万之后，不再拿工资。没盖住时和轻职路线相同。

    景气月、合同、外部工资仍继续上班。停薪不发钱，账单要靠现金和卖掉的指数。
    """
    base = policy_ease(state)
    if _wage_pause_blocked(state, base):
        return base
    slots, consume_cash = _spend_on_consume(state, _open_slots(state, 4))
    plan = Plan(
        "free",
        slots,
        to_index=base.to_index,
        from_index=base.from_index,
        debt_pay=base.debt_pay,
        risk_pct=base.risk_pct if "invest" in slots else 0,
        lock_amount=base.lock_amount if base.from_index == 0 else 0,
        consume_cash=consume_cash,
    )
    return ensure_plan(state, plan)


def policy_dwell(state: GameState) -> Plan:
    """轻职路线走到能买自住的月份，就按安家的首付去买。这个月买不成就退回安家的方案。"""
    plan = policy_ease(state)
    home = policy_nest(state)
    if not home.buy_home:
        return plan
    trial = replace(
        plan,
        buy_home=True,
        from_index=home.from_index,
        to_index=0,
        lock_amount=0,
    )
    if not validate(state, trial):
        return trial
    return home


def lighten_automated(state: GameState, plan: Plan) -> Plan:
    """店已经交给人、少工作的位置也开了，才把全职换成轻职。店还要亲自盯时不换。"""
    position = ease_of(state)
    if (
        not plan.automate
        or not position["open"]
        or state.regime == "bull"
        or state.offer_left > 0
        or plan.accept_job
        or state.contract_left > 0
        or state.condition < 40
        or state.energy < 24
    ):
        return plan
    slots, consume_cash = _spend_on_consume(state, _open_slots(state, 2))
    trial = replace(
        plan,
        employment="light",
        slots=slots,
        sign_months=0,
        consume_cash=consume_cash,
        risk_pct=plan.risk_pct if "invest" in slots else 0,
    )
    if not validate(state, trial):
        return trial
    return plan


def policy_after_shop(state: GameState) -> Plan:
    return ensure_plan(state, lighten_automated(state, policy_owner(state)))


def policy_craft(state: GameState) -> Plan:
    """职业还没到 70、局时还没过一半时，全职的投资槽改去学职业。到了少工作的位置仍按轻职走。"""
    plan = policy_ease(state)
    if state.career >= 70 or state.month >= 60 or plan.employment != "full" or "invest" not in plan.slots:
        return plan
    slots = list(plan.slots)
    slots[slots.index("invest")] = "learn_career"
    trial = replace(plan, slots=slots, risk_pct=0)
    if not validate(state, trial):
        return trial
    return plan


# 1000 局复核后留下。再搜时把它算进已有路线，不重复候选。
PROMOTED = (("coast", policy_coast),)

CANDIDATES = (
    ("dwell", policy_dwell),
    ("after_shop", policy_after_shop),
    ("craft", policy_craft),
)


def _nearest(row: dict, kept: list[dict]) -> tuple[dict, list[str]]:
    nearest = kept[0]
    gaps = axis_gaps(row, nearest)
    for other in kept[1:]:
        other_gaps = axis_gaps(row, other)
        if len(other_gaps) < len(gaps):
            nearest = other
            gaps = other_gaps
    return nearest, gaps


# 写进路线表的先后。留出种子上重判时，后写的要和每一条已经留下的都差够两个轴。
KEPT_ORDER = ("steady", "grind", "yolo", "owner", "nest", "ease", "coast")

# V7 起种子 1 上停住的主力达成率。再压低、又没有新的分叉，常数一档不留。
PLATEAU_WIN = {"steady": 0.611, "nest": 0.645}


def rank_key(row: dict) -> tuple:
    """达成率高的在前。相同则达标更早的在前。没有赢局的排在有赢局的后面。"""
    month = row.get("median_win_month")
    return (-row["win_rate"], month is None, month if month is not None else 0, row["name"])


def rank_names(rows: list[dict]) -> list[str]:
    return [row["name"] for row in sorted(rows, key=rank_key)]


def retain_routes(rows: list[dict], order: tuple[str, ...] = KEPT_ORDER) -> tuple[list[dict], list[dict]]:
    """按写表先后重判。差不够两个轴的，并进已留下里轴最少的那条；轴数相同就并进更早的。"""
    by_name = {row["name"]: row for row in rows}
    kept: list[dict] = []
    merged: list[dict] = []
    for name in order:
        row = by_name.get(name)
        if row is None:
            continue
        if kept and not all(different(row, other) for other in kept):
            nearest, gaps = _nearest(row, kept)
            merged.append({"name": name, "into": nearest["name"], "gaps": gaps})
            continue
        kept.append(row)
    return kept, merged


def ship_notches(old_holdout: list[dict], new_holdout: list[dict], seed1_notched: list[dict]) -> bool:
    """一档留在游戏里，只有留出种子上留下的名单变了，并且种子 1 的主力达成率没有掉下 V7 的平台。"""
    old_names = [row["name"] for row in retain_routes(old_holdout)[0]]
    new_names = [row["name"] for row in retain_routes(new_holdout)[0]]
    if old_names == new_names:
        return False
    by_name = {row["name"]: row for row in seed1_notched}
    for name, floor in PLATEAU_WIN.items():
        if by_name[name]["win_rate"] < floor:
            return False
    return True


def starting_policies():
    return tuple(POLICIES) + tuple(PROMOTED)


def search_routes(games: int, seed: int) -> dict:
    base = run_batch(games, seed, starting_policies())
    kept = list(base["strategies"])
    holes = []
    dropped = []
    for name, policy in CANDIDATES:
        rows = [play_once(policy, seed + game) for game in range(games)]
        row = summarize(name, rows)
        if not all(different(row, other) for other in kept):
            nearest, gaps = _nearest(row, kept)
            dropped.append({"name": name, "nearest": nearest["name"], "gaps": gaps, "summary": row})
            continue
        if breaks_rules(row, kept):
            holes.append(row)
            continue
        kept.append(row)
    promoted = {name for name, _policy in PROMOTED}
    separations = []
    for row in kept:
        if row["name"] not in promoted:
            continue
        separations.append(
            {
                "name": row["name"],
                "against": [
                    {"name": other["name"], "gaps": axis_gaps(row, other)}
                    for other in kept
                    if other["name"] != row["name"]
                ],
            }
        )
    return {
        "games": games,
        "seed": seed,
        "kept": kept,
        "dropped": dropped,
        "holes": holes,
        "separations": separations,
    }


def describe_mainline(summary: dict) -> str:
    labels = (("early", "前 36 个月"), ("mid", "37 到 72 月"), ("late", "73 月以后"))
    parts = []
    adaptations = []
    for key, label in labels:
        item = summary.get("mainline", {}).get(key)
        if not item:
            continue
        parts.append(f"{label}多半是{EMPLOY_TEXT.get(item['employment'], item['employment'])}")
        second = item.get("second")
        if second and second["share"] >= 0.08:
            adaptations.append(
                f"{label}还有 {second['share']:.0%} 是{EMPLOY_TEXT.get(second['employment'], second['employment'])}"
            )
    line = "，".join(parts) if parts else "没有打完一整段"
    if adaptations:
        return f"{line}。变招：{'；'.join(adaptations)}。"
    return f"{line}。变招很少。"


def format_search(report: dict) -> str:
    lines = [
        f"局数 {report['games']}  种子 {report['seed']}",
        "留下的路线要和每一条已留下的路线至少差两个轴。轴：达成、达标时间、硬失败、中段工作强度、中段时间自主。",
        "名字  达成率  中位达标月  硬失败  工作强度  时间自主  平均可兑现  主线",
    ]
    for row in report["kept"]:
        month = "—" if row["median_win_month"] is None else f"{row['median_win_month']:.0f}"
        lines.append(
            "  ".join(
                [
                    f"{row['name']:<10}",
                    f"{row['win_rate']:.1%}",
                    month,
                    f"{row['hard_fail_rate']:.1%}",
                    f"{_intensity(row):.2f}",
                    f"{_autonomy(row):.1f}",
                    f"{row['mean_net']:.0f}",
                    describe_mainline(row),
                ]
            )
        )
    if report["dropped"]:
        lines.append("没留下：")
        for item in report["dropped"]:
            gaps = "、".join(item["gaps"]) if item["gaps"] else "没有轴分开"
            lines.append(f"  {item['name']} 最接近 {item['nearest']}（{gaps}）")
    if report["holes"]:
        lines.append("漏洞：" + "、".join(row["name"] for row in report["holes"]))
    else:
        lines.append("漏洞：没有")
    for item in report.get("separations", []):
        lines.append(f"{item['name']} 和已有路线差在：")
        for other in item["against"]:
            gaps = "、".join(other["gaps"]) if other["gaps"] else "没有轴分开"
            lines.append(f"  对 {other['name']}：{gaps}")
    return "\n".join(lines)


def routes_public(report: dict) -> dict:
    """界面只展示留下的路线，不展示被丢掉的搜索草稿。"""
    routes = []
    for row in report["kept"]:
        routes.append(
            {
                "name": row["name"],
                "title": TITLES.get(row["name"], row["name"]),
                "win_rate": row["win_rate"],
                "median_win_month": row["median_win_month"],
                "hard_fail_rate": row["hard_fail_rate"],
                "mean_intensity": _intensity(row),
                "mean_autonomy": _autonomy(row),
                "mainline": describe_mainline(row),
            }
        )
    return {"games": report["games"], "seed": report["seed"], "routes": routes}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="搜索有差别的条件路线")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args(argv)
    report = search_routes(args.games, args.seed)
    text = format_search(report)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(routes_public(report), handle, ensure_ascii=False, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    main()
