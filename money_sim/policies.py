"""批量模拟用的固定策略。界面不会调用它们。"""

from __future__ import annotations

from money_sim.constants import LOW_ENERGY_FULL, MIN_CONSUME, TOTAL_SLOTS, WORK_SLOTS
from money_sim.economy import living_cost
from money_sim.engine import quote, validate
from money_sim.state import GameState, Plan


def ensure_plan(state: GameState, plan: Plan) -> Plan:
    if not validate(state, plan):
        return plan
    stripped = Plan(
        employment=plan.employment,
        slots=list(plan.slots),
        consume_cash=plan.consume_cash if "consume" in plan.slots else 0,
        exit_business=plan.exit_business,
        accept_offer=plan.accept_offer,
    )
    if "consume" in stripped.slots:
        stripped.consume_cash = max(stripped.consume_cash, MIN_CONSUME * stripped.slots.count("consume"))
    if not validate(state, stripped):
        return stripped
    for employment in ("free", "part", "full"):
        slots = ["rest"] * (TOTAL_SLOTS - WORK_SLOTS[employment])
        candidate = Plan(employment, slots)
        if not validate(state, candidate):
            return candidate
    raise RuntimeError("找不到合法方案")


def _buffer(state: GameState) -> int:
    return living_cost(state.lifestyle, state.price_index) * 4


def _rebalance(state: GameState, buffer: int) -> tuple[int, int]:
    liquid = max(0, state.cash) + max(0, state.portfolio)
    if state.regime == "bear":
        target = liquid * 40 // 100
    elif state.regime == "bull":
        target = liquid * 88 // 100
    else:
        target = liquid * 72 // 100
    if state.portfolio > target + 8_000:
        return 0, min(state.portfolio, state.portfolio - target)
    room = state.cash - buffer
    if room > 8_000 and state.portfolio < target:
        return min(room, target - state.portfolio), 0
    return 0, 0


def _pay_debt(state: GameState, cash_room: int) -> int:
    if state.debt <= 0 or cash_room <= 0:
        return 0
    return min(state.debt, cash_room)


def policy_steady(state: GameState) -> Plan:
    """全职攒钱，早期学职业，景气差时降低仓位。不碰副业。"""
    if state.energy < LOW_ENERGY_FULL:
        employment = "free"
    elif state.energy < 34 or state.stress > 72:
        employment = "part"
    else:
        employment = "full"
    slots: list[str] = []
    free = TOTAL_SLOTS - WORK_SLOTS[employment]
    for index in range(free):
        if state.energy < 42 or state.stress > 64:
            slots.append("rest")
        elif state.career < 58 and index == 0 and employment != "free":
            slots.append("learn_career")
        elif state.regime == "bear":
            slots.append("rest")
        else:
            slots.append("invest")
    risk = 0
    if "invest" in slots and state.regime == "bull":
        risk = 25
    elif "invest" in slots and state.regime == "chop" and state.invest >= 20:
        risk = 10
    buffer = _buffer(state)
    debt_pay = _pay_debt(state, max(0, state.cash - buffer))
    to_index, from_index = _rebalance(state, buffer + debt_pay)
    return ensure_plan(
        state,
        Plan(employment, slots, to_index=to_index, from_index=from_index, debt_pay=debt_pay, risk_pct=risk),
    )


def policy_grind(state: GameState) -> Plan:
    """极端偏科：只上班、只买指数，永不学习、永不做副业、几乎不消费。"""
    if state.energy < LOW_ENERGY_FULL:
        employment = "free"
        slots = ["rest", "rest", "rest", "rest"]
    else:
        employment = "full"
        slots = ["rest"] if state.energy < 40 or state.stress > 70 else ["invest"]
    buffer = living_cost(state.lifestyle, state.price_index) * 3
    debt_pay = _pay_debt(state, max(0, state.cash - buffer))
    to_index = max(0, state.cash - buffer - debt_pay)
    return ensure_plan(state, Plan(employment, slots, to_index=to_index, debt_pay=debt_pay, risk_pct=0))


