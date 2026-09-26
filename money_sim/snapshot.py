"""从中途存档把留下的路线打到第 108 月。

局数和种子在设计里写死。这里的结果不写回标准路线表。
标准局的第 37 到 72 月窗口留在 play_once，不在这里改。
"""

from __future__ import annotations

import random
import statistics
from collections import Counter

from money_sim.batch import phase_mainline
from money_sim.constants import LOCK_TERM, MONTHS, WORK_SLOTS
from money_sim.economy import mortgage_payment
from money_sim.engine import resolve
from money_sim.policies import POLICIES, ensure_plan
from money_sim.routes import (
    AUTONOMY_GAP,
    EMPLOY_TEXT,
    FAIL_GAP,
    HOLDOUT_MERGED,
    INTENSITY_GAP,
    MONTH_GAP,
    TITLES,
    WIN_GAP,
    _autonomy,
    _intensity,
    starting_policies,
)
from money_sim.state import GameState, realizable_net, store_rng

# 设计里写死。看到打分结果之后不改。
SNAPSHOT_GAMES = 200
SNAPSHOT_SEED = 20001
MONEY_CAP = 1_000_000_000

_FIELDS = (
    ("month", "月份", 1, MONTHS),
    ("cash", "现金", 0, MONEY_CAP),
    ("portfolio", "指数", 0, MONEY_CAP),
    ("locked", "封闭", 0, MONEY_CAP),
    ("debt", "负债", 0, MONEY_CAP),
    ("home_value", "房子", 0, MONEY_CAP),
    ("mortgage", "贷款", 0, MONEY_CAP),
    ("career", "职业", 0, 100),
    ("venture", "经营", 0, 100),
    ("invest", "投资", 0, 100),
    ("condition", "状态", 0, 100),
    ("contract_left", "合同剩余", 0, 12),
    ("price_index", "物价", 1, 10_000),
)


def glide_bounds(start_month: int) -> tuple[int, int]:
    """快照晚于第 72 月才改看剩余月份。第 13 月仍是 37 到 72。"""
    if start_month > 72:
        return start_month, MONTHS
    return 37, 72


def _whole(data: dict, key: str, label: str, low: int, high: int) -> int:
    if key not in data:
        raise ValueError(f"缺{label}")
    value = data[key]
    if isinstance(value, bool) or isinstance(value, str):
        raise ValueError(f"{label}要是整数")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{label}要是整数")
        value = int(value)
    if not isinstance(value, int):
        raise ValueError(f"{label}要是整数")
    if value < low or value > high:
        raise ValueError(f"{label}要在 {low} 和 {high} 之间")
    return value


def build_snapshot(form: dict) -> GameState:
    """表上没有的字段用开局默认。晚存档因此会像刚休息过，这是表的边界，不是行情。"""
    if not isinstance(form, dict):
        raise ValueError("存档必须是对象")
    values = {key: _whole(form, key, label, low, high) for key, label, low, high in _FIELDS}
    if values["locked"] > values["portfolio"]:
        raise ValueError("封闭不能多于指数")
    if values["home_value"] <= 0 and values["mortgage"] > 0:
        raise ValueError("没有房子就不能有贷款")
    state = GameState(
        month=values["month"],
        status="playing",
        seed=SNAPSHOT_SEED,
        cash=values["cash"],
        portfolio=values["portfolio"],
        locked=values["locked"],
        lock_left=LOCK_TERM if values["locked"] > 0 else 0,
        debt=values["debt"],
        home_value=values["home_value"],
        mortgage=values["mortgage"],
        mortgage_payment=mortgage_payment(values["mortgage"]),
        career=values["career"],
        venture=values["venture"],
        invest=values["invest"],
        condition=values["condition"],
        contract_left=values["contract_left"],
        contract_term=values["contract_left"],
        price_index=values["price_index"],
        regime="chop",
    )
    state.history = [realizable_net(state)]
    return state


