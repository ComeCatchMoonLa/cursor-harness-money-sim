"""一组 if-then 的数据。不是再写一条固定策略函数。

预算和留下规则在 docs/dev/设计/v12.md。看到结果不改这些数。
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import replace

from money_sim.batch import play_once, summarize
from money_sim.constants import WORK_SLOTS
from money_sim.engine import ease_of, validate
from money_sim.policies import _spend_on_consume, policy_steady
from money_sim.routes import (
    _open_slots,
    axis_gaps,
    breaks_rules,
    different,
    starting_policies,
)
from money_sim.state import GameState, realizable_net

SEARCH_SEED = 11
N_CANDIDATES = 24
RULES_PER = 2
SCREEN_GAMES = 60
CONFIRM_GAMES = 200
HOLDOUT_GAMES = 1000
HOLDOUT_SEED = 10001
GAME_SEED = 1

WORTH_STEPS = (None, 900_000, 1_200_000, 1_400_000)
CONDITION_STEPS = (None, 74, 58, 40)
CONTRACT_STEPS = (None, 6, 0)
REGIMES = (None, "bull", "chop", "bear")
POSITIONS = ("any", "closed", "open", "covered")
AUTOMATED = (None, False, True)
EMPLOYMENTS = ("full", "light", "part", "free")

REGIME_TEXT = {None: "任何景气", "bull": "景气", "chop": "平淡", "bear": "收缩"}
POSITION_TEXT = {"any": "任何位置", "closed": "少工作还没开", "open": "少工作开了但没盖住", "covered": "少工作已经盖住"}
EMPLOY_TEXT = {"full": "全职", "light": "轻职", "part": "兼职", "free": "不拿固定工资"}


def sample_rule(rng: random.Random) -> dict:
    return {
        "worth": rng.choice(WORTH_STEPS),
        "condition": rng.choice(CONDITION_STEPS),
        "regime": rng.choice(REGIMES),
        "contract": rng.choice(CONTRACT_STEPS),
        "position": rng.choice(POSITIONS),
        "automated": rng.choice(AUTOMATED),
        "employment": rng.choice(EMPLOYMENTS),
    }


def sample_rules(rng: random.Random, count: int = RULES_PER) -> tuple[dict, ...]:
    return tuple(sample_rule(rng) for _ in range(count))


def _position(state: GameState) -> str:
    place = ease_of(state)
    if place["covered"]:
        return "covered"
    if place["open"]:
        return "open"
    return "closed"


def matches(state: GameState, rule: dict) -> bool:
    if rule["worth"] is not None and realizable_net(state) < rule["worth"]:
        return False
    if rule["condition"] is not None and state.condition > rule["condition"]:
        return False
    if rule["regime"] is not None and state.regime != rule["regime"]:
        return False
    if rule["contract"] is not None and state.contract_left > rule["contract"]:
        return False
    if rule["position"] != "any" and _position(state) != rule["position"]:
        return False
    if rule["automated"] is not None and state.automated != rule["automated"]:
        return False
    return True


def describe_rule(rule: dict, index: int) -> str:
    parts = []
    if rule["worth"] is not None:
        parts.append(f"可兑现至少 {rule['worth'] // 10_000} 万")
    if rule["condition"] is not None:
        parts.append(f"状态不高于 {rule['condition']}")
    if rule["regime"] is not None:
        parts.append(REGIME_TEXT[rule["regime"]])
    if rule["contract"] is not None:
        parts.append("没有合同" if rule["contract"] == 0 else f"合同还剩不超过 {rule['contract']} 个月")
    if rule["position"] != "any":
        parts.append(POSITION_TEXT[rule["position"]])
    if rule["automated"] is True:
        parts.append("店已经交给人")
    elif rule["automated"] is False:
        parts.append("店还没交给人")
    body = "、".join(parts) if parts else "任何月份"
    return f"规则 {index + 1}：{body}，就改成{EMPLOY_TEXT[rule['employment']]}"


def make_policy(rules: tuple[dict, ...]):
    fires: Counter[int] = Counter()

    def policy(state: GameState):
        base = policy_steady(state)
        for index, rule in enumerate(rules):
            if not matches(state, rule):
                continue
            employment = rule["employment"]
            slots, consume_cash = _spend_on_consume(state, _open_slots(state, 4 - WORK_SLOTS[employment]))
            trial = replace(
                base,
                employment=employment,
                slots=slots,
                sign_months=0 if employment != "full" else base.sign_months,
                consume_cash=consume_cash,
                risk_pct=base.risk_pct if "invest" in slots else 0,
                accept_job=False if employment != "full" else base.accept_job,
            )
            if validate(state, trial):
                continue
            fires[index] += 1
            return trial
        fires[-1] += 1
        return base

    policy.rules = rules
    policy.fires = fires
    return policy


def separates(row: dict, kept: list[dict]) -> bool:
    return all(different(row, other) for other in kept) and not breaks_rules(row, kept)


def _rows_for(policy, games: int, seed: int) -> dict:
    played = [play_once(policy, seed + game) for game in range(games)]
    return summarize("candidate", played)


def search(rng: random.Random | None = None) -> dict:
    """按设计里的预算跑。返回留下的那一条，或 None。"""
    rng = rng or random.Random(SEARCH_SEED)
    catalog = [sample_rules(rng) for _ in range(N_CANDIDATES)]
    kept_policies = starting_policies()
    screen_kept = [
        summarize(name, [play_once(policy, GAME_SEED + game) for game in range(SCREEN_GAMES)])
        for name, policy in kept_policies
    ]
    shortlist = []
    for index, rules in enumerate(catalog):
        row = _rows_for(make_policy(rules), SCREEN_GAMES, GAME_SEED)
        if separates(row, screen_kept):
            shortlist.append(index)
    confirmed = []
    if shortlist:
        confirm_kept = [
            summarize(name, [play_once(policy, GAME_SEED + game) for game in range(CONFIRM_GAMES)])
            for name, policy in kept_policies
        ]
        for index in shortlist:
            row = _rows_for(make_policy(catalog[index]), CONFIRM_GAMES, GAME_SEED)
            if separates(row, confirm_kept):
                confirmed.append(index)
    best = None
    best_score = -1
    held = []
    if confirmed:
        holdout_kept = [
            summarize(name, [play_once(policy, HOLDOUT_SEED + game) for game in range(HOLDOUT_GAMES)])
            for name, policy in kept_policies
        ]
        for index in confirmed:
            policy = make_policy(catalog[index])
            row = _rows_for(policy, HOLDOUT_GAMES, HOLDOUT_SEED)
            gaps = [axis_gaps(row, other) for other in holdout_kept]
            ok = separates(row, holdout_kept)
            held.append(
                {"index": index, "ok": ok, "gaps": gaps, "row": row, "rules": catalog[index], "fires": dict(policy.fires)}
            )
            score = sum(len(item) for item in gaps) if ok else -1
            if ok and (score > best_score or (score == best_score and (best is None or index < best))):
                best = index
                best_score = score
    return {
        "shortlist": shortlist,
        "confirmed": confirmed,
        "held": held,
        "kept_index": best,
        "catalog": catalog,
    }
