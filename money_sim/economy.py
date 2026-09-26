"""纯公式。结算和预览都走这里，避免界面另算一套数。"""

from __future__ import annotations

import math

from money_sim.constants import (
    AUTONOMY_REST_HIGH,
    AUTONOMY_REST_LOW,
    AUTONOMY_RUST_RELIEF,
    BASE_LIVING,
    CONDITION_CONSUME_LOW,
    CONDITION_CONSUME_MID,
    CONDITION_EASE,
    CONDITION_EFFORT,
    CONDITION_HOLD,
    CONDITION_REST,
    CONDITION_WORK,
    CONTRACT_REST_HIGH,
    CONTRACT_REST_LOW,
    CONTRACT_REST_MID,
    HOME_BASIS,
    JOB_OFFER_BUMP,
    JOB_OFFER_BUMP_CAP,
    JOB_OFFER_BUMP_FLOOR,
    JOB_OFFER_FRESH,
    HOME_DOWN_DEN,
    HOME_DOWN_NUM,
    HOME_MAINT_DEN,
    HOME_MAINT_NUM,
    HOME_SELL_COST,
    LIGHT_DEN,
    LIGHT_NUM,
    MONTHS,
    MORTGAGE_MONTHS,
    MORTGAGE_RATE_DEN,
    MORTGAGE_RATE_NUM,
    NETWORK_SALARY_DEN,
    PART_TIME_DEN,
    PART_TIME_NUM,
    PRICE_GROWTH_DEN,
    PRICE_GROWTH_NUM,
    PRICE_START,
    RENT_SHARE,
    RUST_LATE_MONTH,
    SALARY_BASE,
    SALARY_PER_SKILL,
    TRIAL_EXIT_PCT,
    WIN_NET,
)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def clamp_return(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def salary(career: int, network: int, employment: str) -> int:
    full = SALARY_BASE + career * SALARY_PER_SKILL
    full = full * (NETWORK_SALARY_DEN + network) // NETWORK_SALARY_DEN
    if employment == "full":
        return full
    if employment == "light":
        return full * LIGHT_NUM // LIGHT_DEN
    if employment == "part":
        return full * PART_TIME_NUM // PART_TIME_DEN
    return 0


def ease_position(worth: int, month: int, career: int, network: int, bill: int) -> dict:
    """少工作开不开，只承认最多三分之一局的全职储蓄。

    把剩下上百个月的工资都算进去，开局涨一点技能就会“够到”。
    那个位置不是攒出来的。更远的工资不计入。投影不含投资收益，也不发钱。
    轻职若一直做到局终，投影可以低于 150 万：位置只表示现在换时间还有得选。
    """
    left = max(0, MONTHS - month + 1)
    horizon = min(left, MONTHS // 3)
    full_save = salary(career, network, "full") - bill
    light_save = salary(career, network, "light") - bill
    projected_full = worth + max(0, full_save) * horizon
    projected = worth + max(0, light_save) * left
    return {
        "open": left >= 6 and light_save > 0 and projected_full >= WIN_NET,
        "projected": projected,
        "projected_full": projected_full,
        "monthly_save": light_save,
        "months_left": left,
        "covered": projected >= WIN_NET,
    }


def living_cost(lifestyle: int, price_index: int) -> int:
    return BASE_LIVING * lifestyle // 100 * price_index // PRICE_START


def learn_gain(skill: int) -> int:
    return max(1, int(round(8 * (1 - skill / 140))))


def exit_pct(stage: str, last_business_net: int, offer_pct: int, accept_offer: bool) -> int:
    if accept_offer and offer_pct > 0:
        return offer_pct
    if stage == "building":
        return 90
    if stage == "trial":
        return TRIAL_EXIT_PCT
    if stage == "running":
        return 62 if last_business_net > 0 else 48
    return 0


def _capital_factor(book: int) -> float:
    """资金会把店撑起来，但很快饱和。再往后只有成本在涨。"""
    if book <= 0:
        return 0.0
    return 1.35 * (1 - math.exp(-book / 36_000))


def business_gross(
    book: int,
    venture: int,
    demand_bp: int,
    attention: int,
    automated: bool,
    autonomy: int,
) -> int:
    """亲自经营才有完整收入。没人照看会塌；雇人能保住大部分，但不是第二份工资。"""
    if book <= 0:
        return 0
    skill_f = 0.42 + venture * 0.008
    gross = int(12_500 * skill_f * _capital_factor(book) * (demand_bp / 100))
    # 一个时间槽只能维持，两个槽才是在做这家店。更多槽有用，但不再线性加钱。
    if attention <= 0 and not automated:
        gross = gross * 8 // 100
    elif attention <= 0 and automated:
        gross = gross * 82 // 100
    elif attention == 1:
        gross = gross * 48 // 100
    elif attention >= 4:
        gross = gross * 138 // 100
    elif attention == 3:
        gross = gross * 122 // 100
    if autonomy >= 65 and attention > 0:
        gross = gross * 106 // 100
    return gross


def business_opex(book: int, automated: bool) -> int:
    staff = 4_500 if automated else 0
    return 1_000 + book // 2_000 + staff


def demand_bp(regime: str, network: int, noise_bp: int) -> int:
    base = {"bull": 112, "chop": 100, "bear": 78}[regime]
    return base * (500 + network) // 500 * noise_bp // 100


def index_distribution(skill: int, regime: str) -> tuple[float, float, float, float]:
    mu = 0.004 + skill * 0.000012
    sigma = max(0.028, 0.042 - skill * 0.00006)
    if regime == "bull":
        mu += 0.003
    elif regime == "bear":
        mu -= 0.007
    return mu, sigma, -0.28, 0.22


def risk_distribution(skill: int, regime: str) -> tuple[float, float, float, float]:
    mu = 0.006 + skill * 0.00002
    sigma = 0.08
    if regime == "bull":
        mu += 0.004
    elif regime == "bear":
        mu -= 0.012
    return mu, sigma, -0.45, 0.40


def condition_after(condition: int, employment: str, slots: list[str]) -> int:
    """整月用月初的状态判断补多少。金额不进这个函数。"""
    delta = CONDITION_WORK.get(employment, CONDITION_WORK["free"])
    for slot in slots:
        if slot == "rest":
            if condition < CONDITION_EASE:
                delta += CONDITION_REST
        elif slot == "consume":
            if condition < CONDITION_HOLD:
                delta += CONDITION_CONSUME_LOW
            elif condition < CONDITION_EASE:
                delta += CONDITION_CONSUME_MID
        elif slot == "venture" or slot.startswith("learn_"):
            delta -= CONDITION_EFFORT
    return clamp(condition + delta, 0, 100)


def consume_lifestyle_gain(spend: int) -> int:
    # 最低 2：按精力能维持的消费频率，加 1 会被下个月的回落抵消，地板显不出来。
    return min(4, max(2, spend // 10_000))


def consume_outlook(lifestyle: int, price_index: int, spend: int, will_consume: bool) -> dict:
    """本月实扣的水准，以及相对「不消费」下个月多出来的生活费。"""
    gain = consume_lifestyle_gain(spend) if will_consume and spend else 0
    charged = clamp(lifestyle + gain, 100, 220)
    if will_consume and spend:
        after = charged
    else:
        after = clamp(max(100, lifestyle - 1), 100, 220)
    skipped = clamp(max(100, lifestyle - 1), 100, 220)
    next_index = price_index * PRICE_GROWTH_NUM // PRICE_GROWTH_DEN

    def parts(level: int) -> tuple[int, int, int]:
        full = living_cost(level, next_index)
        rent = rent_of(full)
        return full, rent, full - rent

    full_after, rent_after, own_after = parts(after)
    full_skip, rent_skip, own_skip = parts(skipped)
    return {
        "charged_lifestyle": charged,
        "lifestyle_next": after,
        "living_delta_rent": full_after - full_skip,
        "living_delta_own": own_after - own_skip,
        "rent_delta": rent_after - rent_skip,
    }


def consume_stress_relief(spend: int) -> int:
    return min(22, spend // 1_500)


def consume_network_gain(spend: int) -> int:
    return min(8, max(1, spend // 3_000))


def contract_rest_gain(autonomy: int) -> int:
    """合同月不能真正下班。时间自主越高，这点休息才越有用。"""
    if autonomy >= AUTONOMY_REST_HIGH:
        return CONTRACT_REST_HIGH
    if autonomy <= AUTONOMY_REST_LOW:
        return CONTRACT_REST_LOW
    return CONTRACT_REST_MID


def rust_step(month: int, autonomy: int) -> int:
    """新鲜耗尽之后每月掉几点。后期更快，除非你还留着时间自主。"""
    if month < RUST_LATE_MONTH or autonomy >= AUTONOMY_RUST_RELIEF:
        return 1
    return 2


def home_price(price_index: int) -> int:
    return HOME_BASIS * price_index // PRICE_START


def down_and_loan(price: int) -> tuple[int, int]:
    down = price * HOME_DOWN_NUM // HOME_DOWN_DEN
    return down, price - down


def mortgage_payment(principal: int) -> int:
    """等额本息。月供在买入时定死，不跟着后来的房价走。"""
    if principal <= 0:
        return 0
    scale = 1_000_000
    growth = scale
    for _ in range(MORTGAGE_MONTHS):
        growth = growth * (MORTGAGE_RATE_DEN + MORTGAGE_RATE_NUM) // MORTGAGE_RATE_DEN
    denom = MORTGAGE_RATE_DEN * (growth - scale)
    return (principal * MORTGAGE_RATE_NUM * growth + denom - 1) // denom


def rent_of(living: int) -> int:
    return living * RENT_SHARE // 100


def home_maintenance(value: int) -> int:
    return value * HOME_MAINT_NUM // HOME_MAINT_DEN if value > 0 else 0


def home_proceeds(value: int, keep_pct: int) -> int:
    return value * keep_pct // 100 if value > 0 else 0


def outside_offer(career: int, network: int, fresh: int) -> int:
    """外部全职报价。新鲜度决定加减，不再另掷一个金额。"""
    base = salary(career, network, "full")
    bump = (fresh - JOB_OFFER_FRESH) * JOB_OFFER_BUMP
    bump = max(JOB_OFFER_BUMP_FLOOR, min(JOB_OFFER_BUMP_CAP, bump))
    return max(1, base * (1000 + bump) // 1000)


def home_equity(value: int, mortgage: int) -> int:
    """主动卖掉、扣掉交易成本、还清贷款之后能拿走的数。可以是负的。"""
    if value <= 0:
        return -mortgage
    return home_proceeds(value, 100 - HOME_SELL_COST) - mortgage