def play_forward(policy, state: GameState, seed: int, window: tuple[int, int]) -> dict:
    """从存档的这个月往前走。随机数用内部种子，不用玩家的。"""
    state = state.clone()
    rng = random.Random(seed)
    store_rng(state, rng)
    state.seed = seed
    state.status = "playing"
    low, high = window
    phase_employ = {"early": Counter(), "mid": Counter(), "late": Counter()}
    months_played = 0
    autonomy_sum = 0
    intensity_sum = 0.0
    glide_months = 0
    glide_autonomy = 0
    glide_intensity = 0.0
    while state.status == "playing":
        plan = ensure_plan(state, policy(state))
        month = state.month
        autonomy_sum += state.autonomy
        intensity = WORK_SLOTS[plan.employment] / 3
        intensity_sum += intensity
        months_played += 1
        if low <= month <= high:
            glide_months += 1
            glide_autonomy += state.autonomy
            glide_intensity += intensity
        if month <= 36:
            phase_employ["early"][plan.employment] += 1
        elif month <= 72:
            phase_employ["mid"][plan.employment] += 1
        else:
            phase_employ["late"][plan.employment] += 1
        state, errors, _report = resolve(state, plan)
        if errors:
            raise RuntimeError(errors)
        if month > MONTHS + 2:
            raise RuntimeError("月份没有停下")
    lived = max(1, months_played)
    return {
        "status": state.status,
        "net_worth": realizable_net(state),
        "win_month": (state.month - 1) if state.status == "won" else None,
        "mean_autonomy": autonomy_sum / lived,
        "mean_intensity": intensity_sum / lived,
        # 窗口里一个月都没走到时，用实际活过的月份，避免记成 0。
        "glide_autonomy": (glide_autonomy / glide_months) if glide_months else autonomy_sum / lived,
        "glide_intensity": (glide_intensity / glide_months) if glide_months else intensity_sum / lived,
        "glide_months": glide_months,
        "phase_employ": {band: dict(counts) for band, counts in phase_employ.items()},
    }


def summarize_forward(name: str, rows: list[dict]) -> dict:
    wins = [row for row in rows if row["status"] == "won"]
    hard = sum(row["status"] in ("bankrupt", "burnout") for row in rows)
    win_months = [row["win_month"] for row in wins if row.get("win_month")]
    return {
        "name": name,
        "games": len(rows),
        "win_rate": len(wins) / len(rows),
        "hard_fail_rate": hard / len(rows),
        "median_win_month": statistics.median(win_months) if win_months else None,
        "mean_autonomy": statistics.fmean(row["mean_autonomy"] for row in rows),
        "mean_intensity": statistics.fmean(row["mean_intensity"] for row in rows),
        "glide_autonomy": statistics.fmean(row["glide_autonomy"] for row in rows),
        "glide_intensity": statistics.fmean(row["glide_intensity"] for row in rows),
        "mainline": phase_mainline(rows),
    }


def _at_least(delta: float, gap: float) -> bool:
    """刚好等于门槛时，二进制会少一丁点。不把 0.0499 收成 0.05。"""
    return delta >= gap - 1e-9


def covers(better: dict, worse: dict) -> bool:
    """五个轴都按既定方向盖住才算。平均净资产不看。"""
    if not _at_least(better["win_rate"] - worse["win_rate"], WIN_GAP):
        return False
    better_month = better.get("median_win_month")
    worse_month = worse.get("median_win_month")
    if better_month is None or worse_month is None or not _at_least(worse_month - better_month, MONTH_GAP):
        return False
    if not _at_least(worse["hard_fail_rate"] - better["hard_fail_rate"], FAIL_GAP):
        return False
    if not _at_least(_intensity(worse) - _intensity(better), INTENSITY_GAP):
        return False
    if not _at_least(_autonomy(better) - _autonomy(worse), AUTONOMY_GAP):
        return False
    return True


def _band_labels(start_month: int) -> list[tuple[str, str]]:
    labels = []
    if start_month <= 36:
        labels.append(("early", _span_text(start_month, 36)))
    if start_month <= 72:
        labels.append(("mid", _span_text(max(start_month, 37), 72)))
    if start_month < MONTHS:
        late_from = max(start_month, 73)
        if late_from == 73:
            labels.append(("late", "73 月以后"))
        else:
            labels.append(("late", f"第 {late_from} 月以后"))
    return labels