def policy_yolo(state: GameState) -> Plan:
    """极端：立刻辞职，只留几个月生活费，其余压进副业和风险仓。"""
    if state.energy < 22:
        slots = ["rest", "rest", "venture", "learn_venture"]
    elif state.business_stage != "running":
        slots = ["venture", "venture", "venture", "learn_venture"]
    elif state.energy < 40:
        slots = ["rest", "venture", "invest", "learn_venture"]
    else:
        slots = ["venture", "invest", "learn_venture", "learn_invest"]
    plan = Plan("free", slots, risk_pct=100 if "invest" in slots else 0)
    quoted = quote(state, plan)
    buffer = living_cost(state.lifestyle, state.price_index) * 5
    # 卖掉大部分指数，但留下两成，避免同月把店贱卖掉。
    keep_index = state.portfolio // 5
    plan.from_index = max(0, state.portfolio - keep_index)
    sell = plan.from_index * 997 // 1_000
    spare = state.cash + sell - quoted["tuition"] - quoted["build_cost"] - buffer
    if "venture" in slots or state.business_stage != "none":
        plan.to_business = max(0, spare)
    else:
        plan.from_index = 0
    return ensure_plan(state, plan)


def _owner_targets(state: GameState, buffer: int) -> tuple[int, int]:
    """店本身已经是风险资产，收缩期不要把指数杀到过低。"""
    liquid = max(0, state.cash) + max(0, state.portfolio)
    if state.regime == "bear":
        target = liquid * 62 // 100
    elif state.regime == "bull":
        target = liquid * 82 // 100
    else:
        target = liquid * 74 // 100
    if state.portfolio > target + 8_000:
        return 0, min(state.portfolio, state.portfolio - target)
    room = state.cash - buffer
    if room > 8_000 and state.portfolio < target:
        return min(room, target - state.portfolio), 0
    return 0, 0


def policy_owner(state: GameState) -> Plan:
    """先上班把店和手艺做出来。店够大再改兼职亲自盯；雇得起人就回到全职。不因一个月亏损就把店卖掉。"""
    can_automate = state.business_stage == "running" and (
        state.automated
        or (
            state.business_book >= 140_000
            and state.venture >= 46
            and state.last_business_net > 0
        )
    )
    tired = state.energy < 36 or state.stress > 72
    mature = state.business_stage == "running" and state.venture >= 40 and state.business_book >= 80_000
    if state.business_stage != "running":
        employment, slots = ("part", ["rest", "rest"]) if tired or state.energy < LOW_ENERGY_FULL else ("full", ["venture"])
    elif state.venture < 46:
        employment, slots = ("part", ["rest", "rest"]) if tired or state.energy < LOW_ENERGY_FULL else ("full", ["learn_venture"])
    elif can_automate:
        employment, slots = ("part", ["rest", "rest"]) if tired or state.energy < LOW_ENERGY_FULL else (
            "full",
            ["rest" if state.regime == "bear" else "invest"],
        )
    elif mature and not tired and state.energy >= 48:
        employment, slots = "part", ["venture", "venture"]
    elif tired or state.energy < LOW_ENERGY_FULL:
        employment, slots = "part", ["rest", "venture"] if state.business_stage == "running" else ["rest", "rest"]
    else:
        employment, slots = "full", ["venture"]

    accept = False
    risk = 15 if "invest" in slots and state.regime == "bull" else 0
    automate = can_automate and not accept and "venture" not in slots
    buffer = _buffer(state)
    debt_pay = _pay_debt(state, max(0, state.cash - buffer))
    to_index, from_index = _owner_targets(state, buffer + debt_pay)
    to_business = 0
    if (
        not accept
        and state.business_stage == "running"
        and state.venture >= 36
        and state.business_book < 200_000
        and state.last_business_net > 0
    ):
        room = state.cash - buffer - debt_pay - to_index
        if room > 16_000:
            to_business = min(8_000, room - 4_000)
    if to_business and from_index:
        from_index = 0
    plan = Plan(
        employment,
        slots,
        to_index=0 if to_business else to_index,
        from_index=from_index,
        to_business=to_business,
        debt_pay=debt_pay,
        risk_pct=risk,
        automate=automate,
        accept_offer=accept,
        exit_business=accept,
    )
    if validate(state, plan) or quote(state, plan)["energy_after"] < 0:
        plan = Plan("part", ["rest", "rest"])
    return ensure_plan(state, plan)


POLICIES = (
    ("steady", policy_steady),
    ("grind", policy_grind),
    ("yolo", policy_yolo),
    ("owner", policy_owner),
)