def _span_text(low: int, high: int) -> str:
    if low == high:
        return f"第 {low} 月"
    return f"第 {low} 到 {high} 月"


def describe_forward(summary: dict, start_month: int) -> str:
    """只写从这个月起会走到的段。不用标准卡片上「前 36 个月」那种说法。"""
    parts = []
    adaptations = []
    for key, label in _band_labels(start_month):
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


def _variant_policies():
    found = dict(POLICIES)
    return [(name, found[name], parent) for name, parent in HOLDOUT_MERGED.items()]


def _run(name: str, policy, state: GameState, games: int, seed: int, window: tuple[int, int]) -> dict:
    rows = [play_forward(policy, state, seed + index, window) for index in range(games)]
    return summarize_forward(name, rows)


def _covered(rows: dict[str, dict], order: list[str]) -> dict[str, str]:
    found = {}
    for name in order:
        for other in order:
            if other == name:
                continue
            if covers(rows[other], rows[name]):
                found[name] = other
                break
    return found


def _card(row: dict, start_month: int, variants: list[dict] | None = None) -> dict:
    card = {
        "name": row["name"],
        "title": TITLES.get(row["name"], row["name"]),
        "win_rate": row["win_rate"],
        "median_win_month": row["median_win_month"],
        "hard_fail_rate": row["hard_fail_rate"],
        "mean_intensity": _intensity(row),
        "mean_autonomy": _autonomy(row),
        "mainline": describe_forward(row, start_month),
    }
    if variants is not None:
        card["variants"] = variants
    return card


def _lead(start_month: int, window: tuple[int, int]) -> str:
    low, high = window
    if start_month > 72:
        where = f"工作强度和时间自主看第 {low} 月到第 {high} 月。"
    else:
        where = "工作强度和时间自主看第 37 到 72 月。"
    return f"按留下的顺序。{where}不把达成率最高的标成最优，也不填这一月的方案。"


def assemble(rows: dict[str, dict], start_month: int, window: tuple[int, int], games: int, seed: int) -> dict:
    kept = [name for name, _policy in starting_policies()]
    variants = [name for name, _policy, _parent in _variant_policies()]
    covered = _covered(rows, kept + variants)
    notes = []
    for name in kept:
        if name in covered:
            notes.append(f"{TITLES.get(name, name)}被五个轴一起盖住，不单列。")
    if "steady" in covered:
        hung = [TITLES.get(name, name) for name in variants if HOLDOUT_MERGED[name] == "steady"]
        if hung:
            notes.append(f"{'、'.join(hung)}不另升上来。")
    for name in variants:
        parent = HOLDOUT_MERGED[name]
        if name in covered and parent not in covered:
            notes.append(f"{TITLES.get(name, name)}被五个轴一起盖住，不挂在{TITLES.get(parent, parent)}下面。")
    routes = []
    for name in kept:
        if name in covered:
            continue
        nested = []
        for variant in variants:
            if HOLDOUT_MERGED[variant] != name or variant in covered:
                continue
            nested.append(_card(rows[variant], start_month))
        routes.append(_card(rows[name], start_month, nested))
    return {
        "scored": True,
        "games": games,
        "seed": seed,
        "month": start_month,
        "glide_from": window[0],
        "glide_to": window[1],
        "message": _lead(start_month, window),
        "notes": notes,
        "routes": routes,
        "omitted": [{"name": name, "by": other} for name, other in covered.items()],
    }


def score_snapshot(form: dict, *, games: int = SNAPSHOT_GAMES, seed: int = SNAPSHOT_SEED) -> dict:
    state = build_snapshot(form)
    if state.month >= MONTHS:
        return {
            "scored": False,
            "month": state.month,
            "games": games,
            "seed": seed,
            "message": "第 108 月已经没有剩下的月份，不打分。",
            "routes": [],
            "notes": [],
        }
    window = glide_bounds(state.month)
    rows = {}
    for name, policy in starting_policies():
        rows[name] = _run(name, policy, state, games, seed, window)
    for name, policy, _parent in _variant_policies():
        rows[name] = _run(name, policy, state, games, seed, window)
    return assemble(rows, state.month, window, games, seed)
